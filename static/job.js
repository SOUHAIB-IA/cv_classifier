// One job: cv-router's verdict, and an editor for the CV that will be sent.
//
// The working copy `doc` is the structured CV behind the PDF. Every field is
// editable; fields that differ from your original CV are highlighted. Nothing
// reaches the PDF until you press "Enregistrer", and nothing is submitted
// until you validate the CV and click submit on the employer's form yourself.

let D = null, doc = null, base = null, TH = { auto: 70, review: 40 };
let dirty = false, previewTimer = null, reverted = new Set();

const $ = id => document.getElementById(id);
const norm = s => String(s ?? "").replace(/[’‘]/g, "'").replace(/[–-]/g, "-").replace(/\s+/g, " ").trim().toLowerCase();
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
  renderHead(); renderSend(); renderVerdict(); renderEdits(); renderEditor();
  schedulePreview(0);
  $("jd").textContent = D.job.jd_text || "";
  setDirty(false);
}

// Where this job stands, and whose move it is now.
function stepper(st, hasMatch, hasCv) {
  const order = ["new", "evaluated", "cv", "validated", "sent"];
  let at = "new";
  if (hasMatch) at = "evaluated";
  if (hasCv || st === "draft") at = "cv";
  if (st === "staged") at = "validated";
  if (["applied", "interview", "rejected", "offer"].includes(st)) at = "sent";
  const by = (D.autoapply && D.autoapply.enabled) ? "auto ou toi" : "toi";
  const labels = [["new", "Ajoutée", "auto"], ["evaluated", "Évaluée", "auto"],
                  ["cv", "CV préparé", "auto"], ["validated", "Validé par toi", "toi"],
                  ["sent", "Envoyée", by]];
  const idx = order.indexOf(at);
  return `<div class="steps">` + labels.map(([k, l, by], i) => {
    const cls = i < idx ? "done" : i === idx ? "now" : "";
    return `${i ? '<span class="sep">→</span>' : ""}<span class="s ${cls}">${l}<span class="sub"> · ${by}</span></span>`;
  }).join("") + `</div>`;
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
    // the buttons for this stage live in the send panel, next to the checks
    actions.push(`<button data-act="applied">J'ai envoyé la candidature</button>`,
                 `<button class="danger" data-act="withdrawn">Abandonner</button>`);
  } else if (["applied", "interview", "rejected", "offer"].includes(st)) {
    actions.push(`<button data-act="interview">Entretien</button>`, `<button data-act="rejected">Refus</button>`,
                 `<button data-act="offer">Offre</button>`);
  }
  const url = j.apply_url || j.jd_url;
  $("head").innerHTML = `
    <div class="t">
      <div class="nb" id="nb"></div>
      <h1>${esc(j.title)}</h1>
      <div class="sub">${esc(j.company)} · ${esc(j.location || "lieu non précisé")} · ${esc(j.source)}
        ${url ? ` · <a href="${esc(url)}" target="_blank" rel="noopener">voir l'annonce ↗</a>` : ""}</div>
      <div style="margin-top:6px"><span class="tag ${st}">${STATUS_FR[st] || st}</span>
        ${a && a.cv_variant ? `<span class="sub"> · CV de base : ${esc(a.cv_variant)}</span>` : ""}</div>
      ${stepper(st, !!m, !!D.cv)}
      <div class="actions">${actions.join("")}</div>
      <div id="send"></div>
      <div id="prefill"></div>
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

// The word on the left is what the CV shows; the address on the right is where
// it goes. They come from profile.toml, so the same three are on every CV, and
// you can still change them here for one application.
function linksEditor(c) {
  const links = c.links || (c.links = []);
  return `<label class="f">Liens cliquables</label>
    <div class="list">${links.map((l, li) => `
      <div class="grid" style="grid-template-columns:1fr 2.6fr auto;gap:6px">
        ${field(["contact", "links", li, "label"], l.label, { ph: "LinkedIn" })}
        ${field(["contact", "links", li, "url"], l.url, { ph: "https://…" })}
        <button class="ico danger" data-op="lk-del" data-li="${li}" title="Retirer">✕</button>
      </div>`).join("")}</div>
    <div class="legend" style="margin-top:4px">Le mot de gauche s'affiche sur le CV
      et renvoie vers l'adresse de droite, cliquable jusque dans le PDF.</div>
    <button class="small" style="margin-top:6px" data-op="lk-add">+ lien</button>`;
}

function renderEditor() {
  if (!doc) { $("b-save").disabled = true; return; }
  $("b-save").disabled = false;
  const c = doc.contact || (doc.contact = {});
  let h = `
    <div style="display:flex;gap:16px;align-items:center;margin-top:10px;font-size:13px;flex-wrap:wrap">
      <label style="display:flex;gap:8px;align-items:center">
        <input type="checkbox" id="show-photo" style="width:auto" ${doc.show_photo === false ? "" : "checked"}>
        Afficher ma photo</label>
      <label style="display:flex;gap:8px;align-items:center">Police
        <select id="cv-style" style="width:auto">
          ${[["calibri", "Calibri"], ["cambria", "Cambria"], ["garamond", "Garamond"], ["arial", "Arial"]]
            .map(([v, l]) => `<option value="${v}" ${(doc.style || "calibri") === v ? "selected" : ""}>${l}</option>`).join("")}
        </select></label>
    </div>
    <label class="f">Nom</label>${field(["name"], doc.name)}
    <label class="f">Accroche (titre sous le nom)</label>${field(["headline"], doc.headline)}
    <div class="grid" style="grid-template-columns:1fr 1fr 1fr;gap:6px">
      <div><label class="f">E-mail</label>${field(["contact", "email"], c.email)}</div>
      <div><label class="f">Téléphone</label>${field(["contact", "phone"], c.phone)}</div>
      <div><label class="f">Lieu</label>${field(["contact", "location"], c.location)}</div>
    </div>
    ${linksEditor(c)}
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
  if (el.id === "cv-style") {
    doc.style = el.value; setDirty(true); schedulePreview(0); return;
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
  const li = +b.dataset.li;
  if (op === "lk-del") (doc.contact.links || []).splice(li, 1);
  if (op === "lk-add") (doc.contact.links ||= []).push({ label: "", url: "" });
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
  // skills, case 1 : items were ADDED to a group ("added Kubernetes, Terraform"):
  // take exactly those back out
  if (!cur && /^added /.test(e.reason || "")) {
    const added = new Set(e.reason.slice(6).split(/\s*,\s*/).map(norm));
    const g = groups.find(g => g.items.some(x => added.has(norm(x))));
    if (g) { g.items = g.items.filter(x => !added.has(norm(x))); return true; }
    return false;
  }
  // skills, case 2 : a whole group was REPLACED by the suggested list: put the old list back
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
    if (revert(list[i])) { reverted.add(i); renderEdits(); renderEditor(); setDirty(true); schedulePreview(); toast("Modification annulée : pense à enregistrer."); }
    else toast("Texte introuvable : tu l'as sans doute déjà modifié à la main.");
  }
  if (ev.target.dataset.copy !== undefined) {
    await navigator.clipboard.writeText(list[+ev.target.dataset.copy].suggested);
    toast("Suggestion copiée : colle-la où tu veux dans l'éditeur.");
  }
});

// ---------------------------------------------------------------- preview --
// zoom: null = fit the available width; otherwise a fixed scale.
let zoom = null, pageH = 1123;
const PAGE_W = 794, PAGE_H = 1123;              // A4 at 96 dpi
const TOLERANCE = 24;                           // about one line of text, in px

function fitScale() {
  const pw = $("pw");
  return Math.max(0.2, (pw.clientWidth - 24) / PAGE_W);   // 24 = wrapper padding
}
function scalePreview() {
  const s = zoom ?? fitScale();
  const ifr = $("preview");
  ifr.style.height = pageH + "px";
  ifr.style.transform = `scale(${s})`;
  $("sizer").style.width = (PAGE_W * s) + "px";
  $("sizer").style.height = (pageH * s) + "px";
  // where page 1 ends, and page 2 if the content runs on
  $("sizer").querySelectorAll(".pagebreak").forEach(n => n.remove());
  // Screen and print lay text out a line apart at most, so a break is only
  // drawn when the content clearly runs past the page; the saved PDF's real
  // page count is shown next to the zoom and is the one that counts.
  for (let p = 1; p * PAGE_H < pageH - TOLERANCE; p++) {
    const d = document.createElement("div");
    d.className = "pagebreak"; d.style.top = (p * PAGE_H * s) + "px";
    d.innerHTML = `<span>≈ fin de la page ${p}</span>`;
    $("sizer").appendChild(d);
  }
  $("z-lvl").textContent = zoom == null ? `ajusté ${Math.round(s * 100)} %` : `${Math.round(s * 100)} %`;
}
function setZoom(z) { zoom = z == null ? null : Math.min(3, Math.max(0.3, z)); scalePreview(); }
$("z-in").onclick = () => setZoom((zoom ?? fitScale()) * 1.2);
$("z-out").onclick = () => setZoom((zoom ?? fitScale()) / 1.2);
$("z-fit").onclick = () => setZoom(null);

function setExpanded(on) {
  $("pv-card").classList.toggle("expanded", on);
  $("b-expand").textContent = on ? "Réduire ✕" : "Agrandir ⤢";
  document.body.style.overflow = on ? "hidden" : "";
  document.body.classList.toggle("pv-open", on);
  requestAnimationFrame(scalePreview);
}
$("b-expand").onclick = () => setExpanded(!$("pv-card").classList.contains("expanded"));
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && $("pv-card").classList.contains("expanded")) setExpanded(false);
  if (e.target.matches("input, textarea, select")) return;
  if (e.key === "+" || e.key === "=") $("z-in").click();
  if (e.key === "-") $("z-out").click();
});

// the preview's real height, so a CV that runs past one page shows it
$("preview").addEventListener("load", () => {
  try {
    const d = $("preview").contentDocument;
    pageH = Math.max(PAGE_H, d.documentElement.scrollHeight);
  } catch (e) { pageH = PAGE_H; }
  scalePreview();
});

function schedulePreview(delay = 400) {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(async () => {
    if (!doc) { $("preview").srcdoc = `<p style="font:14px sans-serif;color:#888;padding:20px">Pas encore de CV adapté.</p>`; return; }
    const density = D.cv?.meta?.density_step ?? 0;
    const html = await api(`/api/job/${JOB_ID}/preview`, { doc, lang: D.cv?.meta?.lang || "fr", density });
    const wrap = $("pw"), top = wrap.scrollTop, left = wrap.scrollLeft;   // keep your place while editing
    $("preview").srcdoc = html;
    $("preview").addEventListener("load", () => { wrap.scrollTop = top; wrap.scrollLeft = left; }, { once: true });
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

// ------------------------------------------------------------- pre-filling --
// Reviewing a queue means going through it, so the next one is a key away
// rather than a return to the dashboard and a hunt for where you were.
let NB = {};

async function neighbours() {
  try { NB = await api(`/api/job/${JOB_ID}/neighbours`); } catch (e) { return; }
  const box = $("nb");
  if (!box || NB.i == null) return;
  box.innerHTML = `<a href="/pipeline">← File d'attente</a>
    <span>·</span><span>${NB.i} sur ${NB.n}</span>
    <button class="ico" ${NB.prev ? "" : "disabled"} data-go="prev" title="Précédente (J)">↑</button>
    <button class="ico" ${NB.next ? "" : "disabled"} data-go="next" title="Suivante (K)">↓</button>`;
}

addEventListener("keydown", e => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) return;
  if (e.key === "j" && NB.prev) location.href = jobHref(NB.prev);
  if (e.key === "k" && NB.next) location.href = jobHref(NB.next);
});

// --------------------------------------------------------- sending it off --
// One panel for the last step, because the last step is the irreversible one.
// It shows the gate before it shows a button: every condition, met or not.
function renderSend() {
  const box = $("send");
  if (!box) return;
  const st = D.app ? D.app.status : "new";
  if (st !== "staged") { box.innerHTML = ""; return; }

  if (D.tier !== 1) {
    box.innerHTML = `<div class="send">
      <h3>À faire à la main</h3>
      <div class="why">LinkedIn et Indeed ne sont pas automatisés : ni remplissage, ni envoi.
        Ouvre l'annonce et postule avec le CV préparé ci-contre.</div>
      <div class="acts">
        <a class="btn primary" target="_blank" rel="noopener" href="${esc(D.job.apply_url || "#")}">Ouvrir l'annonce</a>
        <a class="btn" target="_blank" href="/job/${encodeURIComponent(JOB_ID)}/cv.pdf">Ouvrir le PDF</a>
      </div></div>`;
    return;
  }

  const aa = D.autoapply || {};
  const blockers = aa.blockers || [];
  const m = D.match || {};
  const ready = aa.enabled && !blockers.length;

  const checks = ready ? [
    ["ok", `fit ${m.fit_score} et ATS ${m.ats_score}, au-dessus de tes seuils (${aa.min_fit} / ${aa.min_ats})`],
    ["ok", `CV relu et validé par toi`],
    ["ok", `plafond du jour : ${aa.sent_today} / ${aa.max_per_day} envoyées`],
  ] : blockers.map(b => ["no", b]);

  box.innerHTML = `<div class="send ${ready ? "ready" : "blocked"}">
    <h3>${ready ? (aa.rehearse ? "Tout est vert (mode répétition)" : "Prête à partir sans toi")
                : "L'envoi automatique ne s'appliquera pas ici"}</h3>
    <div class="why">${ready
      ? `Il reste deux vérifications qui ne peuvent se faire qu'une fois le formulaire ouvert :
         <b>aucune question sans une réponse écrite par toi</b>, et <b>aucun CAPTCHA</b>.
         Si l'une échoue, le système s'arrête et te laisse la fenêtre déjà remplie.`
      : `Le formulaire sera rempli, puis la main te revient pour le dernier clic.`}</div>
    <div class="gate">${checks.map(([k, t]) =>
      `<div class="${k}"><span class="m">${k === "ok" ? "✓" : "✕"}</span><span>${esc(t)}</span></div>`).join("")}</div>
    <div class="acts">
      ${ready && !aa.rehearse ? `<button class="primary" data-act="autoapply">Remplir et envoyer</button>` : ""}
      ${ready ? `<button data-act="rehearse">Répétition : tout vérifier, ne rien envoyer</button>` : ""}
      <button class="${ready ? "" : "primary"}" data-act="prefill">Remplir et me laisser la main</button>
      <a class="btn" target="_blank" rel="noopener" href="${esc(D.job.apply_url || "#")}">Ouvrir le formulaire seul</a>
    </div>
    <div id="autostate"></div></div>`;
}

// The window stays visible the whole time, so you can watch and take over.
let autoTimer = null;

function renderAuto(st) {
  const box = $("autostate");
  if (!box) return;
  if (!st || st.state === "idle") { box.innerHTML = ""; return; }
  const r = st.report || {};
  const left = (r.required_left || []).slice(0, 12);
  const body = {
    running: `<h3>Formulaire en cours de remplissage…</h3>
              <div>La fenêtre est visible : tu peux suivre, et reprendre la main à tout moment.</div>`,
    filled: `<h3>Rempli : ${(r.filled || []).length} champs, ${(r.answered || []).length} réponses</h3>
             <div>Vérification de la dernière barrière…</div>`,
    handed_over: `<h3>Arrêté avant l'envoi</h3>
      <div>Le formulaire est rempli et ouvert. Ce qui a bloqué :</div>
      <ul>${(st.blockers || []).map(b => `<li>${esc(b)}</li>`).join("")}</ul>
      ${left.length ? `<div>Questions restantes : ${left.map(esc).join(", ")}</div>` : ""}
      <div style="margin-top:6px"><b>Complète dans la fenêtre, puis clique sur Envoyer toi-même.</b></div>`,
    rehearsed: `<h3>Répétition réussie</h3>
      <div>Toutes les vérifications sont passées. <b>Rien n'a été envoyé.</b> Mets
      <code>rehearse = false</code> dans <code>pipeline.toml</code> pour que ce cas parte vraiment.</div>`,
    sent: `<h3 style="color:var(--accent)">Envoyée, et confirmée par l'employeur</h3>
           <div>Le statut est passé à « envoyée ».</div>`,
    unconfirmed: `<h3>Envoyée, mais sans confirmation lue</h3>
      <div>Le clic est parti, mais aucune page de confirmation n'a été reconnue.
      Vérifie dans la fenêtre : si c'est bien passé, marque-la comme envoyée.</div>`,
    refused: `<h3>Non éligible</h3><ul>${(st.blockers || []).map(b => `<li>${esc(b)}</li>`).join("")}</ul>`,
    error: `<h3>Échec</h3><div>${esc(st.note || "")}</div>`,
  }[st.state] || `<div>${esc(st.state)}</div>`;

  box.innerHTML = `<div class="panel" style="margin-top:12px">${body}
    ${["handed_over", "unconfirmed"].includes(st.state)
      ? `<div class="acts" style="margin-top:8px"><button class="primary" data-act="applied">C'est envoyé</button></div>` : ""}
  </div>`;
}

async function pollAuto() {
  clearTimeout(autoTimer);
  let st;
  try { st = await api(`/api/job/${JOB_ID}/autoapply`); } catch (e) { return; }
  renderAuto(st);
  if (["running", "filled"].includes(st.state)) autoTimer = setTimeout(pollAuto, 2000);
  else if (st.state === "sent") load();
}

// The form opens in a real window, filled with your details and CV, and stops
// there. Nothing clicks submit: that is yours.
let prefillTimer = null;

function renderPrefill(st) {
  const box = $("prefill");
  if (!st || st.state === "idle") { box.innerHTML = ""; return; }
  if (st.state === "running" && !st.report) {
    box.innerHTML = `<div class="panel">Ouverture du formulaire et remplissage…</div>`;
    return;
  }
  if (st.state === "error") {
    box.innerHTML = `<div class="panel"><h3>Le formulaire n'a pas pu être ouvert</h3>${esc(st.error || "")}</div>`;
    return;
  }
  const r = st.report || {};
  box.innerHTML = `<div class="panel">
    <h3>${st.state === "closed" ? "Fenêtre fermée" : "Formulaire ouvert dans une fenêtre"}</h3>
    <div>Champs remplis : <b>${(r.filled || []).join(", ") || "aucun"}</b></div>
    <div>CV : <b>${r.resume ? "joint" : "NON joint, attache-le toi-même"}</b></div>
    ${r.captcha ? `<div><b>Un CAPTCHA est présent</b> : à toi de le résoudre, rien ici n'y touche.</div>` : ""}
    ${(r.required_left || []).length ? `<div style="margin-top:6px">Il reste à répondre, toi seul peux le faire :
      <ul>${r.required_left.slice(0, 12).map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>` : ""}
    <div style="margin-top:8px"><b>Relis, complète, puis clique sur « Envoyer » dans la fenêtre.</b></div>
    <div class="actions" style="margin-top:8px">
      <button class="primary" data-act="applied">C'est envoyé</button>
      <button data-act="prefill">Rouvrir le formulaire</button>
    </div></div>`;
}

async function pollPrefill() {
  clearTimeout(prefillTimer);
  let st;
  try { st = await api(`/api/job/${JOB_ID}/prefill`); } catch (e) { return; }
  renderPrefill(st);
  if (st.state === "running" || st.state === "filled") prefillTimer = setTimeout(pollPrefill, 2000);
}

// ---------------------------------------------------------------- actions --
async function save() {
  $("b-save").disabled = true; $("b-save").textContent = "Génération du PDF…";
  try {
    const r = await api(`/api/job/${JOB_ID}/cv`, { doc });
    // the server returns the document as saved (em dashes removed, for one)
    if (r.doc) { doc = r.doc; renderEditor(); }
    D.cv.meta = { ...D.cv.meta, pages: r.pages, density_step: r.density_step, edited_by_hand: true };
    setDirty(false); schedulePreview(0);
    toast(r.problems.length ? "PDF généré, à vérifier : " + r.problems.join(" ; ") : `PDF régénéré : ${r.pages} page(s), relu sans problème.`);
  } catch (e) { toast("Échec : " + e.message); }
  $("b-save").disabled = false; $("b-save").textContent = "Enregistrer et régénérer le PDF";
}
$("b-save").onclick = save;

$("head").addEventListener("click", async ev => {
  const go = ev.target.dataset.go;
  if (go) { const id = NB[go]; if (id) location.href = jobHref(id); return; }
  const act = ev.target.dataset.act;
  if (!act) return;
  const b = ev.target; b.disabled = true; const label = b.textContent;
  try {
    if (act === "evaluate") { b.textContent = "cv-router réfléchit (≈ 2 min)…"; await api(`/api/job/${JOB_ID}/evaluate`, {}); }
    else if (act === "tailor" || act === "approve-tailor") {
      if (act === "tailor" && D.cv && !confirm("Repartir de ton CV d'origine avec les modifications de cv-router ? Tes retouches manuelles seront perdues.")) { b.disabled = false; return; }
      if (act === "approve-tailor") await api(`/api/job/${JOB_ID}/status`, { action: "approve" });
      b.textContent = "Préparation du CV…"; await api(`/api/job/${JOB_ID}/tailor`, {});
    } else if (act === "prefill") {
      b.textContent = "Ouverture…";
      const r = await api(`/api/job/${JOB_ID}/prefill`, {});
      if (r.profile_set === false) toast("profile.toml est vide : seul le CV sera joint.");
      pollPrefill();
      b.disabled = false; b.textContent = label;
      return;
    } else if (act === "autoapply" || act === "rehearse") {
      // The only irreversible action in the interface, so it is the only one
      // that asks — and it names the employer, not just "confirm?".
      const real = act === "autoapply";
      if (real && !confirm(
            `Envoyer ta candidature à ${D.job.company} pour « ${D.job.title} » ?\n\n`
          + `Le formulaire sera rempli puis soumis, sans autre confirmation.\n`
          + `Une candidature envoyée ne se reprend pas.`)) {
        b.disabled = false; return;
      }
      b.textContent = real ? "Envoi en cours…" : "Répétition…";
      await api(`/api/job/${JOB_ID}/autoapply`, { rehearse: !real });
      pollAuto();
      b.disabled = false; b.textContent = label;
      return;
    } else if (act === "validate") {
      if (dirty) await save();
      await api(`/api/job/${JOB_ID}/status`, { action: "validate" });
      toast("CV validé : prêt à être soumis.");
    } else {
      const notes = ["interview", "rejected", "offer"].includes(act) ? (prompt("Note (optionnelle) :") || "") : "";
      await api(`/api/job/${JOB_ID}/status`, { action: act, notes });
    }
    await load();
  } catch (e) { toast("Erreur : " + e.message); b.disabled = false; b.textContent = label; }
});

// After load, not before: both panels render into containers that renderHead
// and renderSend create, so polling first would drop the state on the floor.
load()
  .then(() => { pollPrefill(); pollAuto(); neighbours(); })
  .catch(e => { $("head").innerHTML = `<div class="empty">Erreur : ${esc(e.message)}</div>`; });
