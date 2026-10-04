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
