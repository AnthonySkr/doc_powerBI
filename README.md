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
3. Lit le rapport (`.Report`) : pages, visuels, champs et filtres.
4. Pose les questions déclarées dans `inputs:`.
5. Écrit le document en suivant le plan `sections:` du YAML, à la suite du
   contenu déjà présent dans le template.
6. Remplace les textes de l'en-tête et du pied de page du template, puis marque
   la table des matières comme à recalculer.

Les captures d'écran ne sont pas insérées : le script réserve l'emplacement
avec un texte descriptif (`[IMAGE] ...`) qu'il suffit de remplacer par la
capture correspondante une fois le document généré.

## Configuration — `config_doc_pbi.yaml`

| Bloc | Rôle |
| --- | --- |
| `document` | Template, dossier et nom de sortie, page de garde, en-tête / pied de page, propriétés du fichier |
| `styles` | Correspondance avec les styles du template (`Heading 1`, `Ref Valeur`, `Code DAX`…) |
| `rendering` | Mise en forme commune : sauts de page, emplacements d'images, zones à compléter, liens internes, table des matières |
| `data` | Filtres et tris appliqués aux pages, visuels, tables et mesures |
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
| `table` | Tableau construit à partir des données extraites |
| `loop` | Répétition d'un sous-plan sur une collection (pages, visuels, tables, mesures) |

### Variables et conditions

Les chaînes acceptent des variables `{{ ... }}` :

```yaml
title: "{{ page.display_name }}"
description: "Capture complète de la page « {{ page.display_name }} »"
```

Collections disponibles dans les boucles : `report.pages`, `page.visuals`,
`visual.references`, `model.tables`, `model.tables_with_measures`,
`table.measures`.

Une section ou un bloc peut être conditionné par `when` :

```yaml
when: inputs.pages_secondaires      # vrai si la réponse est vraie
when: "!inputs.pages_secondaires"   # négation
when: "ref.kind == mesure"          # égalité
```

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

  parsers/
      pbip.py                 localisation des dossiers d'un projet .pbip
      dependencies.py         dépendances transitives entre mesures
      tmdl/                   modèle sémantique
          reader.py             lecture des fichiers, découpage en blocs
          measures.py           blocs `measure` → DaxMeasure
          tables.py             table, visibilité, partition
          powerquery.py         script `let ... in` → étapes nommées
      report/                 rapport PBIR
          pages.py              pages et visuels
          fields.py             projections et filtres

  generators/
      context.py              assemble le contexte exposé au plan
      filters.py              filtres et tris de `data:`
      references.py           tableau des références, « utilisée dans »
      measure_links.py        repérage des mentions de mesures dans un texte
      word/                   écriture du .docx
          generator.py          ouverture du template, sauvegarde
          document.py           parcours du plan et écriture du contenu
          styles.py             clés de style → styles du template
          links.py              signets et liens internes
          tables.py             réglages OOXML des tableaux
          fields.py             table des matières, en-têtes, pieds de page
          word_app.py           recalcul des champs par Word (optionnel)

tests/                        tests unitaires (118)
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
| lire une nouvelle propriété TMDL | `parsers/tmdl/measures.py` → `_PROPERTIES` |

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
