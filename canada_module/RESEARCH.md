# Canadian resume conventions — what the sources actually say

Research done 2026-10-01 for the Canada Resume Studio module. Every claim below
carries its source and a confidence level, because the sources do not all agree
and some of them are not authorities at all.

## How I ranked the sources

| Tier | What it is | Weight |
|---|---|---|
| **A — government** | Job Bank (ESDC), Canada.ca, Québec.ca, Office québécois de la langue française, Portail linguistique du Canada | binding on content rules (what to leave out), silent on layout |
| **B — university career centres** | UBC, U of T Mississauga | the practical layout and ATS guidance |
| **C — ATS vendor documentation** | Greenhouse support docs, Workday admin guide | the only primary source on what actually breaks a parser |
| **D — commercial resume blogs** | the links in the original brief (airesume.guru, resumegeni, rankresume.io, cvailor, rezume.ca, canadianow, cvmove) | used only to generate hypotheses, never as evidence |

The brief's baseline came from tier D. Most of it holds up. Five points do not,
and they are in **Corrections** below.

## Confirmed

| Claim | Verdict | Source |
|---|---|---|
| 1–2 pages, reverse-chronological | **Confirmed by four tier-A/B sources.** Job Bank: "Limit your resume to two pages." Québec.ca: "Keep it short (1 to 2 pages)." OQLF: « Le curriculum vitæ devrait se limiter à deux pages. » UBC: one page preferred, two if experience is extensive | A, B |
| No photo | **Confirmed.** Job Bank: a photo "is not the norm in Canada. It can actually lower your chances of obtaining a position." OQLF: ne pas ajouter « sa photo au curriculum vitæ, sauf sur demande » | A |
| Omit age, DOB, marital status, nationality, SIN | **Confirmed verbatim.** Job Bank: "leave out any personal details such as age, weight, height, marital status, religious preference, political views" and "never include your Social Insurance Number". OQLF excludes « le numéro d'assurance sociale; l'âge; la date de naissance; l'état matrimonial […] la nationalité ». U of T Mississauga adds **visa status** to that list | A, B |
| No References section | **Confirmed by all three.** Job Bank: "Keep references on a separate sheet and provide them only when they are specifically requested." OQLF: « il est donc inutile de les inclure ». UTM lists "Including references" under what to avoid | A, B |
| Single column, no tables, no headers/footers, no graphics | **Confirmed — but by tier C, not by Canada.** Greenhouse's own parse-failure doc names: graphics and photos, image-based resumes, "complex resumes with tables, headers, and footers", contact details "in the header, footer, or text box", and "a columned layout". Workday: "use resumes that don't have images or image-based styles". UTM independently warns that tables or columns "can cause issues for employers who use Automated Tracking Systems (ATS) or screen readers" | B, C |
| Standard fonts, 10–12 pt | **Confirmed.** UBC: "10-12 pt", one font throughout, from Calibri / Times New Roman / Arial / Verdana / Cambria / Garamond / Book Antiqua / Trebuchet MS. UTM: 11–12 pt, margins 3/4" to 1" | B |
| Results-oriented bullets, no "Responsible for" | **Confirmed in spirit.** Job Bank prescribes "persuasive verbs such as handled, managed, led, developed, increased, accomplished, leveraged" and caps each section at **5–7 bullet points** — a concrete number worth linting | A |
| Third person, never "I" | **New rule, tier A.** Job Bank: "Do not use 'I,' 'my,' or 'me' — write your resume in the third person." Not in the original baseline; now lintable | A |

## Corrections to the baseline

### 1. Canadian spelling is -ize and -yze, not -ise and -yse

The brief left this open ("analyse/analyze: check what is actually preferred").
The answer is **analyze, organize, optimize**. The Portail linguistique du
Canada's comparison table puts Canadian English with the American forms on this
axis and with the British forms on `-our` and `-re`:

| Axis | Canadian | British | American |
|---|---|---|---|
| `-our` | colo**ur**, labo**ur**, behavio**ur** | same | color, labor |
| `-re` | cent**re**, fib**re**, met**re** | same | center, fiber |
| `-ize` / `-yze` | organi**ze**, analy**ze**, paraly**ze** | organise, analyse | same as Canadian |
| `-ce` noun / `-se` verb | defen**ce**, licen**ce** (noun) / licen**se** (verb), practi**ce** (noun) / practi**se** (verb) | same | defense, license (both) |
| doubled consonant | travel**l**ed, label**l**ed, model**l**ing | same | traveled, modeling |
| silent e | judgment, acknowledgement, likeable, aging | judgement, ageing | judgment, acknowledgment |

Two consequences for my CVs. Nothing has to change in `optimize`,
`containerize`, `prioritize`, `standardize` — they are already Canadian. And
`programme` would be **wrong**: Canadian English uses `program`. The real
substitutions are `color → colour`, `behavior → behaviour`,
`center → centre`, `modeling → modelling`, `labeled → labelled`,
`defense → defence`, plus the British forms if any crept in
(`analyse → analyze`, `organise → organize`).

`modeling → modelling` matters: "data modeling" is in my Data Engineer and
Software Engineer skills lines today.

### 2. An ECA number does not belong on an employment resume

The brief said to "add your ECA reference number or state the Canadian
equivalent". An **Educational Credential Assessment is an immigration
instrument**: IRCC "uses ECA reports to award immigration selection points or
make program eligibility decisions". Canada.ca states plainly that ECAs "do not
guarantee automatic employment or licensing in any particular occupation", and
that for **non-regulated occupations** — which is what software, data and AI
engineering are — "assessment and recognition of qualifications is at the
discretion of employers".

So the default is one plain-language equivalence line and no reference number.
The ECA line stays available in config for the case where I actually hold one.

### 3. ISO YYYY-MM-DD has no support

No tier-A or tier-B source recommends it, and none specifies a date format at
all. `Mon YYYY` is the convention in every Canadian university career-centre
sample I read. Default `Mon YYYY`; ISO is not offered.

### 4. "City, Province only" is practice, not a rule — and government templates disagree

Three tier-A sources still ask for a postal address. Job Bank: "your name,
**address**, email and phone number". Québec.ca: "Your **full address**". OQLF:
« le nom, **l'adresse**, le ou les numéros de téléphone et l'adresse de
courriel ». Only the career centres cut it back — U of T Mississauga: "The only
personal information you need to provide is your name and method of contact
(email address, phone number)", and separately "Don't put key information in
headers (including your address) as the ATS can't distinguish this information".

I keep `City, Province` as the default because it is what the Canadian market
expects in 2026 and it satisfies both camps, but the rule is **configurable to
three values** rather than asserted, since a federal or Quebec public-sector
application may want the full address.

### 5. PDF versus DOCX is an unresolved conflict, not a settled default

U of T Mississauga says the opposite of the brief: "**Avoid saving the document
as a pdf** as not all ATS have the ability to search keywords in these
documents." Greenhouse accepts `.doc .docx .pdf .rtf .txt`. The career-centre
advice is dated with respect to the major vendors, but it is a real tier-B
source and the cost of being wrong is a dropped application.

Resolution: **emit both on every build.** PDF is the default for a human
reader, DOCX ships beside it for a portal that asks for Word.

## Quebec and the French variant

This is where Quebec is genuinely different, and it is more than vocabulary.

- **The document is a « curriculum vitæ », abbreviated « CV » or « C. V. »** —
  OQLF, with the æ ligature.
- **Experience is described with action nouns or infinitive verbs**, not past
  participles: « Pour y décrire ses expériences de travail, une candidate ou un
  candidat peut employer des **noms d'action ou des verbes à l'infinitif**. »
  My current French CVs lead bullets with past participles (« Conçu »,
  « Développé »). The Quebec variant should read « Conception de… » or
  « Concevoir… ». This is the single largest difference from my existing FR
  track.
- **Quebec terminology**: « courriel » for email, « téléphone cellulaire » /
  « cellulaire » for mobile.
- **OQLF's suggested section order puts formation before expériences**
  (personnel, objectif, sommaire, **formation, expériences**, réalisations,
  associations, langues) — which happens to match the order I already use on my
  six role CVs.
- **« infonuagique » is the OQLF term for cloud computing.** I am *not*
  substituting it automatically. A Quebec tech recruiter reads "cloud" without
  friction, and replacing the English keyword would cost ATS matches on a
  posting that says "cloud". It stays an opt-in substitution.
- **Quebec's exclusions are the same as the federal ones** (OQLF lists SIN, age,
  DOB, marital status, nationality, photo), so no separate rule set is needed
  for what to leave out.

## Work authorization: the conflict the brief flagged

It resolves toward `omit`, and now with a tier-B source rather than duelling
blogs. U of T Mississauga's tip sheet for international students: "don't include
personal information such as age, marital status, nationality, **visa status**,
social insurance number, or photo." IRCC's own help centre answers the "how do I
show an employer I'm allowed to work" question with *documents you provide on
request*, not with a resume line.

`omit` stays the default. `one_line` and `relocation_note` remain available,
because an overseas applicant with no Canadian address has a real signalling
problem that the career-centre advice does not address.

## What I did not establish

- **US Letter paper.** No tier-A or tier-B source states a paper size. Letter is
  the North American office and print standard and A4 would look foreign in a
  Canadian print queue, so the module defaults to Letter — but this is practice,
  not a sourced rule. It matters mechanically: `templates/cv.html:12` hardcodes
  `@page { size: A4 }`, so the Canada module needs its own template rather than
  a flag on the shared one.
- **Whether a Moroccan Diplôme d'Ingénieur maps to a Canadian master's or
  bachelor's.** Only an assessing body can say. The config carries the wording
  but the module will not assert a level I cannot source.

## Sources

Tier A — government:
- [How to write a good resume — Job Bank (ESDC)](https://www.jobbank.gc.ca/findajob/resources/write-good-resume)
- [Rédiger son curriculum vitæ — Québec.ca](https://www.quebec.ca/en/employment/find-job-internship/tips/prepare-application/resume)
- [Le curriculum vitæ : conseils de rédaction — OQLF, Vitrine linguistique](https://vitrinelinguistique.oqlf.gouv.qc.ca/22593/la-redaction-et-la-communication/redaction-administrative-et-commerciale/curriculum-vitae/conseils-pour-la-redaction-du-curriculum-vitae)
- [Curriculum vitæ — OQLF, Vitrine linguistique](https://vitrinelinguistique.oqlf.gouv.qc.ca/la-redaction-et-la-communication/redaction-administrative-et-commerciale/curriculum-vitae)
- [Canadian, British and American: It's all English, but the spelling is different — Portail linguistique du Canada](https://our-languages.canada.ca/en/blogue-blog/english-spelling-differences-eng)
- [analyze, analyse — Writing Tips Plus, Portail linguistique du Canada](https://our-languages.canada.ca/en/writing-tips-plus/analyze-analyse)
- [Foreign Credential Recognition — Canada.ca](https://www.canada.ca/en/immigration-refugees-citizenship/corporate/transparency/committees/cimm-nov-18-2025/foreign-credential-recognition.html)
- [Educational credential assessment, professional bodies: overview — Canada.ca](https://www.canada.ca/en/immigration-refugees-citizenship/corporate/partners-service-providers/foreign-educational-credential-assessment/professional/overview.html)
- [How can I show a potential employer I'm allowed to work…? — IRCC Help Centre](https://ircc.canada.ca/english/helpcentre/answer.asp?qnum=1507&top=15)

Tier B — university career centres:
- [Formatting Matters — U of T Mississauga Career Centre](https://www.utm.utoronto.ca/careers/resume-cover-letter-resources/formatting-matters)
- [Resume and cover letter tips for international students — U of T Mississauga](https://www.utm.utoronto.ca/careers/career-exploration/tip-sheets/tips-resume-and-cover-letter-tips-international-students)
- [Resumes and cover letters — UBC Student Services](https://students.ubc.ca/career/career-resources/resumes-cover-letters/)
- [Resume Toolkit — UBC Applied Science Co-op (PDF)](https://experience.apsc.ubc.ca/sites/default/files/2022-08/Resume%20ToolKit_2022%20AugustCOPY.pdf)

Tier C — ATS vendor documentation:
- [Unsuccessful resume parse — Greenhouse Support](https://support.greenhouse.io/hc/en-us/articles/200989175-Unsuccessful-resume-parse)
- [Supported formats for resumes and other candidate uploads — Greenhouse Support](https://support.greenhouse.io/hc/en-us/articles/360052218132-Supported-formats-for-resumes-cover-letters-and-other-candidate-uploads)
- [Concept: Resume Parsing — Workday Administrator Guide](https://doc.workday.com/admin-guide/en-us/human-capital-management/recruiting/candidates/set-up-prospects-and-candidates/hdc1552497830785.html)
