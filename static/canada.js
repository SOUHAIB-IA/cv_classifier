// The Canada studio page.
//
// Thin on purpose: every decision — role, language, score, what changed — is
// made server-side by the module and arrives already explained. The page's job
// is to show the reasoning, not to re-derive it.

const $ = (id) => document.getElementById(id);
let STATE = {};

const SEV = { fail: "Échec", warn: "Avertissement", info: "Note" };

function card(title, body) {
  return `<div style="margin-bottom:10px"><b>${esc(title)}</b>${body}</div>`;
}

function renderScore(m) {
  const cls = m.score >= 70 ? "hi" : m.score >= 45 ? "mid" : "lo";
  let h = `<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
    <span class="fit ${cls}" style="font-size:20px;padding:6px 12px">${m.score}</span>
    <span class="sub">${esc(m.reason)}</span></div>`;
  if (m.matched.length)
    h += `<div class="sub" style="margin-top:8px"><b>Déjà dans le CV :</b> ${
      m.matched.slice(0, 24).map(([t]) => esc(t)).join(", ")}</div>`;
  if (m.gaps.length)
    h += `<div class="sub" style="margin-top:6px"><b>Demandé, absent du CV :</b> ${
      m.gaps.slice(0, 24).map(([t, n]) => `${esc(t)}<span class="sub"> ×${n}</span>`).join(", ")}
      <div style="margin-top:4px">Signalé, jamais inséré : un terme que tu ne peux
      pas défendre en entretien coûte plus qu'il ne rapporte.</div></div>`;
  return h;
}

function renderReport(r) {
  if (!r.findings.length)
    return card("Conformité", `<div class="sub">Aucun problème. ${
      r.not_checked.length ? "Non vérifié ici : " + r.not_checked.map(esc).join(" ; ") : ""}</div>`);
  const rows = r.findings.map(f => `<tr>
    <td><span class="tag ${f.severity === "fail" ? "error" : f.severity === "warn" ? "draft" : ""}">${SEV[f.severity]}</span></td>
    <td><code>${esc(f.check)}</code></td>
    <td>${esc(f.message)}${f.evidence ? `<div class="sub">trouvé : <code>${esc(f.evidence)}</code></div>` : ""}
        ${f.fix ? `<div class="sub">correctif : ${esc(f.fix)}</div>` : ""}</td></tr>`).join("");
  return card(`Conformité — ${r.ok ? "conforme" : "non conforme"}`,
    `<table class="data"><tbody>${rows}</tbody></table>` +
    (r.not_checked.length ? `<div class="sub" style="margin-top:6px">Non vérifié ici : ${
      r.not_checked.map(esc).join(" ; ")}</div>` : ""));
}

function renderChanges(c) {
  const rows = c.changes.map(x => `<tr><td><code>${esc(x.what)}</code></td>
    <td>${esc(x.where)}</td>
    <td>${x.before || x.after ? `<code>${esc(x.before)}</code> → <code>${esc(x.after)}</code>` : ""}
        ${x.why ? `<div class="sub">${esc(x.why)}</div>` : ""}</td></tr>`).join("");
  let h = card(`${c.changes.length} changement(s)`,
    `<table class="data"><tbody>${rows}</tbody></table>`);
  if (c.unresolved.length)
    h += card("À toi de trancher",
      `<ul>${c.unresolved.map(u => `<li>${esc(u)}</li>`).join("")}</ul>`);
  return h;
}

function renderFiles(files) {
  return card("Fichiers", `<div style="display:flex;gap:8px;flex-wrap:wrap">${
    files.map(f => `<a class="btn" href="/canada/api/file/${encodeURIComponent(f)}"
      download>${esc(f)}</a>`).join("")}</div>`);
}

async function run() {
  const jd = $("c-jd").value.trim();
  if (jd.length < 80) { toast("Colle l'offre complète (au moins 80 caractères)."); return; }
  $("c-run").disabled = true;
  $("c-head").textContent = "Adaptation en cours…";
  $("c-out").hidden = false;
  try {
    const d = await api("/canada/api/tailor", {
      method: "POST",
      body: {
        jd, company: $("c-company").value, city: $("c-city").value,
        role: $("c-role").value || null, lang: $("c-lang").value || null,
        no_bullets: $("c-nobullets").checked,
      },
    });
    $("c-head").textContent = d.stem;
    $("c-score").innerHTML =
      `<div class="sub" style="margin-bottom:8px">rôle <b>${esc(d.role)}</b> — ${esc(d.why_role)}
       · langue <b>${esc(d.lang)}</b> — ${esc(d.why_lang)}
       · source ${esc(d.source)} · ${d.pages} page(s)</div>` + renderScore(d.match);
    $("c-report").innerHTML = renderReport(d.report);
    $("c-changes").innerHTML = renderChanges(d.changelog);
    $("c-files").innerHTML = renderFiles(d.files)
      + (d.advice ? `<div class="sub" style="margin-top:6px"><b>Conseil :</b> ${esc(d.advice)}</div>` : "");
    list();
  } catch (e) {
    $("c-head").textContent = "Erreur";
    $("c-score").innerHTML = `<div class="sub">${esc(e.message)}</div>`;
  } finally { $("c-run").disabled = false; }
}

async function lint() {
  $("c-out").hidden = false;
  $("c-head").textContent = "Vérification du CV source";
  $("c-score").innerHTML = "";
  $("c-changes").innerHTML = "";
  $("c-files").innerHTML = "";
  try {
    const d = await api("/canada/api/check", {
      method: "POST",
      body: { role: $("c-role").value || "de", lang: $("c-lang").value || "en" },
    });
    $("c-report").innerHTML = renderReport(d);
  } catch (e) { $("c-report").innerHTML = `<div class="sub">${esc(e.message)}</div>`; }
}

async function list() {
  try {
    const d = await api("/canada/api/output");
    $("c-dir").textContent = d.dir || "";
    $("c-list").innerHTML = d.files.length
      ? `<div style="display:flex;gap:6px;flex-wrap:wrap">${d.files.map(f =>
          `<a class="btn" href="/canada/api/file/${encodeURIComponent(f.name)}"
            download>${esc(f.name)}</a>`).join("")}</div>`
      : `<div class="empty">Rien encore.</div>`;
  } catch (e) { /* the folder may not exist yet */ }
}

$("c-run").onclick = run;
$("c-lint").onclick = lint;

(async () => {
  try {
    STATE = await api("/canada/api/state");
    $("c-role").innerHTML = `<option value="">détecté depuis l'offre</option>` +
      Object.entries(STATE.roles).map(([k, v]) =>
        `<option value="${esc(k)}">${esc(v)}</option>`).join("");
    $("c-state").innerHTML =
      `papier <b>${esc(STATE.paper)}</b> · ${STATE.pages.prefer} page préférée,
       ${STATE.pages.max} au maximum · lieu <b>${esc(STATE.location_mode)}</b>
       · autorisation de travail <b>${esc(STATE.auth_mode)}</b>
       · diplôme <b>${esc(STATE.credential_mode)}</b>${
         STATE.credential_mode === "equivalence_line" && !STATE.equivalence_set
           ? ` <span class="tag draft">équivalence non renseignée</span>` : ""}`;
  } catch (e) { $("c-state").textContent = "Erreur : " + e.message; }
  list();
})();
