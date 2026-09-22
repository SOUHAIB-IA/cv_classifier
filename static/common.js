// Shared helpers for the pipeline pages.

// Every call that changes something carries X-CV-Router: the server refuses
// mutations without it, which keeps other sites from driving this localhost app.
async function api(path, body, method) {
  const opt = { method: method || (body === undefined ? "GET" : "POST"), headers: {} };
  if (body !== undefined) {
    opt.headers["Content-Type"] = "application/json";
    opt.headers["X-CV-Router"] = "1";
    opt.body = JSON.stringify(body);
  }
  const r = await fetch(path, opt);
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error((data && data.detail) || data.error || r.statusText);
  return data;
}

// Evaluations stored before the model was told to avoid it still carry the em
// dash; strip it on display too, so it never shows up anywhere.
function noDash(s) {
  return String(s ?? "").replace(/\s+[—―]\s+/g, ", ").replace(/[—―]/g, "-");
}

function esc(s) {
  s = noDash(s);
  return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function fitClass(f, th) {
  if (f == null) return "";
  return f >= th.auto ? "hi" : f >= th.review ? "mid" : "lo";
}

function jobHref(id) { return "/job/" + encodeURIComponent(id).replace(/%3A/g, ":"); }

let toastTimer;
function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.classList.add("on");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("on"), 3500);
}

const STATUS_FR = {
  draft: "à relire", staged: "à soumettre", review: "revue", pending: "en préparation",
  applied: "envoyée", interview: "entretien", rejected: "refus", offer: "offre",
  skipped: "écartée", withdrawn: "abandonnée"
};

// jobs.stage, for the places that show a posting nobody has acted on yet
const STAGE_FR = {
  sourced: "collectée", filtered: "écartée au pré-filtre", candidate: "en attente",
  matched: "évaluée", tailored: "CV préparé", skipped: "écartée", error: "erreur"
};

function ago(ts) {
  if (!ts) return "";
  const s = (Date.now() - new Date(ts).getTime()) / 1000;
  if (s < 60) return "à l'instant";
  if (s < 3600) return Math.round(s / 60) + " min";
  if (s < 86400) return Math.round(s / 3600) + " h";
  return Math.round(s / 86400) + " j";
}

// --------------------------------------------------------- search anywhere --
// Ctrl+K from any page. Five thousand postings and four pages of navigation
// make "where was that Doctolib one" a question the menus cannot answer, so
// the answer is a box that is always one key away.
(function () {
  let box, input, list, rows = [], at = 0, timer;

  function build() {
    box = document.createElement("div");
    box.className = "palette";
    box.innerHTML = `<div class="pal-card">
      <input id="pal-in" placeholder="Entreprise ou intitulé…" autocomplete="off" spellcheck="false">
      <div class="pal-list" id="pal-list"></div>
      <div class="pal-foot"><kbd>↑</kbd><kbd>↓</kbd> parcourir
        <kbd>Entrée</kbd> ouvrir <kbd>Échap</kbd> fermer</div></div>`;
    document.body.appendChild(box);
    input = box.querySelector("#pal-in");
    list = box.querySelector("#pal-list");
    box.addEventListener("mousedown", e => { if (e.target === box) close(); });
    input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(run, 160); });
    input.addEventListener("keydown", key);
    list.addEventListener("mousedown", e => {
      const a = e.target.closest("[data-i]");
      if (a) { at = +a.dataset.i; go(); }
    });
  }

  function open() {
    if (!box) build();
    box.classList.add("on");
    input.value = ""; rows = []; at = 0;
    list.innerHTML = `<div class="pal-empty">Tape au moins deux lettres.</div>`;
    input.focus();
  }
  function close() { if (box) box.classList.remove("on"); }

  async function run() {
    const q = input.value.trim();
    if (q.length < 2) { rows = []; list.innerHTML = `<div class="pal-empty">Tape au moins deux lettres.</div>`; return; }
    try { rows = (await api("/api/search?q=" + encodeURIComponent(q))).rows; }
    catch (e) { return; }
    at = 0;
    list.innerHTML = rows.length ? rows.map((r, i) => `
      <a class="pal-row ${i === at ? "on" : ""}" data-i="${i}" href="${jobHref(r.job_id)}">
        <span class="t"><b>${esc(r.title)}</b><span>${esc(r.company)} · ${esc(r.location || "")}</span></span>
        ${r.fit_score != null ? `<span class="fit">${r.fit_score}</span>` : ""}
        <span class="tag ${r.status || ""}">${STATUS_FR[r.status] || STAGE_FR[r.stage] || r.stage || ""}</span>
      </a>`).join("")
      : `<div class="pal-empty">Rien pour « ${esc(q)} ».</div>`;
  }

  function move(d) {
    if (!rows.length) return;
    at = (at + d + rows.length) % rows.length;
    [...list.querySelectorAll(".pal-row")].forEach((el, i) => el.classList.toggle("on", i === at));
    list.querySelectorAll(".pal-row")[at].scrollIntoView({ block: "nearest" });
  }
  function go() { if (rows[at]) location.href = jobHref(rows[at].job_id); }

  function key(e) {
    if (e.key === "Escape") { close(); return; }
    if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
    if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
    if (e.key === "Enter") { e.preventDefault(); go(); }
  }

  addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); open(); }
    // "/" is the other habit, but not while you are writing in a CV
    if (e.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) {
      e.preventDefault(); open();
    }
  });
  addEventListener("click", e => {
    if (e.target.closest("#open-search")) open();
  });
})();
