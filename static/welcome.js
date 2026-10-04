// The welcome page reads its own state rather than being told. A step is done
// because the thing is done, so the page cannot claim progress that was undone
// behind it.

async function paintSteps() {
  let s;
  try { s = await api("/api/setup"); } catch (e) { return; }
  s.steps.forEach((st, i) => {
    const li = document.getElementById("w" + (i + 1));
    const tag = document.getElementById("w" + (i + 1) + "state");
    if (!li) return;
    li.classList.toggle("done", st.done);
    li.classList.toggle("now", !!st.current);
    if (tag) tag.textContent = st.done ? "Fait" : "";
  });
}

// Where the CVs are. Offered, not typed: an absolute path is not something to
// ask of someone who is here because they do not want a terminal. The PDF count
// is what makes the choice obvious.
async function paintFolders() {
  const box = document.getElementById("folders");
  if (!box) return;
  let d;
  try { d = await api("/api/folders"); }
  catch (e) { box.innerHTML = `<div class="fhelp" style="margin:0">Dossiers introuvables.</div>`; return; }

  box.innerHTML = d.folders.map(f => `
    <button type="button" role="radio" aria-checked="${f.current}"
            class="f${f.current ? " on" : ""}${f.pdfs ? "" : " empty"}"
            data-path="${esc(f.path)}">
      <span class="nm">${esc(f.label)}</span>
      <span class="pp">${esc(f.path)}</span>
      <span class="ct">${f.pdfs ? f.pdfs + (f.pdfs >= 400 ? "+" : "") + " PDF" : "aucun PDF"}</span>
    </button>`).join("");
}

async function useFolder(path) {
  if (!path) return;
  try {
    await api("/api/settings", { changes: { "paths.cv_root": path } });
    toast("Dossier enregistré.");
    await paintFolders();
    await paintSteps();
  } catch (e) {
    toast("Refusé : " + e.message);
  }
}

document.getElementById("folders")?.addEventListener("click", ev => {
  const b = ev.target.closest("button[data-path]");
  if (b) useFolder(b.dataset.path);
});

document.getElementById("b-other")?.addEventListener("click", () => {
  useFolder(document.getElementById("f-other").value.trim());
});

paintSteps();
paintFolders();
