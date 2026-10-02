#!/usr/bin/env python3
"""Twelve one-page CVs: six target roles, English and French.

Every line here comes from the 103 CVs already in the collection. Nothing is
invented: where a claim existed in only one or two sources and could not be
confirmed, it was dropped rather than reworded (the availability percentage and
the concurrent-user count, both removed on request).

A shared project carries a different TITLE and different bullets on each CV,
because a recruiter reading the DevOps CV should see deployment work, not a
recommendation engine with deployment bullets bolted on.

Every bullet is problem, solution, impact: what was wrong, missing or manual,
what was built and with which tools named precisely, and what changed as a
result. Where no source gives a measurable result the impact is qualitative but
concrete, and FACTS.md next to this file lists that gap. FACTS.md is the merged
fact sheet behind every line, with the number of source CVs per claim and the
contradictions left for the owner to settle.
"""
from __future__ import annotations

def me() -> dict:
    """Name and contact details, read from profile.toml.

    Not hardcoded here: profile.toml is gitignored and this file is not, and a
    phone number on a public repository is read by address harvesters rather
    than by the employer it was written for. profile.toml is already the one
    place these live, and already what fills an employer's form.
    """
    from pipeline import config as pc

    ident = pc.load_profile().get("base") or {}
    name = " ".join(x for x in (ident.get("first_name"),
                                ident.get("last_name")) if x)
    links = [{"label": label, "url": ident[key]}
             for key, label in (("linkedin", "LinkedIn"), ("github", "GitHub"),
                                ("portfolio", "Portfolio"))
             if ident.get(key)]
    if not name or not ident.get("email"):
        raise SystemExit(
            "build/role_cvs.py reads your name and contact details from "
            "profile.toml, and found none. Copy profile.example.toml to "
            "profile.toml and fill in [identity].")
    return {"name": name,
            "contact": {"email": ident.get("email", ""),
                        "phone": ident.get("phone", ""), "links": links}}

EDU = {
    "en": [
        {"heading": "Engineering Degree, Data Science & Artificial Intelligence",
         "org": "École Nationale Supérieure d'IA et des Sciences des Données",
         "dates": "09/2023 – 06/2026", "location": "Taroudant", "bullets": []},
        {"heading": "Bachelor's Degree in Computer Engineering",
         "org": "Faculté des Sciences et Techniques de Mohammedia",
         "dates": "09/2020 – 06/2023", "location": "Mohammedia", "bullets": []},
    ],
    "fr": [
        {"heading": "Diplôme d'Ingénieur, Data Science & Intelligence Artificielle",
         "org": "École Nationale Supérieure d'IA et des Sciences des Données",
         "dates": "09/2023 – 06/2026", "location": "Taroudant", "bullets": []},
        {"heading": "Licence en Informatique",
         "org": "Faculté des Sciences et Techniques de Mohammedia",
         "dates": "09/2020 – 06/2023", "location": "Mohammedia", "bullets": []},
    ],
}

OTHER = {
    "en": [["Languages", "Arabic (native)  |  French (fluent)  |  English (fluent)"],
           ["Certifications", "Data Engineering Essentials, Coursera 2023  |  Data Structures & Backend, Coursera 2023  |  Intro to Deep Learning, Kaggle 2023"]],
    "fr": [["Langues", "Arabe (langue maternelle)  |  Français (courant)  |  Anglais (courant)"],
           ["Certifications", "Data Engineering Essentials, Coursera 2023  |  Data Structures & Backend, Coursera 2023  |  Intro to Deep Learning, Kaggle 2023"]],
}

# Employers, dates and cities are identical on every CV; only the job title on
# the software-engineering CV differs, and only the bullets are re-angled. The
# cities come from the sources, where they are unambiguous: Rabat for Veolia,
# El Jadida for OCP, Casablanca for AVA LUX and for Corporate Software.
COUNTRY = {"en": "Morocco", "fr": "Maroc"}
EMPLOYERS = {
    "veolia": ("Veolia Software Solutions", "02/2026 – 08/2026", "Rabat"),
    "ocp":    ("OCP Group", "07/2025 – 09/2025", "El Jadida"),
    "ava":    ("AVA LUX", "06/2024 – 09/2024", "Casablanca"),
    "corp":   ("Corporate Software", "04/2023 – 06/2023", "Casablanca"),
}


# ---------------------------------------------------------------------------
# The same four jobs, told six ways. Every bullet is problem, solution, impact:
# what was wrong or missing, what was built and with what, and what changed.
# The facts are identical across roles; only the lens moves.
#
# No em dashes: the renderer rewrites a spaced one as a comma, which turns a
# parenthetical into comma soup. Parentheses and colons survive it.
# ---------------------------------------------------------------------------
EXP = {
"ai": {"en": {
  "veolia": ["Built a water-consumption anomaly detection pipeline where manual review could not keep up: an Isolation Forest and autoencoder ensemble with an LLM confirmation step (Claude 3.5), reaching a detection rate above 80% with under 5% false positives.",
             "Industrialized the prototype into a reusable AI backend platform (FastAPI, Docker, CI/CD), carried from PoC to production and owned end to end.",
             "Presented model performance to non-technical stakeholders and retuned the detection thresholds on their feedback, so alerts matched what operations treats as abnormal."],
  "ocp":    ["Built a generative AI application for predictive maintenance (FastAPI, Next.js, LangChain) in place of maintenance plans written by hand from historical data, integrated into the business tools through APIs.",
             "Constrained the model's output with LangChain and Pydantic, turning free-form text into structured JSON the downstream tools consume without manual checking.",
             "Diagnosed the 40-second response time that made the first version unusable and cut it to about 5 seconds, by benchmarking prompting and inference strategies with LangSmith."],
  "ava":    ["Embedded an AI analytics module in a Spring Boot supply-chain application where decisions were taken without visibility, and exposed it through Java REST APIs into the company's ERP.",
             "Analysed more than 50,000 logistics records with K-means clustering and correlation analysis, isolating three major bottlenecks; the recommendations contributed to a 15% gain in logistics efficiency."],
  "corp":   ["Built a customer support platform (React.js, Spring Boot, MongoDB) in a microservices architecture, serving more than 10,000 clients in place of ad-hoc request handling."]},
       "fr": {
  "veolia": ["Conçu un pipeline de détection d'anomalies de consommation d'eau là où la revue manuelle ne suivait plus : ensemble Isolation Forest et autoencodeur avec confirmation par LLM (Claude 3.5), pour un taux de détection supérieur à 80 % et moins de 5 % de faux positifs.",
             "Industrialisé le prototype en plateforme backend IA réutilisable (FastAPI, Docker, CI/CD), menée du PoC à la production et portée de bout en bout.",
             "Présenté les performances du modèle à des interlocuteurs non techniques et réajusté les seuils de détection d'après leur retour, pour que les alertes correspondent à ce que l'exploitation considère comme anormal."],
  "ocp":    ["Développé une application d'IA générative pour la maintenance prédictive (FastAPI, Next.js, LangChain) en remplacement de plans rédigés à la main depuis l'historique, intégrée aux outils métiers via API.",
             "Contraint la sortie du modèle avec LangChain et Pydantic : du texte libre à du JSON structuré, consommé par les outils en aval sans vérification manuelle.",
             "Diagnostiqué les 40 secondes de temps de réponse qui rendaient la première version inutilisable et ramené la latence à environ 5 secondes, en comparant les stratégies de prompting et d'inférence avec LangSmith."],
  "ava":    ["Intégré un module d'analyse par IA dans une application supply chain Spring Boot où les décisions se prenaient sans visibilité, et exposé via des API REST Java jusqu'à l'ERP de l'entreprise.",
             "Analysé plus de 50 000 enregistrements logistiques par clustering K-means et analyse de corrélation, isolant trois goulots d'étranglement majeurs ; les recommandations ont contribué à 15 % d'efficacité logistique gagnée."],
  "corp":   ["Développé une plateforme de support client (React.js, Spring Boot, MongoDB) en architecture microservices, servant plus de 10 000 clients là où les demandes étaient traitées au cas par cas."]}},

"mlops": {"en": {
  "veolia": ["Built the MLOps lifecycle of a model that had no path to production: an MLflow registry with alias-based promotion (candidate, staging, production) and Evidently AI drift monitoring at KS ≤ 0.15.",
             "Automated the gate, so a degraded model is blocked inside the pipeline before it reaches users, with no manual review step.",
             "Industrialized the PoC into a production-ready platform (Docker containerization, Git versioning, CI/CD build, deployment and monitoring), running at over 80% detection with under 5% false positives."],
  "ocp":    ["Containerized the generative application with Docker and wired end-to-end LangSmith observability, so production behaviour was traced rather than inferred.",
             "Measured prompting and inference strategies systematically and brought response time down from 40 seconds to about 5."],
  "ava":    ["Dockerized the analytics service and delivered it into a running Spring Boot application, making a Python model deployable without touching the host application's build."],
  "corp":   ["Built and shipped a microservices platform (Spring Boot, MongoDB, React.js) serving more than 10,000 clients, with API testing in an Agile cycle."]},
          "fr": {
  "veolia": ["Construit le cycle MLOps d'un modèle qui n'avait aucune voie vers la production : registre MLflow avec promotion par alias (candidate, staging, production) et monitoring de dérive Evidently AI à KS ≤ 0,15.",
             "Automatisé le gating : un modèle dégradé est bloqué dans le pipeline avant d'atteindre les utilisateurs, sans étape de revue manuelle.",
             "Industrialisé le PoC en plateforme production-ready (conteneurisation Docker, versioning Git, build, déploiement et monitoring en CI/CD), en service à plus de 80 % de détection et moins de 5 % de faux positifs."],
  "ocp":    ["Conteneurisé l'application générative avec Docker et câblé une observabilité LangSmith de bout en bout, pour que le comportement en production soit tracé et non supposé.",
             "Mesuré systématiquement les stratégies de prompting et d'inférence et ramené le temps de réponse de 40 secondes à environ 5."],
  "ava":    ["Conteneurisé le service d'analyse, puis livré dans une application Spring Boot en fonctionnement, rendant un modèle Python déployable sans toucher au build de l'application hôte."],
  "corp":   ["Développé et livré une plateforme en microservices (Spring Boot, MongoDB, React.js) servant plus de 10 000 clients, avec tests d'API dans un cycle Agile."]}},

"devops": {"en": {
  "veolia": ["Built and ran the delivery chain of an AI platform that had none: Azure DevOps CI/CD covering build, deployment, versioning and monitoring, from prototype to production.",
             "Containerized the platform with Docker and put Git versioning and automated delivery in place, so a release stopped being a manual operation.",
             "Set up the monitoring that blocks a degraded model inside the pipeline, catching regressions before production instead of after."],
  "ocp":    ["Containerized the application with Docker and set up application monitoring (LangSmith) to track production behaviour end to end.",
             "Tuned the deployed service from a 40-second response time down to about 5 seconds."],
  "ava":    ["Dockerized the analytics service and integrated it into the delivery chain of a Spring Boot application, so the Python model shipped with the application rather than beside it."],
  "corp":   ["Deployed a customer support platform (Spring Boot, MongoDB, React.js) as microservices for more than 10,000 clients, with API testing and code review in an Agile cycle."]},
           "fr": {
  "veolia": ["Construit et exploité la chaîne de livraison d'une plateforme IA qui n'en avait pas : CI/CD Azure DevOps couvrant build, déploiement, versioning et monitoring, du prototype à la production.",
             "Conteneurisé la plateforme avec Docker et mis en place versioning Git et livraison automatisée, pour qu'une mise en production cesse d'être une opération manuelle.",
             "Mis en place le monitoring qui bloque un modèle dégradé dans le pipeline, détectant les régressions avant la production et non après."],
  "ocp":    ["Conteneurisé l'application avec Docker et mis en place le monitoring applicatif (LangSmith) pour suivre le comportement en production de bout en bout.",
             "Optimisé le service déployé, de 40 secondes de temps de réponse à environ 5."],
  "ava":    ["Conteneurisé le service d'analyse et intégré à la chaîne de livraison d'une application Spring Boot, pour que le modèle Python soit livré avec l'application et non à côté."],
  "corp":   ["Déployé une plateforme de support client (Spring Boot, MongoDB, React.js) en microservices pour plus de 10 000 clients, avec tests d'API et revues de code dans un cycle Agile."]}},

"ds": {"en": {
  "veolia": ["Turned the business need for spotting abnormal water consumption into a working model: an Isolation Forest and autoencoder ensemble with an LLM confirmation step, reaching over 80% detection with under 5% false positives.",
             "Prepared and enriched the underlying data (collection, processing, feature enrichment) and measured accuracy and drift continuously with MLflow and Evidently AI (KS ≤ 0.15).",
             "Explored consumption patterns with the business and retuned the detection thresholds on their feedback, so alerts reflected what operations treats as abnormal."],
  "ocp":    ["Extracted and prepared historical maintenance data in SQL and engineered features over multi-sensor time series, replacing a generation context assembled by hand.",
             "Built the evaluation: benchmarked prompting and inference strategies with LangSmith, which is what identified the change taking response time from 40 seconds to about 5."],
  "ava":    ["Analysed more than 50,000 supply-chain records (lead times, stock, transport costs) with correlation analysis and K-means clustering, isolating three major bottlenecks nobody had named.",
             "Automated the monthly KPI reporting in Python so the analysis was repeatable rather than rebuilt by hand; the recommendations contributed to a 15% gain in logistics efficiency."],
  "corp":   ["Built a customer support platform (React.js, Spring Boot, MongoDB) for more than 10,000 clients, and cut the load time of critical data by 40% by rewriting the SQL behind it."]},
       "fr": {
  "veolia": ["Traduit le besoin métier de repérer les consommations d'eau anormales en modèle opérationnel : ensemble Isolation Forest et autoencodeur avec confirmation par LLM, pour plus de 80 % de détection et moins de 5 % de faux positifs.",
             "Préparé et enrichi les données sous-jacentes (collecte, traitement, enrichissement des variables) et mesuré en continu justesse et dérive avec MLflow et Evidently AI (KS ≤ 0,15).",
             "Exploré les patterns de consommation avec le métier et réajusté les seuils de détection d'après leur retour, pour que les alertes reflètent ce que l'exploitation considère comme anormal."],
  "ocp":    ["Extrait et préparé les données historiques de maintenance en SQL et construit les variables sur séries temporelles multi-capteurs, en remplacement d'un contexte de génération assemblé à la main.",
             "Construit l'évaluation : comparaison des stratégies de prompting et d'inférence avec LangSmith, qui a permis d'identifier le changement ramenant le temps de réponse de 40 secondes à environ 5."],
  "ava":    ["Analysé plus de 50 000 enregistrements supply chain (délais, stocks, coûts de transport) par analyse de corrélation et clustering K-means, isolant trois goulots d'étranglement que personne n'avait nommés.",
             "Automatisé en Python le reporting mensuel des KPI pour rendre l'analyse reproductible au lieu d'être refaite à la main ; les recommandations ont contribué à 15 % d'efficacité logistique gagnée."],
  "corp":   ["Développé une plateforme de support client (React.js, Spring Boot, MongoDB) pour plus de 10 000 clients, et réduit de 40 % le temps de chargement des données critiques en réécrivant les requêtes SQL."]}},

"de": {"en": {
  "veolia": ["Designed and built the data pipeline behind water-consumption anomaly detection (collection, processing, feature enrichment), which is what made detection above 80% with under 5% false positives possible.",
             "Implemented business-rule controls on the processed data, so a bad upstream record was caught in the pipeline instead of becoming a false alert.",
             "Built the delivery chain around it: Docker containerization, Git versioning, automated deployment and monitoring, carrying the flow from prototype to production."],
  "ocp":    ["Rewrote and optimized the SQL extracting historical maintenance data, replacing a context assembled by hand and cutting the application's response time from 40 seconds to about 5.",
             "Cleaned and structured large industrial sensor datasets into features usable for modelling."],
  "ava":    ["Built ingestion and transformation pipelines (Python, Pandas, SQL) consolidating more than 50,000 records from heterogeneous logistics sources into a single analysable base.",
             "Automated the KPI reporting on top of it and exposed the results through Spring Boot REST APIs into the company's ERP, replacing manual report assembly."],
  "corp":   ["Built backend services over MongoDB and MySQL in a microservices architecture, and cut critical-data load time by 40% by rewriting complex SQL queries."]},
      "fr": {
  "veolia": ["Conçu et développé le pipeline de données derrière la détection d'anomalies de consommation d'eau (collecte, traitement, enrichissement des variables), ce qui a rendu possible plus de 80 % de détection avec moins de 5 % de faux positifs.",
             "Implémenté des contrôles de règles métier sur les données traitées, pour qu'un enregistrement amont erroné soit arrêté dans le pipeline au lieu de devenir une fausse alerte.",
             "Mis en place la chaîne de livraison associée : conteneurisation Docker, versioning Git, déploiement automatisé et monitoring, du prototype à la production."],
  "ocp":    ["Réécrit et optimisé les requêtes SQL d'extraction des données historiques de maintenance, en remplacement d'un contexte assemblé à la main, et ramené le temps de réponse de l'application de 40 secondes à environ 5.",
             "Nettoyé et structuré de grands jeux de données de capteurs industriels en variables exploitables pour la modélisation."],
  "ava":    ["Développé des pipelines d'ingestion et de transformation (Python, Pandas, SQL) consolidant plus de 50 000 enregistrements de sources logistiques hétérogènes vers une base unique analysable.",
             "Automatisé le reporting des KPI au-dessus de ces pipelines et exposé les résultats via des API REST Spring Boot jusqu'à l'ERP de l'entreprise, en remplacement de l'assemblage manuel des rapports."],
  "corp":   ["Développé les services backend sur MongoDB et MySQL en architecture microservices, et réduit de 40 % le temps de chargement des données critiques en réécrivant des requêtes SQL complexes."]}},

"swe": {"en": {
  "veolia": ["Designed and shipped a reusable backend platform (FastAPI, Docker) where only a prototype existed, carried to production and owned end to end.",
             "Designed the APIs and containerized the service, with Git versioning and automated CI/CD delivery replacing manual releases.",
             "Implemented business-rule controls so invalid input was rejected at the boundary instead of corrupting downstream processing."],
  "ocp":    ["Built a full-stack application (FastAPI, Next.js) integrating generation into an existing data platform, exposed to the business tools through APIs.",
             "Diagnosed and fixed the 40-second response time that made the first version unusable, bringing it down to about 5 seconds by rewriting the Python path and the SQL behind it."],
  "ava":    ["Designed Java Spring Boot REST APIs for logistics data processing and analysis, integrated into the company's ERP.",
             "Containerized the service with Docker and integrated it into a running Spring Boot application without changing its build."],
  "corp":   ["Built a customer support platform (React.js, Spring Boot, MongoDB) in a microservices architecture, serving more than 10,000 clients in place of ad-hoc request handling.",
             "Cut the load time of critical data by 40% by rewriting complex SQL queries, in an Agile cycle with code review and API testing."]},
       "fr": {
  "veolia": ["Conçu et livré une plateforme backend réutilisable (FastAPI, Docker) là où il n'existait qu'un prototype, menée jusqu'en production et portée de bout en bout.",
             "Conçu les API et conteneurisé le service, avec versioning Git et livraison CI/CD automatisée en remplacement des mises en production manuelles.",
             "Implémenté des contrôles de règles métier pour que les entrées invalides soient rejetées à la frontière au lieu de corrompre les traitements en aval."],
  "ocp":    ["Développé une application full-stack (FastAPI, Next.js) intégrant la génération à une plateforme de données existante, exposée aux outils métiers via API.",
             "Diagnostiqué et corrigé les 40 secondes de temps de réponse qui rendaient la première version inutilisable, ramenées à environ 5 en réécrivant le chemin Python et les requêtes SQL."],
  "ava":    ["Conçu des API REST Java Spring Boot pour le traitement et l'analyse de données logistiques, intégrées à l'ERP de l'entreprise.",
             "Conteneurisé le service avec Docker et intégré à une application Spring Boot en fonctionnement, sans modifier son build."],
  "corp":   ["Développé une plateforme de support client (React.js, Spring Boot, MongoDB) en architecture microservices, servant plus de 10 000 clients là où les demandes étaient traitées au cas par cas.",
             "Réduit de 40 % le temps de chargement des données critiques en réécrivant des requêtes SQL complexes, dans un cycle Agile avec revues de code et tests d'API."]}},
}


# ---------------------------------------------------------------------------
# Projects. A shared project gets its own title per role, not the same heading
# with different bullets: the title is the first thing read, and on the DevOps
# CV it should say deployment, not recommendation.
# Each bullet is problem, solution, impact, in that order where the source
# material supports all three. Order inside each list is the order on the page.
# ---------------------------------------------------------------------------
P = lambda h, org, b: {"heading": h, "org": org, "dates": "", "location": "", "bullets": b}

PROJ = {
"ai": {"en": [
  P("Multi-agent documentation generation system", "Python, LangChain, LangGraph, Tauri, Next.js",
    ["Orchestrated specialised LangChain and LangGraph agents to read Java source, map its dependencies and write the technical documentation nobody kept up to date, behind a desktop Mission Control interface with a human review step before anything is accepted."]),
  P("Production recommendation engine integration", "Next.js, Flask, Supabase, Azure",
    ["Exposed a content-based engine (cosine similarity) as a Flask API orchestrated from Next.js routes with NextAuth, so the recommendations reached the running product instead of staying in a notebook."]),
  P("Plant disease classifier served through an API", "Deep Learning, Flask, Microservices, RAG",
    ["Compared pre-trained CNN architectures, kept an ensemble of four, and served it behind REST APIs with a RAG pipeline that turns a diagnosis into a treatment a grower can act on."]),
  P("Low-latency inference service", "Python, FastAPI, Redis",
    ["Designed a FastAPI inference API for agricultural decision support around data-structure and Redis caching optimizations, then load-tested and tuned it so response time held as volume rose."]),
  P("ML model deployment, MoroccoAI InnovAI Hackathon, Top 4", "2024 MoroccoAI Annual Conference",
    ["Built the APIs and deployed the backend and ML models of an irrigation-optimization and drought-prediction system inside the hackathon window; top 4 of more than 50 teams."])],
       "fr": [
  P("Système multi-agents de génération documentaire", "Python, LangChain, LangGraph, Tauri, Next.js",
    ["Orchestré des agents spécialisés LangChain et LangGraph pour lire le code Java, cartographier ses dépendances et rédiger la documentation technique que personne ne tenait à jour, derrière une interface desktop Mission Control avec validation humaine avant acceptation."]),
  P("Intégration d'un moteur de recommandation en production", "Next.js, Flask, Supabase, Azure",
    ["Exposé un moteur par filtrage de contenu (similarité cosinus) en API Flask orchestrée depuis les routes Next.js avec NextAuth, pour que les recommandations atteignent le produit en service au lieu de rester dans un notebook."]),
  P("Classifieur de maladies des plantes exposé en API", "Deep Learning, Flask, Microservices, RAG",
    ["Comparé des architectures CNN pré-entraînées, retenu un ensemble de quatre, et servi derrière des API REST avec un pipeline RAG qui transforme un diagnostic en traitement actionnable par l'agriculteur."]),
  P("Service d'inférence à faible latence", "Python, FastAPI, Redis",
    ["Conçu une API d'inférence FastAPI pour l'aide à la décision agricole autour d'optimisations de structures de données et de cache Redis, puis soumise à des tests de charge et ajustée pour tenir le temps de réponse à la montée en volume."]),
  P("Déploiement de modèles ML, Hackathon MoroccoAI InnovAI, Top 4", "MoroccoAI Annual Conference 2024",
    ["Développé les API et déployé le backend et les modèles ML d'un système d'optimisation de l'irrigation et de prédiction de sécheresse dans le temps du hackathon ; top 4 parmi plus de 50 équipes."])]},

"mlops": {"en": [
  P("Reusable industrialization template for AI services", "Cookiecutter, Python, FastAPI, Docker, Azure DevOps",
    ["Packaged the CI/CD, MLOps components and multi-mode authentication every new AI service was re-implementing into one Cookiecutter template: setting up a new service went from days to minutes."]),
  P("Training and deployment pipelines on Dataiku DSS", "Dataiku, Apache Spark, Python, RAG",
    ["Built ETL and ML pipelines for failure prediction on the NASA Turbofan data, with model versioning and scheduled retraining.",
     "Added a Python RAG layer linking a sensor alert to the matching technical PDF through vector search, so an alert arrives with its documentation instead of sending a technician looking."]),
  P("Model serving service", "Python, FastAPI, Redis",
    ["Served the model behind a FastAPI service with Redis caching layers, load-tested and tuned so latency stayed stable as request volume rose."])],
          "fr": [
  P("Template réutilisable d'industrialisation de services IA", "Cookiecutter, Python, FastAPI, Docker, Azure DevOps",
    ["Rassemblé dans un seul template Cookiecutter le CI/CD, les composants MLOps et l'authentification multi-mode que chaque nouveau service IA réimplémentait : la mise en place d'un service est passée de quelques jours à quelques minutes."]),
  P("Pipelines d'entraînement et de déploiement sur Dataiku DSS", "Dataiku, Apache Spark, Python, RAG",
    ["Construit les pipelines ETL et ML de prédiction de pannes sur les données NASA Turbofan, avec versioning des modèles et réentraînement planifié.",
     "Ajouté une couche RAG en Python reliant une alerte capteur au PDF technique correspondant par recherche vectorielle, pour que l'alerte arrive avec sa documentation au lieu d'envoyer un technicien la chercher."]),
  P("Service de serving de modèles", "Python, FastAPI, Redis",
    ["Servi le modèle derrière un service FastAPI avec couches de cache Redis, soumis à des tests de charge et ajusté pour que la latence reste stable à la montée en volume."])]},

"devops": {"en": [
  P("Cloud deployment of a web application", "Azure, GitHub Actions, Next.js, Flask",
    ["Replaced deployment by hand with continuous delivery to Azure through GitHub Actions, on a service-oriented architecture with NextAuth authentication."]),
  P("Reusable CI/CD foundation for AI services", "Cookiecutter, Docker, Azure DevOps",
    ["Built a Cookiecutter template shipping CI/CD, MLOps components and authentication pre-wired, so a new service starts on a working delivery chain: setup went from days to minutes."]),
  P("Microservices architecture and resilience", "Microservices, Flask, REST",
    ["Exposed computer-vision models as REST services behind load balancing and redundancy, consumed by a mobile client whose caching strategy keeps it usable on a weak connection."]),
  P("API performance tuning and load testing", "Python, FastAPI, Redis",
    ["Tuned a FastAPI service with data-structure and Redis caching optimizations, then load-tested it to find where response time degrades and fixed it before users met it."]),
  P("Infrastructure and backend deployment, MoroccoAI Hackathon, Top 4", "2024 MoroccoAI Annual Conference",
    ["Owned DevOps and cloud for an irrigation and drought-prediction system: Azure infrastructure, GitHub Actions CI/CD, API delivery, backend and ML model deployment, monitoring; top 4 of more than 50 teams."])],
           "fr": [
  P("Déploiement cloud d'une application web", "Azure, GitHub Actions, Next.js, Flask",
    ["Remplacé le déploiement manuel par une livraison continue sur Azure via GitHub Actions, sur une architecture orientée services avec authentification NextAuth."]),
  P("Socle CI/CD réutilisable pour services IA", "Cookiecutter, Docker, Azure DevOps",
    ["Construit un template Cookiecutter livrant CI/CD, composants MLOps et authentification pré-câblés, pour qu'un nouveau service démarre sur une chaîne de livraison fonctionnelle : de quelques jours à quelques minutes."]),
  P("Architecture microservices et résilience", "Microservices, Flask, REST",
    ["Exposé des modèles de vision en services REST derrière équilibrage de charge et redondance, consommés par un client mobile dont la stratégie de cache le garde utilisable sur une connexion faible."]),
  P("Optimisation et tests de charge d'une API", "Python, FastAPI, Redis",
    ["Optimisé un service FastAPI par structures de données et cache Redis, puis soumis à des tests de charge pour trouver où le temps de réponse se dégrade et corriger avant que les utilisateurs y arrivent."]),
  P("Infrastructure et déploiement backend, Hackathon MoroccoAI, Top 4", "MoroccoAI Annual Conference 2024",
    ["Porté le DevOps et le cloud d'un système d'irrigation et de prédiction de sécheresse : infrastructure Azure, CI/CD GitHub Actions, livraison des API, déploiement du backend et des modèles ML, monitoring ; top 4 parmi plus de 50 équipes."])]},

"ds": {"en": [
  P("Optimal crop type prediction, research project", "Machine Learning, CRISP-DM, Python",
    ["Ran the full cycle on soil and weather data, from business understanding to feature engineering and hyperparameter optimization, to answer which crop to plant.",
     "Beat the state-of-the-art baselines, and wrote up the methodology, model evaluation and contributions in a scientific paper."]),
  P("Anomaly detection on financial transactions", "PySpark, MLlib, Python",
    ["Processed financial transactions as they arrive with PySpark rather than after the fact, and improved detection accuracy on potentially fraudulent activity with MLlib models."]),
  P("Content-based recommendation system", "Python, Flask, Next.js, Supabase",
    ["Built and evaluated a recommendation engine on cosine similarity, then exposed it through a Flask API to a Next.js front end, taking it from an offline score to something users could click."]),
  P("Plant disease classification by transfer learning", "Deep Learning, CNNs, Python",
    ["Trained and compared several pre-trained CNN architectures and kept an ensemble of four, the combination that classified best while still running inside a mobile application."]),
  P("ML modelling, MoroccoAI InnovAI Hackathon, Top 4", "2024 MoroccoAI Annual Conference",
    ["Built and deployed the ML models for irrigation optimization and drought prediction under hackathon time pressure; top 4 of more than 50 teams."])],
       "fr": [
  P("Prédiction du type de culture optimal, projet de recherche", "Machine Learning, CRISP-DM, Python",
    ["Mené le cycle complet sur données de sol et météo, de la compréhension métier à l'ingénierie de variables et à l'optimisation d'hyperparamètres, pour répondre à la question du type de culture à planter.",
     "Dépassé les baselines de l'état de l'art, et publié méthodologie, évaluation des modèles et contributions dans un article scientifique."]),
  P("Détection d'anomalies sur transactions financières", "PySpark, MLlib, Python",
    ["Traité les transactions financières au fil de l'eau avec PySpark plutôt qu'après coup, et amélioré la précision de détection des activités potentiellement frauduleuses avec des modèles MLlib."]),
  P("Système de recommandation par filtrage de contenu", "Python, Flask, Next.js, Supabase",
    ["Construit et évalué un moteur de recommandation sur la similarité cosinus, puis exposé via une API Flask à une interface Next.js, passant d'un score hors ligne à un produit que l'on peut utiliser."]),
  P("Classification de maladies des plantes par transfer learning", "Deep Learning, CNN, Python",
    ["Entraîné et comparé plusieurs architectures CNN pré-entraînées et retenu un ensemble de quatre, la combinaison la plus juste qui tourne encore dans une application mobile."]),
  P("Modélisation ML, Hackathon MoroccoAI InnovAI, Top 4", "MoroccoAI Annual Conference 2024",
    ["Construit et déployé les modèles ML d'optimisation de l'irrigation et de prédiction de sécheresse sous la contrainte de temps du hackathon ; top 4 parmi plus de 50 équipes."])]},

"de": {"en": [
  P("Decision-support data warehouse", "SQL Server, SSMS, ETL, Power BI",
    ["Modelled a star-schema warehouse and the ETL feeding it, turning a tourism site's raw user-engagement events into indicators a Power BI dashboard can answer questions from."]),
  P("ETL pipeline and real-time sensor streams", "Dataiku, Apache Spark, Kafka, Python",
    ["Built ETL pipelines on Dataiku DSS for failure prediction (NASA Turbofan), where the raw sensor history was unusable as it stood.",
     "Cleaned and structured real-time IoT streams with Kafka and Spark into the time series the models were then trained on."]),
  P("Real-time ingestion and processing of financial transactions", "PySpark, MLlib, Python",
    ["Processed a transaction stream as it arrives with PySpark and analysed it with MLlib models to flag potentially fraudulent activity, where a nightly batch would have answered too late."]),
  P("Document ingestion and vectorization pipeline", "Python, LangChain, FAISS, Docker",
    ["Built the ELT behind a retrieval system: document extraction, chunking, embedding creation and loading into a FAISS vector store, orchestrated with LangChain and tuned on search query performance."])],
      "fr": [
  P("Entrepôt de données décisionnel", "SQL Server, SSMS, ETL, Power BI",
    ["Modélisé un entrepôt en schéma en étoile et l'ETL qui l'alimente, transformant les événements bruts d'engagement d'un site touristique en indicateurs interrogeables depuis un tableau de bord Power BI."]),
  P("Pipeline ETL et flux capteurs temps réel", "Dataiku, Apache Spark, Kafka, Python",
    ["Construit les pipelines ETL sur Dataiku DSS pour la prédiction de pannes (NASA Turbofan), là où l'historique brut des capteurs était inexploitable en l'état.",
     "Nettoyé et structuré des flux IoT temps réel avec Kafka et Spark en séries temporelles sur lesquelles les modèles ont ensuite été entraînés."]),
  P("Ingestion et traitement temps réel de transactions financières", "PySpark, MLlib, Python",
    ["Traité un flux de transactions au fil de l'eau avec PySpark et analysé par des modèles MLlib pour signaler les activités potentiellement frauduleuses, là où un batch nocturne aurait répondu trop tard."]),
  P("Pipeline d'ingestion et de vectorisation documentaire", "Python, LangChain, FAISS, Docker",
    ["Construit l'ELT derrière un système de recherche : extraction des documents, chunking, création des embeddings et chargement dans une base vectorielle FAISS, orchestré avec LangChain et ajusté sur la performance des requêtes."])]},

"swe": {"en": [
  P("Full-stack web application", "Next.js, NextAuth, Flask, Supabase, Azure",
    ["Built a Next.js front end (API Routes, server-side rendering) with NextAuth over a Python service and Supabase, deployed to Azure through GitHub Actions rather than by hand."]),
  P("Optimized REST API", "Python, FastAPI, Redis",
    ["Designed a FastAPI REST API for low latency through data-structure optimizations and Redis caching layers, then load-tested and tuned it so response time held as volume rose."]),
  P("Desktop application with a multi-agent backend", "Tauri, Next.js, Python, LangChain",
    ["Packaged a multi-agent documentation generator behind a native Tauri and Next.js desktop interface (Mission Control), with a review step so generated documentation is approved before it is kept."]),
  P("Distributed platform and mobile client", "Microservices, Flask, REST, Mobile",
    ["Exposed models through REST APIs in a microservices architecture behind load balancing and redundancy, with a mobile client whose caching strategy keeps it usable when the network is not."])],
       "fr": [
  P("Application web full-stack", "Next.js, NextAuth, Flask, Supabase, Azure",
    ["Développé un frontend Next.js (API Routes, rendu côté serveur) avec authentification NextAuth au-dessus d'un service Python et de Supabase, déployé sur Azure via GitHub Actions plutôt qu'à la main."]),
  P("API REST optimisée", "Python, FastAPI, Redis",
    ["Conçu une API REST FastAPI pour la faible latence par optimisations de structures de données et couches de cache Redis, puis soumise à des tests de charge et ajustée pour tenir le temps de réponse à la montée en volume."]),
  P("Application desktop avec backend multi-agents", "Tauri, Next.js, Python, LangChain",
    ["Empaqueté un générateur de documentation multi-agents derrière une interface desktop native Tauri et Next.js (Mission Control), avec une étape de revue pour que la documentation générée soit approuvée avant d'être conservée."]),
  P("Plateforme distribuée et client mobile", "Microservices, Flask, REST, Mobile",
    ["Exposé les modèles via des API REST en architecture microservices derrière équilibrage de charge et redondance, avec un client mobile dont la stratégie de cache le garde utilisable quand le réseau ne l'est pas."])]},
}


# ---------------------------------------------------------------------------
# Identity: one role per CV, never a hybrid. French job titles follow what the
# French-speaking market actually says — "Ingénieur IA" but "Data Scientist" —
# and the same form is used on every CV rather than varying by document.
# ---------------------------------------------------------------------------
ROLES = {
"ai": {
 "title": {"en": "AI Engineer", "fr": "Ingénieur IA"},
 "headline": {"en": "AI Engineer | LLM Applications, RAG & Model Integration",
              "fr": "Ingénieur IA | Applications LLM, RAG et intégration de modèles"},
 "summary": {"en": "AI engineer who takes models to production: anomaly detection ensembles, LLM applications with controlled structured output, and inference exposed through robust APIs. Shipped a water-anomaly pipeline at over 80% detection with under 5% false positives at Veolia, and took a generative application's response time from 40 seconds to 5 at OCP.",
             "fr": "Ingénieur IA qui mène les modèles jusqu'en production : ensembles de détection d'anomalies, applications LLM à sortie structurée contrôlée, inférence exposée via des API robustes. Pipeline de détection d'anomalies livré chez Veolia à plus de 80 % de détection et moins de 5 % de faux positifs, et temps de réponse d'une application générative ramené de 40 secondes à 5 chez OCP."},
 "skills": {"en": [("AI & LLM", "LangChain, LangGraph, RAG, prompt engineering, multi-agent orchestration, Pydantic structured output, LangSmith"),
                   ("Machine Learning", "PyTorch, TensorFlow, Scikit-learn, CNNs, transfer learning, anomaly detection (Isolation Forest, autoencoders)"),
                   ("Backend & serving", "Python, FastAPI, Flask, REST APIs, Redis, Docker"),
                   ("Data & tools", "SQL, PostgreSQL, MongoDB, Git, Azure, MLflow")],
            "fr": [("IA & LLM", "LangChain, LangGraph, RAG, prompt engineering, orchestration multi-agents, sorties structurées Pydantic, LangSmith"),
                   ("Machine Learning", "PyTorch, TensorFlow, Scikit-learn, CNN, transfer learning, détection d'anomalies (Isolation Forest, autoencodeurs)"),
                   ("Backend & serving", "Python, FastAPI, Flask, API REST, Redis, Docker"),
                   ("Données & outils", "SQL, PostgreSQL, MongoDB, Git, Azure, MLflow")]}},

"mlops": {
 "title": {"en": "MLOps Engineer", "fr": "Ingénieur MLOps"},
 "headline": {"en": "MLOps Engineer | CI/CD for Models, Drift Monitoring & Model Registry",
              "fr": "Ingénieur MLOps | CI/CD des modèles, monitoring de dérive et registre de modèles"},
 "summary": {"en": "MLOps engineer who industrializes models: CI/CD covering build, deployment, versioning and monitoring, with an MLflow registry, Evidently AI drift gating at KS ≤ 0.15, and degraded models blocked before they reach users. Built the reusable template that took setting up a new AI service from days to minutes.",
             "fr": "Ingénieur MLOps qui industrialise les modèles : CI/CD couvrant build, déploiement, versioning et monitoring, registre MLflow, gating de dérive Evidently AI à KS ≤ 0,15, et blocage des modèles dégradés avant les utilisateurs. Auteur du template réutilisable qui a ramené la mise en place d'un service IA de quelques jours à quelques minutes."},
 "skills": {"en": [("MLOps", "MLflow, Evidently AI, model registry & promotion, drift monitoring (KS), retraining pipelines, model versioning"),
                   ("CI/CD & containers", "Azure DevOps, GitHub Actions, Docker, Git, automated build, deployment and monitoring"),
                   ("Serving & platforms", "Python, FastAPI, Redis, Dataiku DSS, Azure, LangSmith"),
                   ("ML & data", "Scikit-learn, TensorFlow, PyTorch, Apache Spark, SQL")],
            "fr": [("MLOps", "MLflow, Evidently AI, registre et promotion de modèles, monitoring de dérive (KS), pipelines de réentraînement, versioning"),
                   ("CI/CD & conteneurs", "Azure DevOps, GitHub Actions, Docker, Git, build, déploiement et monitoring automatisés"),
                   ("Serving & plateformes", "Python, FastAPI, Redis, Dataiku DSS, Azure, LangSmith"),
                   ("ML & données", "Scikit-learn, TensorFlow, PyTorch, Apache Spark, SQL")]}},

"devops": {
 "title": {"en": "DevOps Engineer", "fr": "Ingénieur DevOps"},
 "headline": {"en": "DevOps Engineer | CI/CD, Containers, Azure & Observability",
              "fr": "Ingénieur DevOps | CI/CD, conteneurs, Azure et observabilité"},
 "summary": {"en": "DevOps engineer who builds and runs delivery chains: Azure DevOps CI/CD covering build, deployment, versioning and monitoring, Docker containerization and continuous deployment to Azure, where releases were manual before. Led DevOps and cloud infrastructure for a top-4 team of more than 50 at the 2024 MoroccoAI hackathon.",
             "fr": "Ingénieur DevOps qui construit et exploite des chaînes de livraison : CI/CD Azure DevOps couvrant build, déploiement, versioning et monitoring, conteneurisation Docker et déploiement continu sur Azure, là où les mises en production étaient manuelles. Responsable infrastructure DevOps et cloud d'une équipe classée top 4 sur plus de 50 au hackathon MoroccoAI 2024."},
 "skills": {"en": [("CI/CD", "Azure DevOps, GitHub Actions, automated build, deployment, versioning and monitoring"),
                   ("Containers & cloud", "Docker, microservices, Microsoft Azure, load balancing, redundancy"),
                   ("Observability", "application monitoring, LangSmith, MLflow, Evidently AI"),
                   ("Development & data", "Python, FastAPI, Flask, Spring Boot, Git, SQL, Redis")],
            "fr": [("CI/CD", "Azure DevOps, GitHub Actions, build, déploiement, versioning et monitoring automatisés"),
                   ("Conteneurs & cloud", "Docker, microservices, Microsoft Azure, équilibrage de charge, redondance"),
                   ("Observabilité", "monitoring applicatif, LangSmith, MLflow, Evidently AI"),
                   ("Développement & données", "Python, FastAPI, Flask, Spring Boot, Git, SQL, Redis")]}},

"ds": {
 "title": {"en": "Data Scientist", "fr": "Data Scientist"},
 "headline": {"en": "Data Scientist | Modelling, Feature Engineering & Evaluation",
              "fr": "Data Scientist | Modélisation, ingénierie de variables et évaluation"},
 "summary": {"en": "Data scientist who runs the full cycle: business understanding, feature engineering, model choice and evaluation, through to a reading the business can act on. Designed the water-consumption anomaly detection at Veolia (over 80% detection, under 5% false positives), and published a research project on optimal crop prediction as a scientific paper.",
             "fr": "Data scientist qui mène le cycle complet : compréhension métier, ingénierie de variables, choix et évaluation des modèles, jusqu'à une lecture exploitable par le métier. Conception de la détection d'anomalies de consommation d'eau chez Veolia (plus de 80 % de détection, moins de 5 % de faux positifs), et projet de recherche sur la prédiction de culture optimale publié dans un article scientifique."},
 "skills": {"en": [("Machine Learning", "Scikit-learn, TensorFlow, PyTorch, MLlib, CNNs, transfer learning, LSTM, ARIMA, anomaly detection"),
                   ("Method & evaluation", "CRISP-DM, feature engineering, model evaluation, drift measurement (Evidently AI, KS), MLflow"),
                   ("Data", "Python, Pandas, SQL, PySpark, data cleaning, structuring and labelling"),
                   ("Delivery", "Flask, FastAPI, Docker, Power BI, Jupyter")],
            "fr": [("Machine Learning", "Scikit-learn, TensorFlow, PyTorch, MLlib, CNN, transfer learning, LSTM, ARIMA, détection d'anomalies"),
                   ("Méthode & évaluation", "CRISP-DM, ingénierie de variables, évaluation de modèles, mesure de dérive (Evidently AI, KS), MLflow"),
                   ("Données", "Python, Pandas, SQL, PySpark, nettoyage, structuration et labellisation"),
                   ("Restitution", "Flask, FastAPI, Docker, Power BI, Jupyter")]}},

"de": {
 "title": {"en": "Data Engineer", "fr": "Data Engineer"},
 "headline": {"en": "Data Engineer | ETL/ELT Pipelines, Data Modeling & Orchestration",
              "fr": "Data Engineer | Pipelines ETL/ELT, modélisation de données et orchestration"},
 "summary": {"en": "Data engineer who builds the pipelines models depend on: ingestion, transformation and enrichment from heterogeneous sources into a warehouse, batch and streaming, with the delivery chain around them. Built the pipeline behind water-consumption anomaly detection at Veolia, and consolidated more than 50,000 logistics records into a single analysable base at AVA LUX.",
             "fr": "Data engineer qui construit les pipelines dont dépendent les modèles : ingestion, transformation et enrichissement de sources hétérogènes vers un entrepôt, en batch et en streaming, avec la chaîne de livraison associée. Auteur du pipeline derrière la détection d'anomalies de consommation d'eau chez Veolia, et de la consolidation de plus de 50 000 enregistrements logistiques en une base unique chez AVA LUX."},
 "skills": {"en": [("Pipelines & ETL", "Talend, Dataiku DSS, Apache Spark / PySpark, Kafka, Python, Pandas, batch and streaming ingestion"),
                   ("Modeling & storage", "SQL, SQL Server, PostgreSQL, MongoDB, MySQL, data warehousing, star schema, data quality"),
                   ("Platform", "Docker, Azure, Azure DevOps, GitHub Actions, Git, monitoring"),
                   ("Tools", "SSMS, Power BI, FastAPI, Jupyter")],
            "fr": [("Pipelines & ETL", "Talend, Dataiku DSS, Apache Spark / PySpark, Kafka, Python, Pandas, ingestion batch et streaming"),
                   ("Modélisation & stockage", "SQL, SQL Server, PostgreSQL, MongoDB, MySQL, data warehousing, schéma en étoile, qualité des données"),
                   ("Plateforme", "Docker, Azure, Azure DevOps, GitHub Actions, Git, monitoring"),
                   ("Outils", "SSMS, Power BI, FastAPI, Jupyter")]}},

"swe": {
 "title": {"en": "Software Engineer", "fr": "Ingénieur Logiciel"},
 "headline": {"en": "Software Engineer | Backend APIs, Full-Stack & Microservices",
              "fr": "Ingénieur Logiciel | API backend, full-stack et microservices"},
 "summary": {"en": "Software engineer building backend and full-stack applications: REST APIs in FastAPI and Spring Boot, microservices architectures, relational and document databases, containerized and delivered through CI/CD. Shipped a reusable backend platform end to end at Veolia, and cut an application's response time from 40 seconds to 5 at OCP.",
             "fr": "Ingénieur logiciel qui construit des applications backend et full-stack : API REST en FastAPI et Spring Boot, architectures microservices, bases relationnelles et documentaires, conteneurisées et livrées en CI/CD. Plateforme backend réutilisable livrée de bout en bout chez Veolia, et temps de réponse d'une application ramené de 40 secondes à 5 chez OCP."},
 "skills": {"en": [("Backend", "Python, FastAPI, Flask, Java, Spring Boot, REST API design, Redis, microservices"),
                   ("Frontend", "JavaScript, TypeScript, React.js, Next.js (API Routes, SSR), NextAuth, Tauri"),
                   ("Databases", "PostgreSQL, MySQL, MongoDB, SQL Server, SQL, data modeling"),
                   ("Delivery & testing", "Docker, Git, GitHub Actions, Azure DevOps, Azure, API testing")],
            "fr": [("Backend", "Python, FastAPI, Flask, Java, Spring Boot, conception d'API REST, Redis, microservices"),
                   ("Frontend", "JavaScript, TypeScript, React.js, Next.js (API Routes, SSR), NextAuth, Tauri"),
                   ("Bases de données", "PostgreSQL, MySQL, MongoDB, SQL Server, SQL, modélisation de données"),
                   ("Livraison & tests", "Docker, Git, GitHub Actions, Azure DevOps, Azure, tests d'API")]}},
}

# The job title carried by each employer, per CV. "Intern" appears nowhere.
JOB_TITLES = {
 "swe": {"veolia": {"en": "Software Engineer", "fr": "Ingénieur Logiciel"},
         "ocp":    {"en": "Software Engineer", "fr": "Ingénieur Logiciel"},
         "ava":    {"en": "Software Engineer (Freelance)", "fr": "Ingénieur Logiciel (Freelance)"},
         "corp":   {"en": "Full-Stack Developer", "fr": "Développeur Full-Stack"}},
 "*":   {"veolia": {"en": "AI Engineer", "fr": "Ingénieur IA"},
         "ocp":    {"en": "AI Engineer", "fr": "Ingénieur IA"},
         "ava":    {"en": "Backend & AI Developer (Freelance)", "fr": "Développeur Backend & IA (Freelance)"},
         "corp":   {"en": "Full-Stack Developer", "fr": "Développeur Full-Stack"}},
}

HEADINGS = {
 "en": {"edu": "EDUCATION", "exp": "PROFESSIONAL EXPERIENCE", "proj": "PROJECTS",
        "skills": "TECHNICAL SKILLS", "other": "LANGUAGES & CERTIFICATIONS"},
 "fr": {"edu": "FORMATION", "exp": "EXPÉRIENCE PROFESSIONNELLE", "proj": "PROJETS",
        "skills": "COMPÉTENCES TECHNIQUES", "other": "LANGUES & CERTIFICATIONS"},
}


# ---------------------------------------------------------------------------
# Assembly and rendering. Section order is the one asked for: education first,
# then experience, projects, skills, and languages/certifications last.
# ---------------------------------------------------------------------------
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FILE_ROLE = {"ai": "AI_Engineer", "mlops": "MLOps", "devops": "DevOps",
             "ds": "Data_Scientist", "de": "Data_Engineer", "swe": "Software_Engineer"}


def document(role: str, lang: str) -> dict:
    r, h, ME = ROLES[role], HEADINGS[lang], me()
    titles = JOB_TITLES.get(role, JOB_TITLES["*"])
    exp = []
    for key in ("veolia", "ocp", "ava", "corp"):
        company, dates, city = EMPLOYERS[key]
        exp.append({"heading": titles[key][lang], "org": company, "dates": dates,
                    "location": f"{city}, {COUNTRY[lang]}",
                    "bullets": EXP[role][lang][key]})
    return {
        "name": ME["name"],
        "headline": r["headline"][lang],
        "contact": dict(ME["contact"]),
        "summary": r["summary"][lang],
        "style": "cambria",
        "link_style": "label",
        "sections": [
            {"title": h["edu"], "kind": "education", "items": EDU[lang]},
            {"title": h["exp"], "kind": "experience", "items": exp},
            {"title": h["proj"], "kind": "projects", "items": PROJ[role][lang]},
            {"title": h["skills"], "kind": "skills",
             "groups": [{"label": a, "items": [b]} for a, b in r["skills"][lang]]},
            {"title": h["other"], "kind": "list",
             "lines": [f"{a} : {b}" if lang == "fr" else f"{a}: {b}"
                       for a, b in OTHER[lang]]},
        ],
    }


def build(out_dir: Path) -> list[dict]:
    """Render all twelve, and report the page count of each."""
    import cvrouter as cr
    from pipeline import config as pc
    from pipeline import tailor as T

    pcfg, cfg = pc.load(), cr.load_config()
    chrome, photo_cache = T.find_chrome(pcfg), {}
    out_dir.mkdir(parents=True, exist_ok=True)
    report = []
    for role in ROLES:
        for lang in ("en", "fr"):
            doc = T.no_em_dash(document(role, lang))
            stem = f"Souhaib_Garaaouch_{FILE_ROLE[role]}_{lang.upper()}"
            pdf = out_dir / f"{stem}.pdf"
            if lang not in photo_cache:
                photo_cache[lang] = T.photo_uri(pcfg, lang)
            pages, step = T.render_fitted(doc, lang, pdf, chrome, max_pages=1,
                                          photo=photo_cache[lang])
            (out_dir / f"{stem}.cv.json").write_text(
                json.dumps(doc, ensure_ascii=False, indent=1))
            problems = T.verify(pdf, doc, [], max_pages=1)
            report.append({"file": pdf.name, "role": role, "lang": lang,
                           "pages": pages, "density": step, "problems": problems})
    return report


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "out"
    for row in build(target):
        flag = "OK " if row["pages"] == 1 and not row["problems"] else "!! "
        print(f"  {flag}{row['pages']}p  densité {row['density']}  {row['file']}"
              + (f"   {row['problems']}" if row["problems"] else ""))
