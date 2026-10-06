# cv-router, revue UX, deuxième passage

Faite le 6 octobre 2026, sur le code du commit `be4f81a` (rien de non committé
hors `.claude/`), contre les dix problèmes de `ux-review.md`. Les captures sont
dans `ux-review-shots/review-2/`, **gitignorées, avec tes vraies données**.

## Comment j'ai mesuré

- Une instance du code actuel sur ton installation réelle (121 CV, 5 174 offres),
  lue sans clic qui écrive. Chrome piloté par son protocole, captures à 390,
  700 et 1280 px.
- Une copie jetable de `HEAD`, sans CV indexé, pour l'état que la première revue
  n'avait pas pu capturer : `/` avec zéro CV (`p8-accueil-bandeau-1280.png`).
- Un contrôle automatique du défilement horizontal : 7 pages, 3 largeurs, soit
  21 mesures de `scrollWidth` contre `clientWidth`.
- Sept suites de tests, toutes vertes, test de contraste compris.
- **Limite** : Playwright n'a pas pu servir, un autre Chrome tient son profil.
  Pour chaque ligne ci-dessous, « vu » veut dire que j'ai regardé la capture,
  « mesuré » que la preuve est un nombre ou un texte lu dans la page.

## Verdict

| # | Problème | Verdict |
|---|---|---|
| 1 | Résultat d'analyse en anglais | **Corrigé** |
| 2 | Réglages inatteignable sur téléphone | **Corrigé** |
| 3 | Le résultat ne mène à rien | **Corrigé** |
| 4 | « Tout effacer » au-dessus de 5 174 offres | **Corrigé** |
| 5 | Clés de configuration affichées | **Corrigé** |
| 6 | Fichiers et commande dans l'interface | **Corrigé en partie** |
| 7 | ATS, fit et pré-filtre jamais expliqués | **Corrigé en partie** |
| 8 | Le même bouton change d'apparence | **Corrigé** |
| 9 | Action placée avant son champ | **Corrigé**, avec un coût |
| 10 | Bienvenue garde son attirail | **Corrigé** |

Sept corrigés, deux corrigés en partie, aucun intact. Les deux « en partie »
sont des textes, pas de la mise en page.

---

## 1. Résultat d'analyse en anglais : corrigé

**Captures** `p1-analyse-annonce-fr-1280.png`, `p1-analyse-annonce-en-1280.png`
(prises le 5 octobre sur le code actuel de `matcher.py`, pas rejouées : chaque
rejeu coûte quatre appels modèle).

Deux analyses réelles, une annonce française et une anglaise. Dans les deux cas,
le choix du CV, la lisibilité, les « pourquoi » des modifications, les points de
vigilance, le second choix et la raison de la présélection sont en français. Le
texte à coller suit la langue du CV, l'accroche de lettre celle de l'annonce, ce
qui est voulu.

**Ce que la revue d'origine avait faux** : elle attribuait le français de la
fiche `/job/{id}` à une consigne différente. Il n'y en a qu'une, et le modèle
choisissait la langue au hasard. La règle explicite est ce qui rend le résultat
stable.

**Reste fragile** (pas un défaut de ce problème) : un appel sur trois a rendu
« model did not return JSON ». Voir les nouveaux constats.

## 2. Réglages inatteignable sur téléphone : corrigé

**Captures** `p2-reglages-390.png`, `p2-analyser-390.png` (vues).

À 390 px la barre passe sur deux lignes : Réglages, Avis et la recherche sont
visibles et cliquables. **Mesuré : aucun défilement horizontal sur les 21
combinaisons page et largeur.** La mesure a aussi trouvé un débordement que la
revue n'avait pas vu, `/pipeline` à 390 px (444 px de large), dû à une grille
aux colonnes de 420 px minimum. Corrigé au passage.

À 700 px, la recherche garde son libellé « Rechercher une offre », c'est le
raccourci qui disparaît.

## 3. Le résultat ne mène à rien : corrigé

**Capture** `p3-barre-actions-1280.png` (vue).

Trois boutons sous le résultat : « Ouvrir le CV », « Montrer le fichier »,
« Suivre cette candidature ». Les deux premiers fonctionnent sur le CV source,
le troisième enregistre l'offre sans nouvel appel modèle, en statut « à
trancher » (jamais « en préparation », qui ferait fabriquer un CV seul).

**Limite** : « Montrer le fichier » ouvre une fenêtre du gestionnaire de
fichiers, je ne l'ai pas déclenché. Modifier le CV n'est possible qu'après avoir
suivi la candidature, via « Voir la fiche ».

## 4. « Tout effacer » : corrigé

**Capture** `p4-p7-donnees-1280.png`. **Mesuré** dans le texte de la page : le
bouton s'appelle « Effacer les filtres ».

## 5. Clés de configuration affichées : corrigé

**Capture** `p5-p9-canada-1280.png`. **Mesuré** : la ligne est devenue une
phrase (« Format lettre US · une page de préférence, deux au maximum · la ville
et le pays sont indiqués… »), sans `city_country`, `omit` ni `equivalence_line`.
Les fichiers de travail `.cv.json` et `.changelog.txt` ne sont plus listés.

## 6. Fichiers et commande dans l'interface : corrigé en partie

**Captures** `p6-pipeline-auto-1280.png` (vue), `p6-reglages-1280.png`.

**Corrigé, les trois phrases citées** : « 4 réponses que tu as déjà écrites »,
« une réponse que tu as écrite toi-même », et « lancée par un autre programme,
qui est le seul à pouvoir la relire » (mesurée sur `/settings`).

**Pas corrigé, même défaut ailleurs** (lu dans le code et dans le texte des
pages) :
- `/settings` : « config.toml et pipeline.toml, que tu peux toujours ouvrir à
  la main », « profile.toml est rempli / est vide ».
- `/pipeline`, envoi automatique désactivé : « `enabled = true` dans la section
  `[autoapply]` de `pipeline.toml` », « ajoute une section `[[answers]]` »,
  « `rehearse = true` ».
- Fiche d'offre : « `rehearse = false` dans `pipeline.toml` », et un message
  « profile.toml est vide ».

Ces phrases sont plus défendables que celles corrigées (le fichier existe et
l'utilisateur peut l'ouvrir), mais elles restent des instructions de
développeur dans un produit pour quelqu'un qui n'en est pas un.

## 7. ATS, fit et pré-filtre jamais expliqués : corrigé en partie

**Captures** `p4-p7-donnees-1280.png`, `p7-fiche-1280.png`,
`p6-p7-pipeline-entonnoir-1280.png` (la fiche et l'envoi automatique vus).

**Corrigé** : « Correspondance » remplace « Fit » dans les colonnes et badges ;
« Tri gratuit » remplace « Pré-filtre » ; « écartée avant lecture » ; les
priorités sont « prioritaire / utile / optionnel » ; les sources sont lisibles
sur `/data` (« Greenhouse », « saisie à la main » dans la colonne et le menu) ;
la carte ATS de `/` est « Lisibilité par les logiciels de tri », avec la phrase
d'explication.

**Pas corrigé** :
- **ATS reste nu** sur `/data`, `/pipeline` et la fiche : la glose n'existe que
  sur `/`. Un « 57 ATS » sans échelle subsiste.
- **« fit » survit en minuscule** à côté de « Correspondance » : « Pourquoi ce
  fit » (fiche), « Score de fit minimum » et « Au-dessus de ce score de fit »
  (réglages), « score de fit » et « fit 40 à 49 » (graphiques), « fit ≥ 70 »,
  « décision … fit … ATS » (journal). Deux mots pour la même chose sur la même
  page.
- **La source brute** s'affiche encore sur la fiche : « DHM IT · frane · manual ».
  Le dictionnaire de traduction n'a été branché que sur `/data`.

## 8. Le même bouton change d'apparence : corrigé

**Capture** `p8-accueil-bandeau-1280.png` (vue). **Mesuré** : plus aucun bloc
`button { … }` dans les gabarits, et « Masquer » a un fond blanc, donc en
contour, comme sur les autres pages. « Reprendre » et « Lire mes CV » sont les
seuls éléments pleins de l'écran.

**Cette capture est aussi l'état « zéro CV » que la première revue n'avait pas
pu voir** : « Commençons par tes CV », le dossier, un seul bouton plein « Lire
mes CV », et la carte « Et si je n'ai qu'un seul CV ? ». Rien d'alarmant.

## 9. Action placée avant son champ : corrigé, avec un coût

**Captures** `p5-p9-canada-1280.png`, `p9-fiche-bas-1280.png` (vues).

Sur `/canada`, « Adapter » et « Vérifier le CV source » sont sous le texte de
l'offre. Sur la fiche, « Enregistrer et régénérer le PDF » est à la fin du
formulaire.

**Le coût** : ce formulaire fait environ 5 400 px de haut sur la fiche mesurée.
Pour enregistrer une seule correction, il faut maintenant descendre tout en
bas. Un bouton collant en bas de la carte garderait l'ordre de lecture et la
visibilité. Décision attendue, non appliquée.

## 10. Bienvenue garde son attirail : corrigé

**Captures** `p10-bienvenue-tout-fait-1280.png`,
`p10-bienvenue-etape2-1280.png`. Je n'ai regardé que les versions du lot
précédent (`after-batch4/`), prises sur le même code ; celles de ce dossier sont
rejouées et non relues.

Tout fait : trois lignes, titre, « Fait », « Modifier », au même endroit sur
chaque étape. Étape 2 non faite : l'étape 1 est repliée, la 2 est ouverte avec
le seul bouton plein, la 3 est en contour. « Modifier » rouvre et « Replier »
referme (testé dans le navigateur).

**Limite connue** : quand tout est fait, plus aucun bouton plein ne guide. La
sortie reste le lien « Passer cette page » et le menu.

---

# Ce qui marchait, et marche encore

Rien de ce que la revue d'origine demandait de ne pas toucher n'a régressé.

| Élément | Vérifié par |
|---|---|
| Entonnoir du pipeline, étiquettes AUTO et TOI, cases ambrées | vu, `p6-pipeline-auto-1280.png` |
| « Comment ça marche » du pipeline | lu dans le texte de la page |
| Bloc « Mode répétition », « Rien ne part » | vu, même capture |
| Textes d'aide des réglages | vus, `p2-reglages-390.png` |
| Aperçu PDF en direct sur la fiche | vu, `p7-fiche-1280.png` |
| Dossiers choisis par nombre de PDF | vu, capture `p10` de l'étape 2 |
| Verdict en français sur la fiche | vu, `p7-fiche-1280.png` |
| Contrastes mesurés par un test | `test_portable.py` vert |
| États vides qui nomment l'action suivante | non rejoué |

---

# Nouveaux constats

À traiter après les deux « en partie », par ordre d'importance.

1. **Une analyse peut échouer en affichant du bruit.** Un appel sur trois a
   renvoyé un JSON invalide. L'erreur qui s'affiche est le message interne
   (`model did not return JSON: {…}`, jusqu'à 300 caractères de la réponse du
   modèle, en anglais), d'après `portal.py`. Deux correctifs : un nouvel essai
   automatique dans `ask_json`, et un message en français qui dit quoi faire
   (« relance l'analyse »).
2. **Au moins cinq boutons bleus pleins « Ouvrir »** empilés dans le tableau
   « Candidatures éligibles » de l'envoi automatique (`p6-pipeline-auto`). C'est
   le même défaut que le n°8, à l'échelle d'un tableau : aucune ligne ne domine.
3. **La coche des étapes faites** est légèrement trop basse dans son cercle sur
   `/bienvenue`. Elle l'était avant ce passage.
4. **Le serveur sur 8770 est resté lancé avec l'ancien code Python.** Les
   gabarits et le JavaScript se rechargent seuls, pas les routes (favicon,
   « Ouvrir le CV », suivi). À redémarrer pour voir l'état réel.

---

# Ce que je n'ai pas fait

- Les analyses du problème 1 ne sont pas rejouées dans ce passage.
- « Montrer le fichier » et « Suivre cette candidature » n'ont pas été cliqués
  sur ton installation réelle : le suivi a été vérifié sur une copie jetable de
  ta base.
- Les onglets `Graphiques` et `Activité` : toujours non analysés.
- Les états vides, hors le cas « zéro CV ».
- Pas de passage en mode sombre : les contrastes sont couverts par le test, pas
  par une relecture à l'œil.
