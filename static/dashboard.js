let TH = { auto: 70, review: 40 };
let timer, tab = "today";

// Charts and the auto-apply list are their own endpoints, fetched only for the
// tab that shows them: the state poll runs every 15s and should stay cheap.
const lazy = { charts: 0, auto: 0 };

function row(r) {
  return `<a class="row" href="${jobHref(r.job_id)}">
    <span class="fit ${fitClass(r.fit_score, TH)}">${r.fit_score ?? "–"}</span>
    <span class="t"><b>${esc(r.role)}</b><span>${esc(r.company)} · ${esc(r.location || "")}</span></span>
    ${r.ats_score != null ? `<span class="sub">ATS ${r.ats_score}</span>` : ""}
  </a>`;
}

function fillQueue(id, items, emptyMsg) {
  document.getElementById("n-" + id).textContent = items.length;
  document.getElementById("q-" + id).innerHTML =
    items.length ? items.map(row).join("") : `<div class="empty">${emptyMsg}</div>`;
}

function evText(e) {
  const d = e.detail || {};
  switch (e.kind) {
    case "source": return `${d.board || "manuel"} : ${d.fetched ?? ""} offres, ${d.new ?? 0} nouvelles${d.error ? " : " + d.error : ""}`;
    case "match": return `envoyée à cv-router (pré-filtre ${d.prefilter ?? "–"})`;
    case "route": return `décision <b>${d.decision}</b> · fit ${d.fit} · ATS ${d.ats}`;
    case "tailor": return d.edited_by_hand ? `CV modifié à la main · ${d.pages} page(s)`
                 : `CV adapté · ${d.applied ?? "?"} modifs appliquées, ${d.refused ?? 0} refusées`;
    case "review": return d.validated_cv ? "CV validé par toi" : (d.approved ? "approuvée en revue" : "écartée en revue");
    case "submit": return d.status ? `soumission : ${d.status}` : `formulaire pré-rempli (${(d.filled || []).length} champs)`;
    case "autoapply": return autoText(d);
    case "status": return `statut → ${d.status}${d.notes ? " · " + esc(d.notes) : ""}`;
    case "error": return `<span style="color:var(--bad)">${esc(d.reason || "erreur")}</span>`;
    default: return esc(JSON.stringify(d));
  }
}

function autoText(d) {
  switch (d.stage) {
    case "sent": return `<b style="color:var(--accent)">envoyée automatiquement</b>`;
    case "unconfirmed": return `envoyée, mais sans confirmation lue : à vérifier`;
    case "filled": return `formulaire rempli (${(d.filled || []).length} champs, ${(d.answered || []).length} réponses)`;
    case "handed_over": return `arrêtée avant l'envoi : ${esc((d.blockers || []).join(" · "))}`;
    case "refused": return `non éligible : ${esc((d.blockers || []).join(" · "))}`;
    case "rehearsed": return `répétition : tout était vert, rien n'a été envoyé`;
    default: return esc(d.reason || d.stage || "");
  }
}

// --------------------------------------------------------------------- tabs --
document.getElementById("tabs").addEventListener("click", ev => {
  const b = ev.target.closest("button[data-tab]");
  if (!b) return;
  tab = b.dataset.tab;
  document.querySelectorAll("#tabs button").forEach(x => x.classList.toggle("on", x === b));
  document.querySelectorAll(".tab").forEach(s => s.classList.toggle("on", s.id === "tab-" + tab));
  if (tab === "charts") loadCharts();
  if (tab === "auto") loadAuto();
});

// ------------------------------------------------------------------- charts --
async function loadCharts() {
  let c;
  try { c = await api("/api/pipeline/charts"); } catch (e) { return; }
  lazy.charts = Date.now();

  const f = window._funnel || {};
  const stats = [["sourced", "offres collectées"], ["candidates", "passées au pré-filtre"],
                 ["evaluated by model", "évaluées par cv-router"], ["auto", "fit ≥ " + TH.auto],
                 ["review", "revue"], ["applied", "envoyées"]];
  document.getElementById("funnel").innerHTML = stats.map(([k, l]) =>
    `<div class="card stat"><b>${f[k] ?? 0}</b><span>${l}</span></div>`).join("");

  const names = ["Collectées", "Évaluées"];
  document.getElementById("k-flowchart").innerHTML = names.map((n, i) =>
    `<span><i style="background:var(--c${i + 1})"></i>${n}</span>`).join("");
  chartLines(document.getElementById("c-daily"), {
    labels: c.days,
    series: [{ name: "Collectées", data: c.series.sourced },
             { name: "Évaluées", data: c.series.evaluated }],
  });

  chartBars(document.getElementById("c-applied"), {
    labels: c.days, data: c.series.applied,
    fmt: v => v === 1 ? "1 candidature" : `${v} candidatures`,
  });

  document.getElementById("hist-note").textContent =
    `Vert : adapté automatiquement (≥ ${c.thresholds.auto}). Orange : pour toi (≥ ${c.thresholds.review}). Rouge : écarté.`;
  chartHist(document.getElementById("c-hist"),
            { data: c.fit_hist, thresholds: c.thresholds });

  const COL = { applied: "--accent", interview: "--accent", offer: "--accent",
                draft: "--info", pending: "--info", staged: "--warn", review: "--warn",
                skipped: "--bad", rejected: "--bad", withdrawn: "--muted" };
  const cssv = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  chartDonut(document.getElementById("c-status"), {
    items: c.status.map(s => ({ label: STATUS_FR[s.status] || s.status, n: s.n,
                                color: cssv(COL[s.status] || "--line") })),
  });

  chartBarsH(document.getElementById("c-sources"),
             { items: c.sources.map(s => ({ label: s.name, n: s.n })) });

  const agg = {};
  for (const w of c.buckets) {
    const a = agg[w.bucket] || (agg[w.bucket] = { applied: 0, responses: 0, interviews: 0 });
    a.applied += w.applied; a.responses += w.responses; a.interviews += w.interviews;
  }
  const order = [">=70", "40-69", "<40", "pre-screen"];
  document.getElementById("buckets").innerHTML = order.filter(b => agg[b]).map(b => {
    const a = agg[b];
    return `<tr><td>${b === "pre-screen" ? "pré-filtre" : "fit " + b}</td>
      <td>${a.applied}</td><td>${a.responses}</td><td>${a.interviews}</td>
      <td>${a.applied ? Math.round(a.responses / a.applied * 100) + " %" : "–"}</td></tr>`;
  }).join("") || `<tr><td colspan="5" class="empty">Pas encore assez de candidatures envoyées.</td></tr>`;
}

// ---------------------------------------------------------------- auto-apply --
async function loadAuto() {
  let a;
  try { a = await api("/api/pipeline/autoapply"); } catch (e) { return; }
  lazy.auto = Date.now();
  document.getElementById("t-auto").textContent = a.enabled ? String(a.rows.filter(r => r.eligible).length) : "off";

  document.getElementById("auto-head").innerHTML = a.enabled
    ? `<div class="send ${a.rehearse ? "blocked" : "ready"}">
         <h3>${a.rehearse ? "Mode répétition" : "Actif"}</h3>
         <div class="why">${a.rehearse
            ? "Chaque vérification est faite jusqu'au bout, puis le système s'arrête avant le clic. Rien ne part."
            : "Les candidatures qui passent toutes les vérifications partent sans te demander."}</div>
         <div class="gate">
           <div class="ok"><span class="m">✓</span>Fit minimum ${a.min_fit}, ATS minimum ${a.min_ats}</div>
           <div class="${a.sent_today < a.max_per_day ? "ok" : "no"}"><span class="m">${a.sent_today < a.max_per_day ? "✓" : "✕"}</span>
             Plafond du jour : ${a.sent_today} / ${a.max_per_day} envoyées</div>
           <div class="${a.answers ? "ok" : "no"}"><span class="m">${a.answers ? "✓" : "✕"}</span>
             ${a.answers ? `${a.answers} réponses écrites par toi dans profile.toml`
                         : "Aucune réponse dans profile.toml : ajoute une section [[answers]], sinon rien ne pourra partir seul"}</div>
         </div>
       </div>`
    : `<div class="send">
         <h3>Désactivé</h3>
         <div class="why">Rien ne part sans toi. Pour l'activer : <code>enabled = true</code> dans la section
           <code>[autoapply]</code> de <code>pipeline.toml</code>, et des réponses sous <code>[[answers]]</code>
           dans <code>profile.toml</code>. Commence par <code>rehearse = true</code> : tout est vérifié, rien n'est envoyé.</div>
       </div>`;

  document.getElementById("auto-rows").innerHTML = a.rows.map(r => `<tr>
      <td><span class="fit ${fitClass(r.fit_score, TH)}">${r.fit_score ?? "–"}</span></td>
      <td>${r.ats_score ?? "–"}</td>
      <td><a href="${jobHref(r.job_id)}">${esc(r.role)}</a><div class="sub">${esc(r.company)}</div></td>
      <td>${r.eligible ? `<span class="tag applied">prête à partir</span>`
                       : `<span class="sub">${esc(r.blockers.join(" · "))}</span>`}</td>
      <td>${r.eligible ? `<a class="btn small primary" href="${jobHref(r.job_id)}">Ouvrir</a>` : ""}</td>
    </tr>`).join("")
    || `<tr><td colspan="5" class="empty">Aucun CV validé en attente.</td></tr>`;
}

// ------------------------------------------------------------------- refresh --
async function refresh() {
  let s;
  try { s = await api("/api/pipeline/state"); } catch (e) { return; }
  TH = s.thresholds;
  window._funnel = s.funnel;
  document.getElementById("th-auto").textContent = TH.auto;
  document.getElementById("th-rev").textContent = TH.review;
  document.getElementById("budget").textContent = `${s.budget.used} / ${s.budget.total}`;

  const f = s.funnel, L = s.lists;
  const auto = s.autoapply || {};
  document.getElementById("headline").innerHTML = auto.enabled
    ? `Le système trouve, trie et prépare. <b>Il envoie lui-même</b> les candidatures qui passent toutes les vérifications ; les autres t'attendent.`
    : `Le système trouve, trie et prépare. <b>C'est toi qui envoies</b> : rien n'est jamais soumis automatiquement.`;
  document.getElementById("never").innerHTML = auto.enabled
    ? `Ce que le système ne fait jamais, même activé : répondre à une question que tu n'as pas écrite toi-même, toucher un CAPTCHA, ou envoyer un CV que tu n'as pas relu.`
    : `Ce que le système ne fait jamais : soumettre une candidature, répondre à une question sur ton autorisation de travail ou ton salaire, ni toucher à un CAPTCHA.`;

  // the journey of one job, and who moves it along at each step
  const last = auto.enabled ? "auto ou toi" : "toi";
  const flow = [
    { n: f["sourced"] ?? 0, nm: "Collectées", by: "auto" },
    { n: f["candidates"] ?? 0, nm: "Retenues au pré-filtre", by: "auto" },
    { n: f["evaluated by model"] ?? 0, nm: "Évaluées par cv-router", by: "auto" },
    { n: L.review.length, nm: "À trancher", by: "toi", you: true },
    { n: L.draft.length + L.pending.length, nm: "CV à relire", by: "toi", you: true },
    { n: L.staged.length, nm: "À envoyer", by: last, you: !auto.enabled },
    { n: f["applied"] ?? 0, nm: "Envoyées", by: last },
  ];
  document.getElementById("flow").innerHTML = flow.map((x, i) =>
    `${i ? '<span class="arr">→</span>' : ""}
     <div class="st ${x.you ? "you" : ""} ${x.you && !x.n ? "none" : ""}">
       <b>${x.n}</b><span class="nm">${x.nm}</span><span class="by">${x.by}</span></div>`).join("");

  // what is waiting for you, in the order it should be done
  const todo = [
    { n: L.draft.length + L.pending.length, t: "CV à relire et valider",
      s: "Ouvre, lis, corrige si besoin, puis valide.", href: "#q-draft" },
    { n: L.staged.length, t: "Candidatures à envoyer",
      s: "Le formulaire est rempli ; il ne reste qu'à envoyer.", href: "#q-staged" },
    { n: L.review.length, t: "Offres à trancher",
      s: "Fit moyen : à toi de dire si ça vaut le coup.", href: "#q-review" },
  ].filter(x => x.n);
  document.getElementById("t-today").textContent = todo.reduce((a, x) => a + x.n, 0);
  document.getElementById("todo").innerHTML = todo.length ? todo.map(x =>
    `<a class="hot" href="${x.href}"><b>${x.n}</b><span class="t">${x.t}<span>${x.s}</span></span>→</a>`).join("")
    : `<div class="done">Rien ne t'attend. Le pipeline continue de chercher.</div>`;

  fillQueue("draft", s.lists.draft.concat(s.lists.pending), "Aucun CV à relire.");
  fillQueue("staged", s.lists.staged, "Rien de prêt : valide un CV d'abord.");
  fillQueue("review", s.lists.review, "File de revue vide.");

  document.getElementById("recent").innerHTML = s.lists.recent.map(r => `<tr>
      <td><span class="fit ${fitClass(r.fit_score, TH)}">${r.fit_score}</span></td>
      <td>${r.ats_score ?? "–"}</td>
      <td><a href="${jobHref(r.job_id)}">${esc(r.role)}</a><div class="sub">${esc(r.company)}</div></td>
      <td><span class="tag ${r.status}">${STATUS_FR[r.status] || r.status}</span></td></tr>`).join("")
    || `<tr><td colspan="4" class="empty">Aucune offre évaluée.</td></tr>`;

  document.getElementById("cands").innerHTML = s.lists.candidates.map(r => `<tr>
      <td>${(r.prefilter_score ?? 0).toFixed(2)}</td>
      <td><a href="${jobHref(r.job_id)}">${esc(r.role)}</a><div class="sub">${esc(r.company)} · ${esc(r.location || "")}</div></td>
      <td><button class="small" data-eval="${esc(r.job_id)}">Évaluer</button></td></tr>`).join("")
    || `<tr><td colspan="3" class="empty">Aucune candidate en attente.</td></tr>`;

  document.getElementById("events").innerHTML = s.events.map(e => `<tr>
      <td class="sub" style="white-space:nowrap">${ago(e.ts)}</td>
      <td><span class="ev-kind">${e.kind}</span></td>
      <td>${e.job ? `<a href="${jobHref(e.job_id)}">${esc(e.job)}</a><br>` : ""}${evText(e)}</td></tr>`).join("");

  document.getElementById("boards").innerHTML = s.boards.map(b => `<tr>
      <td class="sub">${b.source}</td><td>${esc(b.board)}</td><td>${b.n_jobs ?? "–"}</td>
      <td class="sub">${ago(b.last_fetched)}${b.last_error ? ` <span style="color:var(--bad)">${esc(b.last_error)}</span>` : ""}</td></tr>`).join("");

  document.getElementById("log").textContent = s.log || "-";
  document.getElementById("live").classList.toggle("live", s.running);
  document.getElementById("livetxt").textContent = s.running ? "cycle en cours…" : "à l'arrêt";
  ["b-dry", "b-one", "b-fetch"].forEach(id => document.getElementById(id).disabled = s.running);

  if (tab === "charts" && Date.now() - lazy.charts > 20000) loadCharts();
  if (tab === "auto" && Date.now() - lazy.auto > 10000) loadAuto();

  clearTimeout(timer);
  timer = setTimeout(refresh, s.running ? 2500 : 15000);
}

async function start(body, msg) {
  try { await api("/api/pipeline/run", body); toast(msg); refresh(); }
  catch (e) { toast("Impossible : " + e.message); }
}

document.getElementById("b-dry").onclick = () =>
  start({ mode: "dry", fetch: false, max_matches: 5 }, "Cycle à blanc lancé : aucun appel modèle, rien n'est écrit.");
document.getElementById("b-one").onclick = () =>
  start({ mode: "real", fetch: false, max_matches: 1 }, "Évaluation de la meilleure candidate…");
document.getElementById("b-fetch").onclick = () =>
  start({ mode: "real", fetch: true, max_matches: 3 }, "Collecte puis évaluation de 3 offres…");

document.getElementById("cands").addEventListener("click", async ev => {
  const id = ev.target.dataset.eval;
  if (!id) return;
  ev.target.disabled = true; ev.target.textContent = "…2 appels";
  try {
    const r = await api(`/api/job/${id}/evaluate`, {});
    toast(`Décision : ${r.decision} (fit ${r.fit})`);
    location.href = jobHref(id);
  } catch (e) { toast("Erreur : " + e.message); ev.target.disabled = false; ev.target.textContent = "Évaluer"; }
});

async function addManual(evaluate) {
  const body = {
    company: document.getElementById("m-company").value.trim(),
    title: document.getElementById("m-title").value.trim(),
    location: document.getElementById("m-loc").value.trim(),
    url: document.getElementById("m-url").value.trim(),
    jd: document.getElementById("m-jd").value,
  };
  try {
    const { job_id } = await api("/api/jobs", body);
    if (evaluate) {
      toast("Offre ajoutée : évaluation en cours (≈ 2 min)…");
      await api(`/api/job/${job_id}/evaluate`, {});
    }
    location.href = jobHref(job_id);
  } catch (e) { toast("Erreur : " + e.message); }
}
document.getElementById("m-add").onclick = () => addManual(false);
document.getElementById("m-add-eval").onclick = () => addManual(true);

refresh();
loadAuto();   // the tab badge says off / how many are ready, before you open it
