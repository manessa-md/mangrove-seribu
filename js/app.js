/* WebGIS MGV-KS — Kajian Pemulihan Ekosistem Mangrove di Kepulauan Seribu */
(async function () {
  "use strict";

  const $ = (s, el = document) => el.querySelector(s);
  const fmt = (v, d = 2) => v == null || v === "" ? "–" :
    typeof v === "number" ? v.toLocaleString("id-ID", { maximumFractionDigits: d }) : v;
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const [S, P] = await Promise.all([
    fetch("data/statistik.json").then(r => r.json()),
    fetch("data/progres.json").then(r => r.json()),
  ]);
  const PULAU = S.pulau;
  const KODE = Object.keys(PULAU);
  $("#tgl-update").textContent = "diperbarui " + P.diperbarui;

  Chart.defaults.font.family = '"Source Sans 3", sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = "#5d6b65";
  const charts = {};
  function chart(id, cfg) { if (charts[id]) charts[id].destroy(); charts[id] = new Chart(document.getElementById(id), cfg); }

  /* ---------------- Peta ---------------- */
  const map = L.map("map", { zoomControl: true, preferCanvas: true }).setView([-5.75, 106.58], 10);
  const canvas = L.canvas({ padding: 0.3 });
  const bases = {
    "Citra satelit (Esri)": L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 20, maxNativeZoom: 19, attribution: "Citra © Esri, Maxar, Earthstar Geographics" }),
    "OpenStreetMap": L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      { maxZoom: 20, maxNativeZoom: 19, attribution: "© OpenStreetMap" }),
    "Peta terang (Carto)": L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
      { maxZoom: 20, attribution: "© OpenStreetMap © CARTO" }),
  };
  bases["Citra satelit (Esri)"].addTo(map);
  L.control.scale({ imperial: false, position: "bottomright" }).addTo(map);

  // label pulau
  const labels = L.layerGroup().addTo(map);
  for (const [k, ll] of Object.entries(S.pusat)) {
    L.marker(ll, { opacity: 0, interactive: false, keyboard: false })
      .bindTooltip(PULAU[k], { permanent: true, direction: "center", className: "island-label" }).addTo(labels);
  }

  /* ---- palet ---- */
  const PRIOR = { Tinggi: "#c0392b", Sedang: "#e68a2e", Rendah: "#f2d16b" };
  const KELAS_S2 = { lebat: "#0b5d3b", sedang: "#3f9c5a", jarang: "#a5d36e" };
  const LRR = [["Abrasi tinggi (<-2)", "#b2182b"], ["Abrasi (-2…-0,5)", "#ef8a62"], ["Stabil (±0,5)", "#e0e0e0"],
               ["Akresi (0,5…2)", "#67a9cf"], ["Akresi tinggi (>2)", "#2166ac"]];
  const LRRc = Object.fromEntries(LRR);
  const KONDISI = { "Baik - sangat padat": "#1a9850", "Baik - sedang": "#91cf60", "Rusak - jarang": "#d73027" };
  const SAL_SUMUR = { "Tawar": "#4575b4", "Payau ringan": "#91bfdb", "Payau": "#fc8d59", "Payau tinggi": "#d73027" };
  const KET_AIR = { "Mangrove": "#1a9850", "Non-mangrove": "#f1c40f", "Laut": "#2c7fb8" };
  const yearColor = (y) => { const t = Math.max(0, Math.min(1, (y - 1990) / 35)); return `hsl(${50 - t * 50 + (1 - t) * 160}, 80%, ${55 - t * 10}%)`; };
  const salColor = v => v == null ? "#999" : v < 0.5 ? "#4575b4" : v < 10 ? "#91bfdb" : v < 25 ? "#fee090" : v < 30 ? "#fc8d59" : "#d73027";

  function popupTable(title, rows) {
    return `<div class="pop"><h4>${esc(title)}</h4><table>${rows.filter(r => r[1] != null && r[1] !== "")
      .map(([k, v, d]) => `<tr><td>${esc(k)}</td><td><b>${esc(fmt(v, d))}</b></td></tr>`).join("")}</table></div>`;
  }

  const LAYERS = [
    { id: "daratan", grp: "Dasar", label: "Daratan 2025", file: "daratan_2025", on: false, sw: "#ffffff; outline:1px solid #999",
      style: () => ({ color: "#ffffff", weight: 1.2, fill: false, dashArray: "3 3" }) },
    { id: "kontur", grp: "Dasar", label: "Kontur topo-batimetri (1 m)", file: "kontur_batimetri", on: false, sw: "#5aa9d6",
      style: f => ({ color: f.properties.elevasi_m >= 0 ? "#c9a46a" : "#5aa9d6", weight: f.properties.elevasi_m === 0 ? 1.6 : 0.7, opacity: .85 }),
      popup: p => popupTable("Kontur", [["Elevasi (m)", p.elevasi_m], ["Pulau", PULAU[p.pulau] || p.pulau], ["Sumber", p.interval_sumber]]),
      legend: () => `<div class="lt">Kontur topo-batimetri</div>
        <div class="row"><span class="sw l" style="background:#c9a46a"></span>darat (≥ 0 m)</div>
        <div class="row"><span class="sw l" style="background:#5aa9d6"></span>perairan (&lt; 0 m)</div>` },

    { id: "eksisting", grp: "Sebaran mangrove", label: "Mangrove eksisting (digitasi 2025)", file: "mangrove_eksisting", on: true, sw: "#00e676",
      style: () => ({ color: "#00e676", weight: 1.5, fillColor: "#00c853", fillOpacity: .45 }),
      popup: p => popupTable("Mangrove eksisting – digitasi 2025", [["Pulau", PULAU[p.pulau]], ["Luas (ha)", p.luas_ha], ["Jumlah poligon", p.n_poligon, 0]]) },
    { id: "s2sr", grp: "Sebaran mangrove", label: "Sentinel-2 SR 2,5 m (kelas kerapatan)", fileFn: () => `mangrove_s2sr_${s2Year}`, on: false, sw: "#3f9c5a",
      style: f => ({ color: KELAS_S2[f.properties.kelas], weight: .5, fillColor: KELAS_S2[f.properties.kelas], fillOpacity: .65 }),
      popup: p => popupTable(`Mangrove Sentinel-2 SR ${p.tahun}`, [["Pulau", PULAU[p.kode]], ["Kelas", p.kelas], ["Luas kelas (ha)", p.luas_ha]]),
      legend: () => `<div class="lt">Mangrove Sentinel-2 SR ${s2Year}</div>` +
        Object.entries(KELAS_S2).map(([k, c]) => `<div class="row"><span class="sw" style="background:${c}"></span>${k}</div>`).join(""),
      extra: () => `<select id="s2-year">${S.s2sr_tahun.map(y => `<option ${y === s2Year ? "selected" : ""}>${y}</option>`).join("")}</select>` },
    { id: "rbi", grp: "Sebaran mangrove", label: "Mangrove RBI 25K 2022", file: "mangrove_rbi2022", on: false, sw: "#ff80ab",
      style: () => ({ color: "#ff80ab", weight: 1.2, fill: false, dashArray: "4 3" }),
      popup: p => popupTable("Mangrove RBI 2022", [["Pulau", PULAU[p.pulau]], ["Luas (ha)", p.luas_ha]]) },

    { id: "plot", grp: "Survei lapangan", label: "Plot vegetasi", file: "plot_vegetasi", on: true, sw: "#1a9850", point: true,
      style: f => ({ radius: 6, color: "#fff", weight: 1.5, fillColor: KONDISI[f.properties.kelas_kondisi] || "#888", fillOpacity: 1 }),
      popup: p => popupTable(`Plot ${p.kode_plot}`, [["Tanggal", p.tanggal], ["Jenis dominan", p.jenis_dominan],
        ["Kerapatan batang (ind/ha)", p.kerapatan_batang_ha, 0], ["Pancang (ind/ha)", p.kerapatan_pancang_ha, 0], ["Semai (ind/ha)", p.kerapatan_semai_ha, 0],
        ["DBH rerata (cm)", p.dbh_rerata_cm], ["Tutupan kanopi (%)", p.tutupan_kanopi_pct], ["LAI (ring 4)", p.LAI_ring4],
        ["Karbon batas bawah (t C/ha)", p.karbon_min_t_ha], ["CO₂e batas bawah (t/ha)", p.co2e_min_t_ha],
        ["Kelas kondisi", p.kelas_kondisi], ["BA perlu dicek", p.ba_tidak_wajar ? "Ya" : null]]),
      legend: () => `<div class="lt">Plot vegetasi – kondisi</div>` +
        Object.entries(KONDISI).map(([k, c]) => `<div class="row"><span class="sw c" style="background:${c}"></span>${k}</div>`).join("") },
    { id: "air", grp: "Survei lapangan", label: "Titik kualitas air / groundcheck", file: "titik_kualitas_air", on: false, sw: "#2c7fb8", point: true,
      style: f => ({ radius: 3.5, color: "#000", weight: .4, fillColor: airMode === "ket" ? (KET_AIR[f.properties.keterangan] || "#999") : salColor(f.properties.salinitas_ppt), fillOpacity: .95 }),
      popup: p => popupTable(`Titik ${p.kode_titik}`, [["Tanggal", p.tanggal], ["Tutupan", p.keterangan], ["Substrat", p.substrat],
        ["Kedalaman (cm)", p.kedalaman_cm], ["Suhu (°C)", p.suhu_c], ["pH", p.ph], ["Salinitas (ppt)", p.salinitas_ppt], ["DO (mg/L)", p.do_mg_l],
        ["TDS (ppt)", p.tds_ppt], ["Elevasi (m)", p.elevasi_m]]),
      extra: () => `<select id="air-mode"><option value="ket" ${airMode === "ket" ? "selected" : ""}>Warna: tutupan groundcheck</option><option value="sal" ${airMode === "sal" ? "selected" : ""}>Warna: salinitas</option></select>`,
      legend: () => airMode === "ket"
        ? `<div class="lt">Groundcheck</div>` + Object.entries(KET_AIR).map(([k, c]) => `<div class="row"><span class="sw c" style="background:${c}"></span>${k}</div>`).join("")
        : `<div class="lt">Salinitas air (ppt)</div>` + [["< 0,5", 0], ["0,5–10", 5], ["10–25", 15], ["25–30", 27], ["≥ 30", 31]]
          .map(([k, v]) => `<div class="row"><span class="sw c" style="background:${salColor(v)}"></span>${k}</div>`).join("") },
    { id: "sumur", grp: "Survei lapangan", label: "Sumur air tanah", file: "sumur_air_tanah", on: false, sw: "#fc8d59", point: true,
      style: f => ({ radius: 5, color: "#222", weight: 1, fillColor: SAL_SUMUR[f.properties.kelas_salinitas] || "#999", fillOpacity: 1 }),
      popup: p => popupTable(`Sumur ${p.kode_sumur}`, [["Tanggal", p.tanggal], ["Salinitas (ppt)", p.salinitas_ppt], ["Kelas", p.kelas_salinitas],
        ["pH", p.ph], ["TDS (ppt)", p.tds_ppt], ["Suhu (°C)", p.suhu_c], ["Kedalaman (cm)", p.kedalaman_cm]]),
      legend: () => `<div class="lt">Sumur – salinitas</div>` + Object.entries(SAL_SUMUR).map(([k, c]) => `<div class="row"><span class="sw c" style="background:${c}"></span>${k}</div>`).join("") },
    { id: "lai", grp: "Survei lapangan", label: "Foto hemispherical (tutupan kanopi)", file: "foto_lai", on: false, sw: "#7fbc41", point: true,
      style: f => { const t = f.properties.tutupan_kanopi_pct; return { radius: 3.5, color: "#000", weight: .4, fillOpacity: 1,
        fillColor: t == null ? "#999" : t >= 75 ? "#1a9850" : t >= 50 ? "#fee08b" : "#d73027" }; },
      popup: p => popupTable(`Foto ${p.id_titik}`, [["Tanggal", p.Tanggal], ["Transek", p.ID_Transek], ["Plot", p.kode_plot], ["Spesies", p.Spesies],
        ["Tutupan kanopi (%)", p.tutupan_kanopi_pct], ["LAI ring 4", p.LAI_Ring4]]),
      legend: () => `<div class="lt">Tutupan kanopi (Kepmen LH 201/2004)</div>
        <div class="row"><span class="sw c" style="background:#1a9850"></span>≥ 75 % sangat padat</div>
        <div class="row"><span class="sw c" style="background:#fee08b"></span>50–75 % sedang</div>
        <div class="row"><span class="sw c" style="background:#d73027"></span>&lt; 50 % jarang</div>` },

    { id: "transek", grp: "Garis pantai", label: "Transek DSAS (laju LRR)", file: "transek_garis_pantai", on: false, sw: "#ef8a62",
      style: f => ({ color: LRRc[f.properties.kelas_LRR] || "#999", weight: 3, opacity: .95 }),
      popup: p => popupTable(`Transek ${p.id_transek}`, [["Pulau", PULAU[p.pulau]], ["LRR (m/th)", p.LRR_m_th], ["R²", p.LRR_R2], ["EPR (m/th)", p.EPR_m_th],
        ["NSM (m)", p.NSM_m], ["Jumlah tahun", p.n_tahun], ["Kelas", p.kelas_LRR]]),
      legend: () => `<div class="lt">Laju garis pantai (LRR)</div>` + LRR.map(([k, c]) => `<div class="row"><span class="sw l" style="background:${c}"></span>${k}</div>`).join("") },
    { id: "garis", grp: "Garis pantai", label: "Garis pantai tahunan 1990–2025", file: "garis_pantai_tahunan", on: false, sw: "#f39c12",
      style: f => ({ color: yearColor(f.properties.year), weight: 1.3, opacity: .9 }),
      popup: p => popupTable("Garis pantai", [["Tahun", p.year, 0], ["Pulau", PULAU[p.pulau]]]),
      legend: () => `<div class="lt">Garis pantai</div>` + [1990, 2000, 2010, 2020, 2025].map(y => `<div class="row"><span class="sw l" style="background:${yearColor(y)}"></span>${y}</div>`).join("") },

    { id: "prioritas", grp: "Pemulihan", label: "Lokasi prioritas pemulihan", file: "lokasi_prioritas", on: true, sw: "#c0392b",
      style: f => ({ color: PRIOR[f.properties.prioritas], weight: 1, fillColor: PRIOR[f.properties.prioritas], fillOpacity: .55 }),
      popup: p => popupTable(`Lokasi ${p.id_lokasi || ""}`, [["Pulau", PULAU[p.pulau]], ["Prioritas", p.prioritas], ["Luas (ha)", p.luas_ha], ["Skor rerata", p.skor_rerata],
        ["Lintang", p.lintang, 6], ["Bujur", p.bujur, 6]]),
      legend: () => `<div class="lt">Prioritas pemulihan</div>` + Object.entries(PRIOR).map(([k, c]) => `<div class="row"><span class="sw" style="background:${c}"></span>${k}</div>`).join("") },
  ];
  let s2Year = S.s2sr_tahun[S.s2sr_tahun.length - 1], airMode = "ket";
  const loaded = {};
  const cache = {};

  async function getGeo(file) {
    if (!cache[file]) cache[file] = fetch(`data/${file}.geojson`).then(r => r.json());
    return cache[file];
  }
  async function buildLayer(def) {
    const file = def.fileFn ? def.fileFn() : def.file;
    const gj = await getGeo(file);
    const opt = {
      style: def.style,
      onEachFeature: def.popup ? (f, l) => l.bindPopup(() => def.popup(f.properties), { maxWidth: 320 }) : undefined,
    };
    if (def.point) opt.pointToLayer = (f, ll) => L.circleMarker(ll, { ...def.style(f), renderer: canvas });
    return L.geoJSON(gj, opt);
  }
  async function toggle(def, on) {
    if (loaded[def.id]) { map.removeLayer(loaded[def.id]); delete loaded[def.id]; }
    if (on) { loaded[def.id] = await buildLayer(def); loaded[def.id].addTo(map); }
    // jaga urutan: poligon di bawah, titik di atas
    LAYERS.forEach(d => { if (loaded[d.id] && d.point) loaded[d.id].bringToFront?.(); });
    renderLegend();
  }
  function renderLegend() {
    $("#legend").innerHTML = LAYERS.filter(d => loaded[d.id] && d.legend).map(d => d.legend()).join("");
  }

  function renderLayerBox() {
    const grps = [...new Set(LAYERS.map(d => d.grp))];
    $("#layerbox").innerHTML = `<details open><summary>Lapisan peta</summary>
      <div class="grp"><div class="gt">Peta dasar</div>
        <select id="basemap">${Object.keys(bases).map(b => `<option>${b}</option>`).join("")}</select>
        <label><input type="checkbox" id="lbl" checked> Nama pulau</label></div>
      ${grps.map(g => `<div class="grp"><div class="gt">${g}</div>${LAYERS.filter(d => d.grp === g).map(d =>
        `<label><input type="checkbox" data-id="${d.id}" ${d.on ? "checked" : ""}><span class="sw" style="background:${d.sw}"></span>${d.label}</label>${d.extra ? d.extra() : ""}`).join("")}</div>`).join("")}
    </details>`;
    $("#layerbox").addEventListener("change", e => {
      const t = e.target;
      if (t.id === "basemap") { Object.values(bases).forEach(b => map.removeLayer(b)); bases[t.value].addTo(map); return; }
      if (t.id === "lbl") { t.checked ? labels.addTo(map) : map.removeLayer(labels); return; }
      if (t.id === "s2-year") { s2Year = +t.value; const d = LAYERS.find(x => x.id === "s2sr"); setChecked("s2sr"); toggle(d, true); return; }
      if (t.id === "air-mode") { airMode = t.value; const d = LAYERS.find(x => x.id === "air"); setChecked("air"); toggle(d, true); return; }
      if (t.dataset.id) toggle(LAYERS.find(d => d.id === t.dataset.id), t.checked);
    });
    if (window.innerWidth < 860) $("#layerbox details").open = false;
  }
  function setChecked(id, v = true) { const c = $(`#layerbox input[data-id="${id}"]`); if (c) c.checked = v; }
  function ensureOn(id) { if (!loaded[id]) { setChecked(id); return toggle(LAYERS.find(d => d.id === id), true); } }

  renderLayerBox();
  for (const d of LAYERS) if (d.on) await toggle(d, true);

  /* ---------------- Tab ---------------- */
  function showTab(name, open = true) {
    document.querySelectorAll(".tabs button").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
    document.querySelectorAll(".tab-pane").forEach(p => p.classList.toggle("active", p.id === "tab-" + name));
    if (open) $("#panel").classList.add("open");
  }
  document.querySelectorAll(".tabs button").forEach(b => b.addEventListener("click", () => showTab(b.dataset.tab)));
  $("#panel-toggle").addEventListener("click", () => $("#panel").classList.toggle("open"));

  /* ---------------- Progres ---------------- */
  const R = S.ringkasan;
  const sum = key => KODE.reduce((a, k) => a + (+R[k]?.[key] || 0), 0);
  const surveyed = KODE.filter(k => (+R[k]?.["Plot vegetasi"] || 0) > 0).length;
  const kel = S.kelengkapan;
  const fields = [["plot_vegetasi", "Veg"], ["kualitas_air", "Air"], ["air_tanah", "Sumur"], ["garis_pantai", "Pantai"],
                  ["gelombang", "Gel."], ["batimetri", "Bati."], ["dtm", "DTM"]];
  $("#tab-progres").innerHTML = `
    <h2>Perkembangan kegiatan</h2>
    <p class="muted">Ringkasan data yang sudah terkumpul dan dianalisis (basis data v03).</p>
    <div class="kpis">
      <div class="kpi"><div class="v">${surveyed}/10</div><div class="l">pulau sudah disurvei</div></div>
      <div class="kpi"><div class="v">${fmt(sum("Plot vegetasi"), 0)}</div><div class="l">plot vegetasi</div></div>
      <div class="kpi"><div class="v">${fmt(sum("Titik kualitas air"), 0)}</div><div class="l">titik kualitas air &amp; groundcheck</div></div>
      <div class="kpi"><div class="v">${fmt(sum("Sumur air tanah"), 0)}</div><div class="l">sumur air tanah</div></div>
      <div class="kpi"><div class="v">${fmt(S.tabel["5"].baris.reduce((a, r) => a + (+r[1] || 0), 0), 0)}</div><div class="l">foto hemispherical</div></div>
      <div class="kpi"><div class="v">${fmt(sum("Responden sosek"), 0)}</div><div class="l">responden sosial-ekonomi</div></div>
    </div>
    <h3>Tahapan</h3>
    <ul class="timeline">${P.tahapan.map(t => `<li class="${t.status}"><span class="dot"></span>
      <div class="nm">${esc(t.nama)}</div><div class="meta">${esc(t.tanggal)} · ${t.status}${t.catatan ? " — " + esc(t.catatan) : ""}</div></li>`).join("")}</ul>
    <h3>Kelengkapan data per pulau</h3>
    <table class="matrix"><thead><tr><th>Pulau</th>${fields.map(f => `<th>${f[1]}</th>`).join("")}<th>Sesuai.</th></tr></thead>
    <tbody>${kel.map(r => { const k = r[Object.keys(r)[0]] || r[""] || r[null]; return `<tr class="clickable" data-k="${k}"><td>${PULAU[k] || k}</td>${fields.map(([f]) =>
      `<td>${(f === "plot_vegetasi" || f === "kualitas_air" || f === "air_tanah") && r[f] ? `<span class="num">${r[f]}</span>` : `<span class="cell ${r[f] ? "y" : "n"}"></span>`}</td>`).join("")}
      <td><span class="cell ${r.lengkap ? "y" : "n"}"></span></td></tr>`; }).join("")}</tbody></table>
    <p class="muted" style="font-size:.8rem">Angka = jumlah plot/titik/sumur. “Sesuai.” = data cukup untuk analisis kesesuaian pemulihan (perlu batimetri/DTM dan gelombang). Klik baris untuk melihat pulau.</p>
    <h3>Catatan mutu data</h3>
    ${S.catatan_mutu.map(c => `<div class="note">${esc(c)}</div>`).join("")}
  `;
  $("#tab-progres").addEventListener("click", e => { const tr = e.target.closest("tr[data-k]"); if (tr) selectIsland(tr.dataset.k); });

  /* ---------------- Per pulau ---------------- */
  let current = null;
  const s2t = Object.fromEntries(S.s2sr_tren.map(r => [r.pulau, r]));
  function rowsFor(k) {
    const r = R[k] || {};
    const keys = ["Jenis dominan", "Kerapatan batang rerata (ind/ha)", "DBH rerata (cm)", "Tutupan kanopi rerata (%)", "LAI rerata",
      "Karbon batas bawah (t C/ha)", "H' Shannon", "% plot rusak-jarang (kerapatan+tutupan)", "Luas mangrove eksisting (ha)",
      "LRR rerata (m/th)", "% transek abrasi", "Hs P90 (m)", "% bersedia berpartisipasi"];
    return keys.filter(x => r[x] != null && r[x] !== "-").map(x => `<tr><td>${esc(x)}</td><td>${esc(fmt(r[x]))}</td></tr>`).join("");
  }
  function selectIsland(k, open = true) {
    current = k; showTab("pulau", open);
    const r = R[k] || {}, s = s2t[k];
    const t13 = S.tabel["13"].baris.find(b => b[0] === PULAU[k]);
    const pri = S.tabel["14"].baris.filter(b => b[1] === PULAU[k]);
    $("#tab-pulau").innerHTML = `
      <div class="chips">${KODE.map(c => `<button class="chip ${c === k ? "active" : ""}" data-k="${c}">${PULAU[c]}</button>`).join("")}</div>
      <h2>Pulau ${PULAU[k]} <small class="muted">(${k})</small></h2>
      <div class="kpis">
        <div class="kpi"><div class="v">${fmt(+r["Plot vegetasi"] || 0, 0)}</div><div class="l">plot vegetasi</div></div>
        <div class="kpi"><div class="v">${fmt(+r["Titik kualitas air"] || 0, 0)}</div><div class="l">titik kualitas air</div></div>
        <div class="kpi"><div class="v">${fmt(r["Luas mangrove eksisting (ha)"])}</div><div class="l">ha mangrove eksisting</div></div>
        <div class="kpi"><div class="v">${fmt(r["LRR rerata (m/th)"])}</div><div class="l">m/th laju garis pantai (LRR)</div></div>
      </div>
      ${(+r["Plot vegetasi"] || 0) === 0 ? `<div class="note">Survei lapangan di pulau ini belum dilakukan.</div>` : ""}
      <h3>Luas mangrove Sentinel-2 SR ${S.s2sr_tahun[0]}–${S.s2sr_tahun.at(-1)}</h3>
      ${s ? `<div class="chartbox"><canvas id="ch-pulau"></canvas></div>
      <p class="muted" style="font-size:.8rem">Batang: luas per kelas kerapatan (S2 super-resolusi 2,5 m, dipotong AOI pulau). Garis putus: digitasi 2025.</p>
      <table class="kv"><tr><td>Luas ${s.tahun_awal} → ${s.tahun_akhir}</td><td>${fmt(s.luas_awal_ha)} → ${fmt(s.luas_akhir_ha)} ha</td></tr>
        <tr><td>Laju regresi</td><td>${fmt(s.laju_ha_th, 3)} ha/th</td></tr>
        <tr><td>Tren Mann-Kendall</td><td>${s.tren} (τ ${fmt(s.tau)}, p ${fmt(s.p, 3)})</td></tr></table>`
        : `<div class="note">Data Sentinel-2 SR untuk pulau ini belum tersedia.</div>`}
      <h3>Indikator</h3>
      <table class="kv">${rowsFor(k)}</table>
      ${t13 ? `<h3>Kesesuaian &amp; prioritas pemulihan</h3><table class="kv">
        <tr><td>S1 sangat sesuai</td><td>${fmt(t13[1])} ha</td></tr><tr><td>S2 sesuai</td><td>${fmt(t13[2])} ha</td></tr>
        <tr><td>S3 sesuai bersyarat</td><td>${fmt(t13[3])} ha</td></tr><tr><td>N tidak sesuai</td><td>${fmt(t13[4])} ha</td></tr>
        <tr><td>Prioritas tinggi</td><td>${fmt(t13[6])} ha</td></tr><tr><td>Prioritas sedang</td><td>${fmt(t13[7])} ha</td></tr>
        <tr><td>Prioritas rendah</td><td>${fmt(t13[8])} ha</td></tr></table>
        ${pri.length ? `<p style="font-size:.85rem"><b>Lokasi prioritas tinggi:</b> ${pri.map(p => `<a href="#" data-ll="${p[6]},${p[7]}">${p[0]}</a> (${fmt(p[2])} ha)`).join(", ")}</p>` : ""}`
        : `<div class="note">Analisis kesesuaian belum tersedia untuk pulau ini (menunggu data batimetri/DTM/gelombang).</div>`}
      <p><button class="btn" id="btn-layers">Tampilkan lapisan survei di peta</button></p>`;
    if (s) {
      const ser = S.s2sr_tahunan[k], dig = S.luas_digitasi_2025[k];
      const ds = ["lebat", "sedang", "jarang"].map((c, i) => ({ type: "bar", label: c, stack: "s", backgroundColor: KELAS_S2[c],
        data: ser.map(r => r[{ jarang: 2, sedang: 3, lebat: 4 }[c]]) }));
      if (dig != null) ds.push({ type: "line", label: "Digitasi 2025", data: ser.map(() => dig), borderColor: "#c8662b", borderDash: [5, 4], borderWidth: 2, pointRadius: 0 });
      chart("ch-pulau", { data: { labels: ser.map(r => r[0]), datasets: ds },
        options: { maintainAspectRatio: false, scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, title: { display: true, text: "ha" } } },
          plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } } } } });
    }
    flyIsland(k);
  }
  function flyIsland(k) {
    const ll = S.pusat[k]; if (!ll) return;
    const z = window.innerWidth < 860 ? 14 : 15;
    map.flyTo(ll, z, { duration: .8 });
  }
  $("#tab-pulau").addEventListener("click", e => {
    const c = e.target.closest(".chip"); if (c) return selectIsland(c.dataset.k);
    const a = e.target.closest("a[data-ll]"); if (a) { e.preventDefault(); const [la, lo] = a.dataset.ll.split(",").map(Number); map.flyTo([la, lo], 17); ensureOn("prioritas"); }
    if (e.target.id === "btn-layers") { ["plot", "air", "lai", "transek"].forEach(ensureOn); flyIsland(current); }
  });
  selectIsland("LCG", false); showTab("progres", false); map.setView([-5.62, 106.58], 10);

  /* ---------------- Analisis ---------------- */
  const t13 = S.tabel["13"].baris, t11 = S.tabel["11"].baris, t6 = S.tabel["6"].baris, t10 = S.tabel["10"].baris;
  $("#tab-analisis").innerHTML = `
    <h2>Hasil analisis (v03)</h2>
    <h3>Luas mangrove total Kepulauan Seribu</h3>
    <div class="chartbox"><canvas id="ch-total"></canvas></div>
    <p class="muted" style="font-size:.8rem">Sentinel-2 super-resolusi 2,5 m, dipotong AOI tiap pulau (daratan + 150 m ∪ mangrove acuan + 30 m ∪ plot + 30 m). Tahun 2022 tidak tersedia. ${S.s2sr_total.some(r => r.n_pulau < 10) ? `Jumlah pulau terhitung: ${S.s2sr_total.at(-1).n_pulau} dari 10.` : ""}</p>
    <h3>Perubahan luas mangrove per pulau (S2SR ${S.s2sr_tahun[0]}–${S.s2sr_tahun.at(-1)})</h3>
    <div class="chartbox" style="height:240px"><canvas id="ch-tren"></canvas></div>
    <h3>Kesesuaian lahan pemulihan (ha)</h3>
    <div class="chartbox"><canvas id="ch-sesuai"></canvas></div>
    <p class="muted" style="font-size:.8rem">AHP 6 kriteria: elevasi 36,6 %, gelombang Hs 23,1 %, substrat 13,6 %, jarak ke mangrove 13,6 %, LRR 8 %, salinitas 5,2 % (CR = 0,012). Grid 10 m; 300 m ke laut, 30 m ke darat.</p>
    <h3>Perubahan garis pantai 1990–2025</h3>
    <div class="chartbox"><canvas id="ch-lrr"></canvas></div>
    <h3>Stok karbon batas bawah (t C/ha)</h3>
    <div class="chartbox"><canvas id="ch-karbon"></canvas></div>
    <div class="note">Batas bawah = individu terukur saja. ${esc(S.catatan_mutu.find(c => c.includes("BA >")) || "")}</div>
    <h3>Akurasi peta sebaran (semua pulau)</h3>
    <table class="kv">${t10.filter(r => r[1] === "Semua pulau").map(r => `<tr><td>${r[0]}</td><td>OA ${fmt(r[3])} % · κ ${fmt(r[4])}</td></tr>`).join("")}</table>
    <p class="muted" style="font-size:.8rem">Diuji terhadap ${fmt(t10.find(r => r[1] === "Semua pulau")?.[2], 0)} titik groundcheck lapangan.</p>`;

  const nm = k => PULAU[k];
  const tot = S.s2sr_total;
  const digTot = Object.keys(S.s2sr_tahunan).reduce((a, k) => a + (S.luas_digitasi_2025[k] || 0), 0);
  chart("ch-total", { data: { labels: tot.map(r => r.tahun), datasets: [
      ...["lebat", "sedang", "jarang"].map(c => ({ type: "bar", label: c, stack: "s", data: tot.map(r => r[c]), backgroundColor: KELAS_S2[c] })),
      { type: "line", label: `Digitasi 2025 (${fmt(digTot)} ha)`, data: tot.map(() => digTot), borderColor: "#c8662b", borderDash: [5, 4], borderWidth: 2, pointRadius: 0 }] },
    options: { maintainAspectRatio: false, scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, title: { display: true, text: "ha" } } },
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } } } } });

  const tren = S.s2sr_tren;
  chart("ch-tren", { type: "bar", data: { labels: tren.map(r => nm(r.pulau)), datasets: [
      { label: "Perubahan luas (ha)", data: tren.map(r => r.perubahan_ha),
        backgroundColor: tren.map(r => r.tren === "Naik" ? "#2f8466" : r.tren === "Turun" ? "#c0392b" : "#b8beb9") }] },
    options: { indexAxis: "y", maintainAspectRatio: false, plugins: { legend: { display: false },
      tooltip: { callbacks: { afterLabel: c => { const t = tren[c.dataIndex]; return `${t.tahun_awal}: ${fmt(t.luas_awal_ha)} ha → ${t.tahun_akhir}: ${fmt(t.luas_akhir_ha)} ha\nTren: ${t.tren} (τ ${t.tau}, p ${t.p})`; } } } },
      scales: { x: { title: { display: true, text: "ha (hijau = naik nyata, merah = turun nyata)" } } } } });

  const sc = [["S1", "#1a9850"], ["S2", "#91cf60"], ["S3", "#fee08b"], ["N", "#d9d9d9"]];
  chart("ch-sesuai", { type: "bar", data: { labels: t13.map(r => r[0]), datasets: sc.map(([l, c], i) => ({ label: l, data: t13.map(r => r[i + 1]), backgroundColor: c })) },
    options: { indexAxis: "y", maintainAspectRatio: false, scales: { x: { stacked: true, title: { display: true, text: "ha" } }, y: { stacked: true } },
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } } } } });

  chart("ch-lrr", { type: "bar", data: { labels: t11.map(r => r[0]), datasets: [
      { label: "LRR rerata (m/th)", data: t11.map(r => r[4]), backgroundColor: t11.map(r => r[4] < 0 ? "#ef8a62" : "#67a9cf"), yAxisID: "y" },
      { label: "Transek abrasi (%)", data: t11.map(r => r[6]), type: "line", borderColor: "#b2182b", backgroundColor: "#b2182b", showLine: false, pointRadius: 4, yAxisID: "y2" }] },
    options: { maintainAspectRatio: false, scales: { y: { title: { display: true, text: "m/th" } }, y2: { position: "right", min: 0, max: 100, grid: { drawOnChartArea: false }, title: { display: true, text: "% abrasi" } } },
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } } } } });

  chart("ch-karbon", { type: "bar", data: { labels: t6.map(r => r[0]), datasets: [{ label: "t C/ha", data: t6.map(r => r[1]), backgroundColor: "#1f5f4a" }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } } } });

  /* ---------------- Tabel ---------------- */
  const tKeys = Object.keys(S.tabel);
  $("#tab-tabel").innerHTML = `<h2>Tabel laporan</h2>
    <select id="tsel" style="width:100%">${tKeys.map(k => `<option value="${k}">${esc(S.tabel[k].judul)}</option>`).join("")}</select>
    <div id="tview"></div><p><button class="btn" id="tcsv">Unduh CSV</button></p>`;
  function renderTable(k) {
    const t = S.tabel[k];
    $("#tview").innerHTML = `<div class="dtable-wrap"><table class="dtable"><thead><tr>${t.kolom.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>${t.baris.map(r => `<tr>${r.map(v => `<td>${esc(fmt(v))}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
      ${t.catatan.map(c => `<p class="muted" style="font-size:.8rem">${esc(c)}</p>`).join("")}`;
  }
  $("#tsel").addEventListener("change", e => renderTable(e.target.value));
  $("#tcsv").addEventListener("click", () => {
    const t = S.tabel[$("#tsel").value];
    const q = v => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const csv = [t.kolom, ...t.baris].map(r => r.map(q).join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv" }));
    a.download = t.judul.split(".")[0].replace(/\s+/g, "_") + ".csv"; a.click();
  });
  renderTable(tKeys[0]);

  /* ---------------- Tentang ---------------- */
  $("#tab-info").innerHTML = `<h2>Tentang WebGIS ini</h2>
    <p>WebGIS ini menyajikan perkembangan data dan hasil analisis sementara <b>Kajian Pemulihan Ekosistem Mangrove di Kepulauan Seribu</b> (2026). Angka masih dapat berubah seiring QA/QC dan penambahan data lapangan.</p>
    <h3>Sumber data</h3>
    <table class="kv">
      <tr><td>Basis data spasial terpadu</td><td>HasilAnalisis_KS v03</td></tr>
      <tr><td>Mangrove eksisting (digitasi citra resolusi tinggi)</td><td>2025</td></tr>
      <tr><td>Seri waktu mangrove Sentinel-2 super-resolusi 2,5 m (dipotong AOI pulau)</td><td>${S.s2sr_tahun[0]}–${S.s2sr_tahun.at(-1)}</td></tr>
      <tr><td>Survei vegetasi, kualitas air, sumur, foto hemispherical</td><td>Sep–Nov 2026</td></tr>
      <tr><td>Garis pantai (DSAS, koreksi pasut GOT4.10c)</td><td>1990–2025</td></tr>
      <tr><td>Kesesuaian &amp; prioritas (AHP)</td><td>v03</td></tr>
    </table>
    <p class="muted" style="font-size:.85rem">Semua lapisan ditampilkan dalam WGS84; sumber asli dalam UTM 48S (EPSG:32748). Geometri disederhanakan (toleransi 0,5–4 m) untuk tampilan web, sehingga luas di peta bisa sedikit berbeda dari tabel.</p>
    <h3>Unduh data</h3>
    <p style="font-size:.88rem">${["mangrove_eksisting", "plot_vegetasi", "titik_kualitas_air", "sumur_air_tanah", "foto_lai", "transek_garis_pantai", "lokasi_prioritas", `mangrove_s2sr_${S.s2sr_tahun.at(-1)}`]
      .map(f => `<a href="data/${f}.geojson" download>${f}.geojson</a>`).join(" · ")}</p>
    <p class="muted" style="font-size:.8rem">Data dibangun: ${esc(S.dibangun)}</p>`;
})();
