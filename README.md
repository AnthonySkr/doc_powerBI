# Documentation automatique Power BI

Génère la documentation Word d'un rapport Power BI (`.pbip`) à partir du
template `template-doc-pbib-v2.docx` et d'un plan décrit en YAML.

Le script ne contient aucune structure de document : **tout le plan est dans
`config_doc_pbi.yaml`**. Pour documenter un rapport différemment, on modifie le
YAML, pas le code.

## Mise en place

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows
pip install taskipy
task install
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
| `-n`, `--dry-run` | Afficher les nouveautés et les changements sans toucher au document |
| `-f`, `--force` | Régénérer le document depuis le template (le contenu rédigé est perdu) |

Le document est écrit dans `doc/documentation_<rapport>.docx`, à côté du `.pbip`.

## Ce que fait le script

0. Si le document de sortie existe déjà, bascule en mise à jour : il est
   complété, jamais réécrit (voir plus bas).
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

## Mise à jour d'un document déjà rédigé

Une documentation livrée est complétée à la main : descriptions, sources,
parties laissées vides. **Si le fichier de sortie existe déjà, le script ne le
réécrit pas** : il compare le document à ce qu'il produirait aujourd'hui et n'y
reporte que les différences.

```
Nouveautés (1) :
  - mesure « Panier moyen » — nouveau
Changements (2) :
  - visuel « CA du mois » — modifié (les champs du visuel)
  - mesure « Chiffre d'affaires » — modifié (le code DAX, les sources utilisées)
Disparus (1) :
  - « Nb jours » — absent du rapport
```

Ce qui est fait, et ce qui ne l'est pas :

| Situation | Traitement |
| --- | --- |
| Item absent du document (mesure, visuel, page, table) | Inséré à sa place dans le plan |
| Bloc `track:` dont le contenu a changé (code DAX, champs d'un visuel…) | Remplacé par la version à jour |
| Bloc `review:` (description) ou zone « à compléter » rédigée | **Jamais réécrit** — surligné en rouge, avec une note à supprimer une fois relu |
| Item disparu du rapport | Signalé par une note, **jamais supprimé** |
| Reste du document | Intact |

Une copie de sauvegarde (`documentation_x.bak.docx`) est écrite avant toute
modification, y compris avec `--force`. Relancer le script sans changement de
modèle ne touche pas au fichier.

### Comment le script s'y retrouve

Le générateur pose un signet Word sur le titre de chaque item (`bookmark:` du
plan) et autour de chaque bloc déclaré `track:` ou `review:`. Ces signets
survivent aux modifications faites dans Word : c'est par eux que la mise à jour
retrouve, dans le document livré, ce qu'elle doit comparer ou remplacer.

```yaml
- type: property
  id: mesure_code
  value: "{{ measure.expression }}"
  track: true          # piloté par le script : remplacé si le modèle change
- type: property
  id: mesure_description
  value: "{{ measure.description }}"
  review: true         # rédigé par l'utilisateur : jamais réécrit
```

### Réglages — `rendering.update`

| Clé | Effet |
| --- | --- |
| `enabled` | `false` : le script refuse d'écrire sur un document existant |
| `backup` / `backup_suffix` | Copie de sauvegarde avant écriture |
| `highlight` | Couleur de surlignage des textes à relire (`red` par défaut) |
| `note_style` | Style des notes de suivi |
| `notes.changed` / `notes.removed` | Texte des notes (`{date}`, `{changes}`) |
| `block_labels` / `labels` | Libellés lisibles des blocs et des natures d'items |

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

## Structure du projet

```
main.py                     orchestration (lecture .pbip, questions, génération)
src/
  doc_config.py               chargement du YAML, variables {{ }}, conditions when
  generators/
      data_context.py         filtres/tris et données exposées au plan
      word_generator.py       écriture du .docx en parcourant le plan
      measure_links.py        repérage des mentions de mesures dans les textes
      docx_index.py           relecture d'un document par ses signets
      doc_updater.py          comparaison et report des seuls changements
      update_runner.py        enchaînement du mode « mise à jour »
  parsers/
      tmdl_parser.py          mesures DAX, tables, sources et étapes Power Query
      report_parser.py        pages, visuels, champs et filtres du rapport
      dependency_analyzer.py  dépendances transitives entre mesures
  models/data_models.py       structures de données
tests/                      tests unitaires (liens internes, noms de signets)
config_doc_pbi.yaml         plan du document
template-doc-pbib.docx      template Word
```

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
task check      # format + lint (ruff)
task clean      # nettoyer les caches
```
