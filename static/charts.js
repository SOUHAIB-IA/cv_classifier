// Charts, drawn as plain SVG. No library: the whole set is five shapes, and a
// charting dependency would be bigger than this file and harder to theme.
//
// Everything reads its colours from the CSS variables in app.css, so the dark
// theme needs no second palette. Each chart redraws on resize because the
// viewBox is the measured pixel width: scaling it instead would stretch the
// labels.

const PAL = ["--c1", "--c2", "--c3", "--c4", "--c5"];
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

function svg(w, h) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", `0 0 ${w} ${h}`);
  s.setAttribute("width", "100%");
  s.setAttribute("height", h);
  s.setAttribute("class", "chart");
  return s;
}

function el(tag, attrs, text) {
  const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (text != null) n.textContent = text;
  return n;
}

// Round a maximum up to something a person would choose for an axis.
function nice(max) {
  if (max <= 5) return 5;
  const p = Math.pow(10, Math.floor(Math.log10(max)));
  return Math.ceil(max / p * 2) / 2 * p;
}

function tip(host) {
  let t = host.querySelector(".ctip");
  if (!t) { t = document.createElement("div"); t.className = "ctip"; host.appendChild(t); }
  return t;
}

function hover(host, s, zones) {
  const t = tip(host);
  s.addEventListener("mousemove", ev => {
    const r = s.getBoundingClientRect();
    const x = (ev.clientX - r.left) / r.width * s.viewBox.baseVal.width;
    const z = zones.find(z => x >= z.x0 && x < z.x1);
    if (!z) { t.classList.remove("on"); return; }
    t.innerHTML = z.html;
    t.classList.add("on");
    t.style.left = Math.min(Math.max(ev.clientX - r.left, 40), r.width - 40) + "px";
    t.style.top = Math.max(ev.clientY - r.top - 42, 0) + "px";
  });
  s.addEventListener("mouseleave", () => t.classList.remove("on"));
}

function frame(host, h) {
  host.classList.add("chart-host");
  host.querySelectorAll("svg").forEach(n => n.remove());
  const w = Math.max(host.clientWidth || 360, 260);
  const s = svg(w, h);
  host.appendChild(s);
  return { s, w, h };
}

// Redraw when the column width changes, so a chart is never drawn for a width
// it no longer has.
function responsive(host, draw) {
  draw();
  if (host._ro) host._ro.disconnect();
  let w = host.clientWidth;
  host._ro = new ResizeObserver(() => {
    if (Math.abs(host.clientWidth - w) < 8) return;
    w = host.clientWidth; draw();
  });
  host._ro.observe(host);
}

// --------------------------------------------------------------- line chart --
function chartLines(host, { labels, series, h = 190 }) {
  responsive(host, () => {
    const { s, w } = frame(host, h);
    const L = 34, R = 8, T = 10, B = 28;
    const iw = w - L - R, ih = h - T - B;
    const max = nice(Math.max(1, ...series.flatMap(x => x.data)));
    const X = i => L + (labels.length < 2 ? iw / 2 : i * iw / (labels.length - 1));
    const Y = v => T + ih - (v / max) * ih;

    for (let g = 0; g <= 4; g++) {
      const y = T + ih - g * ih / 4;
      s.appendChild(el("line", { x1: L, x2: L + iw, y1: y, y2: y,
                                 stroke: css("--line"), "stroke-width": 1 }));
      s.appendChild(el("text", { x: L - 6, y: y + 4, "text-anchor": "end",
                                 class: "ax" }, Math.round(max * g / 4)));
    }
    series.forEach((se, k) => {
      const c = css(PAL[k % PAL.length]);
      const pts = se.data.map((v, i) => `${X(i)},${Y(v)}`).join(" ");
      s.appendChild(el("polygon", {
        points: `${L},${T + ih} ${pts} ${X(labels.length - 1)},${T + ih}`,
        fill: c, opacity: .13 }));
      s.appendChild(el("polyline", { points: pts, fill: "none", stroke: c,
                                     "stroke-width": 2, "stroke-linejoin": "round" }));
    });
    // every 7th day, plus the last one unless it would collide with it
    labels.forEach((d, i) => {
      const last = i === labels.length - 1;
      if (i % 7 && !last) return;
      if (last && (labels.length - 1) % 7 < 4) return;
      s.appendChild(el("text", { x: X(i), y: h - 4, "text-anchor": "middle",
                                 class: "ax" }, d.slice(5).replace("-", "/")));
    });
    hover(host, s, labels.map((d, i) => ({
      x0: X(i) - iw / labels.length / 2, x1: X(i) + iw / labels.length / 2,
      html: `<b>${d}</b>` + series.map((se, k) =>
        `<span style="color:${css(PAL[k % PAL.length])}">■</span> ${se.name} : ${se.data[i]}`).join("<br>"),
    })));
  });
}

// ---------------------------------------------------------------- bar chart --
function chartBars(host, { labels, data, h = 150, fmt }) {
  responsive(host, () => {
    const { s, w } = frame(host, h);
    const L = 28, R = 6, T = 10, B = 22;
    const iw = w - L - R, ih = h - T - B;
    const max = nice(Math.max(1, ...data));
    const bw = Math.max(2, iw / data.length - 2);
    for (let g = 0; g <= 2; g++) {
      const y = T + ih - g * ih / 2;
      s.appendChild(el("line", { x1: L, x2: L + iw, y1: y, y2: y, stroke: css("--line") }));
      s.appendChild(el("text", { x: L - 6, y: y + 4, "text-anchor": "end", class: "ax" },
                       Math.round(max * g / 2)));
    }
    const zones = [];
    data.forEach((v, i) => {
      const x = L + i * iw / data.length;
      const bh = (v / max) * ih;
      if (v) s.appendChild(el("rect", { x, y: T + ih - bh, width: bw, height: bh,
                                        rx: 2, fill: css("--accent") }));
      zones.push({ x0: x, x1: x + iw / data.length,
                   html: `<b>${labels[i]}</b><br>${fmt ? fmt(v) : v}` });
    });
    labels.forEach((d, i) => {
      const last = i === labels.length - 1;
      if (i % 7 && !last) return;
      if (last && (labels.length - 1) % 7 < 4) return;
      s.appendChild(el("text", { x: L + i * iw / data.length + bw / 2, y: h - 4,
                                 "text-anchor": "middle", class: "ax" },
                       d.slice(5).replace("-", "/")));
    });
    hover(host, s, zones);
  });
}

// ---------------------------------------------------------------- histogram --
// Fit scores in bands of ten, coloured by what the pipeline does with them:
// green is sent on for tailoring, amber waits for you, red is dropped.
function chartHist(host, { data, thresholds, h = 170 }) {
  responsive(host, () => {
    const { s, w } = frame(host, h);
    const L = 26, R = 6, T = 12, B = 30;
    const iw = w - L - R, ih = h - T - B;
    const max = nice(Math.max(1, ...data));
    const bw = iw / data.length;
    const zones = [];
    data.forEach((v, i) => {
      const lo = i * 10, hi = lo + 9;
      const c = lo >= thresholds.auto ? "--accent" : lo >= thresholds.review ? "--warn" : "--bad";
      const bh = (v / max) * ih;
      const x = L + i * bw;
      if (v) s.appendChild(el("rect", { x: x + 2, y: T + ih - bh, width: bw - 4,
                                        height: bh, rx: 2, fill: css(c) }));
      s.appendChild(el("text", { x: x + bw / 2, y: h - 16, "text-anchor": "middle",
                                 class: "ax" }, lo));
      zones.push({ x0: x, x1: x + bw, html: `<b>fit ${lo} à ${hi}</b><br>${v} offre(s)` });
    });
    s.appendChild(el("line", { x1: L, x2: L + iw, y1: T + ih, y2: T + ih,
                               stroke: css("--line") }));
    s.appendChild(el("text", { x: L + iw / 2, y: h - 3, "text-anchor": "middle",
                               class: "ax" }, "score de fit"));
    hover(host, s, zones);
  });
}

// -------------------------------------------------------------------- donut --
function chartDonut(host, { items, h = 180, center }) {
  responsive(host, () => {
    const { s, w } = frame(host, h);
    const total = items.reduce((a, x) => a + x.n, 0) || 1;
    const cx = h / 2 + 6, cy = h / 2, r = h / 2 - 14, ir = r * .62;
    let a0 = -Math.PI / 2;
    items.forEach((x, k) => {
      const a1 = a0 + (x.n / total) * Math.PI * 2;
      const big = a1 - a0 > Math.PI ? 1 : 0;
      const p = (rr, a) => `${cx + rr * Math.cos(a)},${cy + rr * Math.sin(a)}`;
      s.appendChild(el("path", {
        d: `M ${p(r, a0)} A ${r} ${r} 0 ${big} 1 ${p(r, a1)} L ${p(ir, a1)} `
         + `A ${ir} ${ir} 0 ${big} 0 ${p(ir, a0)} Z`,
        fill: x.color || css(PAL[k % PAL.length]) }));
      s.appendChild(el("title", {}, `${x.label} : ${x.n}`));
      a0 = a1;
    });
    s.appendChild(el("text", { x: cx, y: cy + 2, "text-anchor": "middle", class: "big" },
                     center != null ? center : total));
    s.appendChild(el("text", { x: cx, y: cy + 18, "text-anchor": "middle", class: "ax" },
                     center != null ? "" : "offres"));
    let y = 18;
    items.slice(0, 7).forEach((x, k) => {
      const lx = h + 18;
      if (lx + 120 > w) return;
      s.appendChild(el("rect", { x: lx, y: y - 9, width: 9, height: 9, rx: 2,
                                 fill: x.color || css(PAL[k % PAL.length]) }));
      s.appendChild(el("text", { x: lx + 15, y, class: "lg" },
                       `${x.label} · ${x.n}`));
      y += 19;
    });
  });
}

// ------------------------------------------------------------ horizontal bars --
function chartBarsH(host, { items, h }) {
  responsive(host, () => {
    const rows = items.slice(0, 8);
    const H = h || Math.max(60, rows.length * 26 + 8);
    const { s, w } = frame(host, H);
    const L = Math.min(130, w * .38), max = Math.max(1, ...rows.map(x => x.n));
    rows.forEach((x, i) => {
      const y = i * 26 + 6;
      s.appendChild(el("text", { x: L - 8, y: y + 13, "text-anchor": "end", class: "lg" },
                       x.label.length > 22 ? x.label.slice(0, 21) + "…" : x.label));
      s.appendChild(el("rect", { x: L, y: y + 3, rx: 3, height: 14,
                                 width: Math.max(2, (x.n / max) * (w - L - 42)),
                                 fill: x.color || css("--accent") }));
      s.appendChild(el("text", { x: L + (x.n / max) * (w - L - 42) + 6, y: y + 14,
                                 class: "lg" }, x.n));
    });
  });
}
