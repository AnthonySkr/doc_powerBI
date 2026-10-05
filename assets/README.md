# Captures d'écran

Dossier de destination des captures prises par `gui_automator`.

À la génération, les images ne sont **pas** écrites ici : elles vivent à côté
du rapport documenté, dans un dossier du même nom créé auprès du `.pbip`.

```
mon_rapport/
├── Rapport.pbip
├── Rapport.Report/
├── Rapport.SemanticModel/
└── assets/                  ← les captures de ce rapport
    └── page_ventes/
        ├── v_evolution.png
        └── g_indicateurs.png
```

C'est voulu : les captures appartiennent au rapport, pas à l'outil. Un rapport
déplacé emporte ses images, et deux rapports documentés depuis le même poste ne
mélangent pas les leurs.

Le nom du dossier se règle dans `config.yaml` :

```yaml
capture:
  directory: assets
```

## Les prendre

```bash
python main.py "C:\chemin\Rapport.pbip" --captures
```

Power BI Desktop doit être **déjà ouvert** sur le rapport, en mode Rapport.
Sans cette option, le document réserve la place de chaque image avec un texte
descriptif — il reste complet, et les captures peuvent être ajoutées après coup
en déposant les fichiers aux emplacements ci-dessus.

| Option | Effet |
| --- | --- |
| `--capture-plan` | Affiche ce qui serait capturé, sans rien ouvrir |
| `--fake-captures` | Écrit des rectangles unis, sans ouvrir Power BI |
| `--calibrate` | Photographie la fenêtre et le canevas, pour régler le cadrage |
| `--page`, `--shot` | Ne capturer que ce dont le nom contient ce fragment |
