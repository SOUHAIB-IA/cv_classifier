# cv-router: the interface, end to end

A reference for what the product is, what it does, and how every screen behaves.
Written from the code as it stands, not from intent. Where something is weak, it
says so.

---

# Part 1. What this is

## The purpose

A job seeker accumulates CVs. Different versions for different roles, different
languages, different years. When a job ad appears, three questions follow, and
answering them by hand takes an evening:

1. Which of my CVs is closest to this ad?
2. What do I change in it before sending?
3. Did I already apply here, and what happened?

cv-router answers all three. You paste an ad, it picks the CV, it lists the
edits, and it keeps the history.

## Who it is for

One person, on their own machine. Not a team, not a service. The whole
application is served at `127.0.0.1:8770` and there is no account, no sign-in
and no shared state.

The intended reader is **a job seeker who is not a developer**. That sentence is
the test every screen has to pass, and it is the one the product failed for a
long time: the first version answered "what do I do now" with an English error
message pointing at a terminal.

## What it does

| | |
|---|---|
| **Reads your collection** | Every PDF in a folder you choose, summarised once, kept locally |
| **Picks the right CV** | For a pasted ad, with a reason and a runner up |
| **Says what to change** | Section by section, with the current wording and the suggested one |
| **Scores the fit** | An ATS estimate, the keywords covered and the ones missing |
| **Files what arrives** | A watcher sorts new CVs from the download folder into your tree |
| **Follows the search** | Every posting seen, evaluated or applied to, searchable and exportable |
| **Prepares applications** | Tailors a CV to a posting, renders the PDF, fills an employer form |
| **Converts for Canada** | A separate studio: Canadian format, its own rules, its own output folder |

## What it refuses to do

Stated here because the interface says it too, and that honesty is part of the
design.

- It never submits an application on its own unless you have explicitly turned
  that on, and even then it stops at anything it would have to invent.
- It never answers a question about your work authorisation or your salary.
- It never solves a CAPTCHA.
- It sends nothing anywhere except the text of the ad and your CV, to the model
  provider you chose.

---

# Part 2. The design system

## Colour

Blue carries the product, green carries success. These are tokens in
`static/app.css`, defined twice, once per theme. Nothing in the application uses
a raw hex value.

| Token | Light | Dark | Role |
|---|---|---|---|
| `--bg` | `#f2f7fb` | `#0c1420` | The page |
| `--card` | `#ffffff` | `#141e2c` | Any raised surface |
| `--ink` | `#0c2338` | `#e6edf5` | Body text |
| `--muted` | `#4b5a6b` | `#9faec0` | Secondary text |
| `--line` | `#dce5ee` | `#263244` | A separator between two surfaces |
| `--line-strong` | `#7e8fa1` | `#5e6e84` | The boundary of a control |
| `--accent` | `#0a6fb0` | `#5aa9e6` | The product, primary actions |
| `--ok` | `#15803d` | `#6dbf86` | Success, done, high fit |
| `--warn` | `#8a5a1f` | `#dcab4f` | Needs attention |
| `--bad` | `#c02626` | `#ef9a9a` | Failure, destructive |
| `--info` | `#3b4fa0` | `#9aa7e8` | Neutral information |
| `--c1` to `--c5` | | | Chart series, in drawing order |

Each has a `-soft` counterpart for a tinted background.

**Two tokens exist because of a measurement, not a preference.** `--line` scores
1.20:1 against the page, which is enough to separate two panels and not enough
to show where an input begins, so `--line-strong` exists at 3:1 for anything a
person has to aim at. And the focus ring scores 1.00:1 against a button of the
same colour, which is why every ring is offset onto the page behind the control.

## Typography

System fonts only. No import, no CDN, no network call. The application works
with the cable unplugged, and a font request to a third party would break that
for a tool whose selling point is that nothing leaves your machine.

Body is 13 to 15px at 1.55 line height. Headings are small and uppercase with
wide tracking (`h2`), or 21 to 26px (`h1`). Monospace is reserved for paths,
identifiers and raw text, through `--mono`.

## Spacing, radius, motion

`--s1` to `--s6` (4 to 32px), `--r1` to `--r3` (6 to 10px).

Motion is named by intent, because one duration for everything is the
anti-pattern:

- `--t-press` 90ms, pointer feedback, has to feel instant
- `--t-state` 180ms, a control changing state
- `--t-reveal` 300ms, content arriving

All of it collapses under `prefers-reduced-motion: reduce`.

---

# Part 3. Navigation

## The bar

Sticky, on every page, same order everywhere.

```
CV Router | Analyser  Pipeline  Données  Canada  Réglages  Avis ↗ | [Rechercher une offre  Ctrl K] | (page control)
```

- The current page is marked with `.on`, in full-strength ink against muted.
- **Avis** is the only outbound link and carries an arrow, because a tab that
  leaves the application should say so before it is clicked, not after.
- The right end carries one control belonging to the current page: the live dot
  on Pipeline, the unsaved marker and Save button on Réglages.

## Ctrl+K

A search overlay from any page, over every posting ever seen. It exists because
four pages of navigation is not a way to find one company among thousands.

## The first-run strip

Below the bar, only while the setup is incomplete. Three steps, their state
derived from reality rather than from a stored wizard:

```
● Tes réglages   ○ Tes CV   ○ Ta première annonce     [Reprendre] [Masquer]
```

A strip and not a modal tour. **Masquer** is the design, not an afterthought: a
forced linear walkthrough is the documented anti-pattern.

---

# Part 4. The pages

## `/bienvenue` Welcome

**Shown when**: a first run opens it automatically. Reachable afterwards from
the strip.

**Contains**: one card explaining the product, then three numbered steps, each
carrying the button that settles it.

1. **Ton nom et ton modèle** links to Réglages
2. **Tes CV** holds the folder path and the **Lire mes CV** button inline, with
   its progress bar
3. **Ta première annonce** links to the analysis page

Each step shows `now` (blue left border, filled number) or `done` (green border,
a drawn tick). A link at the bottom skips the page.

**Honest weakness**: this page is 161 words over 12 sentences, with 81 of them
before the first button, and zero visuals. It tells rather than shows. Step 3 is
a link away rather than something you can finish here, so the page promises
three steps and delivers two. See Part 7.

## `/` Analyser

The home page, and it has two completely different states.

**When the index is empty**, it is a setup step, not an analysis page. The job
ad box is absent on purpose: with no CVs the matcher raises before any model
call, so offering the field would offer a guaranteed failure. The page shows the
CV folder, the **Lire mes CV** button, and a card answering the objection a
newcomer actually has: *Et si je n'ai qu'un seul CV ?*

**When the index has CVs**, it is the main tool:

```
Analyser une offre
3 CV lus. Colle une annonce, tu reçois le CV à envoyer et ce qu'il faut y changer.

[ Description du poste                      ]
[ textarea                                  ]
[ Trouver le meilleur CV ]
Le CV est choisi parmi les tiens, puis relu en entier. Compte une trentaine de secondes.
```

The result renders below, in this order, which is the order of what you do next:

1. **CV à envoyer**: the path, and why that one
2. **Score ATS estimé**: a number out of 100 with a bar and a reason
3. **Mots-clés couverts** and **Manquants ou trop faibles**: chips, green and red
4. **Modifications proposées**: per section, priority tag, the current wording
   struck through, the suggested one, and why
5. **Points de vigilance**, if any
6. **Second choix**: the runner up and its reason
7. **Accroche lettre de motivation**, if any
8. **Présélection**: which CVs were shortlisted and on what basis

## `/pipeline` Pipeline

The journey of a posting, and the page that already explained itself before any
of this work.

- A funnel of six counts, each labelled `AUTO` or `TOI`, so it is always clear
  which steps the system does and which ones you do
- Four tabs: **À faire**, **Graphiques**, **Envoi automatique**, **Activité**
- A **Comment ça marche** block spelling out the six steps in order
- Empty states that name the next action, not the absence

## `/data` Données

Every posting ever seen. Six filters, sortable columns, CSV export of exactly
what is on screen.

Two empty states, deliberately different: with filters set, *Aucune offre ne
correspond à ces filtres*; with none set, *Aucune offre pour l'instant. Le
pipeline en collecte quand tu le démarres, dans l'onglet Pipeline*. One sentence
for both would blame the reader for a filter they never set.

## `/job/{id}` One posting

Everything about a single ad: the evaluation, the proposed edits, the CV that
will be sent with a preview, and the application controls.

## `/settings` Réglages

Eight groups, rendered from a schema so adding a setting never touches the
template: **Pour commencer**, **Le cerveau**, **Comment postuler**, **Envoi
automatique**, **Quand agir**, **Où chercher**, **Ce que je cherche**, **Le CV**.

- Nothing is written until you press Save, and the button counts the changes
- A value that would break the application is refused before it is written
- The files keep their comments, because only the changed line is rewritten
- **Le cerveau** carries the nine providers with the address where each key is
  made, and a **Tester maintenant** button that makes one tiny real call
- **Pour commencer** carries the watcher panel: running or stopped, on which
  folder, with Start, Stop and Restart

## `/canada` Studio Canada

A separate module with its own rules file and its own output folder. Paste a
Canadian ad, get a Canadian-format resume and a list of what changed and why.

---

# Part 5. The flows

## First run

```
python start.py
  -> writes config.toml, pipeline.toml, profile.toml from the examples
  -> checks poppler and Chrome, and names the install command if one is missing
  -> does NOT start the watcher
  -> opens /bienvenue
```

The watcher stays down until the setup is complete. Without a model it can only
fail, once per PDF in the folder it watches, with a desktop notification each
time. That is not hypothetical: it is what the first user outside the author's
machine saw.

## Reading the collection

```
[ Lire mes CV ]
  -> POST /api/index/start, which runs indexer.py as a child process
  -> the page polls GET /api/index every 1.5s
  -> bar and count follow the indexer's own output, not an estimate
  -> done: the page reloads into the analysis state
  -> error: the reason, and how many CVs were kept
```

The count is parsed from lines the indexer already prints. Nothing waits on a
CSS transition to decide whether the button is still busy.

## Analysing an ad

```
paste -> [ Trouver le meilleur CV ] -> two model calls -> the result stack
```

## Applying

The pipeline collects, prefilters for free, evaluates the survivors, tailors a
CV for a high fit, and stops. You read, you adjust, you press send. Automatic
sending is off by default and, when on, stops at any field it would have to
invent, at any CAPTCHA, and at any ambiguous submit button.

---

# Part 6. Components

## Buttons

One system, three roles.

| Role | Look | Used for |
|---|---|---|
| `primary` | Filled accent | The one action a screen wants |
| default | Card background, `--line-strong` border | Everything else |
| `danger` | Red text and border | Destructive, never the default focus |
| `small` | Smaller padding and weight | Inline, beside a field |

States: rest, hover (brightness), active (1px down), focus-visible (ring,
offset), disabled, busy.

**Disabled and busy are not the same thing**, and the cursor says which:
`not-allowed` for disabled, `progress` for busy, plus a spinner drawn from
`currentColor`. Busy keeps the control announced and keeps its label.

## Feedback

- **Toast**, bottom right, 3.5 seconds, for the result of an action
- **Progress**, a bar with a count, for anything measured in minutes
- **Errors** carry `role="alert"` so they are announced and not only drawn
- **Empty states** name the next action rather than reporting absence

## Status language

Statuses are shown in French throughout (`à relire`, `à soumettre`, `envoyée`,
`entretien`, `refus`, `offre`), never as the English keys stored in the database.

---

# Part 7. Where this interface is still weak

Listed so nobody has to rediscover them.

1. **The welcome page tells instead of showing.** No preview of a result, so
   "il te dit quoi changer" stays abstract until after the setup is done. The
   fix is a clearly labelled example of an analysis, placed before the steps.
2. **Step 3 of the welcome page is not completable there.** It links away.
3. **Below roughly 700px the navigation bar crushes** rather than wrapping. The
   application stays usable, it does not stay presentable. It is desktop first
   by choice, but it should degrade rather than break.
4. **The analysis button waits 10 to 40 seconds** with a spinner and nothing
   else. It deserves the same background-job treatment as indexing: a real
   progress signal, and the ability to give up.
5. **The six tabs carry equal weight** with no indication of where a newcomer
   should start. The run strip mitigates this; it does not solve it.
6. **Some vocabulary is still the author's**: `fit`, `pré-filtre`, `ATS` appear
   without explanation outside the pages that define them.

---

# Part 8. Accessibility, and what is actually guaranteed

Not aspirations. These are enforced by a test that reads `static/app.css` and
recomputes the ratios, so a future palette change cannot quietly break them.

- **Text clears 4.5:1** in both themes, for every token pair in use
- **Control boundaries clear 3:1**, which is why `--line-strong` exists
- **Every operable control has a visible focus ring**, offset so it stays
  visible on a filled button
- **Tab order follows visual order**, with no traps
- **Errors are announced**, through `role="alert"` and `aria-live`
- **Reduced motion is respected** globally
- **No emoji as an icon.** The tick on a completed step is drawn in CSS, because
  an emoji renders differently on every machine and reads as a picture to a
  screen reader

## What is deliberately absent

No framework, no bundler, no npm, no build step. No external font, no CDN, no
analytics, no tracking pixel, no cookie. No modal onboarding tour. No gradient,
no glass, no hero illustration.

This is a tool somebody uses while job hunting, on a bad day, often after a
rejection. It should be quiet, legible and fast, and it should never look like
it is selling them something.
