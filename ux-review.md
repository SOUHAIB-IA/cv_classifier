# cv-router, revue UX

Faite le 5 octobre 2026 sur l'instance réelle, `127.0.0.1:8770`, 121 CV indexés,
5 174 offres en base. Navigateur piloté par Playwright, captures à 1280, 700 et
390 px.

## Avant de lire

**`docs/interface.md` n'existe pas.** Le document de référence est resté dans un
espace de travail temporaire et n'a jamais été versionné. J'ai travaillé sur
cette copie, dont les parties 2, 7 et 8 sont bien celles désignées comme
contraignantes. **À committer, sinon la prochaine revue n'aura pas de règle.**

**Les captures contiennent tes vraies données** : noms d'entreprises, offres,
refus, chemins de fichiers, ton nom, ton téléphone, ton email. Elles sont dans
`ux-review-shots/`. Ne les committe pas. Déplace-les ou efface-les après lecture.

**Un état n'a pas été capturé aujourd'hui** : `/` avec zéro CV indexé. Ton
instance en a 121, et le reproduire demande une copie jetable. Je le décris
d'après le gabarit et les essais des jours précédents, et je le signale au lieu
de prétendre l'avoir vu.

**Une analyse réelle a été lancée** (deux appels modèle sur ton abonnement) parce
que l'écran de résultat est le plus important du produit et qu'on ne peut pas le
juger sur un gabarit.

---

# 1. Les dix problèmes, du plus bloquant au moins

## 1. Le résultat d'analyse est en anglais

**Page** `/` · **Capture** `04-resultat-1280.png` · **Effort : moyen**

C'est le problème numéro un, loin devant tous les autres.

L'interface est en français. L'utilisateur colle une annonce française. Et tout
ce qu'il doit lire pour agir arrive en anglais :

> The ad is in French, and this is the French CV built around the data engineer
> role. It evidences Python, SQL, Spark/PySpark and Kafka…

> Python, SQL, Spark, pipelines, ETL, Docker and CI/CD are covered, but Airflow,
> dbt and AWS, three of the six named stack items, are absent.

> → Mirrors the ad's stack (Python, SQL, Spark) and the 'industrialiser les
> modèles' mission.

Les textes **suggérés** pour le CV sont bien en français, c'est le contenu du CV.
Mais chaque explication, chaque « pourquoi », les points de vigilance, le second
choix et la présélection sont en anglais. Un chercheur d'emploi non anglophone
reçoit un écran dont la totalité du raisonnement lui échappe.

**Ce qui rend le défaut réparable, et prouve qu'il est accidentel** : la fiche
d'une offre, `/job/{id}`, affiche le même genre de verdict **en français**
(`13-offre-1280.png`, « Pourquoi ce fit », « Pourquoi ce CV »). Les deux chemins
n'utilisent pas la même consigne modèle. Le pipeline fait déjà bien ce que
l'analyse directe fait mal.

**Le correctif** : aligner la consigne de `matcher.py` sur celle qui produit
déjà du français dans le pipeline. Ajouter une ligne explicite du type « Réponds
en français, sauf le texte suggéré pour le CV qui suit la langue de l'annonce. »
Puis relancer une analyse et vérifier.

## 2. Sur téléphone, Réglages est inatteignable

**Page** toutes · **Captures** `06-analyser-390.png`, `05-resultat-390.png`
· **Effort : petit**

À 390 px la barre affiche « CV Router · Analyser · Pipeline · Données · Canada »
et s'arrête là. **Réglages, Avis et la recherche sont hors écran.** La page entière
part en défilement horizontal, barre grise comprise en bas de l'écran.

La partie 7 du document annonçait « se tasse plutôt que de passer à la ligne ».
C'est plus grave que ça : on ne peut pas atteindre ses réglages depuis un
téléphone, sauf à découvrir qu'il faut faire glisser la page de côté.

**Le correctif** : `flex-wrap: wrap` sur `nav.top` et un `overflow-x: hidden` sur
le corps. Les liens passent sur deux lignes, la barre grandit, rien ne disparaît.
Aucun menu déroulant, aucune icône hamburger : six liens tiennent sur deux lignes.

## 3. Le résultat d'analyse ne mène à rien

**Page** `/` · **Capture** `04-resultat-1280.png` · **Effort : moyen**

Après le score, les mots-clés, sept modifications, les points de vigilance, le
second choix et l'accroche, la page s'arrête. Aucun bouton.

L'utilisateur sait quel CV envoyer et ce qu'il faut y changer. Il ne peut ni
l'ouvrir, ni le modifier, ni suivre cette candidature. Le chemin du fichier est
affiché en police à chasse fixe, non cliquable :

```
2-Diplome-Etudes-Terminees/Data-Engineering-Cloud/Souhaib_Garaaouch_Data_Engineer_FR.pdf
```

C'est un rapport, pas un outil de travail. Le moment où la personne est le plus
prête à agir est celui où on lui retire toute action.

**Le correctif** : une barre d'actions en bas du résultat, trois boutons.
« Ouvrir le CV » · « Montrer le fichier » · « Suivre cette candidature ».
Les deux premiers existent déjà ailleurs dans l'application.

## 4. « Tout effacer » au-dessus de 5 174 offres

**Page** `/data` · **Capture** `11-donnees-1280.png` · **Effort : petit**

Le bouton efface les filtres. Rien d'autre. Mais il s'appelle « Tout effacer »,
il est posé juste au-dessus d'un tableau annonçant « 5 174 OFFRES », et personne
ne clique dessus pour vérifier.

**Le correctif, mot pour mot** : `Tout effacer` → **`Effacer les filtres`**

## 5. Des clés de configuration affichées à l'utilisateur

**Page** `/canada` · **Capture** `12-canada-1280.png` · **Effort : petit**

Sous le champ de l'annonce :

> papier **letter** · 1 page préférée, 2 au maximum · lieu `city_country` ·
> autorisation de travail `omit` · diplôme `equivalence_line`
> ÉQUIVALENCE NON RENSEIGNÉE

`city_country`, `omit` et `equivalence_line` sont des clés de
`canada_rules.yaml`. C'est la vue de débogage du mainteneur, montrée telle quelle.

**Le correctif, mot pour mot** :

> Format lettre US · une page de préférence, deux au maximum · la ville et le
> pays sont indiqués, pas l'adresse · ton autorisation de travail n'est pas
> mentionnée · ton diplôme n'a pas d'équivalence renseignée

## 6. Des noms de fichiers et une commande dans l'interface

**Pages** `/pipeline` (Envoi automatique), `/settings` · **Captures**
`09-pipeline-auto-1280.png`, `10-reglages-1280.png` · **Effort : petit**

- « 4 réponses écrites par toi dans `profile.toml` »
- « une réponse que tu as écrite toi-même dans `profile.toml` »
- « elle a été lancée autrement qu'avec `python start.py` »

Un fichier et une commande que l'utilisateur n'a jamais vus et ne peut pas
atteindre depuis l'écran qui les nomme.

**Les correctifs, mot pour mot** :

| Avant | Après |
|---|---|
| `4 réponses écrites par toi dans profile.toml` | `4 réponses que tu as déjà écrites` |
| `une réponse que tu as écrite toi-même dans profile.toml` | `une réponse que tu as écrite toi-même` |
| `elle a été lancée autrement qu'avec python start.py` | `elle a été lancée par un autre programme, qui est le seul à pouvoir la relire` |

## 7. ATS, fit et pré-filtre ne sont jamais expliqués

**Pages** `/`, `/pipeline`, `/data`, `/job` · **Effort : petit**

Trois mots structurent toute l'application et aucun n'est défini là où il
apparaît. `/data` les affiche en en-têtes de colonne nus : `FIT`, `ATS`,
`PRÉ-FILTRE`. La fiche d'offre les affiche en gros dans le coin : `78 FIT`,
`85 ATS`. Un nombre sans échelle : 78, c'est bien ? 50, c'est mauvais ?

**Les correctifs, mot pour mot** :

| Terme | Remplacement, ou glose à ajouter une fois par page |
|---|---|
| `SCORE ATS ESTIMÉ` | `LISIBILITÉ PAR LES LOGICIELS DE TRI` |
| sous le score | `Les employeurs filtrent les CV avec un logiciel avant qu'un humain les lise. Au-dessus de 70, le tien passe sans problème.` |
| `FIT` (colonne, badge) | `CORRESPONDANCE` |
| `Fit moyen` | `Correspondance moyenne` |
| `pré-filtre` | `tri gratuit` |
| `écartée au pré-filtre` | `écartée avant lecture` |
| `HIGH` / `MEDIUM` / `LOW` | `PRIORITAIRE` / `UTILE` / `OPTIONNEL` |

## 8. Le même bouton change d'apparence selon la page

**Pages** `/` contre toutes les autres · **Captures** `02-analyser-1280.png`
contre `01-bienvenue-1280.png` · **Effort : petit**

`templates/portal.html:24` restyle **tous** les `button` de la page en primaire
bleu plein. C'est le même fork que celui des couleurs, corrigé sur `:root` et
oublié sur les boutons.

Conséquence visible : « Masquer », qui est une action de rejet, s'affiche comme
le bouton le plus important de la page d'accueil, alors qu'il est en contour
partout ailleurs. La règle `button[disabled]{cursor:progress}` y réintroduit
aussi la confusion entre désactivé et occupé, corrigée dans `app.css`.

**Le correctif** : supprimer le bloc `button{…}` de `portal.html` et mettre
`class="primary"` sur le seul bouton qui le mérite, celui qui l'a déjà.

## 9. Le bouton d'action est placé avant le champ sur lequel il agit

**Pages** `/canada`, `/job/{id}` · **Captures** `12-canada-1280.png`,
`13-offre-1280.png` · **Effort : moyen**

Sur Canada, « Adapter » et « Vérifier le CV source » sont **au-dessus** de
« Texte de l'offre ». On propose d'agir avant d'avoir montré où coller.

Même inversion sur la fiche d'offre : « Enregistrer et régénérer le PDF » est en
haut de la colonne, au-dessus des champs qu'il enregistre.

L'œil descend : entrée, puis action. Ici c'est action, puis entrée.

**Le correctif** : déplacer les boutons sous le champ. Aucun autre changement.

## 10. La page de bienvenue garde tout son attirail une fois terminée

**Page** `/bienvenue` · **Capture** `01-bienvenue-1280.png` · **Effort : moyen**

Les étapes 1 et 2 sont marquées « Fait », et affichent toujours l'intégralité de
leurs commandes : les cinq dossiers, le champ libre, le bouton « Lire mes CV ».
La page d'une mise en route achevée ressemble à une mise en route à faire.

Trois boutons bleus pleins s'empilent, « Ouvrir les réglages », « Lire mes CV »
et « Analyser une annonce », alors que deux sur trois ne concernent plus
personne. Aucune action ne domine, donc aucune ne guide.

Le « Fait » de l'étape 1 est à côté de son bouton, celui de l'étape 2 passe à la
ligne en dessous. Deux placements pour le même élément.

**Le correctif** : replier une étape terminée sur son titre et sa mention
« Fait ». Un lien « Modifier » la rouvre. Seule l'étape en cours garde son
bouton primaire ; les autres passent en contour.

---

# 2. Gains rapides, moins de dix minutes chacun

Uniquement du texte, aucun code de mise en page.

| Page | Avant | Après |
|---|---|---|
| `/data` | `Tout effacer` | `Effacer les filtres` |
| `/data` | `manual`, `greenhouse` en valeurs | `saisie à la main`, `Greenhouse` |
| `/` | `SCORE ATS ESTIMÉ` | `LISIBILITÉ PAR LES LOGICIELS DE TRI` |
| `/` | `HIGH` / `MEDIUM` / `LOW` | `PRIORITAIRE` / `UTILE` / `OPTIONNEL` |
| `/` | `PRÉSÉLECTION` + 5 chemins bruts | supprimer la carte, ou la replier sous `Comment ce CV a été choisi` |
| `/pipeline` | `dans profile.toml` | `que tu as déjà écrites` |
| `/pipeline` | `Fit minimum 0, ATS minimum 0` | `Aucun seuil : tout passe la barre pour l'instant` |
| `/settings` | `autrement qu'avec python start.py` | `par un autre programme, qui est le seul à pouvoir la relire` |
| `/canada` | la ligne de clés brutes | la phrase donnée au point 5 |
| `/canada` | fichiers `.cv.json` et `.changelog.txt` listés | ne montrer que le PDF et le DOCX |
| partout | `pré-filtre` | `tri gratuit` |

Trois autres, hors texte, tout aussi rapides :

- **`favicon.ico` renvoie 404** à chaque chargement, visible dans la console du
  navigateur. Un fichier de seize pixels le règle.
- **À 700 px la recherche perd son libellé** et il ne reste que « Ctrl K »
  (`07-analyser-700.png`), incompréhensible pour qui ne connaît pas le raccourci.
  Garder le mot « Rechercher ».
- **Les champs de `/settings` font tous 1 180 px de large**, y compris « Ton
  prénom » (`10-reglages-1280.png`). Un prénom dans un champ large comme l'écran
  dit à l'utilisateur qu'on attend un paragraphe. Limiter à la longueur attendue,
  en gardant les chemins larges.

---

# 3. Ce qui marche, et qu'il ne faut pas toucher

Cette liste existe pour qu'une prochaine refonte ne détruise pas ce qui a déjà
été gagné.

**L'entonnoir du pipeline** (`08-pipeline-1280.png`). Sept étapes, un compte
chacune, et surtout l'étiquette `AUTO` ou `TOI` sous chaque case. On sait d'un
coup d'œil ce que fait le système et ce qu'on doit faire. Les deux cases ambrées
marquent exactement là où on est attendu. C'est le meilleur élément de
l'application.

**« Comment ça marche »** sur la même page. Six étapes numérotées, en français,
qui définissent le jargon au passage. C'est le seul endroit où l'application
s'explique vraiment.

**Le bloc « Mode répétition »** de l'envoi automatique
(`09-pipeline-auto-1280.png`). Fond ambré, trois coches, et la phrase
« Rien ne part. » Sur la fonction la plus angoissante du produit, le ton est
exactement juste : il rassure en montrant les vérifications, pas en promettant.

**Les textes d'aide des réglages.** Chaque champ explique à quoi il sert et ce
qui se passe si on le laisse vide. « Tant qu'il est vide, rien n'est classé »
vaut mieux que n'importe quelle astérisque « obligatoire ».

**L'aperçu du PDF en direct** sur la fiche d'offre (`13-offre-1280.png`). On voit
le document réel pendant qu'on le modifie. Peu d'outils à ce prix font ça.

**Le choix du dossier par nombre de PDF** (`01-bienvenue-1280.png`). « 12 PDF »,
« 390 PDF », « aucun PDF » : c'est le compte qui désigne le bon dossier, pas le
nom. Un menu déroulant aurait caché l'information qui décide.

**Les états vides qui nomment l'action suivante**, et la distinction entre
« aucune offre » et « aucune offre ne correspond à ces filtres ».

**Le verdict en français sur la fiche d'offre.** « Pourquoi ce fit », « Pourquoi
ce CV », rédigés pour être lus. C'est le modèle à répliquer sur `/`, pas
l'inverse.

**Le système de jetons et ses contrastes mesurés.** Quatorze paires vérifiées par
un test qui relit `app.css`. Une refonte visuelle doit passer ce test, pas le
supprimer.

---

# 4. Ce que je n'ai pas fait

- **Aucun code modifié**, comme demandé.
- `/` avec zéro CV indexé : décrit, pas capturé, raison donnée plus haut.
- Les onglets `Graphiques` et `Activité` du pipeline : ouverts, non analysés en
  détail, rien d'alarmant n'y est apparu.
- La barre de navigation qui semble flotter au milieu de `04-resultat-1280.png`
  est un artefact de capture pleine page avec `position: sticky`, pas un défaut.
  Vérifié sur la capture d'écran visible `03-analyse-attente-1280.png`.
