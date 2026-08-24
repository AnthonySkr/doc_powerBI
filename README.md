# Documentation automatique Power BI

Génère la documentation Word d'un rapport Power BI (`.pbip`) à partir du
template `template-doc-pbib.docx` et d'un plan décrit en YAML.

Le script ne contient aucune structure de document : **tout le plan est dans
`config_doc_pbi.yaml`**. Pour documenter un rapport différemment, on modifie le
YAML, pas le code.

## Mise en place

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows
pip install taskipy
task install                      # dépendances + outils de développement
```

## Lancer le script

```bash
task run                                  # demande le chemin du .pbip
python main.py "C:\chemin\Rapport.pbip"   # ou directement
```

Options :

| Option | Effet |
| --- | --- |
| `-c`, `--config` | Utiliser un autre fichier de configuration (défaut : `config_doc_pbi.yaml`) |
| `-y`, `--no-input` | Ne poser aucune question : utilise les valeurs par défaut du YAML |

Le document est écrit dans `doc/documentation_<rapport>.docx`, à côté du `.pbip`.

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
2. la **légende** de cette capture — un tableau numérotant *tout* le contenu du
   groupe, y compris les visuels écartés par `data.visuals.exclude_types`
   (boutons, formes, images) : le lecteur retrouve ainsi chaque élément vu sur
   l'image, sans que ceux-ci soient détaillés pour autant ;
3. puis, d'un cran plus bas, le **détail habituel de chaque visuel documenté**
   du groupe (capture, tableau des références, lecture du visuel).

Les visuels de la page qui n'appartiennent à aucun groupe suivent ensuite, à
plat, exactement comme avant.

Un groupe imbriqué ne crée pas de partie supplémentaire : son contenu rejoint
son groupe racine, et la légende garde trace du chemin
(`Sous-groupe › Nom du visuel`). Un groupe dont aucun visuel n'est documenté est
ignoré, sauf `keep_empty: true`.

Réglages dans `data.visuals.groups` : `enabled`, `keep_empty`, `sort_by`,
`member_sort_by` ; numérotation de la légende sous `options.groups.numbering` de
la section `visuels` du plan.

## Configuration — `config_doc_pbi.yaml`

| Bloc | Rôle |
| --- | --- |
| `document` | Template, dossier et nom de sortie, page de garde, en-tête / pied de page, propriétés du fichier |
| `styles` | Correspondance avec les styles du template (`Heading 1`, `Ref Valeur`, `Code DAX`…) |
| `rendering` | Mise en forme commune : sauts de page, emplacements d'images, zones à compléter, liens internes, table des matières |
| `data` | Filtres et tris appliqués aux pages, visuels, groupes de visuels, tables et mesures |
| `merge` | Regénération au-dessus d'une documentation existante |
| `inputs` | Questions posées à l'utilisateur au lancement |
| `sections` | Le plan du document |

### Sections et blocs

Une `section` = un titre + des `blocks` + des `sections` filles. Types de blocs :

| Type | Effet |
| --- | --- |
| `paragraph` | Texte fixe ; `editable: true` propose sa modification au lancement |
| `image` | Emplacement réservé pour une capture, avec sa description |
| `user_fill` | Zone laissée vide (`[À compléter]`) à rédiger après génération |
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

### Le contrat

> **Le script est propriétaire de ses données, vous êtes propriétaire du
> reste.**

À chaque génération le script réécrit ce qu'il produit — formule DAX, tableau
des champs d'un visuel, sources, mesures appelantes — pour qu'il soit toujours
juste. Tout le reste vous appartient et est recopié tel quel :

| Ce que vous faites dans Word | À la regénération |
| --- | --- |
| Reformuler un titre (« Ventes » → « Analyse des ventes — Europe ») | Conservé |
| Ajouter une note, un paragraphe, une liste n'importe où dans un élément | Conservés, à leur place |
| Écrire une description sous un tableau du script, ou entre ses valeurs | Conservée, remise au même endroit |
| Coller une capture d'écran à la place d'un emplacement `[IMAGE]` | Conservée, image comprise |
| Rédiger une zone `[À compléter]`, sur autant de paragraphes que voulu | Conservée |
| Changer une mise en forme, un style, ajouter un tableau | Conservés |

Aucune contrainte sur la *manière* de remplir : vous pouvez supprimer le
paragraphe repère et en créer d'autres, le contenu est repris quand même. Et
aucune contrainte sur l'*endroit* : même écrit au milieu d'un contenu produit
par le script — sous le tableau d'un groupe, sous une formule DAX — votre
texte est retrouvé et reposé entre les mêmes données à la regénération.

### Ce qui est signalé

| Situation | Effet |
| --- | --- |
| La technique d'un élément a changé (formule DAX, champs du visuel) | Vos textes de cet élément sont **surlignés en jaune** : ils portent peut-être sur une version périmée |
| Élément apparu depuis la version précédente | Sa zone à rédiger est **surlignée en vert** |
| Élément retiré du rapport | Ce que vous y aviez écrit part en annexe (voir ci-dessous) |
| Bilan | Affiché **en console** en fin de génération |

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

C'est ce filet qui rend les cas suivants récupérables plutôt que définitifs :

| Ce que vous faites | Où le retrouver |
| --- | --- |
| Écrire dans une cellule d'un tableau du script | En annexe — le tableau, lui, est réécrit |
| Corriger à la main une valeur produite par le script | En annexe |
| Écrire avant la première partie documentée (page de garde, sommaire) | En annexe |
| Renommer une mesure dans Power BI | En annexe, sous l'ancien nom |
| Écarter un visuel via la question posée au lancement | En annexe |

Le surlignage est retiré à la génération suivante : il signale ce qui a changé
*depuis le document que vous aviez en main*, pas un état à cocher.

### Comment le repérage fonctionne

À la génération, le script pose dans le document des **marqueurs invisibles**
(texte masqué Word, `w:vanish`) :

| Marqueur | Rôle |
| --- | --- |
| `pbi::elem\|<id>\|<empreinte>` | Ancre un élément documenté et fige son état technique |
| `pbi::gen\|<bloc>` … `pbi::endgen\|<empreintes>` | Encadrent un contenu produit par le script. Le marqueur de fin retient l'empreinte de chaque paragraphe et tableau écrits |
| `pbi::seed\|<bloc>` … `pbi::endseed\|<empreintes>` | Encadrent une **amorce** : un contenu écrit à la première génération, puis laissé à vous. Même forme, politique inverse — c'est la version du document qui l'emporte |

Un élément va de son ancre à la suivante. À l'intérieur, ce qui n'est pas
encadré par `gen` est à vous — c'est là toute la souplesse : le script n'a
aucune attente sur la forme de ce contenu.

Et *à l'intérieur* d'un `gen` ? Les empreintes du marqueur de fin disent, ligne
par ligne, ce que le script avait écrit là. À la relecture, ce qui s'y trouve
en plus n'est donc pas de lui : c'est rendu et reposé au même rang, entre les
données remises à jour. Une donnée du script retouchée à la main est en
revanche réécrite — elle reste la sienne.

L'identifiant est le `bookmark:` déclaré dans le plan (`measure:<nom>`,
`visual:<page>:<visuel>`, `page:<page>`, `table:<nom>`), sinon `section:<id>` :
des identifiants stables issus de Power BI ou du plan. Une section qui n'a ni
l'un ni l'autre est repérée par son titre sous la partie qui la contient
(`<parent>><titre>`). L'empreinte est un
condensé du `fingerprint:` déclaré à côté :

```yaml
bookmark: "measure:{{ measure.name }}"
fingerprint: "{{ measure.expression }}"     # change → vos textes à revérifier
```

**Ne supprimez pas ces marqueurs.** Ils sont invisibles à l'écran et à
l'impression ; on les voit en activant « Afficher tout » (¶). Un document sans
marqueurs est simplement régénéré intégralement, sans erreur.

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

Une amorce à laquelle personne n'a touché suit le plan : améliorer une
formulation dans le YAML atteint donc aussi les documents déjà générés. Dès que
vous y écrivez, c'est votre version qui l'emporte.

> **Donnez un `id:` à vos blocs.** C'est lui qui identifie le bloc d'une
> génération à l'autre. Un bloc sans `id:` n'est pas repérable : le plan ne
> pourra ni le réécrire, ni le faire apparaître dans un document existant.

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

Le surlignage retiré d'une génération à l'autre est celui que le script a posé,
reconnu à sa couleur. Celui que vous appliquez vous-même à votre texte reste en
place.

### Une rubrique ajoutée au plan

Ajouter un bloc ou une sous-partie au YAML ne concerne pas que les documents à
venir : la rubrique apparaît aussi dans les éléments **déjà rédigés**, à sa
place dans le plan.

La fusion superpose pour cela deux ordres. Les blocs que le plan et le document
connaissent tous les deux gardent l'ordre du **document** — si vous avez
déplacé la formule DAX sous le tableau, elle y reste. Ceux que seul le **plan**
connaît sont insérés entre leurs voisins connus.

### Limites connues

- L'ordre des **éléments** suit le plan : si vous déplacez un élément entier
  ailleurs dans le document, il revient à sa place. Vos remaniements *à
  l'intérieur* d'un élément sont respectés.
- Une mesure **renommée** dans Power BI est vue comme une suppression suivie
  d'un ajout : vos textes ne sont pas reportés sur le nouveau nom, mais ils
  vous attendent en annexe.
- Ce qui précède la première ancre (page de garde, sommaire) vient du template
  et est régénéré ; ce que vous y aviez ajouté part en annexe.
- Un document produit **avant** cette version ne porte pas encore les
  empreintes du marqueur de fin : ce qui y a été écrit à l'intérieur d'un
  contenu du script n'est retrouvé que sous un tableau. Dès la première
  regénération, l'endroit n'a plus d'importance.

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
powerbi-doc-1.0.0-windows.zip
└── powerbi-doc-1.0.0-windows/
    ├── powerbi-doc.exe          l'application, autonome
    ├── config_doc_pbi.yaml      le plan du document, modifiable
    ├── template-doc-pbib.docx   la charte Word, modifiable
    └── LISEZMOI.txt             mode d'emploi
```

Il n'y a plus qu'à transmettre le `.zip`. L'utilisateur le décompresse et
double-clique sur l'exe — ou y glisse-dépose son fichier `.pbip`.

> **À construire sous Windows.** PyInstaller ne sait pas produire un `.exe`
> depuis Linux ou macOS ; il construit pour le système sur lequel il tourne.
> Le nom de l'archive rappelle la plateforme utilisée.

### Configuration et template restent modifiables

C'est le principe du projet : le plan est dans le YAML, pas dans le code. Les
deux fichiers sont donc livrés **en clair à côté de l'exe**, pas seulement
enfermés dedans. L'utilisateur les édite et relance — sans rien reconstruire.

L'exécutable en embarque tout de même une copie, utilisée si les fichiers
livrés ont été supprimés ou déplacés. L'ordre de recherche est dans
`src/paths.py` :

1. le chemin donné (absolu, ou relatif au dossier courant) ;
2. à côté de l'exécutable — le cas normal ;
3. à l'intérieur de l'exécutable — copie de secours.

### Comportement de l'exécutable chez l'utilisateur

**La fenêtre reste ouverte à la fin.** Lancé par double-clic ou par
glisser-déposer, l'exécutable obtient une console qui se refermerait aussitôt
le travail terminé — emportant le compte rendu et les éventuelles erreurs. Il
attend donc une touche avant de rendre la main, y compris lorsqu'il s'arrête
sur une erreur. La condition est simple : l'attente a lieu dès lors que le
programme tourne depuis l'exécutable, jamais en développement. `--no-pause` la
désactive pour une exécution automatisée.

**Le dossier courant n'est pas fiable.** Un glisser-déposer donne à
l'exécutable un dossier courant sans rapport avec l'endroit où il est
installé. La configuration et le template sont donc cherchés dans cet ordre
(`src/paths.py`) :

1. le chemin tel quel — utile en développement ;
2. à côté du fichier qui le désigne : un template nommé dans une
   configuration est cherché à côté de cette configuration ;
3. à côté de l'exécutable — le cas normal en distribution ;
4. à l'intérieur de l'exécutable — copie de secours.

Si le template reste introuvable, le message d'erreur énumère les emplacements
consultés.

### Étapes séparées

| Commande | Effet |
| --- | --- |
| `task build` | Construit seulement `dist/powerbi-doc.exe` (PyInstaller) |
| `task package` | `lint` + `test` + `build`, puis assemble et zippe |
| `task clean` | Supprime aussi `build/` et `dist/` |

La recette de construction est dans `powerbi-doc.spec` : c'est là qu'on ajoute
un fichier à embarquer, une icône (`icon=`) ou un module manquant
(`hiddenimports`).

## Structure du projet

Chaque module a une responsabilité unique ; les points d'entrée publics d'un
paquet sont exposés par son `__init__.py`.

```
main.py                       lance le script

src/
  console.py                  tout l'affichage console passe par ici
  pipeline.py                 enchaînement .pbip → données → .docx

  cli/
      arguments.py            options de la ligne de commande
      prompts.py              questions déclarées dans `inputs:`

  config/
      defaults.py             valeurs par défaut de la configuration
      doc_config.py           chargement du YAML (DocConfig)
      expressions.py          variables {{ }}, listes `over:`, conditions `when`

  paths.py                    localisation des fichiers livrés (exe compris)

  models/
      data_models.py          structures manipulées par le plan

  merge/                      regénération au-dessus d'une doc existante
      markers.py              marqueurs invisibles posés dans le document
      blocks.py               découpage du corps en blocs ancrés
      previous.py             relecture du document précédent
      salvage.py              textes retrouvés dans un contenu du script
      smart.py                fusion : données du script, reste de l'utilisateur
      orphans.py              annexe des contenus qui n'ont plus de place
      transplant.py           recopie d'un contenu et de ses images
      changes.py              bilan des ajouts / modifications / retraits

  parsers/
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

  generators/
      context.py              assemble le contexte exposé au plan
      filters.py              filtres, tris et groupes de `data:`
      references.py           tableaux numérotés, « utilisée dans »
      measure_links.py        repérage des mentions de mesures dans un texte
      word/                   écriture du .docx
          generator.py          document précédent, écriture, archivage
          merging.py            marqueurs, reprise des textes, surlignage
          document.py           parcours du plan et écriture du contenu
          styles.py             clés de style → styles du template
          links.py              signets et liens internes
          tables.py             réglages OOXML des tableaux
          fields.py             table des matières, en-têtes, pieds de page
          word_app.py           recalcul des champs par Word (optionnel)

tests/                        tests unitaires
tools/package.py              assemblage du dossier distribué
powerbi-doc.spec              recette de construction de l'exécutable
config_doc_pbi.yaml           plan du document
template-doc-pbib.docx        template Word
```

### Par où commencer

| Pour... | Ouvrir |
| --- | --- |
| changer le plan du document | `config_doc_pbi.yaml` (pas de code) |
| ajouter un type de bloc | `generators/word/document.py` → `_block_writers` |
| exposer une donnée au plan | `models/data_models.py` puis `generators/context.py` |
| ajouter un filtre `data:` | `generators/filters.py` et `config/defaults.py` |
| ajouter un type de question | `cli/prompts.py` → `ask_inputs` |
| lire une nouvelle propriété TMDL | `parsers/tmdl/measures.py` → `_PROPERTIES` |
| changer ce qui déclenche une alerte de mise à jour | le `fingerprint:` de la section, dans le YAML |

## Notes

- Les styles déclarés dans `styles:` doivent exister dans le template : sinon
  le script bascule sur `fallback` et le signale une fois dans la console.
- Si la table des matières n'apparaît pas à jour (visionneuse autre que Word,
  mise à jour refusée), la sélectionner dans Word puis « Mettre à jour les
  champs » (F9).

## Commandes utiles

```bash
task run        # lancer la génération
task test       # tests unitaires
task check      # format + lint (ruff) + tests
task build      # construire l'exécutable
task package    # construire le zip à distribuer
task clean      # nettoyer les caches et les artefacts de construction
```
