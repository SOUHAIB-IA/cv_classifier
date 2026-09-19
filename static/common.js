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

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
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

function ago(ts) {
  if (!ts) return "";
  const s = (Date.now() - new Date(ts).getTime()) / 1000;
  if (s < 60) return "à l'instant";
  if (s < 3600) return Math.round(s / 60) + " min";
  if (s < 86400) return Math.round(s / 3600) + " h";
  return Math.round(s / 86400) + " j";
}
