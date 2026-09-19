// One job: cv-router's verdict, and an editor for the CV that will be sent.
//
// The working copy `doc` is the structured CV behind the PDF. Every field is
// editable; fields that differ from your original CV are highlighted. Nothing
// reaches the PDF until you press "Enregistrer", and nothing is submitted
// until you validate the CV and click submit on the employer's form yourself.

let D = null, doc = null, base = null, TH = { auto: 70, review: 40 };
let dirty = false, previewTimer = null, reverted = new Set();

const $ = id => document.getElementById(id);
const norm = s => String(s ?? "").replace(/[’‘]/g, "'").replace(/[–—]/g, "-").replace(/\s+/g, " ").trim().toLowerCase();
const splitItems = s => String(s || "").split(/\s*[|,;•·]\s*/).map(x => x.trim()).filter(Boolean);
const stripLabel = s => String(s || "").replace(/^[^:|]{2,40}:\s*/, "").trim();

// ------------------------------------------------------------------ paths --
function getAt(o, p) { return p.reduce((a, k) => (a == null ? a : a[k]), o); }
function setAt(o, p, v) { const last = p[p.length - 1]; getAt(o, p.slice(0, -1))[last] = v; }

// The original value at the same place. Sections are matched by title, since
// the tailored CV may order them differently from the original.
function baseAt(p) {
  if (!base) return undefined;
  if (p[0] !== "sections") return getAt(base, p);
  const title = norm(doc.sections[p[1]]?.title);
  const bi = (base.sections || []).findIndex(s => norm(s.title) === title);
  return bi < 0 ? undefined : getAt(base, ["sections", bi, ...p.slice(2)]);
}
function differs(p, v) {
  const b = baseAt(p);
  if (b === undefined) return !!v && p[0] === "sections";
  const flat = x => Array.isArray(x) ? x.map(norm).join("|") : norm(x);
  return flat(b) !== flat(v);
}
function origHint(p) {
  const b = baseAt(p);
  if (b === undefined) return "absent de ton CV d'origine";
  return "Original : " + (Array.isArray(b) ? b.join(", ") : b);
}

// ----------------------------------------------------------------- render --
async function load() {
  D = await api("/api/job/" + JOB_ID);
  TH = D.thresholds;
  doc = D.cv && D.cv.doc ? JSON.parse(JSON.stringify(D.cv.doc)) : null;
  base = D.cv ? D.cv.base : null;
  dirty = false; reverted = new Set();
  renderHead(); renderVerdict(); renderEdits(); renderEditor(); schedulePreview(0);
  $("jd").textContent = D.job.jd_text || "";
  setDirty(false);
}

function renderHead() {
  const j = D.job, a = D.app, m = D.match;
  const st = a ? a.status : "new";
  let actions = [];
  if (!m) actions.push(`<button class="primary" data-act="evaluate">Évaluer avec cv-router (2 appels)</button>`);
  else if (!D.cv) {
    if (st === "review") actions.push(`<button class="primary" data-act="approve-tailor">Approuver et préparer le CV</button>`,
                                      `<button class="danger" data-act="skip">Écarter</button>`);
    else actions.push(`<button class="primary" data-act="tailor">Préparer le CV${st === "skipped" ? " quand même" : ""}</button>`);
  } else if (st === "draft") {
    actions.push(`<button class="primary" data-act="validate">Valider ce CV</button>`,
                 `<button data-act="tailor">Refaire depuis l'original</button>`,
                 `<button class="danger" data-act="skip">Écarter l'offre</button>`);
  } else if (st === "staged") {
    actions.push(`<button class="primary" data-act="applied">J'ai envoyé la candidature</button>`,
                 `<button class="danger" data-act="withdrawn">Abandonner</button>`);
  } else if (["applied", "interview", "rejected", "offer"].includes(st)) {
    actions.push(`<button data-act="interview">Entretien</button>`, `<button data-act="rejected">Refus</button>`,
                 `<button data-act="offer">Offre</button>`);
  }
  const url = j.apply_url || j.jd_url;
  $("head").innerHTML = `
    <div class="t">
      <h1>${esc(j.title)}</h1>
      <div class="sub">${esc(j.company)} · ${esc(j.location || "lieu non précisé")} · ${esc(j.source)}
        ${url ? ` · <a href="${esc(url)}" target="_blank" rel="noopener">voir l'annonce ↗</a>` : ""}</div>
      <div style="margin-top:6px"><span class="tag ${st}">${STATUS_FR[st] || st}</span>
        ${a && a.cv_variant ? `<span class="sub"> · CV de base : ${esc(a.cv_variant)}</span>` : ""}</div>
      <div class="actions">${actions.join("")}</div>
      ${st === "staged" ? `<div class="sub" style="margin-top:8px">Pour pré-remplir le formulaire (tu cliques « envoyer » toi-même) :
        <code>python -m pipeline.submit ${esc(JOB_ID)}</code></div>` : ""}
    </div>
    <div class="scores">
      <div class="score"><b class="fit ${fitClass(m?.fit_score, TH)}">${m?.fit_score ?? "–"}</b><span>fit</span></div>
      <div class="score"><b>${m?.ats_score ?? "–"}</b><span>ATS</span></div>
    </div>`;
}

function renderVerdict() {
  const m = D.match;
  if (!m) { $("verdict").innerHTML = `<h2>Verdict de cv-router</h2><div class="empty">Pas encore évaluée.</div>`; return; }
  const r = m.raw || {};
  const chips = (xs, cls) => (xs || []).map(x => `<span class="chip ${cls}">${esc(x)}</span>`).join("");
  $("verdict").innerHTML = `
    <h2>Verdict de cv-router</h2>
    <div style="font-size:13px"><b>Pourquoi ce fit</b><div class="why">${esc(r.fit_reason || m.reason || "")}</div></div>
    <div style="font-size:13px;margin-top:10px"><b>Pourquoi ce CV</b><div class="why">${esc(r.best?.why || "")}</div></div>
    ${r.matched_keywords?.length ? `<div style="margin-top:10px"><b style="font-size:12px">Couverts</b><div class="chips" style="margin-top:4px">${chips(r.matched_keywords, "ok")}</div></div>` : ""}
    ${r.missing_keywords?.length ? `<div style="margin-top:8px"><b style="font-size:12px">Manquants</b><div class="chips" style="margin-top:4px">${chips(r.missing_keywords, "no")}</div></div>` : ""}
    ${r.red_flags?.length ? `<div style="margin-top:10px;font-size:12.5px"><b>Points de vigilance</b><ul style="margin:4px 0 0 16px;padding:0">${r.red_flags.map(f => `<li>${esc(f)}</li>`).join("")}</ul></div>` : ""}
    ${r.cover_letter_hook ? `<div style="margin-top:10px;font-size:12.5px"><b>Accroche de lettre</b><div class="why">${esc(r.cover_letter_hook)}</div></div>` : ""}`;
}

function renderEdits() {
  const list = D.cv?.meta?.edits || (D.match?.suggested_edits || []).map(e => ({ ...e, status: "proposed" }));
  if (!list.length) { $("edits").innerHTML = `<div class="empty">Aucune.</div>`; return; }
  $("edits").innerHTML = list.map((e, i) => {
    const tag = e.status === "applied" ? (reverted.has(i) ? `<span class="tag">annulée</span>` : `<span class="tag applied_ok">appliquée</span>`)
              : e.status === "skipped" ? `<span class="tag rejected">refusée</span>` : `<span class="tag">proposée</span>`;
    const btn = !doc ? "" : e.status === "applied" && !reverted.has(i)
      ? `<button class="small" data-revert="${i}">Annuler</button>`
      : e.status === "skipped" ? `<button class="small" data-copy="${i}">Copier la suggestion</button>` : "";
    return `<div class="edit">
      <div class="h">${tag}<span class="sec">${esc(e.section || "")}</span>${btn}</div>
      ${e.current && !/^\(?absent\)?$/i.test(e.current) ? `<div class="was">${esc(e.current)}</div>` : ""}
      <div class="now">${esc(e.suggested)}</div>
      <div class="why">${e.status === "skipped" ? "Refusée : " + esc(e.reason) : esc(e.why || "")}</div>
    </div>`;
  }).join("");
}

// ----------------------------------------------------------------- editor --
function field(p, value, opts = {}) {
  const cls = differs(p, value) ? "chg" : "";
  const title = esc(origHint(p));
  const pj = esc(JSON.stringify(p));
  if (opts.area) return `<textarea data-p="${pj}" data-kind="${opts.kind || "text"}" class="${cls}" title="${title}" rows="${opts.rows || 2}" placeholder="${esc(opts.ph || "")}">${esc(opts.kind === "list" ? (value || []).join(", ") : opts.kind === "lines" ? (value || []).join("\n") : value || "")}</textarea>`;
  return `<input data-p="${pj}" class="${cls}" title="${title}" value="${esc(value || "")}" placeholder="${esc(opts.ph || "")}">`;
}

function renderEditor() {
  if (!doc) { $("b-save").disabled = true; return; }
  $("b-save").disabled = false;
  const c = doc.contact || (doc.contact = {});
  let h = `
    <label style="display:flex;gap:8px;align-items:center;margin-top:10px;font-size:13px">
      <input type="checkbox" id="show-photo" style="width:auto" ${doc.show_photo === false ? "" : "checked"}>
      Afficher ma photo</label>
    <label class="f">Nom</label>${field(["name"], doc.name)}
    <label class="f">Accroche (titre sous le nom)</label>${field(["headline"], doc.headline)}
    <div class="grid" style="grid-template-columns:1fr 1fr 1fr;gap:6px">
      <div><label class="f">E-mail</label>${field(["contact", "email"], c.email)}</div>
      <div><label class="f">Téléphone</label>${field(["contact", "phone"], c.phone)}</div>
      <div><label class="f">Lieu</label>${field(["contact", "location"], c.location)}</div>
    </div>
    <label class="f">Profil</label>${field(["summary"], doc.summary, { area: true, rows: 6 })}`;

  (doc.sections || []).forEach((s, si) => {
    h += `<div class="ed-sec"><div class="h">
      ${field(["sections", si, "title"], s.title)}
      <span class="tag">${s.kind || "other"}</span>
      <button class="ico" data-op="sec-up" data-si="${si}" title="Monter">↑</button>
      <button class="ico" data-op="sec-down" data-si="${si}" title="Descendre">↓</button></div>`;
    if (s.kind === "skills") {
      (s.groups || []).forEach((g, gi) => {
        h += `<div class="ed-item"><div class="grid" style="grid-template-columns:1fr 2.4fr;gap:6px">
          ${field(["sections", si, "groups", gi, "label"], g.label, { ph: "Libellé du groupe" })}
          ${field(["sections", si, "groups", gi, "items"], g.items, { area: true, kind: "list", rows: 2, ph: "Compétences, séparées par des virgules" })}
        </div></div>`;
      });
      h += `<button class="small" style="margin-top:8px" data-op="add-group" data-si="${si}">+ groupe</button>`;
    } else if (s.kind === "list") {
      h += `<div style="margin-top:8px">${field(["sections", si, "lines"], s.lines, { area: true, kind: "lines", rows: Math.max(2, (s.lines || []).length), ph: "Une ligne par entrée" })}</div>`;
    } else {
      (s.items || []).forEach((it, ii) => {
        h += `<div class="ed-item"><div class="r4">
          ${field(["sections", si, "items", ii, "heading"], it.heading, { ph: "Poste / projet / diplôme" })}
          ${field(["sections", si, "items", ii, "org"], it.org, { ph: "Entreprise / école / stack" })}
          ${field(["sections", si, "items", ii, "location"], it.location, { ph: "Lieu" })}
          ${field(["sections", si, "items", ii, "dates"], it.dates, { ph: "Dates" })}</div>`;
        (it.bullets || []).forEach((b, bi) => {
          h += `<div class="bul">${field(["sections", si, "items", ii, "bullets", bi], b, { area: true, rows: 2 })}
            <div style="display:flex;flex-direction:column;gap:3px">
              <button class="ico" data-op="b-up" data-si="${si}" data-ii="${ii}" data-bi="${bi}" title="Monter">↑</button>
              <button class="ico" data-op="b-down" data-si="${si}" data-ii="${ii}" data-bi="${bi}" title="Descendre">↓</button>
              <button class="ico danger" data-op="b-del" data-si="${si}" data-ii="${ii}" data-bi="${bi}" title="Supprimer">✕</button>
            </div></div>`;
        });
        h += `<button class="small" style="margin-top:6px" data-op="b-add" data-si="${si}" data-ii="${ii}">+ puce</button></div>`;
      });
    }
    h += `</div>`;
  });
  $("editor").innerHTML = h;
}

$("editor").addEventListener("input", ev => {
  const el = ev.target;
  if (el.id === "show-photo") {
    doc.show_photo = el.checked; setDirty(true); schedulePreview(0); return;
  }
  if (!el.dataset.p) return;
  const p = JSON.parse(el.dataset.p);
  let v = el.value;
  if (el.dataset.kind === "list") v = splitItems(v);
  else if (el.dataset.kind === "lines") v = v.split("\n").map(x => x.trim()).filter(Boolean);
  setAt(doc, p, v);
  el.classList.toggle("chg", differs(p, v));
  setDirty(true); schedulePreview();
});

$("editor").addEventListener("click", ev => {
  const b = ev.target.closest("[data-op]");
  if (!b) return;
  const { op } = b.dataset, si = +b.dataset.si, ii = +b.dataset.ii, bi = +b.dataset.bi;
  const secs = doc.sections;
  const swap = (arr, i, j) => { if (j >= 0 && j < arr.length) [arr[i], arr[j]] = [arr[j], arr[i]]; };
  const bul = () => secs[si].items[ii].bullets;
  if (op === "sec-up") swap(secs, si, si - 1);
  if (op === "sec-down") swap(secs, si, si + 1);
  if (op === "b-up") swap(bul(), bi, bi - 1);
  if (op === "b-down") swap(bul(), bi, bi + 1);
  if (op === "b-del") bul().splice(bi, 1);
  if (op === "b-add") (secs[si].items[ii].bullets ||= []).push("");
  if (op === "add-group") (secs[si].groups ||= []).push({ label: "", items: [] });
  renderEditor(); setDirty(true); schedulePreview();
});

// ------------------------------------------------------- revert one edit --
function revert(e) {
  const sug = stripLabel(e.suggested), cur = /^\(?absent\)?$/i.test(e.current || "") ? "" : e.current;
  const groups = (doc.sections || []).flatMap(s => s.groups || []);
  // skills, case 1 — items were ADDED to a group ("added Kubernetes, Terraform"):
  // take exactly those back out
  if (!cur && /^added /.test(e.reason || "")) {
    const added = new Set(e.reason.slice(6).split(/\s*,\s*/).map(norm));
    const g = groups.find(g => g.items.some(x => added.has(norm(x))));
    if (g) { g.items = g.items.filter(x => !added.has(norm(x))); return true; }
    return false;
  }
  // skills, case 2 — a whole group was REPLACED by the suggested list: put the old list back
  const target = norm(splitItems(sug).join(", "));
  const g = groups.find(g => norm(g.items.join(", ")) === target);
  if (g && cur) { g.items = splitItems(stripLabel(cur)); return true; }
  const tryStr = (get, set) => {
    const v = get(); if (!v) return false;
    for (const [from, to] of [[e.suggested, e.current], [sug, stripLabel(e.current || "")]]) {
      if (from && v.includes(from)) { set(v.replace(from, to || "")); return true; }
    }
    if (norm(v) === norm(e.suggested)) { set(e.current || ""); return true; }
    return false;
  };
  if (tryStr(() => doc.headline, v => doc.headline = v)) return true;
  if (tryStr(() => doc.summary, v => doc.summary = v)) return true;
  for (const s of doc.sections || []) {
    for (const it of s.items || []) for (let k = 0; k < (it.bullets || []).length; k++)
      if (tryStr(() => it.bullets[k], v => it.bullets[k] = v)) return true;
    for (let k = 0; k < (s.lines || []).length; k++)
      if (tryStr(() => s.lines[k], v => s.lines[k] = v)) return true;
  }
  return false;
}

$("edits").addEventListener("click", async ev => {
  const list = D.cv?.meta?.edits || [];
  if (ev.target.dataset.revert !== undefined) {
    const i = +ev.target.dataset.revert;
    if (revert(list[i])) { reverted.add(i); renderEdits(); renderEditor(); setDirty(true); schedulePreview(); toast("Modification annulée — pense à enregistrer."); }
    else toast("Texte introuvable : tu l'as sans doute déjà modifié à la main.");
  }
  if (ev.target.dataset.copy !== undefined) {
    await navigator.clipboard.writeText(list[+ev.target.dataset.copy].suggested);
    toast("Suggestion copiée — colle-la où tu veux dans l'éditeur.");
  }
});

// ---------------------------------------------------------------- preview --
function scalePreview() {
  const w = $("pw").clientWidth, s = w / 794;
  $("preview").style.transform = `scale(${s})`;
  $("pw").style.height = (1123 * s) + "px";
}
function schedulePreview(delay = 400) {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(async () => {
    if (!doc) { $("preview").srcdoc = `<p style="font:14px sans-serif;color:#888;padding:20px">Pas encore de CV adapté.</p>`; scalePreview(); return; }
    const density = D.cv?.meta?.density_step ?? 0;
    const html = await api(`/api/job/${JOB_ID}/preview`, { doc, lang: D.cv?.meta?.lang || "fr", density });
    $("preview").srcdoc = html; scalePreview();
  }, delay);
}
window.addEventListener("resize", scalePreview);

function setDirty(v) {
  dirty = v;
  $("dirty").textContent = v ? "● modifications non enregistrées" : "";
  const m = D?.cv?.meta;
  $("pageinfo").textContent = m ? `${m.pages ?? "?"} page(s)${m.edited_by_hand ? " · modifié à la main" : ""}` : "";
  $("b-pdf").href = D?.cv ? `/job/${JOB_ID}/cv.pdf?t=${Date.now()}` : "#";
}
window.addEventListener("beforeunload", e => { if (dirty) { e.preventDefault(); e.returnValue = ""; } });

// ---------------------------------------------------------------- actions --
async function save() {
  $("b-save").disabled = true; $("b-save").textContent = "Génération du PDF…";
  try {
    const r = await api(`/api/job/${JOB_ID}/cv`, { doc });
    // the server returns the document as saved (em dashes removed, for one)
    if (r.doc) { doc = r.doc; renderEditor(); }
    D.cv.meta = { ...D.cv.meta, pages: r.pages, density_step: r.density_step, edited_by_hand: true };
    setDirty(false); schedulePreview(0);
    toast(r.problems.length ? "PDF généré, à vérifier : " + r.problems.join(" ; ") : `PDF régénéré — ${r.pages} page(s), relu sans problème.`);
  } catch (e) { toast("Échec : " + e.message); }
  $("b-save").disabled = false; $("b-save").textContent = "Enregistrer et régénérer le PDF";
}
$("b-save").onclick = save;

$("head").addEventListener("click", async ev => {
  const act = ev.target.dataset.act;
  if (!act) return;
  const b = ev.target; b.disabled = true; const label = b.textContent;
  try {
    if (act === "evaluate") { b.textContent = "cv-router réfléchit (≈ 2 min)…"; await api(`/api/job/${JOB_ID}/evaluate`, {}); }
    else if (act === "tailor" || act === "approve-tailor") {
      if (act === "tailor" && D.cv && !confirm("Repartir de ton CV d'origine avec les modifications de cv-router ? Tes retouches manuelles seront perdues.")) { b.disabled = false; return; }
      if (act === "approve-tailor") await api(`/api/job/${JOB_ID}/status`, { action: "approve" });
      b.textContent = "Préparation du CV…"; await api(`/api/job/${JOB_ID}/tailor`, {});
    } else if (act === "validate") {
      if (dirty) await save();
      await api(`/api/job/${JOB_ID}/status`, { action: "validate" });
      toast("CV validé — prêt à être soumis.");
    } else {
      const notes = ["interview", "rejected", "offer"].includes(act) ? (prompt("Note (optionnelle) :") || "") : "";
      await api(`/api/job/${JOB_ID}/status`, { action: act, notes });
    }
    await load();
  } catch (e) { toast("Erreur : " + e.message); b.disabled = false; b.textContent = label; }
});

load().catch(e => { $("head").innerHTML = `<div class="empty">Erreur : ${esc(e.message)}</div>`; });
