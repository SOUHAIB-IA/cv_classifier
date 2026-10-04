// The welcome page reads its own state rather than being told. A step is done
// because the thing is done, so the page cannot claim progress that was undone
// behind it.
(async () => {
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
})();
