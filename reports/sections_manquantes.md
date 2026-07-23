# Sections manquantes du rapport MTI820

> Rédigé à partir de la proposition de projet (9 juin 2026) et du code réel du dépôt.
> À insérer **avant** la Section 1 actuelle (Architecture technique) pour les parties
> 1 à 3, la partie 4 venant compléter la Section 1.

---

## 1. Introduction

Le secteur des technologies de l'information constitue l'un des marchés de l'emploi
les plus dynamiques et les plus compétitifs au Canada. À Montréal, la concentration
d'entreprises technologiques — des studios de jeu vidéo aux sociétés de services
conseils en passant par les sièges sociaux d'entreprises manufacturières —
alimente une demande soutenue en professionnels qualifiés. Pourtant, cette
abondance d'information ne se traduit pas en clarté pour les acteurs du marché :
les offres sont dispersées sur des dizaines de plateformes, formulées selon des
conventions hétérogènes, et rarement comparables d'une région ou d'une période à
l'autre.

Ce projet, réalisé dans le cadre du cours MTI820 (Entrepôts de données et
intelligence d'affaires), propose de traiter cette dispersion par les méthodes
propres à l'informatique décisionnelle : la collecte automatisée de données
ouvertes, leur normalisation dans un pipeline ETL, leur modélisation dimensionnelle
au sein d'un entrepôt de données, et enfin leur restitution analytique.

Le présent rapport documente la conception et la réalisation de ce prototype. Il
présente successivement la problématique et les objectifs poursuivis, l'analyse des
besoins qui en découle, les sources de données retenues et leurs limites, le modèle
dimensionnel adopté, l'architecture technique de la solution, puis les résultats
analytiques obtenus. Une attention particulière est portée aux limites de qualité
des données rencontrées : loin d'être un accident de parcours, elles constituent
l'un des enseignements les plus instructifs du projet.

---

## 2. Problématique et objectifs

### 2.1 Mise en contexte

Les entreprises technologiques montréalaises font face à une demande croissante de
professionnels qualifiés, tandis que les candidats peinent à identifier les
compétences les plus valorisées, les niveaux de rémunération réalistes et les
segments du marché offrant les meilleures perspectives. Cette asymétrie
d'information nuit aux deux parties : les recruteurs calibrent mal leurs offres,
les candidats orientent mal leurs efforts de formation, et les établissements
d'enseignement ajustent leurs programmes sur des signaux tardifs.

### 2.2 Énoncé de la problématique

Malgré l'abondance des offres d'emploi disponibles en ligne, il n'existe pas de
solution centralisée permettant d'analyser l'évolution du marché de l'emploi en TI
de façon structurée et visuelle. Les informations sont dispersées sur de nombreuses
plateformes, chacune avec son propre format, rendant difficile toute analyse
comparative dans le temps ou entre régions.

La question centrale du projet est donc la suivante :

> **Comment exploiter les données ouvertes sur les offres d'emploi pour produire une
> vision analytique claire et actuelle de l'évolution du marché de l'emploi en TI à
> Montréal ?**

### 2.3 Objectif général

Concevoir et développer un prototype de solution d'intelligence d'affaires
permettant d'analyser et de visualiser l'évolution du marché de l'emploi en TI,
depuis la collecte des données brutes jusqu'à leur restitution décisionnelle.

### 2.4 Objectifs spécifiques

1. **Collecter** des données sur les offres d'emploi en TI via l'API Adzuna, de
   manière automatisée, reproductible et résiliente aux défaillances du service
   distant.
2. **Concevoir** un modèle dimensionnel adapté à l'analyse décisionnelle, articulé
   autour d'une table de faits (les offres d'emploi) et de dimensions d'analyse
   (temps, entreprise, localisation, contrat, compétences).
3. **Développer** un pipeline ETL couvrant l'ingestion, la transformation et le
   chargement des données dans l'entrepôt.
4. **Produire** des restitutions analytiques permettant de répondre aux questions
   d'affaires : compétences les plus demandées, niveaux de rémunération, entreprises
   les plus actives, modalités de contrat, évolution temporelle.
5. **Formuler** des constats sur les tendances du marché, en explicitant le degré de
   confiance associé à chacun compte tenu de la qualité des données sources.

### 2.5 Questions d'affaires retenues

Le prototype a été conçu pour répondre à cinq questions décisionnelles précises,
qui ont guidé la modélisation dimensionnelle :

| # | Question d'affaires | Dimensions mobilisées |
|---|---------------------|-----------------------|
| Q1 | Quelles sont les compétences les plus recherchées par les employeurs ? | Compétences |
| Q2 | Quel est le salaire moyen proposé selon la compétence exigée ? | Compétences × mesures salariales |
| Q3 | Quelles entreprises publient le plus d'offres d'emploi ? | Entreprise |
| Q4 | Quelle est la proportion d'emplois contractuels par rapport aux permanents ? | Contrat |
| Q5 | Observe-t-on une tendance ou une saisonnalité dans la publication des offres ? | Temps |

Cette formalisation préalable est ce qui justifie le grain retenu pour la table de
faits — une ligne par offre d'emploi — puisque chacune de ces questions s'obtient
par agrégation à partir de ce niveau de détail.

---

## 3. Analyse des besoins

### 3.1 Parties prenantes

Trois profils d'utilisateurs ont été considérés lors de la conception :

- **Les chercheurs d'emploi et étudiants en TI**, qui cherchent à orienter leurs
  efforts d'apprentissage vers les compétences effectivement demandées.
- **Les recruteurs et entreprises**, qui souhaitent situer leurs offres par rapport
  au marché (veille concurrentielle sur les salaires et les technologies).
- **Les établissements d'enseignement**, qui ajustent leurs programmes en fonction
  des technologies émergentes.

### 3.2 Besoins fonctionnels

| # | Besoin | Traduction technique |
|---|--------|----------------------|
| BF1 | Collecter automatiquement les offres d'emploi en TI de la région de Montréal | Script d'extraction interrogeant l'API Adzuna avec filtrage par catégorie et rayon géographique |
| BF2 | Éviter les doublons issus de la multi-diffusion des offres | Dédoublonnage à la transformation, puis contrainte d'unicité sur l'identifiant naturel Adzuna au chargement |
| BF3 | Détecter les compétences technologiques mentionnées dans les offres | Repérage par expressions régulières avec délimitation de mots sur les descriptions |
| BF4 | Analyser les rémunérations lorsqu'elles sont disponibles | Mesures `salary_min`, `salary_max`, `salary_avg` et indicateur `has_salary` dans la table de faits |
| BF5 | Analyser l'évolution des publications dans le temps | Dimension temporelle dédiée, à granularité journalière |
| BF6 | Croiser librement les axes d'analyse | Schéma en étoile interrogeable par jointures simples et exploitable dans un outil de restitution |
| BF7 | Conserver l'historique des extractions successives | Archivage horodaté de chaque extraction brute |

### 3.3 Besoins non fonctionnels

| # | Besoin | Traduction technique |
|---|--------|----------------------|
| BNF1 | **Reproductibilité** de l'environnement entre les membres de l'équipe | Conteneurisation de la base via Docker Compose ; dépendances Python figées dans `requirements.txt` |
| BNF2 | **Résilience** aux défaillances transitoires du service distant | Réessais avec délai exponentiel sur les codes 429 et 5xx lors de l'extraction |
| BNF3 | **Idempotence** du chargement : relancer le pipeline ne doit pas dupliquer les données | Insertion conditionnelle (`ON CONFLICT DO NOTHING`) sur la clé naturelle |
| BNF4 | **Sécurité** des accès : aucun secret dans le dépôt de code | Identifiants d'API et de base lus depuis un fichier `.env` exclu du versionnement |
| BNF5 | **Défaillance explicite** : une erreur de configuration doit être immédiatement compréhensible | Vérification des variables d'environnement requises avant toute connexion |
| BNF6 | **Performance** du chargement sur plusieurs milliers de lignes | Insertions par lots et mise en cache des recherches de dimensions |
| BNF7 | **Évolutivité** de la liste des compétences suivies | Table de dimension `dim_skills` et table de liaison, plutôt que des colonnes booléennes figées |
| BNF8 | **Traçabilité** des transformations appliquées | Séparation du pipeline en trois scripts distincts et versionnés (extraction, transformation, chargement) |

### 3.4 Contraintes du projet

- **Contrainte de source** : l'API Adzuna, dans son offre gratuite, retourne des
  descriptions tronquées et une couverture salariale très partielle. Ces limites
  sont subies et non corrigeables en amont ; elles devaient donc être documentées
  et intégrées à l'interprétation des résultats.
- **Contrainte temporelle** : la fenêtre d'observation disponible au moment de la
  rédaction (environ trois mois) est trop courte pour établir une saisonnalité.
- **Contrainte d'environnement** : la solution devait pouvoir être déployée
  localement par chaque membre de l'équipe sans installation manuelle complexe.

---

## 4. Sources de données, pipeline ETL et qualité

### 4.1 La source retenue : l'API Adzuna

Adzuna est un agrégateur d'offres d'emploi exposant une API publique documentée.
L'interrogation porte sur l'endpoint de recherche canadien, avec trois filtres
structurants : la catégorie `it-jobs`, une localisation centrée sur Montréal, et un
rayon de 100 km. Les résultats sont triés par date de publication et paginés par
tranches de 100 enregistrements.

Chaque offre retournée comporte notamment un identifiant unique, un titre, une
description, le nom de l'entreprise, une localisation, une date de publication, des
modalités de contrat et, de façon inconstante, une fourchette salariale.

### 4.2 Extraction

Le script d'extraction parcourt les pages successives de résultats et concatène les
réponses en un fichier CSV brut. Trois mécanismes assurent sa robustesse :

- **Validation préalable de la configuration** : l'absence des identifiants d'API
  interrompt le script avec un message explicite, plutôt que de laisser survenir une
  erreur d'authentification opaque après plusieurs appels réseau.
- **Réessais avec délai exponentiel** : les codes de statut transitoires (429 pour
  la limitation de débit, 5xx pour les défaillances serveur) déclenchent de
  nouvelles tentatives, dans la limite de trois essais par page, avec un délai
  doublant entre chaque essai (2 s puis 4 s). Les erreurs
  définitives (401, 403) échouent immédiatement, sans réessai inutile. Sans ce
  mécanisme, un incident ponctuel sur une seule page interrompait l'extraction
  complète et faisait perdre les pages déjà collectées.
- **Historisation** : chaque exécution dépose une copie horodatée du fichier brut
  dans un répertoire d'archives, en plus du fichier courant. C'est cette
  accumulation qui rendra possible, à terme, l'analyse de tendance visée par la
  question d'affaires Q5.

### 4.3 Transformation

L'étape de transformation applique successivement :

1. **Validation du schéma** — les colonnes attendues sont vérifiées avant toute
   sélection, de sorte qu'une évolution du format de l'API produise un message
   explicite plutôt qu'une erreur d'indexation difficile à diagnostiquer.
2. **Sélection et renommage** des champs utiles, y compris l'identifiant Adzuna
   conservé comme clé naturelle.
3. **Nettoyage textuel** : suppression des retours à la ligne, normalisation des
   espaces, passage en minuscules des titres et descriptions.
4. **Dédoublonnage** sur le triplet (titre, entreprise, description), afin
   d'absorber les republications et les chevauchements entre pages consécutives.
5. **Typage et enrichissement des mesures** : calcul du salaire moyen et ajout d'un
   indicateur booléen `has_salary` distinguant l'absence réelle de rémunération
   déclarée d'une valeur manquante accidentelle.
6. **Détection des compétences** : pour chacune des 11 technologies suivies, une
   expression régulière avec délimiteurs de mots (`\bjava\b`) teste la présence du
   terme dans la description.

> **Note de conception.** Le recours aux délimiteurs de mots n'est pas cosmétique :
> une simple recherche de sous-chaîne faisait correspondre « java » à l'intérieur de
> « javascript », gonflant artificiellement le décompte de Java par l'ensemble des
> offres JavaScript. Le même défaut affectait « sql » au sein de « nosql ».

### 4.4 Chargement

Le chargement alimente le schéma en étoile en quatre temps : pré-alimentation de la
dimension des compétences, résolution des dimensions pour chaque offre, insertion en
lot des faits, puis insertion en lot des associations offre–compétence.

Deux optimisations structurent cette étape :

- **Mise en cache des dimensions** : les clés d'entreprise, de localisation, de
  contrat et de date déjà résolues sont conservées en mémoire, ce qui évite de
  refaire un aller-retour vers la base pour chaque occurrence répétée. Sur un corpus
  où 700 entreprises se partagent 2 671 offres, l'économie est substantielle.
- **Insertions par lots** : les faits et les associations sont insérés par
  `execute_values` plutôt que ligne à ligne, réduisant d'autant le nombre d'allers-
  retours réseau.

L'idempotence est assurée par la contrainte d'unicité portant sur l'identifiant
Adzuna : une insertion conditionnelle ignore silencieusement les offres déjà
présentes. Relancer le chargement sur un corpus inchangé insère donc zéro ligne, ce
qui a été vérifié expérimentalement.

### 4.5 Qualité et limitations des données

L'évaluation de la qualité des données constitue un résultat du projet à part
entière. Trois limites majeures ont été mesurées sur le corpus de 2 671 offres.

**Troncature des descriptions.** L'API retourne des descriptions plafonnées à
environ 500 caractères (longueur moyenne mesurée : 506 caractères ; maximum : 561),
interrompues en fin de chaîne par des points de suspension.
La détection de compétences ne porte donc que sur l'amorce de chaque annonce, là où
figurent généralement la présentation de l'entreprise et le contexte du poste
plutôt que la liste des technologies requises. Conséquence directe : seules 236
offres (8,8 %) laissent apparaître au moins une des 11 compétences suivies. Les
volumes par technologie doivent être lus comme des **planchers**, non comme des
décomptes exhaustifs.

**Couverture salariale marginale.** Seules 206 offres (7,7 %) déclarent une
fourchette de rémunération. Ventilé par compétence, ce sous-ensemble tombe entre 0
et 6 observations, ce qui interdit toute inférence robuste.

**Hétérogénéité des unités de rémunération.** Le champ salarial mélange sans
distinction des taux horaires (de 20 à 120 $), des valeurs manifestement erronées
(1 à 3 $) et des salaires annuels (supérieurs à 100 000 $). Aucune normalisation
financière n'étant appliquée en amont, toute moyenne calculée sur ce champ agrège
des grandeurs non comparables.

**Concentration des annonceurs, sur une seule journée.** Une seule agence de
recrutement est à l'origine de 313 offres, soit 11,7 % du corpus. L'examen de la
dimension temporelle révèle que **la totalité de ces 313 offres porte la même date
de publication** (12 mai 2026) : il s'agit d'un dépôt massif unique, et non d'une
activité de recrutement étalée dans le temps. Ce déséquilibre affecte à la fois le
classement des compétences et le profil temporel du corpus, et illustre la nécessité,
en veille de marché, de contrôler la distribution des sources avant d'interpréter les
volumes.

**Biais de récence sur le volume publié.** Le nombre d'offres par semaine croît
fortement à mesure que l'on approche de la date d'extraction (de 35 offres pour la
semaine du 27 avril à 467 pour celle du 13 juillet). Cette progression ne mesure pas
une croissance de l'embauche : l'API ne retourne que les annonces encore actives, si
bien que les semaines les plus anciennes sont amputées des offres déjà expirées. La
pente observée reflète donc le mécanisme de collecte, non le marché. **La question
d'affaires Q5, portant sur la saisonnalité, ne peut par conséquent pas être tranchée
avec le corpus actuel** ; elle nécessitera l'accumulation de plusieurs mois
d'extractions horodatées successives, ce que l'historisation mise en place rend
désormais possible.

Ces constats ne remettent pas en cause la validité de l'architecture : ils
délimitent le domaine de confiance des conclusions et orientent les améliorations
futures détaillées en conclusion. Leur mise au jour constitue d'ailleurs une
démonstration de l'utilité du modèle dimensionnel : c'est le croisement de la table
de faits avec les dimensions « entreprise » et « temps » qui a permis d'isoler le
dépôt massif du 12 mai, invisible dans le fichier plat d'origine.
