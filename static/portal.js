// The first screen, when there is nothing to analyse yet.
//
// Reading the collection takes minutes and the page has to stay honest the
// whole time: a count that comes from the indexer's own output, a bar that
// follows it, and a failure that says what was kept.

const bIndex = document.getElementById("b-index");

if (bIndex) {
  const box = document.getElementById("index-progress");
  const bar = document.getElementById("index-bar");
  const count = document.getElementById("index-count");
  const note = document.getElementById("index-note");
  const hint = document.getElementById("index-hint");
  let timer = null;

  // The state is read from the server on every tick and written straight to
  // the DOM. Nothing here waits for a transition to end: an interrupted
  // animation must never be what decides whether the button is still busy.
  function paint(s) {
    box.hidden = false;
    const total = s.total || 0;
    const done = Math.min(s.done || 0, total);
    bar.style.width = total ? Math.round((done / total) * 100) + "%" : "0%";

    if (s.state === "running") {
      count.textContent = total
        ? `${done} sur ${total}`
        : "Lecture des fichiers…";
      note.textContent = s.skipped ? `${s.skipped} déjà à jour` : "";
    } else if (s.state === "done" && !total) {
      // An empty folder finishes instantly and changes nothing, so reloading
      // would drop the reader back on this same screen with no explanation.
      bar.style.width = "0%";
      count.textContent = "Aucun PDF dans ce dossier.";
      note.textContent = "Vérifie le chemin, ou dépose tes CV dedans.";
    } else if (s.state === "done") {
      bar.style.width = "100%";
      count.textContent = "Terminé.";
      note.textContent = "La page se recharge.";
    } else if (s.state === "error") {
      box.setAttribute("role", "alert");
      count.textContent = "La lecture s'est arrêtée.";
      note.textContent = s.error || "";
    }

    const busy = s.state === "running";
    bIndex.disabled = busy;
    bIndex.setAttribute("aria-busy", busy ? "true" : "false");
    bIndex.textContent = busy ? "Lecture en cours" : "Lire mes CV";
    hint.textContent = busy
      ? "Tu peux laisser cette page ouverte."
      : "Compte une à deux minutes pour une vingtaine de CV.";
  }

  async function poll() {
    try {
      const s = await api("/api/index");
      paint(s);
      if (s.state === "running") return;
      clearInterval(timer);
      timer = null;
      // Once there is something in the index this page has a different job, so
      // let the server decide what it should now be.
      if (s.state === "done" && s.total) setTimeout(() => location.reload(), 900);
    } catch (e) {
      clearInterval(timer);
      timer = null;
      paint({ state: "error", error: e.message });
    }
  }

  bIndex.onclick = async () => {
    bIndex.disabled = true;
    bIndex.setAttribute("aria-busy", "true");
    try {
      const r = await api("/api/index/start", {});
      paint(r.status);
      timer = setInterval(poll, 1500);
    } catch (e) {
      bIndex.disabled = false;
      bIndex.setAttribute("aria-busy", "false");
      toast("Échec : " + e.message);
    }
  };

  // A run started before this page was opened, or left running in another tab.
  api("/api/index").then(s => {
    if (s.state === "running") { paint(s); timer = setInterval(poll, 1500); }
  }).catch(() => {});
}


// ------------------------------------------------- what to do with a result --
// "Ouvrir" is a plain link. The other two go through the same helpers as the
// rest of the application: api() carries the header the server asks for.
const actions = document.getElementById("result-actions");

if (actions) {
  const data = JSON.parse(document.getElementById("result-data").textContent);
  const form = document.getElementById("follow-form");
  const done = document.getElementById("follow-done");
  const follow = document.getElementById("a-follow");

  document.getElementById("a-reveal").onclick = async () => {
    try {
      const r = await api("/api/cv/reveal", { path: data.result.best.path });
      toast(r.selected ? "Le fichier est sélectionné dans la fenêtre qui vient de s'ouvrir."
                       : "Le dossier est ouvert, le fichier n'est pas sélectionné.");
    } catch (e) { toast(e.message); }
  };

  follow.onclick = () => {
    // the first line of an ad is nearly always the job title
    const first = data.job.split("\n").map(l => l.trim()).find(Boolean) || "";
    document.getElementById("f-title").value ||= first.slice(0, 80);
    form.hidden = false;
    document.getElementById("f-company").focus();
  };

  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const btn = form.querySelector("button");
    btn.disabled = true;
    btn.setAttribute("aria-busy", "true");      // the tracker export takes a moment
    try {
      const r = await api("/api/follow", {
        jd: data.job, result: data.result,
        company: document.getElementById("f-company").value,
        title: document.getElementById("f-title").value,
      });
      form.hidden = true;
      follow.hidden = true;
      done.hidden = false;
      done.innerHTML = (r.already ? "Cette candidature était déjà suivie. " : "C'est suivi. ")
        + `<a href="/job/${encodeURIComponent(r.job_id)}">Voir la fiche</a>`;
    } catch (e) {
      toast(e.message);
      btn.disabled = false;
      btn.removeAttribute("aria-busy");
    }
  };
}
