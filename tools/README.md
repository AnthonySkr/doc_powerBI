# Documentation automatique Power BI

**Version {version}**

Cet outil lit votre rapport Power BI et rédige à votre place tout ce qui peut
l'être : la liste des pages, des visuels, des champs affichés, des tables, des
sources de données et le code de chaque mesure. Il vous rend un document Word,
qu'il ne vous reste plus qu'à compléter et à mettre à vos couleurs.

**Rien à installer** — ni Python, ni Power BI, ni quoi que ce soit d'autre.
Tout ce qui est nécessaire se trouve dans ce dossier.

---

## Avant de commencer

Quatre points à vérifier. Les deux premiers sont indispensables, les deux
suivants font toute la différence entre un document utilisable et un document
qu'il faudra reprendre partout.

### 1. Il vous faut Windows et Microsoft Word

L'outil produit un fichier `.docx`. Word sert à l'ouvrir, le compléter et
l'imprimer. Vous n'avez pas besoin de Power BI Desktop sur ce poste : l'outil
lit des fichiers, il ne se connecte à rien.

### 2. Le rapport doit être enregistré au **format projet** (`.pbip`)

C'est la seule condition vraiment bloquante. Un fichier `.pbix` ordinaire ne
convient pas : l'outil a besoin du format projet, qui expose le contenu du
rapport sous forme de fichiers lisibles.

Dans Power BI Desktop : **Fichier → Enregistrer sous → Projet Power BI
(`.pbip`)**.

Vous devez alors obtenir, **dans un même dossier**, un fichier et deux
sous-dossiers portant tous le même nom :

```
Mon rapport.pbip
Mon rapport.SemanticModel/     ← le modèle : tables, mesures, sources
Mon rapport.Report/            ← les pages, les visuels, les filtres
```

Si vous ne voyez pas les deux sous-dossiers, l'enregistrement n'a pas été fait
au bon format : recommencez. Ne renommez ni ne déplacez l'un des trois
séparément — ils vont ensemble.

> Le format projet est aussi ce qui permet de suivre un rapport dans un outil
> de versionnement. Si votre rapport y est déjà, vous n'avez rien à faire.

### 3. Chaque visuel doit porter un titre

**C'est le point qui décide de la qualité du document.** L'outil reprend le
titre affiché sur chaque visuel pour intituler la partie qui le décrit. Un
visuel sans titre se retrouve dans le document sous un nom technique du genre
`clusteredBarChart (a1b2c3d4)` — illisible, et impossible à retrouver dans le
rapport.

Dans Power BI, pour chaque visuel : volet **Mettre en forme le visuel** →
**Général** → **Titre** → renseignez le **Texte**.

Un titre renseigné mais *masqué* convient parfaitement : l'outil le lit quand
même. Vous pouvez donc nommer proprement un visuel dont le titre n'a pas à
apparaître à l'écran.

**Nommez aussi vos groupes de visuels.** Si vous groupez des visuels dans
Power BI, renommez le groupe dans le volet **Sélection** (double-clic sur son
nom). Sans cela il apparaît comme « Groupe sans nom ».

### 4. Les trois fichiers de ce dossier restent ensemble

| Fichier | À quoi il sert |
| --- | --- |
| `powerbi-doc.exe` | L'application |
| `config_doc_pbi.yaml` | Le plan du document : titres, ordre des parties, questions posées |
| `template-doc-pbib.docx` | L'apparence : styles, page de garde, en-tête et pied de page |

Copiez le dossier entier où vous voulez, mais ne séparez pas les trois
fichiers : l'application cherche les deux autres à côté d'elle.

---

## Lancer l'outil

1. **Glissez votre fichier `.pbip` sur `powerbi-doc.exe`.**
   C'est la façon la plus sûre : aucun chemin à saisir.
   *À défaut :* double-cliquez sur `powerbi-doc.exe`, puis déposez le `.pbip`
   dans la fenêtre qui s'ouvre (ou collez son chemin) et appuyez sur Entrée.

2. **Répondez aux questions** (détaillées ci-dessous). Appuyez sur Entrée pour
   accepter la valeur proposée entre crochets.

3. **Récupérez le document.** Il est écrit à côté de votre `.pbip`, dans un
   sous-dossier `doc`.

La fenêtre reste ouverte à la fin : lisez le compte rendu, puis Entrée pour la
fermer.

---

## Les questions posées

**Dossier où écrire la documentation** — un sous-dossier créé à côté du
`.pbip`. Par défaut `doc`.

**Nom du rapport à afficher sur la page de garde** — le titre visible en
couverture. Par défaut, le nom du fichier `.pbip`.

**Texte à afficher en haut à droite de chaque page** — le texte de l'en-tête.
Par défaut, le même que la page de garde.

**Le rapport comporte-t-il des pages secondaires ?** — répondez *oui* si votre
rapport a des pages de détail atteintes depuis les pages principales. La partie
qui explique cette navigation n'est écrite que dans ce cas.

**Le rapport utilise-t-il un volet de filtre ouvert par un bouton ?** — même
principe : la partie qui décrit ce volet n'apparaît que si vous répondez *oui*.

**Visuels ou groupes déjà présentés ailleurs** — la liste de tous les visuels
du rapport s'affiche, numérotée. Saisissez les numéros de ceux que vous ne
voulez **pas** détailler, séparés par des virgules (par exemple `3,7,12`).
Utile pour un bandeau de titre ou un logo qui se répète : l'écarter une fois
l'écarte de toutes les pages. Laissez vide pour tout documenter.

**Souhaitez-vous relire et modifier les textes types ?** — répondez *oui* pour
que l'outil vous propose, un par un, les paragraphes d'explication du plan, que
vous pourrez réécrire avant qu'ils ne soient posés dans le document.

> **Vos réponses sont conservées.** Elles sont enregistrées dans
> `reponses_<rapport>.yaml`, à côté du `.pbip`, et reproposées au lancement
> suivant : une suite d'Entrée les reconduit à l'identique. C'est important
> pour la liste des visuels écartés — la ressaisir de mémoire à chaque fois
> serait une source d'erreurs. Les entrées déjà retenues sont marquées
> « retenu » dans la liste. Supprimez ce fichier pour repartir de zéro.

---

## Ce que vous recevez, et ce qu'il vous reste à faire

Le document est complet côté technique : tout ce qui vient de Power BI y est
déjà. Trois choses vous attendent.

**Les emplacements de captures.** L'outil n'insère pas d'images : il réserve la
place par une ligne 🖼 décrivant la capture attendue, suivie de sa légende
numérotée. Remplacez cette ligne par votre capture d'écran.

**Les pastilles numérotées.** Sous un emplacement de capture, une rangée de
pastilles rondes porte les numéros du tableau qui suit. Attrapez-en une à la
souris et déposez-la sur l'élément correspondant de votre capture.

**Les zones à rédiger.** Les passages en italique entre crochets — par exemple
`[ce que la mesure calcule, et quand l'employer]` — indiquent ce qu'on attend à
cet endroit. Remplacez le texte par le vôtre.

La table des matières et les numéros de figures se recalculent à l'ouverture
dans Word. Si ce n'est pas le cas : `Ctrl+A` puis `F9`.

---

## Relancer après une évolution du rapport

**Relancez simplement, sur le même `.pbip`.** Le document existant n'est pas
écrasé : il est lu, comparé au rapport actuel, et un document neuf est écrit en
reprenant tout ce que vous y aviez mis.

Ce qui vous revient tel quel : vos textes, vos titres reformulés, vos captures,
vos pastilles là où vous les avez posées, votre mise en forme, vos listes, vos
commentaires de révision.

Ce que l'outil réécrit : ce qu'il avait produit lui-même — code des mesures,
tableaux de champs, sources, mesures appelantes.

**Fermez le document dans Word avant de relancer**, sinon l'enregistrement
échouera.

À la fin de l'exécution, le compte rendu nomme ce qui a changé : les éléments
ajoutés, ceux dont la technique a bougé — leur formule, leurs champs — et donc
dont vos textes parlent peut-être d'une version périmée, et ceux qui ont
disparu du rapport.

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

## Obtenir un meilleur document (facultatif)

Ces habitudes, prises dans Power BI, se retrouvent directement dans le
document :

**Nommez vos étapes Power Query.** Dans « Synthétisation du traitement »,
l'outil ne retient que les étapes qui portent une règle de gestion. Les étapes
que vous n'avez pas nommées — Power BI les nomme d'un code sans signification —
et les gestes de mise en forme courants (`Source`, `Navigation`,
`Type modifié`, `Colonnes renommées`…) sont écartés. Renommer une étape
« Exclusion des commandes annulées » la fait apparaître, et elle se
documentera toute seule.

**Renseignez la description de vos mesures**, dans Power BI. Elle est reprise
dans le document.

**Rangez vos mesures en dossiers d'affichage** : l'outil peut regrouper la
partie « Mesures » par dossier plutôt que par table.

**Masquez ce qui n'a pas à être documenté.** Les tables masquées du modèle sont
écartées d'office.

**Ne documentez que ce qui sert.** Par défaut, seules les mesures réellement
employées par le rapport — affichées dans un visuel ou posées en filtre — sont
documentées, avec leurs dépendances. Les autres sont simplement nommées à la
fin de l'exécution, pour que vous puissiez vérifier qu'aucune ne manque à tort.

---

## Adapter le document à vos usages

**`config_doc_pbi.yaml`** décrit le plan : les titres, l'ordre des parties, les
textes types, les questions posées au lancement, ce qui est documenté ou
écarté. C'est un fichier texte, abondamment commenté : ouvrez-le dans le
Bloc-notes, modifiez-le, relancez. Aucune reconstruction n'est nécessaire.

**`template-doc-pbib.docx`** fournit l'apparence : les styles, la page de
garde, l'en-tête et le pied de page. Ouvrez-le dans Word et modifiez-le comme
un document ordinaire. Les styles nommés qu'il contient (`Code DAX`,
`A completer`, `Legende`…) sont ceux que le plan désigne : si vous en renommez
un, l'outil vous signalera qu'il ne le trouve plus.

---

## En cas de problème

| Message | Que faire |
| --- | --- |
| `Fichier introuvable` | Vérifiez le chemin du `.pbip`. Le glisser-déposer évite les fautes de frappe. |
| `Dossier SemanticModel introuvable` | Le rapport n'est pas au format projet, ou le sous-dossier a été renommé. Réenregistrez-le en `.pbip` (voir le prérequis n° 2). |
| `Dossier Report introuvable` | Même cause, même remède. |
| `Template introuvable` | `template-doc-pbib.docx` doit rester à côté de l'exécutable. Le message liste les emplacements consultés. |
| `Style ... absent du template` | Un style nommé a été renommé ou supprimé dans le template. Le document est produit malgré tout, avec un style de remplacement. |
| `Configuration : YAML illisible` | Une faute de frappe dans `config_doc_pbi.yaml`. Le message donne la ligne. |
| `Impossible d'enregistrer le document` | Le document est ouvert dans Word. Fermez-le et relancez. |
| Des visuels nommés `barChart (a1b2c3d4)` | Ces visuels n'ont pas de titre dans Power BI (voir le prérequis n° 3). |

Si la fenêtre affiche une erreur inattendue, le détail complet y est écrit :
joignez-le à votre demande d'aide.
