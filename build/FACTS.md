# Fiche de faits — source unique des 12 CV

Construite en relisant les **103 CV** de `~/Documents/CV-and-Letters/CVs` (texte extrait
avec `pdftotext`, paragraphes dédupliqués : 1 196 distincts). Pour chaque poste et chaque
projet, la version la plus riche trouvée dans l'ensemble des CV sert de référence. Le
nombre entre crochets est le nombre de CV sources où le fait apparaît.

Les « manques » sont les endroits où aucun résultat mesurable n'existe dans les sources :
l'impact y est qualitatif et concret, et c'est à toi de fournir un chiffre si tu en as un.

---

## Expériences

### Veolia Software Solutions — Ingénieur IA — Rabat, Maroc — 02/2026 – 08/2026

| | |
|---|---|
| **Problème** | Détection d'anomalies de consommation d'eau à faire, et un PoC qui ne pouvait pas passer en production. |
| **Contexte** | PFE, 6 mois. |

- Pipeline de données : collecte, traitement, enrichissement des données de consommation d'eau [6]
- Détection d'anomalies : ensemble **Isolation Forest + autoencodeur**, avec une couche de
  confirmation par LLM (**Claude 3.5**) pour réduire les faux positifs [6]
- **Taux de détection ≥ 80 %** [17], **moins de 5 % de faux positifs** [6]
- Cycle MLOps : **MLflow**, promotion de modèles par alias (candidate → staging → production) [2]
- **Evidently AI**, monitoring de dérive, **KS ≤ 0,15** [24]
- Gating : les modèles dégradés sont bloqués automatiquement avant d'atteindre les
  utilisateurs, sans revue manuelle [1]
- Industrialisation du PoC en plateforme backend production-ready : **FastAPI, Docker**,
  versioning Git, CI/CD, prototype → production [7]
- Contrôles métier et mécanismes de protection des données (conformité, fiabilité) [3]
- Résultats et performances présentés à des **interlocuteurs non techniques**, seuils de
  détection ajustés d'après leur retour [3]

**Manques** — aucun chiffre sur l'industrialisation (nombre de services repris sur la
plateforme, temps gagné) ; aucun volume (compteurs, enregistrements traités).

**Absent des sources, donc non écrit** : ACR (Azure Container Registry), DevContainers,
déploiement sur VM Azure, Kubernetes chez Veolia, Terraform. 0 occurrence sur 103 CV.

### OCP Group — Ingénieur IA — El Jadida, Maroc — 07/2025 – 09/2025

| | |
|---|---|
| **Problème** | Plans de maintenance produits à la main depuis l'historique ; première version de l'application répondant en 40 s, inutilisable. |

- Application full-stack d'IA générative pour la maintenance prédictive (**FastAPI, Next.js**),
  intégrée aux outils métiers via API [9]
- Génération contrôlée : **LangChain + Pydantic** → sorties JSON structurées et fiables [3]
- Extraction et préparation de données historiques en **SQL** pour enrichir le contexte de
  génération (approche proche RAG) [7]
- Conception de prompts ; évaluation et comparaison des stratégies de prompting et
  d'inférence avec **LangSmith** [7]
- **Latence : 40 s → ~5 s** [9]
- **Docker** + observabilité de bout en bout **LangSmith** en production [4]
- Nettoyage, structuration et préparation de grands jeux de données industriels ;
  feature engineering sur **séries temporelles multi-capteurs** [2]

**Contradiction à trancher** — un second groupe de sources décrit OCP comme
« Ingénieur Data Science & IA (Stagiaire), **Juil – Sep 2024** » avec Random Forest,
XGBoost et LSTM (GridSearchCV) à **89 % de précision / 92 % de rappel** et une
**réduction estimée de 30 % des arrêts non planifiés**. Même sujet (maintenance
prédictive), date et intitulé différents. Ces chiffres ne sont **pas** utilisés : dis-moi
s'il s'agit du même stage et je les ajoute.

**Écart de chiffre** — les sources écrivent tantôt « −90 % de latence », tantôt
« 40 s → 5 s » (soit −87,5 %). J'ai gardé les deux valeurs brutes, qui sont vérifiables.

### AVA LUX (Freelance) — Développeur Backend & IA — Casablanca, Maroc — 06/2024 – 09/2024

| | |
|---|---|
| **Problème** | Décisions logistiques prises sans visibilité : goulots d'étranglement inconnus, reporting manuel. |

- Analyse exploratoire et statistique de **plus de 50 000 enregistrements** supply chain
  (délais, stocks, coûts de transport) [8]
- **3 goulots d'étranglement majeurs** identifiés par analyse de corrélation et
  clustering **K-means** [2]
- Module d'analyse par IA intégré à une application supply chain **Spring Boot**
  (Java, PostgreSQL, Python) [9]
- **API REST Spring Boot** exposant les résultats analytiques, intégrées à l'**ERP** [10]
- Tableaux de bord automatisés (Python, Pandas, Matplotlib / Power BI) pour le suivi
  mensuel des KPI ; génération de rapports automatisée en remplacement du travail manuel [3]
- **Conteneurisation Docker** du service d'analyse [8]
- **Amélioration de 15 % de l'efficacité logistique**, à laquelle les recommandations ont
  contribué [4]

**Manques** — le 15 % est formulé comme une contribution, pas comme une mesure directe ;
aucun avant/après sur le temps de reporting.

**Contradiction** — les dates apparaissent en Jun–Jul 2024, Juin–Juil 2023 **et**
Jun–Jul 2022 ; les intitulés vont de « Data Analyst Supply Chain » à « Backend & AI
Developer ». J'utilise ce que tu as fixé : 06/2024 – 09/2024, Développeur Backend & IA.

### Corporate Software — Développeur Full-Stack — Casablanca, Maroc — 04/2023 – 06/2023

| | |
|---|---|
| **Problème** | Demandes de support traitées sans plateforme dédiée, et écrans critiques lents à charger. |

- Plateforme de support client (module CRM sur mesure) en **architecture microservices** :
  services **Spring Boot**, persistance **MongoDB**, frontend **React.js** [6]
- Plateforme gérant **plus de 10 000 clients** [2]
- Gestion des tickets et des données utilisateurs, logique métier, flux de données [2]
- API REST entre le backend et le frontend React [1]
- Optimisation de requêtes SQL complexes → **−40 % sur le temps de chargement** des
  données critiques [4]
- Agile/Scrum : daily stand-ups, sprint planning, rétrospectives, revues de code [6]

**Tension mineure** — MongoDB et SQL apparaissent tous deux ; le −40 % est rattaché à la
réécriture de requêtes SQL.

---

## Projets

| # | Projet | Faits retenus | Impact mesurable ? |
|---|---|---|---|
| 1 | **Agent autonome de documentation Spring Boot**<br>Python, LangChain, LangGraph, FastAPI, Tauri, Next.js | Multi-agents (agents spécialisés, tool-use, gestion de contexte) analysant le code Java, cartographiant les dépendances, générant la documentation technique. Interface desktop Mission Control (Next.js + Tauri), Windows/macOS/Linux. Validation Human-in-the-Loop / peer review. Parsing de fichiers, moteurs de templates, export PDF/Markdown/HTML. API FastAPI conteneurisée pour usage CI/CD. | **Non** — impact qualitatif |
| 2 | **Industrialisation de plateforme IA**<br>Cookiecutter, Python, FastAPI, Docker, Azure DevOps | Template interne amorçant un service IA avec CI/CD, composants MLOps et authentification multi-mode déjà câblés. | **Oui** — « mise en place d'un nouveau service : de quelques jours à quelques minutes » [2] |
| 3 | **Plateforme de recommandation de films**<br>Next.js, Flask, Supabase/PostgreSQL, Azure | Filtrage **basé contenu** avec **similarité cosinus** [30]. Next.js (API Routes, SSR), NextAuth, API Flask exposant le moteur, architecture SOA. Déploiement continu sur Azure via GitHub Actions. | **Non** |
| 4 | **Détection de maladies des plantes**<br>Deep Learning, CNN, Flask, microservices, RAG | Plusieurs CNN pré-entraînés entraînés et comparés ; ensemble de **4 CNN** (transfer learning). Client mobile, architecture microservices d'inférence sur REST. Pipeline RAG produisant les recommandations de traitement. | **Non** — « 95 % de disponibilité » retiré sur ta demande |
| 5 | **API de prédiction haute performance**<br>Python, FastAPI, Redis | API REST d'aide à la décision agricole conçue pour la faible latence. Optimisations de structures de données, couches de cache, tests de charge et ajustements. | **Non** — « plus de 1000 utilisateurs simultanés » retiré sur ta demande |
| 6 | **Agent autonome de maintenance prédictive**<br>Dataiku DSS, Python, Spark | Pipelines ETL et ML sur Dataiku DSS pour la prédiction de pannes (**NASA Turbofan**). RAG Python sur mesure liant les alertes capteurs à la documentation technique (PDF). Recherche vectorielle (embeddings), logique de diagnostic automatisée. | **Non** |
| 7 | **Entrepôt de données décisionnel**<br>SQL Server, SSMS, ETL, Power BI | Entrepôt en **schéma en étoile** modélisé pour l'analyse de l'engagement utilisateur d'un site web touristique. Flux ETL d'alimentation et de transformation. Dashboard interactif des indicateurs clés. | **Non** — schéma en étoile dans 1 source, SSMS/SQL Server dans 2 |
| 8 | **Détection automatisée de fraude**<br>PySpark, MLlib, Python | Transactions financières traitées **en temps réel** et analysées pour identifier les activités potentiellement frauduleuses ; modèles ML améliorant la précision de détection. | **Non** |
| 9 | **Prédiction du type de culture optimal** (recherche)<br>Machine Learning, CRISP-DM, Python | Cycle complet de la collecte à la modélisation sur données de sol et météo ; feature engineering et optimisation d'hyperparamètres. Performance **dépassant les baselines de l'état de l'art**. A abouti à un **article scientifique** détaillant méthodologie, évaluation et contributions [3]. | **Partiel** — « dépasse l'état de l'art » sans chiffre |
| 10 | **Flux IoT temps réel**<br>Kafka, Spark, Python | Nettoyage et structuration de flux de capteurs IoT temps réel ; prétraitement et feature engineering pour la modélisation de séries temporelles (LSTM). | **Non** |
| 11 | **Pipeline d'ingestion et de vectorisation RAG**<br>Python, LangChain, FAISS, Docker | ELT documentaire : extraction, chunking, création d'embeddings, chargement dans une base vectorielle **FAISS**. Orchestration LangChain, optimisation des requêtes de recherche. | **Non** |
| 12 | **Hackathon MoroccoAI InnovAI 2024 — Top 4 / 50+ équipes**<br>MoroccoAI Annual Conference | Système ML d'optimisation de l'irrigation agricole et de prédiction de sécheresse (solution IoT/Web). Ton rôle d'après les sources : développement des API, déploiement du backend et des modèles ML sur Azure avec CI/CD (GitHub Actions) ; architecture cloud, IaC, monitoring ; pipelines ETL et préparation des données pour la prédiction de sécheresse. | **Oui** — Top 4 parmi plus de 50 équipes [2] |

**Contradiction, projet 3** — trois sources décrivent le moteur de films comme du
**filtrage collaboratif** avec un framework de test A/B à **85 % de précision**, ce qui
contredit « basé contenu, similarité cosinus » (30 sources). J'ai gardé la version
majoritaire et je n'utilise pas le 85 %.

---

## Chiffres à confirmer

| Chiffre | Source | Statut |
|---|---|---|
| Veolia — détection ≥ 80 %, < 5 % faux positifs | 17 et 6 CV | **utilisé** |
| Veolia — dérive KS ≤ 0,15 | 24 CV | **utilisé** |
| OCP — 40 s → 5 s | 9 CV | **utilisé** |
| OCP — « −90 % de latence » | 20+ CV | non utilisé : 40 s → 5 s vaut −87,5 % |
| OCP — 89 % précision / 92 % rappel, −30 % d'arrêts non planifiés | 3 CV, **autre date et autre intitulé** | **en attente de ta confirmation** |
| AVA LUX — 50 000+ enregistrements, 3 goulots, +15 % d'efficacité | 8, 2 et 4 CV | **utilisé** |
| Corporate Software — 10 000+ clients, −40 % de temps de chargement | 2 et 4 CV | **utilisé** |
| Cookiecutter — « de quelques jours à quelques minutes » | 2 CV | **utilisé** |
| Films — 85 % de précision (filtrage collaboratif) | 3 CV, contredit par 30 | non utilisé |
| Culture optimale — « dépasse l'état de l'art » | 6 CV | utilisé sans chiffre, **un chiffre serait utile** |
