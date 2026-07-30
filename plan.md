Okay merci je veux bien qu'on construise ensemble ce fichier de config oui, puis on repassera sur le code actuel du projet.
Pour un peu plus de contexte je veux que cette doc auto soit très modulable sur son contenu qui peut être utilisé pour des rapports Power BI très différents les uns des autres. C'est pourquoi je veux qu'on définisse une structure/config précise et complète mais tout en restant assez large pour intégrer différents types de projets. Lors de l'éxecution du script qui écrira la doc dans un docx je vais vouloir utiliser des input de l'utilisateur pour remplir la doc, que ce soit pour rédiger une partie ou pour guider le script. Pour ton info j'ai un fichier docx dans le projet qui sert de template.

On commence donc avec le plan/config : 
- (h1) Initialisation : Première partie à rédiger, titres de cette partie déjà écrit dans le template, on ne s'en occupe pas dans la doc automatié mais il ne faut pas supprimer le contenu déjà présent

- (h1) Organisation Graphique : nouvelle page pour tout les titres 1, ici on va commencer à avoir des images à insérer, lors du script on réservera simplement l'emplacement de l'image avec un texte descriptif pour ensuite quand le fichier est généré l'utilisateur à juste à suivre la description pour prendre la capture d'écran adaptée et l'insérer
    - On commence avec une déscription générale et une capture de la page principale, sous cette forme :
        Chaque page du rapport est organisée de la même manière. L'en-tête permet de contrôler le comportement du rapport à travers un système de filtre, un sélecteur de navigation et un rappel du contexte.
        [Image]
        Le rapport est composé de pages principales et de pages secondaires. Les pages principales
        font état des indicateurs suivis par sous-processus. Les pages secondaires donnent des
        détails ou listes les enregistrements comptabilisés dans le calcul des indicateurs.
    Voila le texte de base, dans le script il faudra proposer à l'utilisateur de modifier ce texte
    - (h2) Navigation : demander à user si rapport à pages secondaires, si oui alors deux titres 3 :
        - (h3) Pages principales : présentation du sélecteur de navigation avec capture :
            Le sélecteur de navigation permet de naviguer entre chaque page "principale". A partir des pages principales nous pouvons naviguer vers les pages de détails des indicateurs.
            [Image]
        - (h3) Pages secondaires : présentation de la navigation secondaire :
            Pour naviguer vers un affichage secondaire il suffit de cliquer sur les flèches matérialisées à côté d'une information.
            [Image] - Visualisation des étapes de navigation vers les onglets secondaires
            Pour retourner vers un affichage principal, il vous suffit de cliquer sur la flèche symbolisant un retour en arrière, en haut à droite de l'entête de l'affichage.
            [Image] - Visualisation des étapes de navigation pour retourner vers un onglet principal
        Ici pareil il faut proposer à l'utilisateur de modifier le texte de base
    sinon présentation uniquement de pages principales sans titre 3
    - (h2) Filtre : 
        - (h3) Volet de filtre :
            Pour ouvrir le volet de sélection de filtre, un bouton « filtre » se trouve dans l'en-tête de chaque onglet principal. En cliquant dessus le volet de filtre apparaîtra.
            [Image] - Visuel explicatif ouverture volet filtre
            Pour le fermer, cliquez sur la croix en haut à droite du volet.
            [Image] - Visuel explicatif fermeture volet filtre

- (h1) Acquisition des données :
    Laisser vide pour remplissage utilisateur après éxecution du script

- (h1) Visuels : Texte descriptif de la partie pour commencer :
    Cette partie est organisée de la même manière que le livrable. Pour chaque section, une nomenclature est affectée à chaque visuel pour être détaillée par la suite, en faisant référence au numéro assigné. Les visuels sont construits à partir de colonnes du jeu de données, de mesures et de concepts liés au projet. Chaque référence est identifiée et renvoie, par un clic, vers la définition via un lien hypertexte.
    - (h2) Un h2 par page, h2 = nom de la page
        [Image] Capture de la page à insérer
        - (h3) Un h3 par visuel, h3 = nom visuel
            [Image] Capture du visuel à insérer
            Tableau avec les formules, filtres, indicateurs, mesures présents dans ce visuel :
                deux colonnes, première est un numéro pour mettre ce même numéro sur la capture et montrer où est utilisé cet indicateur, deuxième colonne on peut avoir "Formule appliquée : nom de la formule", "Filtre appliquée : formule du filtre", "Axe X : nom indicateur", etc...
                lien sur les formules vers la définition de la mesure plus loin dans le document

- (h1) Table de données
    - (h2) Source : à remplir par l'utilisateur après, ajouter seulement le titre
    - (h2) Tables : 
        - (h3) Un h3 par table : sous titres (style docx = Sous-titre 3)
            - Paramètres : source de la table
            - Synthétisation du traitement : traitement effectué sur la source de donnée (ex : filtre, exclusion des doublons, etc...), toutes les étapes de transformation de cette table

- (h1) Définition des mesures :
    - (h2) un h2 pour chaque table contenant au moins une mesure DAX
        - (h3) Nom de la mesure : sous-titres :
            - Code DAX : code de la mesure
            - Description
            - Source utilisée

Voilà pour le plan, je t'ai mentionné d'avoir des input utilisateur pour remplir cette doc, on va pas le faire pour tous pour l'instant, s'il faut juste quelques mots ok, sinon si c'est un paragraphe on laisse vide et on passe à la suite. Il faudra aussi dans une prochaine version pouvoir éditer la doc, la mettre à jour, sans rien perdre des données déjà présentes, et il faudra voir pour inclure api Chat eiffage pour remplir description des visuels, mesures, etc...
Pour commencer on fait le plan yaml ?
