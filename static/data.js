// Every posting the system has seen, in one table.
//
// The filter state lives in the URL, so a view you built is a link you can keep,
// reload, or send yourself — and the CSV button exports exactly what the table
// is showing rather than everything.

const COLS = [
  { k: "company", t: "Entreprise", sort: "company" },
  { k: "title", t: "Intitulé", sort: "title" },
  { k: "location", t: "Lieu" },
  { k: "fit_score", t: "Fit", sort: "fit" },
  { k: "ats_score", t: "ATS", sort: "ats" },
  { k: "prefilter_score", t: "Pré-filtre", sort: "prefilter" },
  { k: "apply_kind", t: "Candidature" },
  { k: "questions_left", t: "Questions" },
  { k: "stage", t: "Étape" },
  { k: "status", t: "Statut" },
  { k: "posted_date", t: "Publiée", sort: "posted" },
  { k: "first_seen", t: "Vue le", sort: "first_seen" },
  { k: "source", t: "Source" },
];

let TH = { auto: 70, review: 40 };
let state = { q: "", stage: "", status: "", source: "", fit_min: "", has_app: "",
              apply_kind: "", sort: "first_seen", dir: "desc", page: 1, per: 50 };

// How much work an application is, and how much of it is already known.
const APPLY_FR = {
  form: "formulaire ATS", site: "site de l'employeur",
  platform: "LinkedIn / Indeed", unknown: "sans lien"
};

function fromUrl() {
  const u = new URLSearchParams(location.search);
  for (const k of Object.keys(state)) if (u.has(k)) state[k] = u.get(k);
  state.page = Math.max(1, +state.page || 1);
  state.per = +state.per || 50;
}

function query(extra = {}) {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries({ ...state, ...extra }))
    if (v !== "" && v != null) u.set(k, v);
  return u;
}

// The URL is the state: replaceState keeps the back button meaning "the page
// before", not "the filter before", which is what people actually expect.
function push() {
  history.replaceState(null, "", "?" + query().toString());
}

function head() {
  document.getElementById("head").innerHTML = COLS.map(c => {
    if (!c.sort) return `<th>${c.t}</th>`;
    const on = state.sort === c.sort;
    return `<th data-sort="${c.sort}">${c.t}${on ? `<span class="ar"> ${state.dir === "asc" ? "▲" : "▼"}</span>` : ""}</th>`;
  }).join("");
}

function cell(r, k) {
  if (k === "company") return `<b>${esc(r.company)}</b>`;
  if (k === "title") {
    const href = r.status || r.fit_score != null ? jobHref(r.job_id) : (r.jd_url || r.apply_url || "#");
    const ext = !(r.status || r.fit_score != null);
    return `<a href="${esc(href)}" ${ext ? 'target="_blank" rel="noopener"' : ""}
            >${esc(r.title)}</a>${ext ? ' <span class="sub">↗</span>' : ""}`;
  }
  if (k === "fit_score" && r.fit_score != null)
    return `<span class="fit ${fitClass(r.fit_score, TH)}">${r.fit_score}</span>`;
  if (k === "prefilter_score" && r.prefilter_score != null)
    return r.prefilter_score.toFixed(2);
  if (k === "status" && r.status)
    return `<span class="tag ${r.status}">${STATUS_FR[r.status] || r.status}</span>`;
  if (k === "apply_kind")
    return `<span class="tag ${r.apply_kind === "form" ? "draft" : ""}">${esc(APPLY_FR[r.apply_kind] || r.apply_kind || "")}</span>`;
  if (k === "questions_left")
    // measured on a real fill: 0 means everything was answerable from your
    // profile, which is as close to "easy apply" as this can honestly say
    return r.questions_left == null ? '<span class="sub">–</span>'
      : r.questions_left === 0 ? `<span class="fit hi">0</span>`
      : `<span class="fit mid">${r.questions_left}</span>`;
  if (k === "stage") return `<span class="sub">${esc(STAGE_FR[r.stage] || r.stage || "")}</span>`;
  // some boards list every country a role is open in; one of those must not
  // become a column three hundred pixels tall
  if (k === "location")
    return `<span class="sub clamp" title="${esc(r.location || "")}">${esc(r.location || "")}</span>`;
  if (k === "source") return `<span class="sub">${esc(r.source || "")}</span>`;
  const v = r[k];
  return v == null || v === "" ? '<span class="sub">–</span>' : esc(String(v).slice(0, 10));
}

async function load() {
  push();
  document.getElementById("f-csv").href = "/api/data.csv?" +
    query({ page: null, per: null }).toString();
  let d;
  try { d = await api("/api/data?" + query().toString()); }
  catch (e) { toast("Erreur : " + e.message); return; }

  head();
  document.getElementById("count").textContent =
    d.total ? `${d.total.toLocaleString("fr")} offre${d.total > 1 ? "s" : ""}` : "Aucune offre";
  // Two sentences, not one. Nothing matching a filter and nothing existing at
  // all are different situations, and the old single sentence blamed the reader
  // for a filter they had never set.
  const filtered = ["q", "stage", "status", "source", "fit_min", "has_app",
                    "apply_kind"].some(k => state[k] !== "" && state[k] != null);
  const nothing = filtered
    ? "Aucune offre ne correspond à ces filtres."
    : "Aucune offre pour l'instant. Le pipeline en collecte quand tu le "
      + "démarres, dans l'onglet Pipeline.";
  document.getElementById("rows").innerHTML = d.rows.map(r =>
    `<tr>${COLS.map(c => `<td>${cell(r, c.k)}</td>`).join("")}</tr>`).join("")
    || `<tr><td colspan="${COLS.length}" class="empty">${nothing}</td></tr>`;

  document.getElementById("pginfo").textContent = `page ${d.page} sur ${d.pages}`;
  document.getElementById("pg-first").disabled = d.page <= 1;
  document.getElementById("pg-prev").disabled = d.page <= 1;
  document.getElementById("pg-next").disabled = d.page >= d.pages;

  // facets are filled once; refilling them on every load would reset a choice
  if (!document.getElementById("f-stage").options.length) {
    const fill = (id, items, label) => {
      document.getElementById(id).innerHTML = `<option value="">${label}</option>` +
        items.filter(x => x.v).map(x =>
          `<option value="${esc(x.v)}">${esc(STATUS_FR[x.v] || x.v)} (${x.n})</option>`).join("");
      document.getElementById(id).value = state[id.slice(2)] || "";
    };
    fill("f-stage", d.facets.stage, "toutes");
    fill("f-status", d.facets.status, "tous");
    fill("f-source", d.facets.source, "toutes");
    document.getElementById("f-apply").innerHTML =
      `<option value="">toutes</option>` + (d.facets.apply_kind || []).filter(x => x.v)
        .map(x => `<option value="${esc(x.v)}">${esc(APPLY_FR[x.v] || x.v)} (${x.n})</option>`).join("");
    document.getElementById("f-apply").value = state.apply_kind || "";
  }
}

// ------------------------------------------------------------------ events --
const bind = (id, key, ev = "change") =>
  document.getElementById(id).addEventListener(ev, e => {
    state[key] = e.target.type === "checkbox" ? (e.target.checked ? "1" : "") : e.target.value;
    state.page = 1;
    load();
  });

let qTimer;
document.getElementById("f-q").addEventListener("input", e => {
  clearTimeout(qTimer);
  qTimer = setTimeout(() => { state.q = e.target.value; state.page = 1; load(); }, 220);
});
bind("f-stage", "stage"); bind("f-status", "status"); bind("f-source", "source");
bind("f-apply", "apply_kind");
bind("f-fit", "fit_min", "input"); bind("f-app", "has_app"); bind("f-per", "per");

document.getElementById("head").addEventListener("click", e => {
  const th = e.target.closest("[data-sort]");
  if (!th) return;
  const s = th.dataset.sort;
  state.dir = state.sort === s && state.dir === "desc" ? "asc" : "desc";
  state.sort = s; state.page = 1;
  load();
});

document.getElementById("f-clear").onclick = () => {
  state = { ...state, q: "", stage: "", status: "", source: "", fit_min: "", has_app: "", apply_kind: "", page: 1 };
  for (const id of ["f-q", "f-fit"]) document.getElementById(id).value = "";
  for (const id of ["f-stage", "f-status", "f-source", "f-apply"]) document.getElementById(id).value = "";
  document.getElementById("f-app").checked = false;
  load();
};
document.getElementById("pg-first").onclick = () => { state.page = 1; load(); };
document.getElementById("pg-prev").onclick = () => { state.page = Math.max(1, state.page - 1); load(); };
document.getElementById("pg-next").onclick = () => { state.page += 1; load(); };

(async () => {
  fromUrl();
  document.getElementById("f-q").value = state.q || "";
  document.getElementById("f-fit").value = state.fit_min || "";
  document.getElementById("f-app").checked = !!state.has_app;
  document.getElementById("f-per").value = String(state.per);
  try { TH = (await api("/api/pipeline/state")).thresholds; } catch (e) { /* defaults */ }
  load();
})();
