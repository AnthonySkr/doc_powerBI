# Documentation automatique Power BI

**Version {version}**

Cet outil lit un rapport Power BI enregistré au format projet (`.pbip`) et en
écrit la documentation dans un document Word : pages, visuels, champs affichés,
tables, sources, et le code DAX de chaque mesure.

Rien à installer — ni Python, ni rien d'autre. Tout est dans ce dossier.

---

## Ce que contient ce dossier

| Fichier | Rôle |
| --- | --- |
| `powerbi-doc.exe` | L'application |
| `config_doc_pbi.yaml` | Le plan du document : titres, ordre des parties, questions posées |
| `template-doc-pbib.docx` | La charte Word : styles, page de garde, en-tête et pied de page |
| `LISEZMOI.md` | Ce fichier |

Les trois premiers doivent rester **ensemble dans le même dossier**.

---

## Démarrer

1. **Double-cliquez sur `powerbi-doc.exe`**, puis collez le chemin du fichier
   `.pbip` de votre rapport et appuyez sur Entrée.
   *Plus rapide :* glissez-déposez directement le `.pbip` sur l'exécutable.
2. **Répondez aux questions** (voir ci-dessous). Entrée valide la valeur
   proposée entre crochets.
3. Le document est écrit **à côté du `.pbip`**, dans un sous-dossier `doc`.

Votre rapport doit être enregistré au **format projet Power BI** : un fichier
`Rapport.pbip` accompagné des dossiers `Rapport.SemanticModel` et
`Rapport.Report`. Dans Power BI Desktop : *Fichier → Enregistrer sous → Projet
Power BI (.pbip)*.

La fenêtre reste ouverte à la fin : lisez le compte rendu, puis Entrée pour la
fermer.

---

## Les questions posées au lancement

**Dossier où écrire la documentation** — un sous-dossier créé à côté du `.pbip`.
Par défaut `doc`.

**Nom du rapport à afficher sur la page de garde** — le titre visible en
couverture. Par défaut, le nom du fichier `.pbip`.

**Texte à afficher en haut à droite de chaque page** — le texte de l'en-tête.
Par défaut, le même que la page de garde.

**Le rapport comporte-t-il des pages secondaires ?** — répondez *oui* si votre
rapport a des pages de détail atteintes depuis les pages principales. La partie
qui explique cette navigation n'est écrite que dans ce cas.

**Le rapport utilise-t-il un volet de filtre ouvert par un bouton ?** — même
principe : la partie qui décrit ce volet n'apparaît que si vous répondez *oui*.

**Visuels ou groupes déjà présentés ailleurs** — la liste de tous les visuels du
rapport s'affiche, numérotée. Saisissez les numéros de ceux que vous ne voulez
**pas** détailler page par page, séparés par des virgules (par exemple
`3, 7, 12`). Utile pour un bandeau de titre ou un logo qui se répète : l'écarter
une fois l'écarte de toutes les pages. Laissez vide pour tout documenter.

**Souhaitez-vous relire et modifier les textes types ?** — répondez *oui* pour
que l'outil vous propose, un par un, les paragraphes d'explication du plan, que
vous pouvez alors réécrire avant qu'ils ne soient posés dans le document.

> **Vos réponses sont conservées.** Elles sont enregistrées dans
> `reponses_<rapport>.yaml`, à côté du `.pbip`, et reproposées au prochain
> lancement : une suite d'Entrée les reconduit à l'identique. C'est important
> pour la liste des visuels écartés — la re-saisir de mémoire à chaque fois
> serait une source d'erreurs. Supprimez ce fichier pour repartir de zéro.

---

## Ce que vous recevez, et ce qu'il vous reste à faire

Le document est complet côté technique : tout ce qui vient de Power BI y est
déjà. Trois choses vous attendent.

**Les emplacements de captures.** L'outil n'insère pas d'images : il réserve la
place avec un encadré `[IMAGE] ...` décrivant la capture attendue. Remplacez
l'encadré par votre capture d'écran.

**Les pastilles numérotées.** Sous un emplacement de capture, une rangée de
pastilles rondes porte les numéros du tableau qui suit. Attrapez-en une à la
souris et déposez-la sur l'élément correspondant de votre capture ; les flèches
du clavier l'ajustent au pixel près. Elles flottent au-dessus de l'image et ne
déplacent aucune ligne du document.

**Les zones à rédiger.** Les passages en italique entre crochets — par exemple
`[ce que la mesure calcule, et quand l'employer]` — indiquent ce qu'on attend à
cet endroit. Remplacez le texte par le vôtre.

La table des matières et les numéros de figures se recalculent à l'ouverture
dans Word. Si ce n'est pas le cas : `Ctrl+A` puis `F9`.

---

## Relancer sur un rapport déjà documenté

**Relancez simplement, sur le même `.pbip`.** Le document existant n'est pas
écrasé : il est lu, comparé au rapport actuel, et un document neuf est écrit en
reprenant tout ce que vous y avez mis.

Ce qui vous revient tel quel : vos textes, vos titres reformulés, vos captures,
vos pastilles là où vous les avez posées, votre mise en forme, vos listes, vos
commentaires de révision.

Ce que l'outil réécrit : ce qu'il avait produit lui-même — code DAX, tableaux de
champs, sources, mesures appelantes. C'est sa part, et elle doit rester juste.

**Deux signalements** vous attendent dans le document :

- **surligné en jaune** — la technique de cet élément a changé depuis votre
  dernière version (la formule DAX, les champs du visuel). Vos textes portent
  peut-être sur une version périmée : relisez-les. Le surlignage disparaît à la
  génération suivante.
- **surligné en vert** — cet élément est apparu depuis la dernière fois. Sa zone
  à rédiger vous attend.

**« Contenu non replacé »**, en fin de document : ce que l'outil n'a pas su
remettre à sa place — une mesure supprimée du rapport, un visuel que vous venez
d'écarter. Rien n'est jeté. Reprenez ce qui vous intéresse, puis supprimez la
partie : elle ne revient pas.

La version précédente est archivée dans le sous-dossier `.versions`, horodatée.
Ce dossier n'est jamais nettoyé automatiquement : videz-le de temps en temps.

> **Ne supprimez pas les marqueurs.** L'outil pose dans le document des repères
> invisibles (`pbi::...`) qui lui permettent de retrouver votre travail. Ils
> n'apparaissent ni à l'écran ni à l'impression — seulement si vous activez
> « Afficher tout » (¶). Un document dont ils auraient disparu serait
> intégralement régénéré, et votre rédaction partirait en annexe.

---

## Adapter le document

**`config_doc_pbi.yaml`** décrit le plan : les titres, l'ordre des parties, les
textes types, les questions posées au lancement, ce qui est documenté ou écarté.
C'est un fichier texte : ouvrez-le dans le Bloc-notes ou un éditeur, modifiez-le,
relancez. Aucune reconstruction n'est nécessaire.

**`template-doc-pbib.docx`** fournit l'apparence : les styles, la page de garde,
l'en-tête et le pied de page. Ouvrez-le dans Word et modifiez-le comme un
document ordinaire. Les styles nommés qu'il contient (`Code DAX`, `A completer`,
`Legende`…) sont ceux que le plan désigne : renommez-les et l'outil vous
signalera qu'il ne les trouve plus.

Gardez une copie de ces deux fichiers avant de les modifier. En cas de fausse
manœuvre, supprimez le fichier modifié : l'exécutable en embarque une copie
d'origine et l'utilisera.

---

## En cas de problème

| Message | Que faire |
| --- | --- |
| `Fichier introuvable` | Vérifiez le chemin du `.pbip`. Le glisser-déposer évite les fautes de frappe. |
| `Dossier SemanticModel introuvable` | Le rapport n'est pas au format projet. Réenregistrez-le en `.pbip` depuis Power BI Desktop. |
| `Template introuvable` | `template-doc-pbib.docx` doit rester à côté de l'exécutable. Le message liste les emplacements consultés. |
| `Style ... absent du template` | Un style nommé a été renommé ou supprimé dans le template. Le document est produit malgré tout, avec un style de remplacement. |
| `Configuration : YAML illisible` | Une erreur de frappe dans `config_doc_pbi.yaml`. Le message donne la ligne. |
| `Impossible d'enregistrer le document` | Le document est probablement ouvert dans Word. Fermez-le et relancez. |

Si la fenêtre affiche une erreur inattendue, le détail complet y est écrit :
copiez-le pour le transmettre.
