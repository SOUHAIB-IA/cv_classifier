// The settings page draws itself from the schema the server sends, so adding a
// setting is one entry in settings.py and nothing here.
//
// Nothing is written until you press Enregistrer: edits live in `edits` until
// then, and the button counts them, because a page that saves as you type gives
// you no moment to change your mind about a setting that sends applications.

let S = null;            // schema + current values
let edits = {};          // id -> new value, only what actually differs
// The tab in view. Empty means the first one the server sends, so the order
// of GROUPS in settings.py decides where a first run lands, and adding a
// group never needs an edit here.
let tab = "";
let testTimer = null;

const val = id => (id in edits ? edits[id] : S.values[id]);

function setVal(id, v) {
  const same = JSON.stringify(v) === JSON.stringify(S.values[id]);
  if (same) delete edits[id]; else edits[id] = v;
  // Switching provider while the model name still belongs to the old one is a
  // guaranteed 404, so carry the new provider's usual name across — but only
  // over a name you did not choose yourself.
  if (id === "ai.provider") {
    const cur = String(val("ai.model") || "");
    const defaults = Object.values(S.providers).map(p => p.model).filter(Boolean);
    if (!cur || defaults.includes(cur)) {
      const next = (S.providers[v] || {}).model || "";
      if (next !== cur) setVal("ai.model", next);
    }
  }
  render();                       // a change can reveal or hide dependent fields
}

// "ai.backend=api" — a field that only makes sense once another is set
function shown(f) {
  if (!f.depends) return true;
  const [id, want] = f.depends.split("=");
  const v = val(id);
  return String(v) === want;
}

function field(f) {
  const v = val(f.id), changed = f.id in edits;
  const help = f.help ? `<div class="fhelp">${esc(f.help)}</div>` : "";
  let body = "";

  if (f.kind === "choice") {
    body = `<div class="opts">${f.options.map(([ov, ol, note]) => `
      <label class="opt ${String(v) === ov ? "on" : ""}">
        <input type="radio" name="${esc(f.id)}" value="${esc(ov)}" ${String(v) === ov ? "checked" : ""}
               data-id="${esc(f.id)}" data-kind="choice">
        <span><b>${esc(ol)}</b>${note ? `<span class="note">${esc(note)}</span>` : ""}</span>
      </label>`).join("")}</div>`;
  } else if (f.kind === "toggle") {
    body = `<label class="sw">
      <input type="checkbox" ${v ? "checked" : ""} data-id="${esc(f.id)}" data-kind="toggle">
      <span class="track"><span class="knob"></span></span>
      <span class="swtxt">${v ? "activé" : "désactivé"}</span></label>`;
  } else if (f.kind === "number") {
    body = `<div class="num">
      <input type="number" value="${esc(v)}" min="${f.min ?? ""}" max="${f.max ?? ""}"
             step="${f.step || 1}" data-id="${esc(f.id)}" data-kind="number">
      ${f.unit ? `<span class="unit">${esc(f.unit)}</span>` : ""}</div>`;
  } else if (f.kind === "model") {
    // a known list with known prices for Anthropic, a name you type for the rest
    if (String(val("ai.provider")) === "anthropic") {
      body = `<div class="opts">${f.options.map(([ov, ol, note]) => `
        <label class="opt ${String(v) === ov ? "on" : ""}">
          <input type="radio" name="${esc(f.id)}" value="${esc(ov)}" ${String(v) === ov ? "checked" : ""}
                 data-id="${esc(f.id)}" data-kind="choice">
          <span><b>${esc(ol)}</b><span class="note">${esc(note)}</span></span>
        </label>`).join("")}</div>`;
    } else {
      const p = S.providers[String(val("ai.provider"))] || {};
      body = `<div class="num">
        <input value="${esc(v)}" placeholder="${esc(p.model || "nom du modèle")}"
               style="max-width:340px" data-id="${esc(f.id)}" data-kind="text">
        ${p.model && v !== p.model ? `<button class="small" data-suggest="${esc(p.model)}">Utiliser ${esc(p.model)}</button>` : ""}
      </div>`;
    }
  } else if (f.kind === "tags") {
    const items = Array.isArray(v) ? v : [];
    body = `<div class="tagbox" data-for="${esc(f.id)}">
      ${items.map((x, i) => `<span class="tg">${esc(x)}<button data-del="${esc(f.id)}" data-i="${i}" title="Retirer">✕</button></span>`).join("")}
      <input class="tagin" placeholder="ajouter, puis Entrée" data-add="${esc(f.id)}">
    </div>`;
  } else {
    body = `<input value="${esc(v)}" data-id="${esc(f.id)}" data-kind="text">`;
  }

  return `<div class="set ${changed ? "edited" : ""}">
    <div class="slab">${esc(f.label)}${changed ? `<span class="badge">modifié</span>` : ""}</div>
    ${help}${body}</div>`;
}

// The brain group carries things no schema field can express: whether a key is
// stored, where Claude Code lives, and whether a real call actually works.
function brainExtras() {
  const backend = String(val("ai.backend"));
  const k = S.key;
  const prov = S.providers[String(val("ai.provider"))] || {};
  const cli = `<div class="set">
    <div class="slab">Claude Code sur cette machine</div>
    ${S.claude_bin
      ? `<div class="okline"><b>✓</b> trouvé : <code>${esc(S.claude_bin)}</code></div>`
      : `<div class="noline"><b>✕</b> introuvable. Installe Claude Code, ou choisis une clé API ci-dessus.</div>`}
  </div>`;
  const key = `<div class="set">
    <div class="slab">Clé ${esc(prov.label || "API")}</div>
    <div class="fhelp">Elle est écrite dans un fichier à part, lisible par toi seul, et
      n'est jamais réaffichée.${prov.keys_at ? ` Tu la crées sur <code>${esc(prov.keys_at)}</code>.` : ""}</div>
    ${k.set
      ? `<div class="okline"><b>✓</b> enregistrée ${k.source === "env"
          ? "dans la variable d'environnement ANTHROPIC_API_KEY"
          : `dans <code>${esc(k.path || "")}</code>`} (se termine par <code>${esc(k.hint)}</code>)</div>`
      : `<div class="noline"><b>✕</b> aucune clé enregistrée</div>`}
    <div class="num" style="margin-top:8px">
      <input type="password" id="key-in" placeholder="${esc(prov.prefix ? prov.prefix + "…" : "colle ta clé ici")}" autocomplete="off">
      <button id="b-key">Enregistrer la clé</button>
      ${k.set && k.source === "file" ? `<button class="danger" id="b-key-del">Supprimer</button>` : ""}
    </div>
  </div>`;
  const none = `<div class="set"><div class="slab">Aucune clé nécessaire</div>
    <div class="fhelp">Le modèle tourne sur ta machine. Vérifie simplement qu'il est
      démarré et que le nom du modèle correspond à celui que tu as installé.</div></div>`;
  return (backend === "claude_cli" ? cli : (prov.no_key ? none : key)) + `
    <div class="set">
      <div class="slab">Vérifier que ça marche</div>
      <div class="fhelp">Un vrai appel, minuscule, sur le réglage actuellement enregistré.
        Avec l'abonnement, compte une vingtaine de secondes.</div>
      <div class="acts"><button id="b-test">Tester maintenant</button>
        <span id="test-out" class="live-state"></span></div>
    </div>`;
}

// Getting a company's slug wrong otherwise costs a whole 45-minute cycle to
// find out, so this asks the three platforms directly and says which one has it.
function boardFinder() {
  return `<div class="set">
    <div class="slab">Chercher une entreprise</div>
    <div class="fhelp">Tape son nom court, tel qu'il apparaît dans l'adresse de sa page
      emploi. Les trois plateformes sont interrogées tout de suite, et je te dis
      laquelle l'héberge et combien d'offres elle a en ce moment.</div>
    <div class="num">
      <input id="b-slug" placeholder="stripe" style="max-width:200px">
      <input id="b-name" placeholder="Nom affiché (optionnel)" style="max-width:220px">
      <button id="b-find">Chercher</button>
    </div>
    <div id="b-out" style="margin-top:8px"></div>
  </div>`;
}

function render() {
  if (!S.groups.some(g => g.id === tab)) tab = (S.groups[0] || {}).id || "";
  document.getElementById("tabs").innerHTML = S.groups.map(g =>
    `<button data-tab="${g.id}" class="${g.id === tab ? "on" : ""}">${esc(g.title)}</button>`).join("");
  document.getElementById("groups").innerHTML = S.groups.map(g => `
    <section class="tab ${g.id === tab ? "on" : ""}" id="g-${g.id}">
      <div class="card">
        ${g.fields.filter(shown).map(field).join("")}
        ${g.id === "brain" ? brainExtras() : ""}
        ${g.id === "sources" ? boardFinder() : ""}
      </div>
    </section>`).join("");

  const n = Object.keys(edits).length;
  document.getElementById("b-save").disabled = !n;
  document.getElementById("b-save").textContent =
    n ? `Enregistrer ${n} changement${n > 1 ? "s" : ""}` : "Enregistrer";
  document.getElementById("dirty").textContent = n ? "non enregistré" : "";
  document.getElementById("profile-state").innerHTML = S.profile_ok
    ? `<b>profile.toml</b> est rempli : ${S.answers} réponse(s) pré-écrite(s) pour les formulaires.`
    : `<b>profile.toml</b> est vide. Sans lui, aucun champ de formulaire ne peut être rempli
       et tes liens ne peuvent pas être mis sur chaque CV.`;
}

// ------------------------------------------------------------------ events --
document.getElementById("tabs").addEventListener("click", ev => {
  const b = ev.target.closest("button[data-tab]");
  if (b) { tab = b.dataset.tab; render(); }
});

document.getElementById("groups").addEventListener("change", ev => {
  const el = ev.target, id = el.dataset.id;
  if (!id) return;
  if (el.dataset.kind === "toggle") setVal(id, el.checked);
  else if (el.dataset.kind === "number") setVal(id, Number(el.value));
  else setVal(id, el.value);
});

document.getElementById("groups").addEventListener("keydown", ev => {
  const id = ev.target.dataset.add;
  if (!id || ev.key !== "Enter") return;
  ev.preventDefault();
  const v = ev.target.value.trim();
  if (!v) return;
  setVal(id, [...(val(id) || []), v]);
});

document.getElementById("groups").addEventListener("click", async ev => {
  const del = ev.target.dataset.del;
  if (del) {
    const arr = [...(val(del) || [])];
    arr.splice(+ev.target.dataset.i, 1);
    setVal(del, arr);
    return;
  }
  if (ev.target.dataset.suggest) {
    setVal("ai.model", ev.target.dataset.suggest);
    return;
  }
  if (ev.target.dataset.add2) {                 // add a found company to a source
    const [src, tag] = ev.target.dataset.add2.split("|");
    const id = `sources.${src}.boards`;
    const cur = val(id) || [];
    if (cur.some(x => x.split("=")[0] === tag.split("=")[0])) {
      toast("Cette entreprise est déjà dans la liste."); return;
    }
    setVal(id, [...cur, tag]);
    toast(`Ajoutée à ${src}. N'oublie pas d'enregistrer.`);
    return;
  }
  if (ev.target.id === "b-find") {
    const slug = (document.getElementById("b-slug").value || "").trim();
    const name = (document.getElementById("b-name").value || "").trim();
    const out = document.getElementById("b-out");
    if (!slug) { toast("Tape un identifiant d'entreprise."); return; }
    ev.target.disabled = true;
    out.innerHTML = `<span class="live-state"><span class="dot live"></span>recherche…</span>`;
    try {
      const r = await api("/api/settings/board", { board: slug });
      const hits = Object.entries(r.hits);
      out.innerHTML = hits.length
        ? hits.map(([src, n]) => `<div class="okline"><b>✓</b>
            <span><b>${esc(r.board)}</b> est sur <b>${esc(src)}</b>, ${n} offre(s) en ce moment
            <button class="small" style="margin-left:8px"
              data-add2="${esc(src)}|${esc(r.board + "=" + (name || r.board))}">Ajouter</button></span>
          </div>`).join("")
        : `<div class="noline"><b>✕</b><span>Aucune des trois plateformes ne connaît
             « ${esc(r.board)} ». Vérifie l'orthographe dans l'adresse de sa page emploi,
             ou cette entreprise utilise un autre système.</span></div>`;
    } catch (e) { out.innerHTML = `<div class="noline"><b>✕</b><span>${esc(e.message)}</span></div>`; }
    ev.target.disabled = false;
    return;
  }
  if (ev.target.id === "b-key" || ev.target.id === "b-key-del") {
    const del = ev.target.id === "b-key-del";
    const key = del ? "" : (document.getElementById("key-in").value || "").trim();
    const provider = String(val("ai.provider") || "anthropic");
    if (del && !confirm("Supprimer la clé API enregistrée ?")) return;
    if (!del && !key) { toast("Colle la clé d'abord."); return; }
    try {
      S.key = await api("/api/settings/key", { key, provider });
      toast(del ? "Clé supprimée." : "Clé enregistrée.");
      render();
    } catch (e) { toast("Refusé : " + e.message); }
    return;
  }
  if (ev.target.id === "b-test") {
    if (Object.keys(edits).length)
      toast("Le test porte sur les réglages enregistrés, pas sur tes changements en cours.");
    try { await api("/api/settings/test", {}); pollTest(); }
    catch (e) { toast("Erreur : " + e.message); }
  }
});

async function pollTest() {
  clearTimeout(testTimer);
  let r;
  try { r = await api("/api/settings/test"); } catch (e) { return; }
  const out = document.getElementById("test-out");
  if (!out) return;
  if (r.state === "running") {
    out.innerHTML = `<span class="dot live"></span>appel en cours…`;
    testTimer = setTimeout(pollTest, 1500);
  } else if (r.state === "done") {
    out.innerHTML = r.ok
      ? `<span style="color:var(--accent)">✓ ça marche</span> — ${r.model}, ${r.seconds}s`
      : `<span style="color:var(--bad)">✕ ${esc(r.error || "échec")}</span>`;
  }
}

document.getElementById("b-save").onclick = async () => {
  const b = document.getElementById("b-save");
  b.disabled = true;
  try {
    const r = await api("/api/settings", { changes: edits });
    S.values = r.values; edits = {};
    toast(`Enregistré : ${r.changed.length} réglage(s). Le pipeline les utilise déjà.`);
    render();
  } catch (e) { toast("Refusé : " + e.message); b.disabled = false; }
};

document.getElementById("b-restart").onclick = async ev => {
  ev.target.disabled = true;
  try { await api("/api/settings/restart", {}); toast("Surveillance redémarrée."); }
  catch (e) { toast("Échec : " + e.message); }
  ev.target.disabled = false;
};

(async () => {
  try {
    S = await api("/api/settings");
    render();
    pollTest();
  } catch (e) {
    document.getElementById("groups").innerHTML =
      `<div class="card empty">Impossible de lire les réglages : ${esc(e.message)}</div>`;
  }
})();
