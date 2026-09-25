"""
Capture depuis Power BI Desktop (Windows).

Pourquoi ces outils-là
──────────────────────
Power BI Desktop ne rend pas ses visuels comme des contrôles Windows : le
canevas est une surface dessinée d'un bloc, dont l'automatisation ne sait rien
extraire. Il n'existe donc pas d'API qui donne « l'image du visuel X » — ni
dans Desktop, ni dans les outils externes. Ce qu'on peut faire, en revanche,
c'est photographier l'écran et **recadrer d'après le rapport**, qui déclare la
place de chaque visuel au pixel logique près (voir `geometry`).

D'où deux outils, chacun sur un seul travail :

    pywinauto   piloter la fenêtre : l'amener devant, changer de page,
                cliquer les boutons de signets
    mss         photographier une région de l'écran, et la rendre en PNG

Laquelle de toutes les fenêtres du bureau est le rapport, c'est `finder` qui
le dit — par le processus qui la porte, et non par son titre, que Power BI
écrit différemment selon les versions.

Les deux sont en option (`pip install -e ".[capture]"`) : un poste qui ne
documente pas de captures n'a pas à les installer, et le document reste
complet sans elles — avec ses emplacements réservés, comme avant.

    Écartés : `pbi-tools` et les API du service, qui n'exportent qu'un rapport
    entier ; Playwright, qui ne voit que Power BI **Service**, pas Desktop ;
    AutoHotkey, qui obligerait l'utilisateur à installer un second exécutable.

Ce que ce module suppose
────────────────────────
Que le rapport soit **déjà ouvert** dans Power BI Desktop, affiché en mode
Rapport. C'est volontaire : ouvrir le `.pbip` soi-même, c'est attendre un
chargement de durée inconnue, parfois une demande d'identifiants — autant de
choses qui échouent silencieusement. Laisser l'utilisateur ouvrir son rapport
comme il en a l'habitude est plus sûr, et rend la mise au point possible.

Le cadrage du canevas dans la fenêtre est **mesuré**, pas déclaré : le ruban,
les volets de droite et la barre d'onglets ont des tailles qui dépendent de la
version, de l'écran et de ce qui est replié — les régler à la main revenait à
les régler faux. Le canevas se cherche donc dans l'image (voir `canvas`), sur
toute la zone utile de la fenêtre, et les marges de `capture.window` ne
reprennent la main que si la recherche échoue.

Ce que le script voit s'écrit sur le disque : `python main.py <rapport>
--calibrate` en fait trois images, dont une où le canevas et chaque visuel
sont entourés. Un cadrage faux s'y voit, et se voit *où*.
"""

import hashlib
import sys
from dataclasses import dataclass, field

from src.core import console
from src.gui_automator import canvas, finder
from src.gui_automator.geometry import Rect, Size
from src.gui_automator.plan import PagePlan
from src.gui_automator.recorder import CaptureError

__all__ = ["DesktopOptions", "DesktopRecorder", "Insets"]

# Écart de proportions toléré entre deux mesures du canevas, au-delà duquel la
# plus juste des deux est gardée.
_RATIO_SLACK = 0.003

# Clics de signet sans effet, d'affilée, au-delà desquels on cesse de cliquer.
_IDLE_CLICKS = 2

_MISSING = (
    "Capture indisponible : `pywinauto` et `mss` ne sont pas installés. "
    'Installez-les avec `pip install -e ".[capture]"`.'
)

# Raccourcis de changement de page, dans la notation de `pywinauto`.
_NEXT = "^{PGDN}"
_PREVIOUS = "^{PGUP}"

# Pauses entre deux touches, et nombre de remontées pour être sûr d'être
# revenu à la première page : un rapport de cinquante onglets est déjà une
# exception.
_KEY_PAUSE = 0.05
_REWIND_PRESSES = 50

# Attente d'un onglet dans l'arbre d'automatisation. Court : les versions qui
# l'exposent le font tout de suite, les autres jamais.
_TAB_TIMEOUT = 2


@dataclass(frozen=True)
class Insets:
    """
    Ce qui entoure le canevas dans la fenêtre, en pixels.

    Le ruban en haut, les volets Visualisations et Filtres à droite, la barre
    des onglets de page en bas. Ces tailles dépendent de la version de Power BI,
    de la résolution et des volets qu'on a repliés : ces marges-ci ne servent
    donc qu'en dernier recours, quand le canevas n'a pas été reconnu dans
    l'image. `--calibrate` dit celles qui conviennent à l'écran qu'il voit.

    Elles se comptent depuis la zone utile de la fenêtre — ce qu'elle dessine
    vraiment —, et non depuis son cadre, dont une partie est hors écran quand
    elle est agrandie (voir `finder.client_box`).
    """

    left: int = 0
    top: int = 130
    right: int = 340
    bottom: int = 60


@dataclass(frozen=True)
class DesktopOptions:
    """Réglages du pilotage, tels que `capture:` les déclare dans le plan."""

    # Fragment cherché dans le titre de la fenêtre — facultatif, et vide par
    # défaut : la fenêtre se reconnaît à son processus (voir `finder`), pas à
    # son titre, qui selon la version ne porte que le nom du rapport. Ce
    # fragment ne sert qu'à désigner un rapport parmi plusieurs ouverts.
    window_title: str = ""
    insets: Insets = field(default_factory=Insets)
    # Temps laissé au rendu après un changement de page, en secondes. Un
    # visuel capturé trop tôt montre son squelette de chargement.
    settle_seconds: float = 1.5
    # Changer de page à la main plutôt que par automatisation : le script
    # s'arrête et attend. Plus lent, mais jamais pris en défaut — c'est le mode
    # à employer pour éprouver le reste de la chaîne.
    manual_pages: bool = False
    # Agrandir la fenêtre avant de capturer. Le cadrage ne dépend plus alors de
    # la taille qu'avait la fenêtre, et le canevas est rendu au plus grand.
    maximize: bool = True
    # Chercher le canevas dans l'image plutôt que de le déduire des marges
    # (voir `canvas`). À couper pour revenir au calcul déclaré, si jamais la
    # détection se trompait sur un habillage de page inhabituel.
    detect_canvas: bool = True

    @classmethod
    def from_plan(cls, capture: dict) -> DesktopOptions:
        """Réglages déclarés dans la section `capture:` du plan."""
        window = capture.get("window") or {}
        return cls(
            window_title=str(window.get("title") or ""),
            insets=Insets(
                left=int(window.get("inset_left", Insets.left)),
                top=int(window.get("inset_top", Insets.top)),
                right=int(window.get("inset_right", Insets.right)),
                bottom=int(window.get("inset_bottom", Insets.bottom)),
            ),
            settle_seconds=float(capture.get("settle_seconds", cls.settle_seconds)),
            manual_pages=bool(capture.get("manual_pages", cls.manual_pages)),
            maximize=bool(window.get("maximize", cls.maximize)),
            detect_canvas=bool(window.get("detect_canvas", cls.detect_canvas)),
        )


class DesktopRecorder:
    """Pilote Power BI Desktop et photographie son canevas."""

    def __init__(self, options: DesktopOptions | None = None):
        self.options = options or DesktopOptions()
        self._window = None
        self._handle = 0
        self._screen = None
        # Canevas reconnu, par dimensions de page et zone cherchée : la
        # reconnaissance coûte une seconde, et rien ne bouge entre deux pages.
        self._canvas_areas: dict[tuple[Size, Rect], Rect | None] = {}
        # Rang de la page affichée, quand on le sait : c'est lui qui donne le
        # nombre de pas à faire pour atteindre la suivante.
        self._order: int | None = None
        # Le clavier change-t-il de page sur cette version ? Éprouvé une fois,
        # à la première page qui en a besoin.
        self._keyboard: bool | None = None
        self._said_undetected = False
        # Dernier canevas reconnu : l'indice de la mesure suivante.
        self._last_canvas: Rect | None = None
        # Clics de signet restés sans effet d'affilée. Un seul se comprend —
        # le signet était déjà actif ; deux disent que le clic ne porte pas.
        self._idle_clicks = 0

    # ── Cycle de vie ──────────────────────────────────────────────
    def start(self) -> None:
        """
        Trouve la fenêtre de Power BI Desktop, l'amène devant, et s'y prépare.

        L'échelle de l'écran est réclamée **avant** de charger `pywinauto` :
        ce dernier la règle lui-même au passage, moins finement, et le premier
        qui parle a raison — sur deux écrans de définitions différentes, cela
        vaut des captures cadrées à côté.
        """
        console.detail(f"Échelle de l'écran : {finder.claim_real_pixels()}")
        pywinauto, mss = _import_tools()

        found = finder.locate(self.options.window_title)
        console.done(f"fenêtre trouvée : {found.describe()}")

        self._window = _attach(pywinauto, found)
        self._handle = found.handle
        self._canvas_areas.clear()
        _bring_to_front(self._window, found)
        if self.options.maximize:
            finder.maximize(found.handle)
        # Une fenêtre qui vient d'être dépliée ou agrandie s'anime : la
        # surprendre en mouvement fausserait le cadrage comme les empreintes.
        _settle(self.options.settle_seconds)
        self._screen = mss.mss()

    def stop(self) -> None:
        """Referme la capture d'écran. Power BI reste ouvert : il l'était déjà."""
        if self._screen is not None:
            self._screen.close()
            self._screen = None
        self._window = None
        self._handle = 0

    # ── Capture ───────────────────────────────────────────────────
    def show_page(self, page: PagePlan) -> Rect:
        """
        Affiche la page demandée et retourne la zone de canevas à l'écran.

        Un rectangle vide dit que la page n'a pas pu être affichée : la séance
        écarte alors ses prises, plutôt que de photographier une autre page en
        croyant tenir celle-là.
        """
        if not self._reach(page):
            return Rect(0, 0, 0, 0)

        _settle(self.options.settle_seconds)
        # Mesuré à nouveau sur chaque page : un signet de la page d'avant a
        # pu ouvrir ou replier un volet, et le canevas n'est plus où il était.
        return self.measure(page)

    def canvas_area(self, size: Size) -> Rect:
        """
        Zone de l'écran où le canevas est rendu.

        Cherchée dans l'image (voir `canvas`), et à défaut déduite des marges
        déclarées — auquel cas `geometry.fit` y placera le canevas comme avant,
        en le supposant ajusté et centré.

        Le résultat est gardé tant que rien n'a pu le déplacer : il est repris
        à chaque page, après chaque signet, et dès que la fenêtre bouge.
        """
        measured = self.measured_canvas(size)
        return self.viewport() if measured is None else measured

    def measured_canvas(self, size: Size) -> Rect | None:
        """
        Le canevas tel qu'il a été reconnu dans l'image, ou `None` faute de mieux.

        `canvas_area` retombe alors sur les marges déclarées, et les deux cas y
        sont indiscernables. Le calibrage, lui, a besoin de les distinguer :
        c'est toute la différence entre un cadrage mesuré et un cadrage réglé
        à la main.
        """
        if not self.options.detect_canvas or size.is_empty:
            return None

        key = (size, self.client_frame())
        if key not in self._canvas_areas:
            self._canvas_areas[key] = self._find_canvas(size)
        return self._canvas_areas[key]

    def _find_canvas(self, size: Size) -> Rect | None:
        """Cherche le canevas dans l'image, et dit ce qu'il en est."""
        ratio = size.width / size.height
        for search in self.search_areas():
            found = self._canvas_in(search, ratio)
            if found is not None:
                console.detail(f"Canevas reconnu dans l'image : {found.describe()}")
                self._last_canvas = found
                return found

        self._say_undetected()
        return None

    def _canvas_in(self, search: Rect, ratio: float) -> Rect | None:
        """
        Le canevas dans une zone de l'écran, ramené aux coordonnées de l'écran.

        Le dernier canevas reconnu sert d'indice : entre deux pages, rien ne
        l'a déplacé la plupart du temps, et un rectangle de traits presque
        aussi grand que lui — le bord d'un tableau, celui du volet Filtres —
        ne doit pas lui être préféré s'il est toujours là.
        """
        image = None if search.is_empty else self._pixels(search)
        if image is None:
            return None
        last = self._last_canvas
        hint = None if last is None else last.moved(-search.left, -search.top)
        found = canvas.detect(image, ratio, hint=hint)
        return None if found is None else found.moved(search.left, search.top)

    def search_areas(self) -> list[Rect]:
        """
        Zones où chercher le canevas, de la plus étroite à la plus large.

        D'abord ce que les marges déclarées retiennent : là, si elles sont
        justes, le canevas se détache franchement de son pourtour — c'est le
        cas le plus facile, et le plus ancien.

        Puis la zone utile entière, ruban et volets compris. C'est elle qui
        rattrape des marges trop larges : elles coupaient le canevas, la
        reconnaissance n'y trouvait plus les proportions annoncées, et le
        cadrage retombait sur ces mêmes marges fausses. Chercher large ne
        coûte rien de plus qu'une seconde, puisque le canevas se reconnaît à
        ses proportions et à sa bordure, pas à ce qui l'entoure.
        """
        client, declared = self.client_frame(), self.viewport()
        return [declared, client] if declared != client and not declared.is_empty else [client]

    def viewport(self) -> Rect:
        """
        Cadrage de dernier recours : la zone utile, marges déclarées déduites.

        N'entre en jeu que si le canevas n'a pas été reconnu dans l'image
        (`detect_canvas`). `geometry.fit` y place alors le canevas en le
        supposant ajusté et centré, comme avant que la détection existe.
        """
        insets = self.options.insets
        return self.client_frame().inset(insets.left, insets.top, insets.right, insets.bottom)

    def client_frame(self) -> Rect:
        """
        Fenêtre sans son cadre invisible — ce qu'elle dessine vraiment.

        Voir `finder.client_box` : une fenêtre agrandie déborde de l'écran de
        l'épaisseur de sa poignée de redimensionnement, et ces pixels-là ne
        ramènent que du noir. Hors de Windows, le cadre entier fait l'affaire.
        """
        box = finder.client_box(self._handle) if self._handle else None
        return Rect(*box) if box is not None else self.window_frame()

    def window_frame(self) -> Rect:
        """Fenêtre entière — ce que `--calibrate` capture pour comparaison."""
        box = self._require_window().rectangle()
        return Rect(box.left, box.top, box.right - box.left, box.bottom - box.top)

    def grab(self, area: Rect) -> bytes:
        """Photographie une région de l'écran et la retourne en PNG."""
        _, mss = _import_tools()
        shot = self._shoot(area)
        return mss.tools.to_png(shot.rgb, shot.size)

    def image(self, area: Rect) -> canvas.Image | None:
        """Pixels bruts d'une région, pour les mesurer ou dessiner dessus."""
        return self._pixels(area)

    # ── Signets ───────────────────────────────────────────────────
    def apply_bookmark(self, title: str, trigger: Rect, rendered: Rect, undo: bool = False) -> bool:
        """
        Applique un signet par Ctrl+clic sur son bouton, et vérifie l'effet.

        Ctrl, parce qu'en mode édition Power BI Desktop sélectionne un bouton
        cliqué au lieu de l'actionner. La souris est ensuite écartée du
        canevas : laissée sur le bouton, elle y laisserait son survol — ou une
        infobulle sur le visuel d'à côté — dans la capture suivante.

        L'effet se lit sur le canevas. Un clic sans effet se comprend une
        fois : le signet était déjà l'affichage en cours. Deux de suite disent
        que le clic ne porte pas, et l'on demande plutôt que de capturer les
        mêmes visuels sous un autre nom.
        """
        if self.options.manual_pages or trigger.is_empty or self._idle_clicks >= _IDLE_CLICKS:
            return self._ask_for_bookmark(title)

        before = self._print(rendered)
        if not self._ctrl_click(_middle_point(trigger)):
            return self._ask_for_bookmark(title)
        _settle(self.options.settle_seconds)
        # Le signet a pu ouvrir ou replier un volet : le canevas mesuré ne
        # vaut plus, ni pour cette page ni pour les suivantes.
        self._canvas_areas.clear()

        if self._print(rendered) != before:
            self._idle_clicks = 0
            return True

        if undo:
            # Défaire un signet change forcément l'affichage : resté tel quel,
            # c'est que le clic a manqué — une fenêtre de filtres reste ouverte.
            console.warn(f"Signet « {title} » : le clic n'a rien refermé.")
            return self._ask_for_bookmark(title)

        self._idle_clicks += 1
        if self._idle_clicks >= _IDLE_CLICKS:
            console.warn(f"Signet « {title} » : le clic sur son bouton reste sans effet.")
            return self._ask_for_bookmark(title)
        console.detail(f"Signet « {title} » : affichage inchangé, sans doute déjà actif")
        return True

    def measure(self, page: PagePlan, keep: Rect | None = None) -> Rect:
        """
        Le canevas de la page affichée, cherché à nouveau dans l'image.

        `keep` est la mesure d'avant un signet. Une fenêtre de filtres ouverte
        par-dessus la page — plus haute que le canevas — peut fausser la
        reconnaissance : une nouvelle mesure aux proportions moins justes que
        l'ancienne ne la remplace pas.
        """
        self._canvas_areas.clear()
        found = self.canvas_area(page.canvas)
        if keep is None or keep.is_empty or found == keep:
            return found
        if _ratio_error(found, page.canvas) > _ratio_error(keep, page.canvas) + _RATIO_SLACK:
            console.detail(f"Mesure douteuse ({found.describe()}) : canevas d'avant gardé.")
            return keep
        return found

    def _ctrl_click(self, point: tuple[int, int]) -> bool:
        """Ctrl+clic en un point de l'écran, puis la souris hors du canevas."""
        window = self._require_window()
        try:
            import pywinauto.mouse  # noqa: PLC0415 — chargé avec les outils

            window.set_focus()
            window.click_input(coords=point, absolute=True, pressed="control")
            client = self.client_frame()
            pywinauto.mouse.move(coords=(int(client.left) + 4, int(client.bottom) - 4))
        except Exception as e:  # noqa: BLE001 — l'échec se rattrape en demandant
            console.detail(f"Clic en {point} non envoyé ({e})")
            return False
        return True

    def _print(self, area: Rect) -> bytes:
        """Empreinte d'une zone de l'écran — le canevas, pour un signet."""
        image = self._pixels(area.rounded())
        return hashlib.sha256(image.rgb).digest() if image is not None else b""

    def _ask_for_bookmark(self, title: str) -> bool:
        """Demande le signet à l'utilisateur, s'il y a quelqu'un pour répondre."""
        if not _can_ask():
            console.detail(f"Signet « {title} » non appliqué, et personne pour le faire.")
            return False
        console.question(f"Appliquez le signet « {title} » dans Power BI Desktop")
        console.note("Ctrl+clic sur son bouton, ou volet Affichage › Signets.")
        console.ask("Entrée quand l'affichage est à l'écran")
        self._canvas_areas.clear()
        return True

    # ── Pages ─────────────────────────────────────────────────────
    def _reach(self, page: PagePlan) -> bool:
        """
        Amène la page demandée à l'écran, et dit si elle y est.

        Trois voies, de la plus sûre à la dernière : l'onglet, si la fenêtre
        l'expose ; le clavier, en comptant les pages ; l'utilisateur, à qui
        l'on demande plutôt que de capturer autre chose.
        """
        if self.options.manual_pages:
            _ask_for_page(page)
            self._order = page.order
            return True
        if self._order == page.order:
            return True

        before = self._fingerprint()
        if self._click_tab(page) and self._moved(before):
            self._order = page.order
            return True
        if self._by_keyboard(page, before):
            self._order = page.order
            return True
        return self._ask_instead(page)

    def _click_tab(self, page: PagePlan) -> bool:
        """
        Clique l'onglet de la page, en bas de la fenêtre.

        Les versions récentes dessinent leurs onglets dans le canevas : elles
        n'en exposent aucun à l'automatisation, et ce chemin ne mène nulle
        part. Il reste tenté d'abord, parce qu'il est le plus direct là où il
        fonctionne encore.
        """
        window = self._require_window()
        try:
            tab = window.child_window(title=page.title, control_type="TabItem")
            tab.wait("exists ready", timeout=_TAB_TIMEOUT)
            tab.click_input()
        except Exception as e:  # noqa: BLE001 — l'échec est une voie de moins
            console.detail(f"Onglet « {page.title} » non exposé par la fenêtre ({e})")
            return False

        _settle(self.options.settle_seconds)
        return True

    def _by_keyboard(self, page: PagePlan, before: bytes) -> bool:
        """
        Change de page au clavier, en comptant les onglets.

        Power BI passe d'une page à l'autre par Ctrl+Page suivante / Ctrl+Page
        précédente. Le rapport dit le rang de chaque page, onglets cachés
        compris : d'un rang connu au suivant, il n'y a qu'à compter les pas.
        Encore faut-il savoir d'où l'on part — d'où la remontée initiale.
        """
        if self._keyboard is None:
            self._keyboard = self._probe_keyboard()
        if not self._keyboard:
            return False

        if self._order is None:
            self._rewind()

        steps = page.order - (self._order or 0)
        self._press(_NEXT if steps > 0 else _PREVIOUS, abs(steps))
        _settle(self.options.settle_seconds)
        return steps == 0 or self._moved(before)

    def _probe_keyboard(self) -> bool:
        """
        Le clavier change-t-il de page sur cette version ?

        Une descente ; et si elle ne donne rien, une montée — sur la dernière
        page du rapport, la descente ne pouvait pas aboutir. Le raccourci
        reconnu, on revient d'où l'on venait.
        """
        for forward, back in ((_NEXT, _PREVIOUS), (_PREVIOUS, _NEXT)):
            before = self._fingerprint()
            self._press(forward, 1)
            _settle(self.options.settle_seconds)
            if self._moved(before):
                self._press(back, 1)
                _settle(self.options.settle_seconds)
                return True

        console.detail("Le clavier ne change pas de page sur cette version.")
        return False

    def _rewind(self) -> None:
        """Remonte jusqu'à la première page : on sait enfin où l'on est."""
        self._press(_PREVIOUS, _REWIND_PRESSES)
        _settle(self.options.settle_seconds)
        self._order = 0

    def _ask_instead(self, page: PagePlan) -> bool:
        """Faute d'y arriver seul, demande — et n'invente rien s'il n'y a personne."""
        console.warn(f"Page « {page.title} » non atteinte automatiquement.")
        if not _can_ask():
            console.detail("Personne pour l'afficher : les prises de cette page sont écartées.")
            return False

        _ask_for_page(page)
        self._order = page.order
        return True

    def _press(self, keys: str, times: int = 1) -> None:
        """Envoie une combinaison à la fenêtre, plusieurs fois s'il le faut."""
        if times <= 0:
            return

        window = self._require_window()
        try:
            window.set_focus()
            window.type_keys(keys * times, pause=_KEY_PAUSE)
        except Exception as e:  # noqa: BLE001 — la vérification suivra de toute façon
            console.detail(f"Raccourci {keys} non envoyé ({e})")

    # ── Ce qui est à l'écran ──────────────────────────────────────
    def _fingerprint(self) -> bytes:
        """
        Empreinte de ce qui est affiché au milieu de la fenêtre.

        C'est la seule façon de savoir qu'un changement de page a eu lieu :
        Power BI n'en dit rien, ni dans son titre, ni à l'automatisation.

        Au milieu, parce que c'est la seule zone dont on sache deux choses à
        la fois : le canevas la couvre — il occupe le centre de la fenêtre,
        quels que soient les volets ouverts —, et le reste de l'habillage n'y
        est pas. Prendre la fenêtre entière ferait passer une simple prise de
        focus, qui ravive la barre de titre, pour un changement de page ; s'en
        remettre aux marges déclarées ferait comparer un bout de ruban
        immobile si elles sont mal réglées, et conclure que la page n'a pas
        tourné alors qu'elle l'a fait.
        """
        image = self._pixels(_middle(self.client_frame()))
        return hashlib.sha256(image.rgb).digest() if image is not None else b""

    def _moved(self, before: bytes) -> bool:
        """L'affichage a-t-il changé depuis cette empreinte ?"""
        after = self._fingerprint()
        return bool(after) and after != before

    def _pixels(self, area: Rect) -> canvas.Image | None:
        """Pixels bruts d'une région de l'écran."""
        try:
            shot = self._shoot(area)
        except CaptureError as e:
            console.detail(str(e))
            return None
        return canvas.Image(shot.size.width, shot.size.height, bytes(shot.rgb))

    def _shoot(self, area: Rect):
        """Photographie une région et retourne l'image brute de `mss`."""
        if self._screen is None:
            raise CaptureError("Capture non démarrée : appelez `start()` d'abord.")

        region = {
            "left": int(area.left),
            "top": int(area.top),
            "width": int(area.width),
            "height": int(area.height),
        }
        try:
            return self._screen.grab(region)
        except Exception as e:
            raise CaptureError(f"Région {region} non capturable ({e})") from e

    def _say_undetected(self) -> None:
        """Le canevas n'a pas été reconnu : on le dit une fois, pas à chaque page."""
        if self._said_undetected:
            return

        self._said_undetected = True
        console.warn("Canevas non reconnu dans l'image — cadrage déduit des marges déclarées.")
        console.note("Les captures seront cadrées d'après `capture.window` du plan, qui")
        console.note("n'est juste que s'il a été réglé pour cette version et cet écran.")
        console.note("`--calibrate` écrit ce que le script voit : le repère y saute aux yeux.")

    def _require_window(self):
        if self._window is None:
            raise CaptureError("Capture non démarrée : appelez `start()` d'abord.")
        return self._window


def _attach(pywinauto, found: finder.WindowInfo):
    """
    Prend la main sur la fenêtre trouvée, par son identifiant système.

    Par l'identifiant plutôt que par le titre : le titre a déjà servi, il peut
    changer entre-temps — Power BI y ajoute une étoile dès la moindre
    modification — et deux rapports peuvent porter le même.
    """
    try:
        window = pywinauto.Desktop(backend="uia").window(handle=found.handle)
        window.wait("exists ready", timeout=10)
    except Exception as e:
        raise CaptureError(
            f"Fenêtre {found.describe()} trouvée, mais impossible à piloter ({e}). "
            "Vérifiez que Power BI Desktop répond, puis relancez."
        ) from e
    return window


def _bring_to_front(window, found: finder.WindowInfo) -> None:
    """
    Déplie la fenêtre et l'amène devant : on photographie l'écran, pas elle.

    Une mise au premier plan refusée — Windows la refuse parfois à un
    processus qui n'a pas la main — n'arrête pas la séance : elle se signale,
    et l'utilisateur voit tout de suite, sur les images, ce qui s'est passé.
    """
    finder.restore(found.handle)
    try:
        window.set_focus()
    except Exception as e:  # noqa: BLE001 — l'échec est sans gravité, il se dit
        console.warn(f"Fenêtre non mise au premier plan ({e}) — capture telle quelle")


def _ask_for_page(page: PagePlan) -> None:
    console.question(f"Affichez la page « {page.title} » dans Power BI Desktop")
    console.note("Puis revenez ici et validez pour lancer la capture.")
    console.ask("Entrée quand la page est à l'écran")


def _middle(area: Rect) -> Rect:
    """La moitié centrale d'une zone, dans les deux sens."""
    margin_x, margin_y = area.width / 4, area.height / 4
    return area.inset(margin_x, margin_y, margin_x, margin_y).rounded()


def _ratio_error(area: Rect, size: Size) -> float:
    """Écart relatif entre les proportions mesurées et celles de la page."""
    if area.is_empty or size.is_empty:
        return float("inf")
    expected = size.width / size.height
    return abs(area.width / area.height - expected) / expected


def _middle_point(area: Rect) -> tuple[int, int]:
    """Centre d'une zone, en pixels entiers."""
    return (round(area.left + area.width / 2), round(area.top + area.height / 2))


def _settle(seconds: float) -> None:
    """Laisse à Power BI le temps de finir son rendu."""
    if seconds > 0:
        import time  # noqa: PLC0415 — hors de la chaîne d'import du script

        time.sleep(seconds)


def _can_ask() -> bool:
    """Y a-t-il quelqu'un pour répondre ? Une exécution automatisée, non."""
    return bool(sys.stdin) and sys.stdin.isatty()


def _import_tools():
    """Charge les outils de capture, ou dit lesquels manquent."""
    try:
        import mss  # noqa: PLC0415
        import mss.tools  # noqa: PLC0415
        import pywinauto  # noqa: PLC0415
    except ImportError as e:
        raise CaptureError(_MISSING) from e
    return pywinauto, mss
