# Documentation automatique Power BI

Génère la documentation Word d'un rapport Power BI (`.pbip`) à partir du
template `template-doc-pbib.docx` et d'un plan décrit en YAML.

Le script ne contient aucune structure de document : **tout le plan est dans
`config.yaml`**.

## Mise en place

```bash
python -m venv .venv
.venv\Scripts\Activate        # Windows
pip install taskipy
task install                  # dépendances + outils de développement
```

## Lancer le script

```bash
task run                                  # demande le chemin du .pbip
python main.py "C:\chemin\Rapport.pbip"   # ou directement
```

Options :

| Option | Effet |
| --- | --- |
| `-c`, `--config` | Utiliser un autre fichier de configuration (défaut : `config.yaml`) |
| `-y`, `--no-input` | Ne poser aucune question : utilise les valeurs par défaut du YAML |

Le document est écrit dans `documentation_<rapport>.docx`, sous le dossier
demandé au lancement (`/doc` par défaut), à côté du `.pbip`.

## Ce que fait le script

1. Lit le modèle sémantique (`.SemanticModel`) : mesures DAX, tables, sources
   et étapes de transformation Power Query.
2. Analyse les dépendances entre mesures (mesures et colonnes utilisées).
3. Lit le rapport (`.Report`) : pages, groupes de visuels, visuels, champs
   et filtres.
4. Pose les questions déclarées dans `inputs:`.
5. Écrit le document en suivant le plan `sections:` du YAML, à la suite du
   contenu déjà présent dans le template.
6. Remplace les textes de l'en-tête et du pied de page du template, puis marque
   la table des matières comme à recalculer.
7. Si une documentation existait déjà, en reprend tout ce que vous y avez
   écrit et signale ce qui a changé (voir « Regénération » plus bas).

Les captures d'écran ne sont pas insérées : le script réserve l'emplacement
avec un texte descriptif (`[IMAGE] ...`) qu'il suffit de remplacer par la
capture correspondante une fois le document généré.

### Groupes de visuels

Les visuels regroupés dans Power BI (`parentGroupName` d'un `visual.json`) sont
documentés ensemble, dans une partie au nom du groupe :

1. un emplacement pour une **capture d'ensemble du groupe** ;
2. la **légende** de cette capture — un tableau numérotant les visuels
   documentés du groupe : le lecteur relie ainsi chaque numéro reporté sur
   l'image au visuel détaillé plus bas. Les visuels écartés par `data.visuals`
   (`exclude_types`, `exclude_titles`) n'y figurent pas — un visuel exclu de la
   documentation l'est aussi à l'intérieur de son groupe ;
3. puis, d'un cran plus bas, le **détail de chaque visuel documenté**
   du groupe (capture, tableau des références, lecture du visuel).

Les visuels de la page qui n'appartiennent à aucun groupe suivent ensuite.

Un groupe **réduit à un seul visuel documenté** n'ouvre pas de partie : son
titre et sa légende d'une ligne ne feraient que redire ce que le visuel dit
déjà, au prix d'un niveau de plan de plus. Le visuel est alors documenté seul,
à la suite de la page. Ce sont bien les visuels *documentés* qui comptent : un
groupe de cinq visuels dont quatre sont écartés par `data.visuals` tombe lui
aussi sur ce cas, et un visuel logé dans un sous-groupe compte pour son groupe
racine. `data.visuals.groups.keep_single: true` rétablit la partie de groupe.

### Hiérarchies dans le tableau des références

Une hiérarchie déposée sur un axe — une hiérarchie de dates au premier chef —
est projetée niveau par niveau dans le `visual.json` : posée telle quelle, elle
remplirait autant de lignes du tableau des références (« Date Année »,
« Date Trimestre », « Date Mois »). Le lecteur du rapport, lui, ne voit qu'un
champ.

Les niveaux d'une même hiérarchie **affichés sur le même rôle** sont donc réunis
en une seule référence, dans l'ordre de forage du visuel :

| N° | Rôle | Élément référencé |
| --- | --- | --- |
| 3 | Axe X | Date (Année > Trimestre > Mois) |

La même hiérarchie posée sur deux rôles différents (axe et légende) reste sur
deux lignes, et un niveau isolé garde son nom d'origine. Une hiérarchie de dates
est nommée d'après la colonne qui l'engendre (« Date »), comme dans Power BI ;
une hiérarchie du modèle porte son propre nom.

Le comportement se règle dans `options.references.hierarchies` de la section
`visuels` :

| Clé | Effet |
| --- | --- |
| `group` | `false` rend une ligne à chaque niveau |
| `format` | Gabarit de la référence — `{hierarchy}`, `{levels}` |
| `separator` | Séparateur entre les niveaux (`" > "` par défaut) |

## Configuration — `config.yaml`

| Bloc | Rôle |
| --- | --- |
| `document` | Template, dossier et nom de sortie, mémoire des réponses, page de garde, en-tête / pied de page, propriétés du fichier |
| `styles` | Correspondance avec les styles du template (`Heading 1`, `Ref Valeur`, `Code DAX`…) |
| `rendering` | Mise en forme commune : sauts de page, emplacements d'images, zones à compléter, liens internes, table des matières |
| `data` | Filtres et tris appliqués aux pages, visuels, groupes de visuels, tables et mesures |
| `merge` | Regénération au-dessus d'une documentation existante |
| `inputs` | Questions posées à l'utilisateur au lancement |
| `sections` | Le plan du document |

### Sections et blocs

Une `section` = un titre + des `blocks` + des `sections` filles.

Une section peut déclarer `seed: true` : toute la partie — ses sous-titres
compris — est alors écrite à la première génération, puis **vous appartient
entièrement**. Rien n'y est repéré : vous ajoutez, renommez, supprimez et
déplacez les sous-titres comme vous voulez, tout revient tel quel. C'est ce
qu'emploient « Initialisation » et « Acquisition des données », qui sont
rédigées de bout en bout.

Types de blocs :

| Type | Effet |
| --- | --- |
| `paragraph` | Texte fixe ; `editable: true` propose sa modification au lancement |
| `image` | Emplacement réservé pour une capture, avec sa description ; `markers:` y ajoute les repères numérotés à glisser sur l'image |
| `user_fill` | Zone laissée vide (`[À compléter]`) à rédiger après génération ; `hint:` remplace cette amorce par ce qu'on attend à cet endroit ; `show_placeholder: false` laisse une ligne vraiment vide |
| `property` | Sous-titre + valeur, ou liste de valeurs (`value_list`) |
| `table` | Tableau construit à partir des données extraites ; `label:` ajoute un sous-titre |
| `loop` | Répétition d'un sous-plan sur une collection (pages, visuels, tables, mesures) |

### Variables et conditions

Les chaînes acceptent des variables `{{ ... }}` :

```yaml
title: "{{ page.display_name }}"
description: "Capture complète de la page « {{ page.display_name }} »"
```

Collections disponibles dans les boucles : `report.pages`, `page.groups`,
`page.ungrouped_visuals`, `page.visuals` (les deux précédentes réunies),
`group.members`, `group.visuals`, `visual.references`, `model.tables`,
`model.tables_with_measures`, `table.measures`, `table.transformation_steps`,
`table.calculated_columns`.

Une section ou un bloc peut être conditionné par `when` :

```yaml
when: inputs.pages_secondaires      # vrai si la réponse est vraie
when: "!inputs.pages_secondaires"   # négation
when: "ref.kind == mesure"          # égalité
```

### Ce que le script demande au lancement

Les questions viennent de `inputs:`. Cinq types : `text`, `textarea`, `confirm`,
`choice` et `multi_choice` (numéros séparés par une virgule). Les options d'un
`choice` ou d'un `multi_choice` peuvent être une liste figée du YAML **ou une
expression** — `choices.visuals` liste alors les titres réellement présents dans
le rapport :

```yaml
  - id: visuels_non_detailles
    type: multi_choice
    label: "Visuels ou groupes déjà présentés ailleurs, à ne pas détailler"
    options: "{{ choices.visuals }}"
```

Les filtres `data:` peuvent reprendre une réponse. C'est ainsi que la question
ci-dessus agit : le titre choisi rejoint les titres écartés, et le visuel — ou
le groupe, avec tout son contenu — disparaît de la partie « Visuels ».

```yaml
data:
  visuals:
    exclude_titles: "{{ inputs.visuels_non_detailles }}"
```

Un bandeau d'en-tête porte le même titre sur toutes les pages : les titres
proposés sont dédoublonnés, et en écarter un l'écarte partout à la fois.

**Vos réponses sont conservées.** Elles sont écrites à côté du `.pbip`
(`reponses_<rapport>.yaml`) et reproposées à la génération suivante — marquées
d'une flèche pour les listes : un Entrée les reconduit.

### Table de données : ce qui est écrit, et ce qui ne l'est pas

Une sous-partie ne s'écrit que si elle a quelque chose à dire — une table sans
paramètres de connexion n'ouvre pas de rubrique « Paramètres » vide (`when:` sur
le bloc).

Les **paramètres** reprennent l'expression de l'étape source de Power Query
telle qu'elle est écrite, indentation comprise, dans le style `Code DAX`. Une
source qui n'apprend rien ne compte pas comme une source : `ignore_sources`
liste ces expressions — `{1}`, la source de la table de mesures créée à la main
— et la rubrique disparaît comme si la table n'en avait pas.

La **synthétisation du traitement** est un tableau *étape → opération*, réduit
aux étapes qui portent une règle de gestion. Sont écartées, via
`data.tables.steps` :

| Réglage | Écarte |
| --- | --- |
| `exclude_unnamed` | les étapes sans nom — Power BI les nomme d'un GUID |
| `exclude_names` | les noms exacts listés (`Source`) |
| `exclude_prefixes` | tout nom commençant par (`Navigation`, `Type modifié`, `Colonnes renommées`, `Colonnes permutées`) — suffixes numérotés compris |

La **particularité** n'apparaît que si la table porte des colonnes calculées :
un tableau *colonne → code DAX*. Une colonne calculée est un `column` du .tmdl
porteur d'une expression (`column Marge = [Montant] - [Coût]`) ; une colonne
ramenée de la source n'en a pas, et n'a donc rien à documenter ici. Les mesures
mentionnées dans le code sont liées à leur définition.

### Mesures documentées

Le plan livré ne documente que les mesures que le rapport **emploie**
(`data.measures.scope: used_in_report`). Est employée une mesure :

- affichée par un visuel — **étiquettes de référence d'une carte comprises** ;
- posée en **filtre**, de visuel, de page ou de rapport entier ;
- **dont dépend** une mesure employée (`DIVIDE([Marge], [CA])` documente `CA`).

Les mesures restantes sont nommées en fin de génération, une par ligne :

```
2 mesure(s) du modèle non documentée(s) — non utilisée(s) :
  · Autre orpheline
  · Jamais utilisée
```

Les compter ne suffirait pas : sans leur nom, impossible de dire si l'une
manque à tort. `scope: all` documente tout le modèle et vide cette liste.

### Étiquettes de référence d'une carte

Une carte affiche une valeur principale, et peut porter des **étiquettes de
référence** — chacune avec sa valeur et, au-dessous, un détail. Ces champs-là
ne passent pas par la requête du visuel : Power BI les déclare dans l'objet de
mise en forme. Ils sont lus quand même, et rejoignent le tableau des
références du visuel avec leur propre rôle :

| N° | Rôle | Élément référencé |
| --- | --- | --- |
| 1 | Valeur | Chiffre d'affaires |
| 2 | Étiquette de référence | Objectif CA |
| 3 | Étiquette de référence — détail | Écart objectif |

C'est aussi ce qui empêche une mesure qui n'apparaît que là de passer pour
inutilisée.

### Liens internes

Le titre d'une mesure déclare un signet :

```yaml
bookmark: "measure:{{ measure.name }}"          # sur le titre de la mesure
```

**Toute mention d'une mesure renvoie ensuite vers ce signet**, sans avoir à la
déclarer : le générateur reconnaît les noms de mesures dans tous les textes
qu'il écrit — libellés du tableau des références d'un visuel, code DAX,
« Source utilisée », descriptions, paragraphes du plan — et les transforme en
liens. Les titres (h1/h2/h3) en sont exclus pour ne pas perturber le sommaire,
ainsi que la mesure en cours de définition (pas de lien vers soi-même).

Le comportement se règle dans `rendering.links.auto` :

| Clé | Effet |
| --- | --- |
| `enabled` | Désactive la détection automatique |
| `source` | Collection des mesures documentées (cibles possibles) |
| `target` | Gabarit de la cible ; doit reprendre le `bookmark:` du plan |
| `in_code` | Liens à l'intérieur des blocs de code DAX |
| `skip_self` | Pas de lien d'une mesure vers elle-même |
| `first_occurrence_only` | Une seule mention liée par paragraphe |
| `case_sensitive` | Respect de la casse dans la reconnaissance des noms |
| `min_length` | Longueur minimale d'un nom pris en compte |
| `exclude` | Mesures à ne jamais lier (nom trop courant, mesure technique) |

Un bloc peut refuser les liens avec `links: false`.

`hyperlink:` reste disponible sur une colonne de tableau pour forcer une cible
particulière ; il est ignoré si le signet visé n'existe pas dans le document.

Pour qu'aucun lien ne pointe dans le vide, une mesure référencée par un visuel
ou par une autre mesure est documentée même si les filtres de `data.measures`
l'écartaient (`include_referenced: true`). En fin de génération, le script
indique le nombre de liens créés et signale les mesures mentionnées qui ne sont
pas documentées.

### Liens retour : où une mesure est-elle utilisée ?

La définition d'une mesure liste aussi les endroits qui l'emploient, en sens
inverse des liens précédents :

- **Utilisée dans** — un lien par visuel affichant la mesure, qui renvoie au
  titre du visuel (`bookmark: "visual:{{ page.name }}:{{ visual.id }}"`).
  Les libellés et les cibles se règlent dans `options.usages` de la section
  `visuels`.
- **Utilisée par** — les mesures dont l'expression DAX appelle celle-ci ; ces
  noms sont liés automatiquement vers leur propre définition.

## Regénération au-dessus d'une documentation existante

Si le fichier de sortie existe déjà, il n'est pas écrasé : il est lu, comparé
au rapport actuel, et un document neuf est écrit en reprenant tout ce que vous
y avez mis.

### Ce qui est signalé

**Le document ne porte aucune marque.** Ce qui a été ajouté ou modifié est
nommé, un par ligne, dans le résumé affiché en fin de génération :

```
Mise à jour : 1 élément(s) ajouté(s), 1 élément(s) modifié(s) — à vérifier.
  1 ajouté(s) :
  · Tendance mensuelle
  1 modifié(s) — à vérifier :
  · Seuil alerte
  41 contenu(s) rédigé(s) repris tels quels
```

| Situation | Effet |
| --- | --- |
| La technique d'un élément a changé (formule DAX, champs du visuel) | Nommé parmi les **modifiés** : vos textes portent peut-être sur une version périmée |
| Élément apparu depuis la version précédente | Nommé parmi les **ajoutés** |
| Élément renommé dans Power BI | Reconnu à son état technique : vos textes le suivent |
| Élément retiré du rapport | Ce que vous y aviez écrit part en annexe (voir ci-dessous) |

Le surlignage reste disponible si vous le préférez dans le document :
`merge.highlight_changed` et `merge.highlight_new` acceptent une couleur
(`yellow`, `green`, `turquoise`, `gray`) au lieu de `none`.

### Rien ne se perd — l'annexe

Il reste des cas où un texte ne peut pas revenir là où il était : l'élément a
disparu du rapport, le bloc a été retiré du plan, ou la donnée du script sur
laquelle vous aviez écrit a été remaniée à la main. Ces contenus ne sont pas
supprimés : ils sont rassemblés en fin de document, sous « Contenu non
replacé », avec leur provenance.

```
Contenu non replacé
  Retiré du rapport — measure:Ancienne marge
    <ce que vous aviez écrit là>
```

Vous reprenez ce qui vous intéresse, puis vous supprimez la partie : elle ne
revient pas. Tant qu'elle n'est pas vidée, elle se reconduit d'une génération à
l'autre. Le bilan console dit combien de contenus y ont été déposés.

Si vous rétablissez le surlignage, il est retiré à la génération suivante : il
signale ce qui a changé *depuis le document que vous aviez en main*, pas un
état à cocher.

### Comment le repérage fonctionne

À la génération, le script pose dans le document des **marqueurs invisibles**
(texte masqué Word, `w:vanish`) :

| Marqueur | Rôle |
| --- | --- |
| `pbi::elem\|<id>\|<empreinte>` | Ancre un élément documenté et fige son état technique |
| `pbi::gen\|<bloc>` … `pbi::endgen\|<empreintes>` | Encadrent un contenu produit par le script. Le marqueur de fin retient l'empreinte de chaque paragraphe et tableau écrits |
| `pbi::seed\|<bloc>` … `pbi::endseed\|<empreintes>` | Encadrent une **amorce** : un contenu écrit à la première génération, puis laissé à vous. Même forme, politique inverse — c'est la version du document qui l'emporte |

L'identifiant est le `bookmark:` déclaré dans le plan (`measure:<nom>`,
`visual:<page>:<visuel>`, `page:<page>`, `table:<nom>`), sinon `section:<id>` :
des identifiants stables issus de Power BI ou du plan. Une section qui n'a ni
l'un ni l'autre est repérée par son titre sous la partie qui la contient
(`<parent>><titre>`). L'empreinte est un condensé du `fingerprint:` déclaré à côté :

```yaml
bookmark: "measure:{{ measure.name }}"
fingerprint: "{{ measure.expression }}"     # change → vos textes à revérifier
```

**Ne supprimez pas ces marqueurs.** Ils sont invisibles à l'écran et à
l'impression ; on les voit en activant « Afficher tout » (¶). Un document sans
marqueurs est simplement régénéré intégralement, sans erreur.

Chaque marqueur occupe un paragraphe à lui, dont la **marque de paragraphe est
masquée elle aussi** : Word le joint au suivant, et il ne prend donc aucune
place — ni ligne vide, ni écart entre les paragraphes qu'il sépare. Affichés
(¶). 

### Quels blocs le script s'attribue

Par défaut les blocs `property` et `table` — ceux qui n'affichent que des
données du rapport. Les paragraphes, emplacements d'image et zones
`user_fill` sont des **amorces** : écrites à la première génération, puis
laissées à l'utilisateur. Un bloc du plan peut trancher explicitement :

```yaml
- type: paragraph
  id: rappel_legal
  generated: true      # toujours réécrit depuis le YAML
```
### Réglages — bloc `merge`

| Clé | Effet |
| --- | --- |
| `enabled` | `false` : régénère toujours de zéro, sans lire l'existant |
| `keep_user_text` | `false` : ignore le contenu du document précédent |
| `backup` / `backup_dir` | Archive la version précédente avant d'écrire la nouvelle |
| `highlight_changed` | Couleur des textes d'un élément qui a changé (`yellow`) |
| `highlight_new` | Couleur de la zone à rédiger d'un nouvel élément (`green`) |
| `orphans.enabled` | `false` : ne pas écrire l'annexe des contenus non replacés |
| `orphans.title` / `orphans.intro` | Titre et texte d'explication de cette annexe |

### Limites connues

- L'ordre des **éléments** suit le plan : si vous déplacez un élément entier
  ailleurs dans le document, il revient à sa place. Vos remaniements *à
  l'intérieur* d'un élément sont respectés.
- Une mesure **renommée** dans Power BI est reconnue par son état technique :
  la formule DAX n'a pas bougé, donc c'est la même mesure, et vos textes la
  suivent. Le rapprochement n'a lieu que s'il est sans ambiguïté — une seule
  disparition et une seule apparition portant cette empreinte. Sinon, vos
  textes vous attendent en annexe.
- Ce qui précède la première ancre (page de garde, sommaire) vient du template
  et est régénéré ; ce que vous y aviez ajouté part en annexe. La table des
  matières fait exception : Word la recalcule à chaque ouverture, elle n'est
  donc jamais prise pour de la rédaction.

## Template

Le plan pointe sur `template-doc-pbib.docx`, qui apporte des styles nommés
repris par la configuration :

| Clé `styles` | Style du template | Usage |
| --- | --- | --- |
| `table` | `Tableau Reference` | Tableau des références d'un visuel (en-tête bleu, lignes alternées) |
| `table_data` | `Tableau Donnees` | Tableau neutre, disponible pour d'autres tableaux du plan |
| `ref_header` / `ref_number` / `ref_role` / `ref_value` | `Ref Entete` / `Ref Numero` / `Ref Role` / `Ref Valeur` | Les quatre styles de ce tableau |
| `image` | `Image Placeholder` | Encadré pointillé réservant la capture |
| `caption` | `Legende` | Légende numérotée sous l'emplacement |
| `todo` | `A completer` | Zones à rédiger après génération |
| `technical_id` | `Id technique` | Type du visuel affiché en gris à la suite du titre |

### Tableaux

Un bloc `table` accepte, en plus de ses colonnes :

| Clé | Effet |
| --- | --- |
| `header` / `header_labels` / `header_style` | Ligne d'en-tête et son style |
| `layout` | `fixed` (défaut) : Word respecte les largeurs déclarées |
| `repeat_header` | Répète l'en-tête en haut de chaque page |
| `cant_split` | Empêche une ligne d'être coupée par un saut de page |
| `vertical_align` | Alignement vertical des cellules (`center` par défaut) |

Chaque colonne peut porter `width_cm`, `style` (style de paragraphe de la
cellule) et `header_style`.

### Titres

Un titre de section peut être suivi d'une mention technique discrète :

```yaml
title: "{{ visual.title }}"
title_suffix: "{{ visual.visual_type }}"
title_suffix_style: "{{ styles.technical_id }}"
```

## Distribuer aux utilisateurs Power BI

Le script est empaqueté en un exécutable autonome : les utilisateurs n'ont ni
Python ni dépendances à installer.

```bash
task package     # vérifie, construit, assemble et zippe
```

Résultat dans `dist/` :

```
powerbi-doc-2.0.0-windows.zip
└── powerbi-doc-2.0.0-windows/
    ├── powerbi-doc.exe          l'application, autonome
    ├── config.yaml      le plan du document, modifiable
    ├── template-doc-pbib.docx   la charte Word, modifiable
    └── LISEZMOI.md              mode d'emploi
```

Il n'y a plus qu'à transmettre le `.zip`. L'utilisateur le décompresse et
double-clique sur l'exe — ou y glisse-dépose son fichier `.pbip`.

### Configuration et template restent modifiables

Le plan est dans le YAML, pas dans le code. Les deux fichiers sont donc 
livrés **en clair à côté de l'exe**, pas seulement enfermés dedans. 
L'utilisateur les édite et relance — sans rien reconstruire.

L'exécutable en embarque tout de même une copie, utilisée si les fichiers
livrés ont été supprimés ou déplacés. L'ordre de recherche est dans
`src/core/paths.py` :

1. le chemin donné (absolu, ou relatif au dossier courant) ;
2. à côté de l'exécutable — le cas normal ;
3. à l'intérieur de l'exécutable — copie de secours.

### Étapes séparées

| Commande | Effet |
| --- | --- |
| `task build` | Construit seulement `dist/powerbi-doc.exe` (PyInstaller) |
| `task package` | `lint` + `test` + `build`, puis assemble et zippe |
| `task clean` | Supprime aussi `build/` et `dist/` |

La recette de construction est dans `powerbi-doc.spec` : c'est là qu'on ajoute
un fichier à embarquer, une icône (`icon=`) ou un module manquant
(`hiddenimports`).

## Un programme, trois modules

Le projet est **un seul programme**, découpé en trois modules qui ont chacun
une responsabilité et une seule :

```
.pbip  ──►  pbi_extractor  ──►  [ gui_automator ]  ──►  report_generator  ──►  .docx
```

| Module | Sa seule responsabilité |
| --- | --- |
| `pbi_extractor` | Lire le projet `.pbip` et retourner ce qu'il contient |
| `gui_automator` | Piloter Power BI Desktop et enregistrer des images |
| `report_generator` | Écrire le `.docx` à partir de ces données et de ces images |

Ils vivent sous `src/`. Aucun des trois ne connaît les autres : ils ne
partagent que `src/core`, et les données qui passent de l'un à l'autre.
`main.py`, à la racine, les enchaîne — c'est tout ce qu'il fait.

### Ce qui circule

Un seul objet, d'un bout à l'autre : le `PowerBiMetadata` de `src/core/models.py`.

```python
metadata = extract(project)  # produit par l'extraction
capturer.capture(metadata, config, options)  # enrichi de ses images
write_document(metadata, config, inputs, output_dir)  # lu par le document
```

Rien ne transite par le disque entre deux étapes : pas de fichier intermédiaire
à écrire, à relire, à supprimer ni à tenir à jour.

### Le socle commun — `src/core/`

Ce que les trois partagent, et rien de plus :

| Module | Rôle |
| --- | --- |
| `models.py` | Les structures de données, dont `PowerBiMetadata` |
| `config.py` | Le plan (`config.yaml`), ses valeurs par défaut, son accès |
| `expressions.py` | Les `{{ ... }}`, les listes `over:`, les conditions `when:` |
| `selection.py` | Ce que le plan retient du rapport — pages, visuels, groupes |
| `console.py` | Tout le dialogue avec le terminal |
| `questions.py` | Les questions élémentaires posées au terminal |
| `prompts.py` | Le questionnaire déclaré par `inputs:` |
| `answers.py` | La mémoire des réponses d'une génération à l'autre |
| `paths.py` | La localisation des fichiers livrés (exécutable compris) |
| `window.py` | La fenêtre console de l'exécutable : attente et plantages |

**`core` ne dépend d'aucun des trois modules ; les trois dépendent de lui, et
jamais les uns des autres.**

`selection.py` y vit parce que deux modules le consultent : le document pour
savoir quoi écrire, la capture pour savoir quoi photographier — photographier
un visuel que le document tait serait du temps perdu.

### Lire la documentation du code

Les docstrings et les annotations du code sont servies comme un site, par
[pdoc](https://pdoc.dev) :

```bash
task docs                    # tout le projet, sur http://127.0.0.1:8080
task docs -- extractor       # le seul module d'extraction
task docs -- capturer        # … ou capturer, writer, core, main
task docs-build              # le site statique, dans docs/site/
```

Le serveur **recharge à chaud** : on modifie un docstring, on rafraîchit, c'est
à jour. Chaque page porte le code source déplié, un bouton vers GitHub, une
recherche, et le rappel du module auquel elle appartient.

Ces pages ne peuvent pas se périmer sans que le code change — c'est tout
l'intérêt par rapport à une documentation écrite à côté.

`tools/docs.py` s'occupe d'énumérer les modules (un paquet qui déclare `__all__`
cache ses sous-modules à pdoc) et de découper par module.

## Captures d'écran des visuels

Le document réserve la place des captures ; `gui_automator` les prend.
**Les deux ne se connaissent que par un dossier d'images** — celui que
`capture.directory` désigne, à côté du `.pbip` :

```
assets/
    page_ventes/
        page.png              ← la page entière
        g_indicateurs.png     ← un groupe : son cadre, visuels compris
        v_evolution.png       ← nom technique du visuel, pas son titre
```

Une image par emplacement que le document réserve : **une par page, une par
groupe, une par visuel documenté** — y compris les visuels d'un groupe, que le
document détaille un à un sous la capture d'ensemble.
`--capture-plan` les énumère avec leur nom de fichier, avant toute capture.

C'est tout le contrat. Renommer un visuel dans Power BI ne perd pas sa capture,
et remplacer une image par une meilleure — retouchée, prise autrement — revient
à écrire dans ce dossier.

### Comment ça marche

Power BI Desktop ne rend pas ses visuels comme des contrôles Windows : le
canevas est une surface dessinée d'un bloc, dont aucune API ne sait extraire
« l'image du visuel X ». Ce qui est possible, en revanche, c'est de
**photographier l'écran et de recadrer d'après le rapport** — qui déclare la
place de chaque visuel dans un canevas logique de 1280 × 720.

    pywinauto   piloter la fenêtre : l'amener devant, changer de page
    mss         photographier une région de l'écran, et la rendre en PNG

Les deux sont en option : `pip install -e ".[capture]"`.

### Reconnaître la fenêtre

La fenêtre du rapport se reconnaît au **processus** qui la porte —
`PBIDesktop.exe`, ou `PBIDesktopStore.exe` pour la version du Microsoft Store —
et non à son titre. C'est volontaire : le titre change d'une version à l'autre,
et les versions récentes n'y écrivent plus que le nom du rapport.

    Ventes 2024 - Power BI Desktop      les versions anciennes
    Ventes 2024 - Power BI              certaines versions intermédiaires
    Ventes 2024                         les versions récentes — le rapport seul

`capture.window.title` reste lisible, mais il n'est plus un critère : il ne
sert qu'à désigner **un rapport parmi plusieurs ouverts en même temps**. Laissé
vide — sa valeur par défaut —, la fenêtre de Power BI trouvée est retenue ;
s'il y en a plusieurs, la plus grande, c'est-à-dire le rapport plutôt que
l'écran de démarrage.

```yaml
capture:
  window:
    title: "Ventes 2024"   # facultatif : seulement si plusieurs rapports sont ouverts
```

Quand rien n'est trouvé, le message d'erreur énumère les fenêtres vues et
l'exécutable de chacune : de quoi voir tout de suite si Power BI était ouvert,
et sous quel nom. Une fenêtre réduite dans la barre des tâches est dépliée
avant la capture — sinon les images seraient celles du bureau.

### Tester module par module

Chaque étape s'éprouve seule, de la plus sûre à la moins sûre :

| Commande | Ce qu'elle vérifie | Besoin de Power BI |
| --- | --- | --- |
| `task test` | le cadrage, le plan, le dossier, le déroulé d'une séance | non |
| `python main.py <rapport> --capture-plan` | ce qui serait capturé, et à quelles dimensions | non |
| `python main.py <rapport> --fake-captures` | la chaîne entière, en rectangles unis | non |
| `python main.py <rapport> --calibrate` | le cadrage du canevas dans la fenêtre | oui |
| `python main.py <rapport> --captures --manual-pages` | les vraies captures, pages changées à la main | oui |
| `python main.py <rapport> --captures` | tout, y compris le changement de page | oui |

`--page` et `--shot` restreignent à une page ou à une prise : de quoi reprendre
une seule capture sans redérouler le rapport.

### Où le canevas est rendu

Tout le cadrage découle d'un seul rectangle : celui où Power BI dessine le
canevas à l'écran. Il est **cherché dans l'image**, pas déduit de mesures
déclarées — Power BI dessine le canevas sur un fond uni, et le canevas est le
rectangle de ce qui n'est pas ce fond (voir `src/gui_automator/canvas.py`).

Le rectangle trouvé n'est retenu que s'il a les proportions que la page
déclare (1280 × 720, ou ce qu'elle dit). Sinon le script ne devine pas : il
revient aux marges déclarées et le signale. Ce contrôle attrape du même coup
le rapport qui n'est pas en « Ajuster à la page », ou dont on a zoomé — deux
états où **aucun** calcul de cadrage ne peut être juste.

Les marges de `capture.window` ne servent plus qu'à délimiter la recherche :
elles doivent contenir le canevas entier, bordé de fond sur ses quatre côtés.
Être large suffit ; être exact n'est plus nécessaire.

```yaml
capture:
  directory: assets      # où ranger les images, à côté du .pbip
  window:
    maximize: true       # agrandir la fenêtre : cadrage reproductible, image nette
    detect_canvas: true  # chercher le canevas dans l'image (recommandé)
    inset_top: 130       # ruban
    inset_right: 340     # volets Visualisations et Filtres
    inset_bottom: 60     # barre des onglets de page
```

### Régler le cadrage

`--calibrate` écrit trois images dans `assets/_calibrage/` :

| Image | Ce qu'elle montre |
| --- | --- |
| `fenetre.png` | la fenêtre entière, telle qu'elle est à l'écran |
| `canevas.png` | ce que le script retient comme canevas |
| `reperes.png` | la même fenêtre, **canevas et visuels entourés** |

`reperes.png` est celle qui répond à « pourquoi mes captures sont mal
cadrées » : les rectangles verts doivent tomber sur les visuels, le rouge sur
le canevas. S'ils sont décalés, l'image dit de combien et dans quel sens. Les
repères sont ceux de la première page du plan — affichez-la dans Power BI
avant de lancer le calibrage.

### Changer de page

Trois voies, essayées dans cet ordre, parce qu'aucune ne marche partout :

1. **l'onglet**, cliqué par l'automatisation — les versions récentes dessinent
   leurs onglets dans le canevas et n'en exposent aucun ([le problème est
   connu](https://stackoverflow.com/questions/71948392/pywinauto-automate-power-bi-desktop-tabs)) ;
2. **le clavier** : `Ctrl+Page suivante` / `Ctrl+Page précédente`. Le rapport
   donne le rang de chaque page, onglets cachés compris : d'un rang connu au
   suivant, il n'y a qu'à compter les pas. Le script remonte d'abord à la
   première page pour savoir d'où il part, après avoir éprouvé une fois que le
   raccourci fonctionne ;
3. **vous**, à qui le script demande d'afficher la page.

Chaque voie est **vérifiée** : le script compare ce qui est à l'écran avant et
après. Rien n'a changé, la page n'a pas été atteinte — et il préfère demander,
ou écarter les prises de cette page, plutôt que de photographier une autre page
en croyant tenir celle-là. `--manual-pages` court-circuite tout cela et
demande à chaque page.

## Structure du projet

Chaque module a une responsabilité unique ; ce qu'il expose est déclaré par son
`__init__.py`, et un seul fichier en porte le point d'entrée — `extractor.py`,
`capturer.py`, `writer.py`. Les tests sont rassemblés sous `tests/`.

```
main.py                       le chef d'orchestre : enchaîne les trois modules
config.yaml                   le plan du document
template-doc-pbib.docx        le template Word

src/
  core/                       le socle commun — aucun module n'en dépend d'un autre
      models.py               les structures qui circulent, dont PowerBiMetadata
      config.py               le plan : chargement, valeurs par défaut, accès
      expressions.py          variables {{ }}, listes `over:`, conditions `when:`
      selection.py            ce que le plan retient du rapport
      console.py              tout le dialogue avec le terminal passe par ici
      questions.py            questions élémentaires posées au terminal
      prompts.py              questionnaire déclaré par `inputs:`
      answers.py              mémoire des réponses d'une génération à l'autre
      paths.py                localisation des fichiers livrés (exe compris)
      window.py               fenêtre de l'exécutable : attente et plantages

  pbi_extractor/              le .pbip ──► PowerBiMetadata
      extractor.py            le point d'entrée : les trois sources croisées
      pbip.py                 localisation des dossiers d'un projet .pbip
      dependencies.py         dépendances transitives entre mesures
      tmdl/                   modèle sémantique
          reader.py             lecture des fichiers, découpage en blocs
          measures.py           blocs `measure` → DaxMeasure
          columns.py            blocs `column ... = ...` → colonnes calculées
          tables.py             table, visibilité, partition
          powerquery.py         script `let ... in` → étapes nommées
      report/                 rapport PBIR
          pages.py              pages, groupes et visuels
          fields.py             projections et filtres

  gui_automator/              Power BI Desktop ──► les PNG
      capturer.py             le point d'entrée : une séance, de bout en bout
      geometry.py             du repère du rapport à celui de l'écran
      plan.py                 ce qu'il y a à capturer, sans rien ouvrir
      library.py              où vivent les images, et sous quel nom
      canvas.py               où le canevas est rendu, cherché dans l'image
      png.py                  écrire une image, sans bibliothèque d'images
      finder.py               quelle fenêtre du bureau est le rapport
      recorder.py             le contrat d'un preneur de captures
      fake.py                 un preneur qui n'ouvre rien : rectangles unis
      desktop.py              le vrai : Power BI Desktop (pywinauto + mss)

  report_generator/           PowerBiMetadata ──► le .docx
      writer.py               le point d'entrée : l'écriture et son bilan
      context.py              assemble les collections que le plan parcourt
      filters.py              tables, mesures et étapes retenues par `data:`
      references.py           tableaux numérotés, « utilisée dans »
      measure_links.py        mentions de mesures repérées dans un texte
      word/                   écriture du .docx
          generator.py          document précédent, écriture, archivage
          errors.py             DocumentError, seule erreur remontée
          merging.py            marqueurs, reprise des textes, surlignage
          builder.py            parcours du plan et écriture du contenu
          body.py               insertion en fin de corps, sans reparcours
          styles.py             clés de style → styles du template
          links.py              signets et liens internes
          tables.py             réglages OOXML des tableaux
          figures.py            emplacement de capture, légende, repères
          shapes.py             repères numérotés à glisser sur une capture
          values.py             valeurs déclarées dans le plan
          fields.py             champs Word : sommaire, numéros, en-têtes
          word_app.py           recalcul des champs par Word (optionnel)
      merge/                  régénération au-dessus d'une doc existante
          markers.py            marqueurs invisibles posés dans le document
          blocks.py             découpage du corps en blocs ancrés
          previous.py           relecture du document précédent
          salvage.py            textes retrouvés dans un contenu du script
          cells.py              annotations retrouvées dans un tableau
          smart.py              fusion : données du script, reste à l'auteur
          orphans.py            annexe des contenus qui n'ont plus de place
          transplant.py         recopie d'un contenu et de ses dépendances
          changes.py            bilan des ajouts / modifications / retraits

assets/                       destination des captures (voir assets/README.md)
tests/                        core/, extract/, capture/, document/, et le
                              parcours complet sur le plan livré
tools/docs.py                 documentation du code (pdoc)
tools/package.py              assemblage du dossier distribué
docs/templates/               habillage du site de documentation
powerbi-doc.spec              recette de construction de l'exécutable
```

### Par où commencer

| Pour... | Ouvrir |
| --- | --- |
| changer le plan du document | `config.yaml` (pas de code) |
| ajouter un type de bloc | `src/report_generator/word/builder.py` → `_block_writers` |
| exposer une donnée au plan | `src/core/models.py` puis `src/report_generator/context.py` |
| ajouter un filtre `data:` | `src/core/selection.py` ou `src/report_generator/filters.py` |
| ajouter un type de question | `src/core/questions.py`, branché dans `src/core/prompts.py` → `_ask` |
| capturer autrement qu'avec Power BI Desktop | écrire un `Recorder` (voir `src/gui_automator/recorder.py`) |
| corriger un cadrage de capture | `src/gui_automator/geometry.py`, et ses tests |
| changer ce qui passe d'un module à l'autre | `PowerBiMetadata`, dans `src/core/models.py` |
| changer l'enchaînement des étapes | `main.py` → `generate` |
| changer où sont mémorisées les réponses | `document.answers_file` du YAML |
| lire une nouvelle propriété TMDL | `src/pbi_extractor/tmdl/measures.py` → `_PROPERTIES` |
| changer ce qui déclenche une alerte de mise à jour | le `fingerprint:` de la section, dans le YAML |

## Notes

- Les styles déclarés dans `styles:` doivent exister dans le template : sinon
  le script bascule sur `fallback` et le signale une fois dans la console.
- Si la table des matières n'apparaît pas à jour (visionneuse autre que Word,
  mise à jour refusée), la sélectionner dans Word puis « Mettre à jour les
  champs » (F9).

## Commandes utiles

```bash
task run        # générer la documentation d'un rapport
task test       # tous les tests
task check      # format + lint (ruff) + tests
task build      # construire l'exécutable
task package    # construire le zip à distribuer
task clean      # nettoyer les caches et les artefacts de construction
task docs       # servir la documentation du code
```

Mise au point des captures, sans écrire de document :

```bash
task capture-plan -- rapport.pbip     # ce qui serait capturé
task calibrate    -- rapport.pbip     # régler le cadrage de la fenêtre
```
