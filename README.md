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

Le document est écrit dans `doc/documentation_<rapport>.docx`, à côté du `.pbip`.

## Ce que fait le script

1. Lit le modèle sémantique (`.SemanticModel`) : mesures DAX, tables, sources
   et étapes de transformation Power Query.
2. Analyse les dépendances entre mesures (mesures et colonnes utilisées).
3. Lit le rapport (`.Report`) : pages, visuels, champs et filtres.
4. Pose les questions déclarées dans `inputs:`.
5. Écrit le document en suivant le plan `sections:` du YAML, à la suite du
   contenu déjà présent dans le template.

Les captures d'écran ne sont pas insérées : le script réserve l'emplacement
avec un texte descriptif (`[IMAGE] ...`) qu'il suffit de remplacer par la
capture correspondante une fois le document généré.

## Configuration — `config_doc_pbi.yaml`

| Bloc | Rôle |
| --- | --- |
| `document` | Template, dossier et nom de sortie, page de garde, propriétés du fichier |
| `styles` | Correspondance avec les styles du template (`Heading 1`, `Sous-titre 3`, `Code DAX`…) |
| `rendering` | Mise en forme commune : sauts de page, emplacements d'images, zones à compléter, liens internes |
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

Un titre peut déclarer un signet, une cellule de tableau peut pointer dessus :

```yaml
bookmark: "measure:{{ measure.name }}"          # sur le titre de la mesure
hyperlink:
  when: "ref.kind == mesure"
  target: "measure:{{ ref.name }}"              # depuis le tableau du visuel
  text: "{{ ref.name }}"
```

## Structure du projet

```
main.py                     orchestration (lecture .pbip, questions, génération)
src/
  doc_config.py               chargement du YAML, variables {{ }}, conditions when
  generators/
      data_context.py         filtres/tris et données exposées au plan
      word_generator.py       écriture du .docx en parcourant le plan
  parsers/
      tmdl_parser.py          mesures DAX, tables, sources et étapes Power Query
      report_parser.py        pages, visuels, champs et filtres du rapport
      dependency_analyzer.py  dépendances transitives entre mesures
  models/data_models.py       structures de données
config_doc_pbi.yaml         plan du document
template-doc-pbib.docx      template Word
```

## Notes

- Les styles déclarés dans `styles:` doivent exister dans le template : sinon
  le script bascule sur `fallback` et le signale dans la console.

## Commandes utiles

```bash
task run        # lancer la génération
task check      # format + lint (ruff)
task clean      # nettoyer les caches
```
