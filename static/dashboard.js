let TH = { auto: 70, review: 40 };
let timer;

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
    case "status": return `statut → ${d.status}${d.notes ? " · " + esc(d.notes) : ""}`;
    case "error": return `<span style="color:var(--bad)">${esc(d.reason || "erreur")}</span>`;
    default: return esc(JSON.stringify(d));
  }
}

async function refresh() {
  let s;
  try { s = await api("/api/pipeline/state"); } catch (e) { return; }
  TH = s.thresholds;
  document.getElementById("th-auto").textContent = TH.auto;
  document.getElementById("th-rev").textContent = TH.review;
  document.getElementById("budget").textContent = `${s.budget.used} / ${s.budget.total}`;

  const f = s.funnel;
  const stats = [["sourced", "offres collectées"], ["candidates", "passées au pré-filtre"],
                 ["evaluated by model", "évaluées par cv-router"], ["auto", "fit ≥ " + TH.auto],
                 ["review", "revue"], ["applied", "envoyées"]];
  document.getElementById("funnel").innerHTML = stats.map(([k, l]) =>
    `<div class="card stat"><b>${f[k] ?? 0}</b><span>${l}</span></div>`).join("");

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
