#!/usr/bin/env python3
"""Twelve one-page CVs: six target roles, English and French.

Every line here comes from the 103 CVs already in the collection. Nothing is
invented: where a claim existed in only one or two sources and could not be
confirmed, it was dropped rather than reworded (the availability percentage and
the concurrent-user count, both removed on request).

A shared project carries a different TITLE and different bullets on each CV,
because a recruiter reading the DevOps CV should see deployment work, not a
recommendation engine with deployment bullets bolted on.
"""
from __future__ import annotations

ME = {
    "name": "Souhaib GARAAOUCH",
    "contact": {
        "email": "ada.lovelace@example.org",
        "phone": "+1 514 555 0199",
        "links": [
            {"label": "LinkedIn", "url": "https://www.linkedin.com/in/ada-lovelace"},
            {"label": "GitHub", "url": "https://github.com/SOUHAIB-IA"},
            {"label": "Portfolio", "url": "https://souhaib-garaaouch.vercel.app"},
        ],
    },
}

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

# Employers, dates and locations are identical on every CV. Only the job title
# on the software-engineering CV differs, and only the bullets are re-angled.
# The place is written in the CV's own language; AVA LUX carries none, because
# the job title already says Freelance and repeating it wastes the line.
PLACE = {"en": "Morocco", "fr": "Maroc"}
EMPLOYERS = {
    "veolia": ("Veolia Software Solutions", "02/2026 – 08/2026", True),
    "ocp":    ("OCP Group", "07/2025 – 09/2025", True),
    "ava":    ("AVA LUX", "06/2024 – 09/2024", False),
    "corp":   ("Corporate Software", "04/2023 – 06/2023", True),
}


# ---------------------------------------------------------------------------
# The same four jobs, told six ways. Each list is the bullets for that employer
# on that role's CV; the facts are the same, the lens is not.
# ---------------------------------------------------------------------------
EXP = {
"ai": {"en": {
  "veolia": ["Built a water-consumption anomaly detection pipeline combining an Isolation Forest and autoencoder ensemble with an LLM confirmation step.",
             "Designed and shipped a reusable AI backend platform (FastAPI, Docker) from prototype to production, owned end to end.",
             "Exposed inference through robust APIs and integrated the models into the existing business platform."],
  "ocp":    ["Developed a generative AI application for predictive maintenance, integrated with business tools through APIs.",
             "Built a controlled generation pipeline with LangChain and Pydantic producing structured, reliable JSON output.",
             "Diagnosed and resolved a critical performance issue: response time cut from 40 seconds to about 5 (−87%)."],
  "ava":    ["Integrated an AI analytics module into a Spring Boot supply-chain application.",
             "Designed backend APIs serving the analysis to the existing product."],
  "corp":   ["Full-stack development of a customer support platform (React.js, Spring Boot, MongoDB) in a microservices architecture."]},
       "fr": {
  "veolia": ["Conception d'un pipeline de détection d'anomalies de consommation d'eau combinant Isolation Forest, autoencodeur et une étape de confirmation par LLM.",
             "Industrialisation d'un PoC en plateforme backend IA réutilisable (FastAPI, Docker), de la maquette à la production.",
             "Exposition de l'inférence via des API robustes et intégration des modèles à la plateforme métier existante."],
  "ocp":    ["Développement d'une application d'IA générative pour la maintenance prédictive, intégrée aux outils métiers via API.",
             "Pipeline de génération contrôlée (LangChain, Pydantic) produisant des sorties JSON structurées et fiables en production.",
             "Diagnostic et résolution d'un problème critique de performance : temps de réponse ramené de 40 secondes à environ 5 (−87 %)."],
  "ava":    ["Intégration d'un module d'analyse par IA dans une application supply chain Spring Boot.",
             "Conception des API backend exposant l'analyse au produit existant."],
  "corp":   ["Développement full stack d'une plateforme de support client (React.js, Spring Boot, MongoDB) en architecture microservices."]}},

"mlops": {"en": {
  "veolia": ["Built and operated a complete CI/CD pipeline covering build, deployment, versioning and monitoring.",
             "Built an evaluation and gating pipeline (MLflow, Evidently AI, KS drift ≤ 0.15) continuously measuring model accuracy and reliability.",
             "Industrialized a prototype into a production-ready platform: Docker containerization, Git versioning, automated delivery."],
  "ocp":    ["Containerized the system with Docker and set up end-to-end observability with LangSmith for production tracking.",
             "Evaluated generated responses systematically and optimized inference latency from 40 seconds to about 5 (−87%)."],
  "ava":    ["Dockerized the analytics service and delivered it into the existing Spring Boot application."],
  "corp":   ["Microservices platform (Spring Boot, MongoDB, React.js) with API testing."]},
          "fr": {
  "veolia": ["Mise en place et exploitation d'un pipeline CI/CD complet : build, déploiement, versioning et monitoring.",
             "Pipeline d'évaluation et de gating (MLflow, Evidently AI, dérive KS ≤ 0,15) mesurant en continu la justesse et la fiabilité du modèle.",
             "Industrialisation d'un prototype en plateforme production-ready : conteneurisation Docker, versioning Git, livraison automatisée."],
  "ocp":    ["Conteneurisation Docker et mise en place d'une observabilité de bout en bout (LangSmith) pour le suivi en production.",
             "Évaluation systématique des réponses générées et optimisation de la latence d'inférence de 40 secondes à environ 5 (−87 %)."],
  "ava":    ["Conteneurisation du service d'analyse et livraison dans l'application Spring Boot existante."],
  "corp":   ["Plateforme en microservices (Spring Boot, MongoDB, React.js) avec tests d'API."]}},

"devops": {"en": {
  "veolia": ["Built and operated a CI/CD pipeline (build, deployment, versioning, monitoring) with Azure DevOps.",
             "Containerized the platform with Docker and set up Git versioning and automated delivery from prototype to production.",
             "Put monitoring in place so regressions were caught in the pipeline rather than in production."],
  "ocp":    ["Containerized the application with Docker and set up application monitoring for production tracking."],
  "ava":    ["Dockerized the analytics service and integrated it into the delivery chain of a Spring Boot application."],
  "corp":   ["Microservices deployment of a customer support platform (Spring Boot, MongoDB, React.js), with API testing."]},
           "fr": {
  "veolia": ["Mise en place et exploitation d'un pipeline CI/CD (build, déploiement, versioning, monitoring) sous Azure DevOps.",
             "Conteneurisation Docker de la plateforme, versioning Git et livraison automatisée, du prototype à la production.",
             "Mise en place du monitoring afin que les régressions soient détectées dans le pipeline et non en production."],
  "ocp":    ["Conteneurisation Docker de l'application et monitoring applicatif pour le suivi en production."],
  "ava":    ["Conteneurisation du service d'analyse et intégration à la chaîne de livraison d'une application Spring Boot."],
  "corp":   ["Déploiement en microservices d'une plateforme de support client (Spring Boot, MongoDB, React.js), avec tests d'API."]}},

"ds": {"en": {
  "veolia": ["Designed an anomaly detection approach for water consumption: Isolation Forest and autoencoder ensemble, with an LLM confirmation step to cut false positives.",
             "Measured model accuracy and reliability continuously (MLflow, Evidently AI, KS drift ≤ 0.15).",
             "Prepared and enriched the underlying data: collection, processing, feature enrichment."],
  "ocp":    ["Extracted and prepared historical data through SQL to enrich the generation context.",
             "Evaluated the quality and reliability of generated responses systematically with LangSmith."],
  "ava":    ["Built a Python data model analysing key operational metrics to support logistics decisions."],
  "corp":   ["Full-stack development of a customer support platform (React.js, Spring Boot, MongoDB)."]},
       "fr": {
  "veolia": ["Conception d'une approche de détection d'anomalies de consommation d'eau : ensemble Isolation Forest et autoencodeur, avec confirmation par LLM pour réduire les faux positifs.",
             "Mesure continue de la justesse et de la fiabilité du modèle (MLflow, Evidently AI, dérive KS ≤ 0,15).",
             "Préparation et enrichissement des données sous-jacentes : collecte, traitement, enrichissement des variables."],
  "ocp":    ["Extraction et préparation de données historiques par requêtes SQL pour enrichir le contexte de génération.",
             "Évaluation systématique de la qualité et de la fiabilité des réponses générées avec LangSmith."],
  "ava":    ["Construction d'un modèle de données Python analysant les indicateurs opérationnels clés pour la décision logistique."],
  "corp":   ["Développement full stack d'une plateforme de support client (React.js, Spring Boot, MongoDB)."]}},

"de": {"en": {
  "veolia": ["Designed and developed a data pipeline (collection, processing, enrichment) feeding water-consumption anomaly detection.",
             "Built the delivery pipeline around it: containerization, versioning, automated deployment and monitoring.",
             "Implemented business-rule controls on the processed data to keep it reliable downstream."],
  "ocp":    ["Wrote and optimized SQL queries to extract and prepare historical data feeding the application."],
  "ava":    ["Built ingestion and transformation pipelines (Python, Pandas, SQL) consolidating heterogeneous sources into a data warehouse.",
             "Deployed the data flows on Azure, containerized with Docker."],
  "corp":   ["Backend services over MongoDB and MySQL in a microservices architecture."]},
      "fr": {
  "veolia": ["Conception et développement d'un pipeline de données (collecte, traitement, enrichissement) alimentant la détection d'anomalies de consommation d'eau.",
             "Mise en place de la chaîne de livraison associée : conteneurisation, versioning, déploiement automatisé et monitoring.",
             "Implémentation de contrôles de règles métier sur les données traitées pour en garantir la fiabilité en aval."],
  "ocp":    ["Rédaction et optimisation de requêtes SQL pour extraire et préparer les données historiques alimentant l'application."],
  "ava":    ["Développement de pipelines d'ingestion et de transformation (Python, Pandas, SQL) consolidant des sources hétérogènes vers un Data Warehouse.",
             "Mise en production des flux de données sur Azure, conteneurisés avec Docker."],
  "corp":   ["Services backend sur MongoDB et MySQL en architecture microservices."]}},

"swe": {"en": {
  "veolia": ["Designed and shipped a reusable backend platform (FastAPI, Docker) from prototype to production, owned end to end.",
             "Designed robust APIs and containerized the service, with Git versioning and automated delivery.",
             "Implemented business-rule controls to keep processing correct and reliable."],
  "ocp":    ["Built a backend application integrating generation into an existing data platform, exposed through APIs.",
             "Wrote and optimized SQL queries; cut response time from 40 seconds to about 5 (−87%)."],
  "ava":    ["Designed Java Spring Boot backend APIs for logistics data processing and analysis.",
             "Containerized the service with Docker and integrated it into the existing application."],
  "corp":   ["Full-stack development of a customer support platform (React.js, Spring Boot, MongoDB) in a microservices architecture, with API testing."]},
       "fr": {
  "veolia": ["Conception et livraison d'une plateforme backend réutilisable (FastAPI, Docker), du prototype à la production, portée de bout en bout.",
             "Conception d'API robustes et conteneurisation du service, avec versioning Git et livraison automatisée.",
             "Implémentation de contrôles de règles métier garantissant l'exactitude et la fiabilité des traitements."],
  "ocp":    ["Développement d'une application backend intégrant la génération à une plateforme de données existante, exposée via API.",
             "Rédaction et optimisation de requêtes SQL ; temps de réponse ramené de 40 secondes à environ 5 (−87 %)."],
  "ava":    ["Conception d'API backend Java Spring Boot pour le traitement et l'analyse de données logistiques.",
             "Conteneurisation du service avec Docker et intégration à l'application existante."],
  "corp":   ["Développement full stack d'une plateforme de support client (React.js, Spring Boot, MongoDB) en architecture microservices, avec tests d'API."]}},
}


# ---------------------------------------------------------------------------
# Projects. A shared project gets its own title per role, not the same heading
# with different bullets: the title is the first thing read, and on the DevOps
# CV it should say deployment, not recommendation.
# Order inside each list is the order on the page.
# ---------------------------------------------------------------------------
P = lambda h, org, b: {"heading": h, "org": org, "dates": "", "location": "", "bullets": b}

PROJ = {
"ai": {"en": [
  P("Multi-agent documentation generation system", "Python, LangChain, LangGraph, Tauri, Next.js",
    ["Specialised agents orchestrated to generate technical documentation from source code, with a desktop Mission Control interface and peer-review validation."]),
  P("Production recommendation engine integration", "Next.js, Flask, Supabase, Azure",
    ["Python recommendation engine exposed as a Flask API and orchestrated from Next.js routes, with NextAuth authentication."]),
  P("Plant disease classifier served through an API", "Deep Learning, Flask, Microservices, RAG",
    ["Ensemble of pre-trained CNNs served behind REST APIs, with a RAG pipeline producing treatment recommendations."]),
  P("Low-latency inference service", "Python, FastAPI, Redis",
    ["REST inference API for agricultural decision support, with caching layers and load testing to hold latency down under high request volume."]),
  P("ML model deployment — MoroccoAI InnovAI Hackathon, Top 4", "2024 MoroccoAI Annual Conference",
    ["Built the APIs and deployed the backend and the ML models for the team's system; top 4 of more than 50 teams."])],
       "fr": [
  P("Système multi-agents de génération documentaire", "Python, LangChain, LangGraph, Tauri, Next.js",
    ["Agents spécialisés orchestrés pour générer la documentation technique à partir du code source, avec interface desktop Mission Control et validation par revue."]),
  P("Intégration d'un moteur de recommandation en production", "Next.js, Flask, Supabase, Azure",
    ["Moteur de recommandation Python exposé en API Flask et orchestré depuis les routes Next.js, avec authentification NextAuth."]),
  P("Classifieur de maladies des plantes exposé en API", "Deep Learning, Flask, Microservices, RAG",
    ["Ensemble de CNN pré-entraînés servis derrière des API REST, avec un pipeline RAG produisant les recommandations de traitement."]),
  P("Service d'inférence à faible latence", "Python, FastAPI, Redis",
    ["API REST d'inférence pour l'aide à la décision agricole, avec couches de cache et tests de charge pour tenir la latence à fort volume."]),
  P("Déploiement de modèles ML — Hackathon MoroccoAI InnovAI, Top 4", "MoroccoAI Annual Conference 2024",
    ["Développement des API et déploiement du backend et des modèles ML du système de l'équipe ; top 4 parmi plus de 50 équipes."])]},

"mlops": {"en": [
  P("Reusable industrialization template for AI services", "Cookiecutter, Python, FastAPI, Docker, Azure DevOps",
    ["Internal tool bootstrapping a new AI service with CI/CD, MLOps components and authentication already wired, cutting setup time."]),
  P("Training and deployment pipelines on Dataiku DSS", "Dataiku, Apache Spark, Python, CRISP-DM",
    ["ETL and ML pipelines for failure prediction (NASA Turbofan), with model versioning and scheduled retraining."]),
  P("Model serving service", "Python, FastAPI, Redis",
    ["Inference service with caching layers, load-tested and tuned to keep response latency stable under sustained request volume."])],
          "fr": [
  P("Template réutilisable d'industrialisation de services IA", "Cookiecutter, Python, FastAPI, Docker, Azure DevOps",
    ["Outil interne amorçant un nouveau service IA avec CI/CD, composants MLOps et authentification déjà câblés, réduisant le temps de mise en place."]),
  P("Pipelines d'entraînement et de déploiement sur Dataiku DSS", "Dataiku, Apache Spark, Python, CRISP-DM",
    ["Pipelines ETL et ML de prédiction de pannes (NASA Turbofan), avec versioning des modèles et réentraînement planifié."]),
  P("Service de serving de modèles", "Python, FastAPI, Redis",
    ["Service d'inférence avec couches de cache, soumis à des tests de charge et ajusté pour maintenir la latence sous un volume soutenu."])]},

"devops": {"en": [
  P("Cloud deployment of a web application", "Azure, GitHub Actions, Next.js, Flask",
    ["Continuous deployment to Azure through GitHub Actions, service-oriented architecture and NextAuth authentication."]),
  P("Reusable CI/CD foundation for AI services", "Cookiecutter, Docker, Azure DevOps",
    ["Template shipping CI/CD, MLOps components and authentication pre-wired, so a new service starts from a working delivery chain."]),
  P("Microservices architecture and resilience", "Microservices, Flask, REST",
    ["Computer-vision models exposed as REST services behind load balancing and redundancy, consumed by a mobile client with a caching strategy."]),
  P("API performance tuning and load testing", "Python, FastAPI, Redis",
    ["Data-structure and caching optimizations, then load testing and tuning to hold response time under high request volume."]),
  P("Infrastructure and backend deployment — MoroccoAI Hackathon, Top 4", "2024 MoroccoAI Annual Conference",
    ["Owned DevOps and cloud infrastructure: API delivery, backend and ML model deployment, monitoring; top 4 of more than 50 teams."])],
           "fr": [
  P("Déploiement cloud d'une application web", "Azure, GitHub Actions, Next.js, Flask",
    ["Déploiement continu sur Azure via GitHub Actions, architecture orientée services et authentification NextAuth."]),
  P("Socle CI/CD réutilisable pour services IA", "Cookiecutter, Docker, Azure DevOps",
    ["Template livrant CI/CD, composants MLOps et authentification pré-câblés, pour qu'un nouveau service démarre sur une chaîne de livraison fonctionnelle."]),
  P("Architecture microservices et résilience", "Microservices, Flask, REST",
    ["Modèles de vision exposés en services REST derrière équilibrage de charge et redondance, consommés par un client mobile avec stratégie de cache."]),
  P("Optimisation et tests de charge d'une API", "Python, FastAPI, Redis",
    ["Optimisations de structures de données et de cache, puis tests de charge et ajustements pour tenir le temps de réponse à fort volume."]),
  P("Infrastructure et déploiement backend — Hackathon MoroccoAI, Top 4", "MoroccoAI Annual Conference 2024",
    ["Responsable infrastructure DevOps et cloud : livraison des API, déploiement du backend et des modèles ML, monitoring ; top 4 parmi plus de 50 équipes."])]},

"ds": {"en": [
  P("Optimal crop type prediction — research project", "Machine Learning, CRISP-DM, Python",
    ["Full data science lifecycle from business understanding to feature engineering and modelling, on soil composition and weather data.",
     "Methodology, model evaluation and contributions written up in a scientific paper."]),
  P("Anomaly detection on financial transactions", "PySpark, MLlib, Python",
    ["Transaction data analysed to identify potentially fraudulent activity, with machine learning models improving detection accuracy."]),
  P("Content-based recommendation system", "Python, Flask, Next.js, Supabase",
    ["Recommendation engine built and evaluated, then exposed through a Flask API to a web front end."]),
  P("Plant disease classification by transfer learning", "Deep Learning, CNNs, Python",
    ["Several pre-trained CNN architectures trained and compared for a mobile plant disease classifier."]),
  P("ML modelling — MoroccoAI InnovAI Hackathon, Top 4", "2024 MoroccoAI Annual Conference",
    ["Built and deployed the team's ML models under hackathon constraints; top 4 of more than 50 teams."])],
       "fr": [
  P("Prédiction du type de culture optimal — projet de recherche", "Machine Learning, CRISP-DM, Python",
    ["Cycle complet de data science, de la compréhension métier à l'ingénierie de variables et à la modélisation, sur données de sol et météo.",
     "Méthodologie, évaluation des modèles et contributions publiées dans un article scientifique."]),
  P("Détection d'anomalies sur transactions financières", "PySpark, MLlib, Python",
    ["Analyse des données de transactions pour identifier les activités potentiellement frauduleuses, avec des modèles améliorant la précision de détection."]),
  P("Système de recommandation par filtrage de contenu", "Python, Flask, Next.js, Supabase",
    ["Moteur de recommandation construit et évalué, puis exposé via une API Flask à une interface web."]),
  P("Classification de maladies des plantes par transfer learning", "Deep Learning, CNN, Python",
    ["Entraînement et comparaison de plusieurs architectures CNN pré-entraînées pour un classifieur mobile."]),
  P("Modélisation ML — Hackathon MoroccoAI InnovAI, Top 4", "MoroccoAI Annual Conference 2024",
    ["Construction et déploiement des modèles ML de l'équipe sous contrainte de hackathon ; top 4 parmi plus de 50 équipes."])]},

"de": {"en": [
  P("Decision-support data warehouse", "SQL Server, SSMS, ETL, Power BI",
    ["Designed and modelled a star-schema warehouse for user-engagement analysis on a tourism website, with the ETL feeding it."]),
  P("ETL pipeline and real-time sensor streams", "Dataiku, Apache Spark, Kafka, Python",
    ["ETL pipelines on Dataiku DSS for failure prediction (NASA Turbofan), and cleaning and structuring of real-time IoT streams for time-series modelling."]),
  P("Real-time ingestion and processing of financial transactions", "PySpark, MLlib, Python",
    ["Transaction stream processed as it arrives and analysed to identify potentially fraudulent activity."])],
      "fr": [
  P("Entrepôt de données décisionnel", "SQL Server, SSMS, ETL, Power BI",
    ["Conception et modélisation d'un entrepôt en schéma en étoile pour l'analyse de l'engagement utilisateur d'un site touristique, avec l'ETL qui l'alimente."]),
  P("Pipeline ETL et flux capteurs temps réel", "Dataiku, Apache Spark, Kafka, Python",
    ["Pipelines ETL sur Dataiku DSS pour la prédiction de pannes (NASA Turbofan), et nettoyage et structuration de flux IoT temps réel pour la modélisation de séries temporelles."]),
  P("Ingestion et traitement temps réel de transactions financières", "PySpark, MLlib, Python",
    ["Flux de transactions traité au fil de l'eau et analysé pour identifier les activités potentiellement frauduleuses."])]},

"swe": {"en": [
  P("Full-stack web application", "Next.js, NextAuth, Flask, Supabase, Azure",
    ["Next.js front end with API Routes and server-side rendering, NextAuth authentication, a Python service behind it, deployed to Azure."]),
  P("Optimized REST API", "Python, FastAPI, Redis",
    ["REST API designed for low latency: data-structure optimizations, caching layers, then load testing and tuning under high request volume."]),
  P("Desktop application with a multi-agent backend", "Tauri, Next.js, Python, LangChain",
    ["Native desktop interface (Mission Control) over a multi-agent documentation generator, with a peer-review validation step."]),
  P("Distributed platform and mobile client", "Microservices, Flask, REST, Mobile",
    ["Microservices architecture exposing models through REST APIs, with a mobile client consuming them and a caching strategy, behind load balancing and redundancy."])],
       "fr": [
  P("Application web full-stack", "Next.js, NextAuth, Flask, Supabase, Azure",
    ["Frontend Next.js avec API Routes et rendu côté serveur, authentification NextAuth, service Python en arrière-plan, déployé sur Azure."]),
  P("API REST optimisée", "Python, FastAPI, Redis",
    ["API REST conçue pour la faible latence : optimisations de structures de données, couches de cache, puis tests de charge et ajustements à fort volume."]),
  P("Application desktop avec backend multi-agents", "Tauri, Next.js, Python, LangChain",
    ["Interface desktop native (Mission Control) au-dessus d'un générateur de documentation multi-agents, avec étape de validation par revue."]),
  P("Plateforme distribuée et client mobile", "Microservices, Flask, REST, Mobile",
    ["Architecture microservices exposant les modèles via API REST, avec client mobile et stratégie de cache, derrière équilibrage de charge et redondance."])]},
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
 "summary": {"en": "AI engineer who takes models to production: anomaly detection ensembles, LLM applications with controlled structured output, and inference exposed through robust APIs. Built and shipped an AI backend platform end to end during an engineering internship at Veolia, and cut a generative application's response time by 87% at OCP.",
             "fr": "Ingénieur IA qui mène les modèles jusqu'en production : ensembles de détection d'anomalies, applications LLM à sortie structurée contrôlée, inférence exposée via des API robustes. Plateforme backend IA conçue et livrée de bout en bout chez Veolia, et temps de réponse d'une application générative réduit de 87 % chez OCP."},
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
 "summary": {"en": "MLOps engineer who industrializes models: complete CI/CD covering build, deployment, versioning and monitoring, with continuous evaluation and gating on drift. Built a reusable template that bootstraps a new AI service with its delivery chain already wired.",
             "fr": "Ingénieur MLOps qui industrialise les modèles : CI/CD complet couvrant build, déploiement, versioning et monitoring, avec évaluation continue et gating sur la dérive. Auteur d'un template réutilisable amorçant un service IA avec sa chaîne de livraison déjà câblée."},
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
 "summary": {"en": "DevOps engineer who builds and runs delivery chains: CI/CD covering build, deployment, versioning and monitoring, Docker containerization and continuous deployment to Azure. Led DevOps and cloud infrastructure for a top-4 team at the 2024 MoroccoAI hackathon.",
             "fr": "Ingénieur DevOps qui construit et exploite des chaînes de livraison : CI/CD couvrant build, déploiement, versioning et monitoring, conteneurisation Docker et déploiement continu sur Azure. Responsable infrastructure DevOps et cloud d'une équipe classée top 4 au hackathon MoroccoAI 2024."},
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
 "summary": {"en": "Data scientist who runs the full cycle: business understanding, feature engineering, model choice and evaluation, through to the reading a business can act on. Designed an anomaly detection approach for water consumption at Veolia, and published a research project on optimal crop prediction as a scientific paper.",
             "fr": "Data scientist qui mène le cycle complet : compréhension métier, ingénierie de variables, choix et évaluation des modèles, jusqu'à la lecture exploitable par le métier. Conception d'une approche de détection d'anomalies de consommation d'eau chez Veolia, et projet de recherche sur la prédiction de culture optimale publié dans un article scientifique."},
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
 "summary": {"en": "Data engineer who builds the pipelines models depend on: ingestion, transformation and enrichment from heterogeneous sources into a warehouse, batch and real-time, with the delivery chain around them. Built the data pipeline behind water-consumption anomaly detection at Veolia.",
             "fr": "Data engineer qui construit les pipelines dont dépendent les modèles : ingestion, transformation et enrichissement de sources hétérogènes vers un entrepôt, en batch et en temps réel, avec la chaîne de livraison associée. Auteur du pipeline de données derrière la détection d'anomalies de consommation d'eau chez Veolia."},
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
 "summary": {"en": "Software engineer building backend and full-stack applications: REST APIs in FastAPI and Spring Boot, microservices architectures, relational and document databases, containerized and delivered through CI/CD. Shipped a reusable backend platform end to end at Veolia.",
             "fr": "Ingénieur logiciel qui construit des applications backend et full-stack : API REST en FastAPI et Spring Boot, architectures microservices, bases relationnelles et documentaires, conteneurisées et livrées en CI/CD. Plateforme backend réutilisable livrée de bout en bout chez Veolia."},
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
    r, h = ROLES[role], HEADINGS[lang]
    titles = JOB_TITLES.get(role, JOB_TITLES["*"])
    exp = []
    for key in ("veolia", "ocp", "ava", "corp"):
        company, dates, in_country = EMPLOYERS[key]
        exp.append({"heading": titles[key][lang], "org": company, "dates": dates,
                    "location": PLACE[lang] if in_country else "",
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
