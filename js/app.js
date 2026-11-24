/* WebGIS MGV-KS — Kajian Pemulihan Ekosistem Mangrove di Kepulauan Seribu */
(async function () {
  "use strict";

  const $ = (s, el = document) => el.querySelector(s);
  const fmt = (v, d = 2) => v == null || v === "" ? "–" :
    typeof v === "number" ? v.toLocaleString("id-ID", { maximumFractionDigits: d }) : v;
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const [S, P] = await Promise.all([
    fetch("data/statistik.json", { cache: "no-cache" }).then(r => r.json()),
    fetch("data/progres.json", { cache: "no-cache" }).then(r => r.json()),
  ]);
  const SO = await fetch("data/sosek.json", { cache: "no-cache" }).then(r => r.ok ? r.json() : {}).catch(() => ({}));
  const AN = await fetch("data/analisis.json", { cache: "no-cache" }).then(r => r.ok ? r.json() : {}).catch(() => ({}));
  const IF = await fetch("data/infrastruktur.json", { cache: "no-cache" }).then(r => r.ok ? r.json() : {}).catch(() => ({}));
  const ST = await fetch("data/strategi.json", { cache: "no-cache" }).then(r => r.ok ? r.json() : {}).catch(() => ({}));
  const GL = await fetch("data/gelombang.json", { cache: "no-cache" }).then(r => r.ok ? r.json() : {}).catch(() => ({}));
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
  const KES = { S1: "#1a9850", S2: "#91cf60", S3: "#d9ef8b" };
  const KES_NM = { S1: "S1 sangat sesuai", S2: "S2 sesuai", S3: "S3 sesuai bersyarat" };
  const KELAS_S2 = { lebat: "#0b5d3b", sedang: "#3f9c5a", jarang: "#a5d36e" };
  const LRR = [["Abrasi tinggi (<-2)", "#b2182b"], ["Abrasi (-2…-0,5)", "#ef8a62"], ["Stabil (±0,5)", "#e0e0e0"],
               ["Akresi (0,5…2)", "#67a9cf"], ["Akresi tinggi (>2)", "#2166ac"]];
  const LRRc = Object.fromEntries(LRR);
  const KONDISI = { "Baik - sangat padat": "#1a9850", "Baik - sedang": "#91cf60", "Rusak - jarang": "#d73027" };
  const SAL_SUMUR = { "Tawar": "#4575b4", "Payau ringan": "#91bfdb", "Payau": "#fc8d59", "Payau tinggi": "#d73027" };
  const MUSIM_NM = { DJF: "Musim Barat (Des–Feb)", MAM: "Peralihan I (Mar–Mei)", JJA: "Musim Timur (Jun–Agu)", SON: "Peralihan II (Sep–Nov)" };
  const MUSIM_PENDEK = { DJF: "Barat (DJF)", MAM: "Peralihan I (MAM)", JJA: "Timur (JJA)", SON: "Peralihan II (SON)" };
  const HS_KLS = [[0.15, "#c6dbef", "< 0,15"], [0.3, "#6baed6", "0,15–0,3"], [0.5, "#2171b5", "0,3–0,5"], [0.75, "#f16913", "0,5–0,75"], [99, "#a50f15", "≥ 0,75"]];
  const hsColor = v => (HS_KLS.find(([b]) => v < b) || HS_KLS.at(-1))[1];
  const SETUJU = { "Setuju": "#2b8cbe", "Tidak setuju": "#e7298a", "Belum ada keterangan": "#bdbdbd" };
  const KET_AIR = { "Mangrove": "#1a9850", "Non-mangrove": "#f1c40f", "Laut": "#2c7fb8" };
  const yearColor = (y) => { const t = Math.max(0, Math.min(1, (y - 1990) / 35)); return `hsl(${50 - t * 50 + (1 - t) * 160}, 80%, ${55 - t * 10}%)`; };
  const salColor = v => v == null ? "#999" : v < 0.5 ? "#4575b4" : v < 10 ? "#91bfdb" : v < 25 ? "#fee090" : v < 30 ? "#fc8d59" : "#d73027";

  function popupTable(title, rows) {
    return `<div class="pop"><h4>${esc(title)}</h4><table>${rows.filter(r => r[1] != null && r[1] !== "")
      .map(([k, v, d]) => `<tr><td>${esc(k)}</td><td><b>${esc(fmt(v, d))}</b></td></tr>`).join("")}</table></div>`;
  }

  const STRUK = { "Breakwater laut dangkal": "#6a3d9a", "Breakwater lepas pantai": "#e31a1c", "Jetty / dermaga": "#ff7f00",
    "Tanggul beton / seawall": "#525252", "Struktur lain (tanpa atribut)": "#a6761d" };
  const fmtRp = v => v == null ? "–" : v >= 1e9 ? `Rp ${fmt(v / 1e9, 2)} M` : `Rp ${fmt(v / 1e6, 0)} jt`;
  const TAHAP = { "I": "#b2182b", "II": "#ef8a62", "III": "#f6c85f", "Bersyarat": "#7b3294" };
  const TAHAP_NM = { "I": "Tahap I (2027)", "II": "Tahap II (2028–2029)", "III": "Tahap III (2030)", "Bersyarat": "Perluasan bersyarat (2031)" };
  const tahapKey = p => p.status === "Bersyarat" ? "Bersyarat" : p.tahap;
  const TEKNIK_NM = Object.fromEntries(((ST.teknik || {}).baris || []).map(r => [r[0], r[1]]));
  const JALUR = { "Trayek Reguler Dishub": "#d6604d", "Trayek Perintis Dishub": "#b2182b", "Trayek Kapal Cepat": "#f4a582",
    "Trayek Penyeberangan Tradisional": "#8c510a", "Jalur Antar Pulau": "#35978f", "Alur Masuk Dermaga": "#fdd835" };
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
        ["DBH rerata (cm; = keliling/π)", p.dbh_rerata_cm], ["Tutupan kanopi (%)", p.tutupan_kanopi_pct], ["LAI (ring 4)", p.LAI_ring4],
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
        ["pH", p.ph], ["DO (mg/L)", p.do_mg_l], ["TDS (ppt)", p.tds_ppt], ["Suhu (°C)", p.suhu_c], ["Kedalaman (cm)", p.kedalaman_cm]]),
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

    { id: "kesesuaian", grp: "Analisis pemulihan", label: "Kesesuaian lahan (hasil AHP)", file: "kesesuaian_ahp", on: true, sw: "#1a9850",
      style: f => ({ color: KES[f.properties.kelas], weight: .6, fillColor: KES[f.properties.kelas], fillOpacity: .6 }),
      popup: p => popupTable(`Kesesuaian ${p.kelas}`, [["Pulau", PULAU[p.pulau]], ["Kelas", KES_NM[p.kelas]], ["Luas kelas di pulau (ha)", p.luas_ha]]),
      legend: () => `<div class="lt">Kesesuaian lahan (AHP ${esc(AN.versi || "")})</div>` +
        Object.entries(KES).map(([k, c]) => `<div class="row"><span class="sw" style="background:${c}"></span>${KES_NM[k]}</div>`).join("") +
        `<div class="row muted" style="font-size:.72rem">tanpa warna = N tidak sesuai</div>` },
    { id: "prioritas", grp: "Analisis pemulihan", label: "Prioritas pemulihan (sesuai + disetujui masyarakat)", file: "prioritas_masyarakat", on: true, sw: "#c0392b",
      style: f => ({ color: "#3b0d0d", weight: 1.2, fillColor: PRIOR[f.properties.prioritas], fillOpacity: .8 }),
      popup: p => popupTable(`Prioritas ${p.id}`, [["Pulau", PULAU[p.pulau]], ["Prioritas", p.prioritas], ["Luas (ha)", p.luas_ha], ["Skor AHP rerata", p.skor_rerata],
        ["Lokasi AHP", p.id_lokasi], ["Area FGD", p.id_fgd], ["Lintang", p.lintang, 6], ["Bujur", p.bujur, 6]]),
      legend: () => `<div class="lt">Prioritas pemulihan (AHP ∩ FGD setuju)</div>` + Object.entries(PRIOR).map(([k, c]) => `<div class="row"><span class="sw" style="background:${c}"></span>${k}</div>`).join("") },
    { id: "prioritas_ahp", grp: "Analisis pemulihan", label: "Prioritas AHP (belum mempertimbangkan masyarakat)", file: "lokasi_prioritas", on: false, sw: "#e68a2e",
      style: f => ({ color: PRIOR[f.properties.prioritas], weight: 1.5, dashArray: "3 3", fill: false }),
      popup: p => popupTable(`Lokasi ${p.id_lokasi || ""}`, [["Pulau", PULAU[p.pulau]], ["Prioritas AHP", p.prioritas], ["Luas (ha)", p.luas_ha], ["Skor rerata", p.skor_rerata],
        ["Elevasi median (m MSL)", p.elevasi_median_m]]),
      legend: () => `<div class="lt">Prioritas AHP (garis putus)</div>` + Object.entries(PRIOR).map(([k, c]) => `<div class="row"><span class="sw l" style="background:${c}"></span>${k}</div>`).join("") },
    { id: "setuju", grp: "Analisis pemulihan", label: "Persetujuan masyarakat (FGD)", file: "persetujuan_masyarakat", on: false, sw: "#2b8cbe",
      style: f => ({ color: SETUJU[f.properties.status] || "#999", weight: 2, dashArray: "5 3", fillColor: SETUJU[f.properties.status] || "#999", fillOpacity: .3 }),
      popup: p => popupTable(`Area FGD ${p.id}`, [["Pulau", PULAU[p.pulau]], ["Masyarakat", p.status], ["Catatan", p.catatan], ["Luas (ha)", p.luas_ha]]),
      legend: () => `<div class="lt">Penanaman mangrove – sikap masyarakat (FGD)</div>` +
        Object.entries(SETUJU).map(([k, c]) => `<div class="row"><span class="sw" style="background:${c}"></span>${k}</div>`).join("") },
    { id: "gelombang", grp: "Angin & gelombang", label: "Gelombang (tinggi & arah, pasang tertinggi)", fileFn: () => `gelombang_${musim}`, on: false, sw: "#2171b5",
      style: f => ({ color: hsColor(f.properties.hs), weight: 1.6, opacity: .95 }),
      popup: p => popupTable(`Gelombang – ${MUSIM_NM[p.musim]}`, [["Pulau", PULAU[p.pulau]], ["Tinggi gelombang Hs (m)", p.hs], ["Periode Tp (s)", p.tp],
        ["Arah datang (°)", `${p.dari}° (${arahMA(p.dari)})`]]),
      legend: () => `<div class="lt">Gelombang ${MUSIM_NM[musim]} – Hs (m), muka air HHWS</div>` +
        HS_KLS.map(([, c, l]) => `<div class="row"><span class="sw l" style="background:${c}"></span>${l}</div>`).join("") +
        `<div class="row muted" style="font-size:.72rem">panah = arah rambat gelombang</div>`,
      extra: () => `<select id="musim-sel">${Object.entries(MUSIM_NM).map(([k, v]) => `<option value="${k}" ${k === musim ? "selected" : ""}>${v}</option>`).join("")}</select>` },
    { id: "angin", grp: "Angin & gelombang", label: "Angin (arah & kecepatan rata-rata)", file: "angin", on: false, sw: "#444",
      filter: f => f.properties.musim === musim,
      style: () => ({ color: "#222", weight: 4, opacity: .85 }),
      popup: p => popupTable(`Angin – ${MUSIM_NM[p.musim]}`, [["Pulau", PULAU[p.pulau]], ["Kecepatan U10 (m/s)", p.U10_ms], ["Arah datang (°)", `${p.dari}° (${p.dari_ma})`]]),
      legend: () => `<div class="lt">Angin ${MUSIM_NM[musim]}</div><div class="row"><span class="sw l" style="background:#222"></span>panah = arah tiup (dari pilihan musim di atas)</div>` },
    { id: "rencana", grp: "Rencana aksi", label: "Lokasi rencana aksi (tahap pelaksanaan)", file: "rencana_aksi", on: false, sw: "#b2182b",
      style: f => { const k = tahapKey(f.properties); return { color: k === "Bersyarat" ? TAHAP[k] : "#3b0d0d", weight: k === "Bersyarat" ? 1.6 : 1, dashArray: k === "Bersyarat" ? "4 3" : null,
        fillColor: TAHAP[k] || "#999", fillOpacity: k === "Bersyarat" ? .25 : .85 }; },
      popup: p => popupTable(`Lokasi aksi ${p.id_lokasi}`, [["Pulau", PULAU[p.pulau]], ["Prioritas", p.prioritas], ["Tahap", TAHAP_NM[tahapKey(p)]], ["Tahun tanam", p.tahun, 0],
        ["Status", p.status], ["Teknik", `${p.teknik} – ${TEKNIK_NM[p.teknik] || ""}`], ["Zona pasut", p.zona], ["Luas (ha)", p.luas_ha], ["Elevasi median (m MSL)", p.elevasi_median_m],
        ["Bibit (batang)", p.bibit, 0], ["APO bambu (m)", p.apo_m || null, 0], ["Biaya pembangunan", fmtRp(p.biaya_rp)]]),
      legend: () => `<div class="lt">Rencana aksi – tahap pelaksanaan</div>` + Object.entries(TAHAP).map(([k, c]) => `<div class="row"><span class="sw" style="background:${c}${k === "Bersyarat" ? ";opacity:.5" : ""}"></span>${TAHAP_NM[k]}</div>`).join("") },
    { id: "struktur", grp: "Infrastruktur pesisir", label: "Breakwater, jetty & tanggul", file: "struktur_pantai", on: false, sw: "#6a3d9a",
      style: f => ({ color: STRUK[f.properties.kelompok] || "#555", weight: 3.5, opacity: .95 }),
      popup: p => popupTable(p.tipe || p.kelompok, [["Pulau", PULAU[p.pulau]], ["Kelompok", p.kelompok], ["Panjang (m)", p.panjang_m, 0], ["Tahun data", p.tahun, 0]]),
      legend: () => `<div class="lt">Struktur pantai</div>` + Object.entries(STRUK).map(([k, c]) => `<div class="row"><span class="sw l" style="background:${c}"></span>${k}</div>`).join("") },
    { id: "jalur", grp: "Infrastruktur pesisir", label: "Jalur kapal", file: "jalur_kapal", on: false, sw: "#d6604d",
      style: f => ({ color: JALUR[f.properties.tipe] || "#d6604d", weight: f.properties.tipe === "Alur Masuk Dermaga" ? 3 : 2, dashArray: "8 5", opacity: .9 }),
      popup: p => popupTable(p.nama, [["Pulau", PULAU[p.pulau]], ["Jenis", p.tipe], ["Asal", p.asal], ["Tujuan", p.tujuan], ["Panjang (km)", p.panjang_km]]),
      legend: () => `<div class="lt">Jalur kapal</div>` + Object.entries(JALUR).map(([k, c]) => `<div class="row"><span class="sw l" style="background:${c}"></span>${k}</div>`).join("") },
  ];
  let s2Year = S.s2sr_tahun[S.s2sr_tahun.length - 1], airMode = "ket", musim = "DJF";
  function arahMA(d) { return d == null ? "–" : ["U", "TL", "T", "TG", "S", "BD", "B", "BL"][Math.floor(((d % 360) + 22.5) / 45) % 8]; }
  const loaded = {};
  let urut = [];
  const ATAS = ["angin", "gelombang", "struktur", "jalur"];   // legenda selalu di atas   // id lapisan sesuai urutan dinyalakan
  const cache = {};

  async function getGeo(file) {
    if (!cache[file]) cache[file] = fetch(`data/${file}.geojson`, { cache: "no-cache" }).then(r => r.json());
    return cache[file];
  }
  async function buildLayer(def) {
    const file = def.fileFn ? def.fileFn() : def.file;
    const gj = await getGeo(file);
    const opt = {
      style: def.style, filter: def.filter,
      onEachFeature: def.popup ? (f, l) => l.bindPopup(() => def.popup(f.properties), { maxWidth: 320 }) : undefined,
    };
    if (def.point) opt.pointToLayer = (f, ll) => L.circleMarker(ll, { ...def.style(f), renderer: canvas });
    return L.geoJSON(gj, opt);
  }
  const giliran = {};   // nomor panggilan terakhir per lapisan: hasil pemuatan yang sudah usang dibuang
  async function toggle(def, on) {
    const n = giliran[def.id] = (giliran[def.id] || 0) + 1;
    if (loaded[def.id]) { map.removeLayer(loaded[def.id]); delete loaded[def.id]; }
    urut = urut.filter(id => id !== def.id);
    if (on) {
      const lyr = await buildLayer(def);
      if (n !== giliran[def.id]) return;   // ada panggilan lebih baru (mis. ganti musim cepat) – jangan ditumpuk
      if (loaded[def.id]) map.removeLayer(loaded[def.id]);
      loaded[def.id] = lyr; lyr.addTo(map); urut.push(def.id);
    }
    // jaga urutan: poligon di bawah, lalu infrastruktur & gelombang/angin, titik paling atas
    [...ATAS].reverse().forEach(id => loaded[id]?.bringToFront?.());
    LAYERS.forEach(d => { if (loaded[d.id] && d.point) loaded[d.id].bringToFront?.(); });
    renderLegend();
  }
  let legendOpen = window.innerWidth >= 860;
  function renderLegend() {
    // urutan legenda = urutan tumpukan di peta: lapisan paling atas tampil paling atas
    // (titik selalu di atas poligon/garis; di dalam tiap jenis, yang terakhir dinyalakan di atas)
    const aktif = urut.map(id => LAYERS.find(d => d.id === id)).filter(d => d && loaded[d.id] && d.legend).reverse();
    // angin, gelombang & infrastruktur pesisir selalu di bagian atas legenda
    const atas = ATAS.map(id => LAYERS.find(d => d.id === id)).filter(d => loaded[d.id] && d.legend);
    const isi = [...atas, ...aktif.filter(d => d.point), ...aktif.filter(d => !d.point && !ATAS.includes(d.id))].map(d => `<div class="lg">${d.legend()}</div>`).join("");
    $("#legend").innerHTML = isi ? `<button class="lg-head" id="lg-toggle">Legenda <span>${legendOpen ? "▾" : "▸"}</span></button>${legendOpen ? `<div class="lg-body">${isi}</div>` : ""}` : "";
  }
  $("#legend").addEventListener("click", e => { if (e.target.closest("#lg-toggle")) { legendOpen = !legendOpen; renderLegend(); } });

  function renderLayerBox() {
    const grps = [...new Set(LAYERS.map(d => d.grp))];
    $("#layerbox").innerHTML = `<details open><summary>Lapisan peta</summary>
      <div class="grp"><div class="gt">Peta dasar</div>
        <select id="basemap">${Object.keys(bases).map(b => `<option>${b}</option>`).join("")}</select>
        <label><input type="checkbox" id="lbl" checked> Nama pulau</label></div>
      ${grps.map(g => { const ls = LAYERS.filter(d => d.grp === g); return `<details class="grp" ${ls.some(d => d.on) ? "open" : ""}><summary class="gt">${g}</summary>${ls.map(d =>
        `<label><input type="checkbox" data-id="${d.id}" ${d.on ? "checked" : ""}><span class="sw" style="background:${d.sw}"></span>${d.label}</label>${d.extra ? d.extra() : ""}`).join("")}</details>`; }).join("")}
    </details>`;
    $("#layerbox").addEventListener("change", e => {
      const t = e.target;
      if (t.id === "basemap") { Object.values(bases).forEach(b => map.removeLayer(b)); bases[t.value].addTo(map); return; }
      if (t.id === "lbl") { t.checked ? labels.addTo(map) : map.removeLayer(labels); return; }
      if (t.id === "s2-year") { s2Year = +t.value; const d = LAYERS.find(x => x.id === "s2sr"); setChecked("s2sr"); toggle(d, true); return; }
      if (t.id === "musim-sel") { musim = t.value; const aktif = ["gelombang", "angin"].filter(id => loaded[id] || $(`#layerbox input[data-id="${id}"]`)?.checked);
        if (!aktif.length) { setChecked("gelombang"); aktif.push("gelombang"); }
        aktif.forEach(id => toggle(LAYERS.find(x => x.id === id), true)); return; }
      if (t.id === "air-mode") { airMode = t.value; const d = LAYERS.find(x => x.id === "air"); setChecked("air"); toggle(d, true); return; }
      if (t.dataset.id) toggle(LAYERS.find(d => d.id === t.dataset.id), t.checked);
    });
    if (window.innerWidth < 860) $("#layerbox > details").open = false;
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
    if (name === "strategi" && ST.versi) ensureOn("rencana");
  }
  document.querySelectorAll(".tabs button").forEach(b => b.addEventListener("click", () => showTab(b.dataset.tab)));
  $("#panel-toggle").addEventListener("click", () => {
    const o = $("#panel").classList.toggle("open");
    $("#panel-toggle").textContent = o ? "✕" : "☰";
  });

  /* ---------------- Progres ---------------- */
  const R = S.ringkasan;
  const sum = key => KODE.reduce((a, k) => a + (+R[k]?.[key] || 0), 0);
  const surveyed = KODE.filter(k => (+R[k]?.["Plot vegetasi"] || 0) > 0).length;
  const fields = [["plot_vegetasi", "Veg"], ["kualitas_air", "Air"], ["air_tanah", "Sumur"], ["garis_pantai", "Pantai"],
                  ["gelombang", "Gel."], ["batimetri", "Bati."], ["dtm", "DTM"], ["sosek", "Sosek"], ["fgd", "FGD"]];
  // sosek = jumlah responden kuesioner (Tabel 15/ringkasan); FGD = peta area setuju/tidak setuju (09_Sosek)
  const kel = S.kelengkapan.map(r => { const k = r[Object.keys(r)[0]] || r[""] || r[null];
    return { ...r, sosek: +R[k]?.["Responden sosek"] || 0, fgd: SO.persetujuan && SO.persetujuan[k] ? 1 : 0 }; });
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
    <table class="matrix"><thead><tr><th>Pulau</th>${fields.map(f => `<th>${f[1]}</th>`).join("")}<th>Ses.</th></tr></thead>
    <tbody>${kel.map(r => { const k = r[Object.keys(r)[0]] || r[""] || r[null]; return `<tr class="clickable" data-k="${k}"><td>${PULAU[k] || k}</td>${fields.map(([f]) =>
      `<td>${(f === "plot_vegetasi" || f === "kualitas_air" || f === "air_tanah" || f === "sosek") && r[f] ? `<span class="num">${r[f]}</span>` : `<span class="cell ${r[f] ? "y" : "n"}"></span>`}</td>`).join("")}
      <td><span class="cell ${r.lengkap ? "y" : "n"}"></span></td></tr>`; }).join("")}</tbody></table>
    <p class="muted" style="font-size:.8rem">Angka = jumlah plot/titik/sumur/responden sosek. “FGD” = peta area yang disetujui/tidak disetujui masyarakat untuk ditanami mangrove. “Ses.” = data cukup untuk analisis kesesuaian pemulihan (perlu batimetri/DTM dan gelombang). Klik baris untuk melihat pulau.</p>
  `;
  $("#tab-progres").addEventListener("click", e => {
    const tr = e.target.closest("tr[data-k]"); if (tr) return selectIsland(tr.dataset.k);
  });

  /* ---------------- Per pulau ---------------- */
  let current = null;
  const s2t = Object.fromEntries(S.s2sr_tren.map(r => [r.pulau, r]));
  function rowsFor(k) {
    const r = R[k] || {};
    const keys = ["Jenis dominan", "Kerapatan batang rerata (ind/ha)", "DBH rerata (cm)", "Tutupan kanopi rerata (%)", "LAI rerata",
      "Karbon batas bawah (t C/ha)", "H' Shannon", "% plot rusak-jarang (kerapatan+tutupan)", "Luas mangrove eksisting (ha)",
      "LRR rerata (m/th)", "% transek abrasi", "Hs P90 musim tertinggi (m)", "% bersedia berpartisipasi"];
    return keys.filter(x => r[x] != null && r[x] !== "-").map(x => `<tr><td>${esc(x === "DBH rerata (cm)" ? "DBH rerata (cm; = keliling batang/π)" : x)}</td><td>${esc(fmt(r[x]))}</td></tr>`).join("");
  }
  const bar = (obj, n, warna = "#3f9c5a") => Object.entries(obj).map(([a, b]) =>
    `<div class="bar"><span class="bl">${esc(a)}</span><span class="bt"><span style="width:${Math.round(100 * b / Math.max(n, 1))}%;background:${warna}"></span></span><span class="bv">${b}</span></div>`).join("");
  function panelAnalisis(k) {
    const a = (AN.pulau || {})[k] || {}, ks = a.kesesuaian_ha, pa = a.prioritas_ahp_ha, pm = a.prioritas_masyarakat_ha || {};
    if (!ks) return `<div class="note">Analisis kesesuaian belum tersedia untuk pulau ini.</div>`;
    const tot = o => Object.values(o || {}).reduce((x, y) => x + y, 0);
    const fg = SO.persetujuan && SO.persetujuan[k];
    return `<h3>Analisis pemulihan</h3>
      <table class="kv"><tr><td colspan="2"><b>1. Kesesuaian lahan (AHP ${esc(AN.versi)})</b></td></tr>
        ${["S1", "S2", "S3"].map(c => `<tr><td><span class="sw" style="background:${KES[c]}"></span> ${KES_NM[c]}</td><td>${fmt(ks[c])} ha</td></tr>`).join("")}
        <tr><td>N tidak sesuai</td><td>${fmt(ks.N)} ha</td></tr>
        ${a.masukan && a.masukan.struktur_ha != null ? `<tr><td>Dikeluarkan: struktur pantai / jalur kapal</td><td>${fmt(a.masukan.struktur_ha)} / ${fmt(a.masukan.jalur_ha)} ha</td></tr>
        <tr><td>Zona terlindung breakwater</td><td>${fmt(a.masukan.terlindung_ha)} ha <small class="muted">(${fmt(a.masukan.sesuai_terlindung_ha)} ha sesuai)</small></td></tr>` : ""}
        <tr><td colspan="2"><b>2. Prioritas pemulihan (sesuai + disetujui masyarakat)</b></td></tr>
        ${["Tinggi", "Sedang", "Rendah"].map(c => `<tr><td><span class="sw" style="background:${PRIOR[c]}"></span> Prioritas ${c.toLowerCase()}</td><td>${fmt(pm[c])} ha <small class="muted">dari ${fmt(pa[c])} ha AHP</small></td></tr>`).join("")}
        <tr><td>Total prioritas</td><td>${fmt(tot(pm))} ha</td></tr></table>
      ${fg ? (a.setuju_tidak_sesuai_ha > 0.05 ? `<p class="muted" style="font-size:.8rem">${fmt(a.setuju_tidak_sesuai_ha)} ha area yang disetujui masyarakat tidak termasuk kelas S1–S3 (mangrove eksisting, daratan, elevasi di luar zona pasut, struktur pantai, atau jalur kapal).</p>` : "")
        : `<div class="note">Belum ada peta FGD untuk pulau ini, sehingga prioritas belum dapat dipadukan dengan keinginan masyarakat.</div>`}
      ${fg ? `<p class="muted" style="font-size:.82rem">Area FGD: ${Object.entries(fg).map(([st, v]) => `${esc(st.toLowerCase())} ${fmt(v.luas_ha)} ha`).join(" · ")} — <a href="#" id="lnk-setuju">tampilkan di peta</a></p>` : ""}`;
  }
  function panelGelombang(k) {
    const g = (GL.pulau || {})[k];
    if (!g) return "";
    const e = g.ekstrem;
    return `<h3>Angin &amp; gelombang</h3>
      <div class="kpis one"><div class="kpi"><div class="v">${fmt(e.Hs_maks)} m</div><div class="l">tinggi gelombang ekstrem (Hs maks pesisir, ${esc(e.nama)}, dari ${esc(e.gelombang_dari_ma)})</div></div></div>
      <table class="kv wave"><thead><tr><th>Musim</th><th>Angin dari</th><th>Gelombang dari</th><th>Hs P90 / maks (m)</th></tr></thead>
      ${g.musim.map(r => `<tr><td>${esc(MUSIM_PENDEK[r.musim] || r.nama)}</td><td>${esc(r.angin_dari_ma)} ${fmt(r.angin_dari, 0)}° · ${fmt(r.U10_ms, 1)} m/s</td>
        <td>${esc(r.gelombang_dari_ma)} ${fmt(r.gelombang_dari, 0)}°</td><td>${fmt(r.Hs_p90)} / ${fmt(r.Hs_maks)}</td></tr>`).join("")}</table>
      <p class="muted" style="font-size:.78rem">Model gelombang 4 musim MGV-KS v03 pada muka air pasang tertinggi (HHWS); Hs = tinggi gelombang signifikan di perairan dekat pantai (≤ 300 m). Angin = rata-rata Sentinel-1 + ERA5. <a href="#" id="lnk-gel">Tampilkan di peta</a></p>`;
  }
  function panelInfra(k) {
    const d = (IF.pulau || {})[k];
    if (!d) return "";
    const st = d.struktur || {}, tot = Object.values(st).reduce((a, v) => a + v.panjang_m, 0);
    return `<h3>Struktur pelindung pantai</h3>
      ${Object.keys(st).length ? `<table class="kv">${Object.entries(st).map(([n, v]) => `<tr><td><span class="sw" style="background:${STRUK[n] || "#555"}"></span> ${esc(n)}</td><td>${v.n} ruas · ${fmt(v.panjang_m, 0)} m</td></tr>`).join("")}
        <tr><td>Total</td><td>${fmt(tot, 0)} m</td></tr></table>` : `<div class="note">Tidak ada data struktur pantai.</div>`}
      <h3>Jalur kapal</h3>
      ${(d.jalur || []).length ? `<table class="kv">${d.jalur.map(j => `<tr><td><span class="sw" style="background:${JALUR[j.tipe] || "#d6604d"}"></span> ${esc(j.nama)}<br><small class="muted">${esc(j.tipe)}</small></td><td>${fmt(j.panjang_km, j.panjang_km < 10 ? 2 : 1)} km</td></tr>`).join("")}</table>` : `<div class="note">Tidak ada data jalur kapal.</div>`}
      <p class="muted" style="font-size:.78rem">Sumber: data sekunder breakwater &amp; jalur kapal per pulau (01_DATA_SEKUNDER). <a href="#" id="lnk-infra">Tampilkan di peta</a></p>`;
  }
  function panelRencana(k) {
    const r = (ST.rekap_pulau || {})[k];
    if (!r) return "";
    const th = [2027, 2028, 2029, 2030, 2031].map(y => [y, r[`Luas tanam ${y} (ha)`]]).filter(([, v]) => v > 0);
    return `<h3>Rencana aksi ${esc(ST.versi)}</h3>
      <table class="kv"><tr><td>Luas tanam dasar + pilot</td><td>${fmt(r["Total dasar+pilot (ha)"])} ha</td></tr>
        ${th.map(([y, v]) => `<tr><td>&nbsp;&nbsp;tahun ${y}</td><td>${fmt(v)} ha</td></tr>`).join("")}
        ${r["Bersyarat (ha)"] > 0 ? `<tr><td>Perluasan bersyarat (guludan, 2031)</td><td>${fmt(r["Bersyarat (ha)"])} ha</td></tr>` : ""}
        <tr><td>Kebutuhan bibit</td><td>${fmt(r["Bibit dasar+pilot (batang)"], 0)} batang</td></tr>
        <tr><td>Biaya pembangunan (dasar + pilot)</td><td>${fmtRp(r["Pembangunan dasar+pilot (Rp)"])}</td></tr></table>
      <p class="cap">Teknik, tahap dan biaya tiap lokasi: klik poligon pada lapisan "Lokasi rencana aksi". <a href="#" id="lnk-rencana">Tampilkan di peta</a> · <a href="#" id="lnk-strategi">Lihat strategi</a></p>`;
  }
  function panelSosek(k) {
    const s = (SO.survei || {})[k];
    if (!s) return `<h3>Sosial-ekonomi</h3><div class="note">Survei sosial-ekonomi belum tersedia untuk pulau ini.</div>`;
    const q = s.pertanyaan, i = s.indikator;
    const blok = key => q[key] ? `<div class="qs"><div class="ql">${esc(q[key].label)}</div>${bar(q[key].jawaban, q[key].n)}</div>` : "";
    return `<h3>Sosial-ekonomi masyarakat <small class="muted">(${s.n} responden)</small></h3>
      <div class="kpis">${Object.entries(i).map(([a, b]) => `<div class="kpi"><div class="v">${fmt(b, 0)}%</div><div class="l">${esc(a.replace(" (%)", "").toLowerCase())}</div></div>`).join("")}</div>
      ${["kelebatan", "kondisi", "program", "pelibatan", "kesediaan", "peran", "dukungan", "pengaruh_ikan", "perilaku", "pemanfaatan", "sektor_laut"].map(blok).join("")}
      <p class="muted" style="font-size:.78rem">Ringkasan kuesioner survei sosial ekonomi-kelembagaan MGV-KS 2026; data pribadi responden tidak ditampilkan.</p>`;
  }
  const SUBTAB = [["ringkasan", "Ringkasan"], ["vegetasi", "Vegetasi"], ["gelombang", "Pesisir"], ["pemulihan", "Pemulihan"], ["sosek", "Sosek"]];
  let subTab = "ringkasan";
  function selectIsland(k, open = true) {
    current = k; showTab("pulau", open);
    const r = R[k] || {}, s = s2t[k];
    const sec = {
      ringkasan: `<div class="kpis">
        <div class="kpi"><div class="v">${fmt(+r["Plot vegetasi"] || 0, 0)}</div><div class="l">plot vegetasi</div></div>
        <div class="kpi"><div class="v">${fmt(+r["Titik kualitas air"] || 0, 0)}</div><div class="l">titik kualitas air</div></div>
        <div class="kpi"><div class="v">${fmt(r["Luas mangrove eksisting (ha)"])}</div><div class="l">ha mangrove eksisting</div></div>
        <div class="kpi"><div class="v">${fmt(r["LRR rerata (m/th)"])}</div><div class="l">m/th laju garis pantai (LRR)</div></div>
      </div>
      ${(+r["Plot vegetasi"] || 0) === 0 ? `<div class="note">Survei lapangan di pulau ini belum dilakukan.</div>` : ""}
      <h3>Luas mangrove Sentinel-2 SR ${S.s2sr_tahun[0]}–${S.s2sr_tahun.at(-1)}</h3>
      ${s ? `<div class="chartbox"><canvas id="ch-pulau"></canvas></div>
      <p class="cap">Batang: luas per kelas kerapatan (S2 super-resolusi 2,5 m, dipotong AOI pulau). Garis putus: digitasi 2025.</p>
      <table class="kv"><tr><td>Luas ${s.tahun_awal} → ${s.tahun_akhir}</td><td>${fmt(s.luas_awal_ha)} → ${fmt(s.luas_akhir_ha)} ha</td></tr>
        <tr><td>Laju regresi</td><td>${fmt(s.laju_ha_th, 3)} ha/th</td></tr>
        <tr><td>Tren Mann-Kendall</td><td>${s.tren} (τ ${fmt(s.tau)}, p ${fmt(s.p, 3)})</td></tr></table>`
        : `<div class="note">Data Sentinel-2 SR untuk pulau ini belum tersedia.</div>`}`,
      vegetasi: `<h3>Indikator vegetasi &amp; pesisir</h3><table class="kv">${rowsFor(k)}</table>
        <p><button class="btn" id="btn-layers">Tampilkan lapisan survei di peta</button></p>`,
      gelombang: (panelGelombang(k) || `<div class="note">Data angin &amp; gelombang belum tersedia.</div>`) + panelInfra(k),
      pemulihan: panelAnalisis(k) + panelRencana(k),
      sosek: panelSosek(k),
    };
    if (!sec[subTab]) subTab = "ringkasan";
    $("#tab-pulau").innerHTML = `
      <div class="pulau-head">
        <div class="chips">${KODE.map(c => `<button class="chip ${c === k ? "active" : ""}" data-k="${c}">${PULAU[c]}</button>`).join("")}</div>
        <h2>Pulau ${PULAU[k]} <small class="muted">(${k})</small></h2>
        <div class="subtabs">${SUBTAB.map(([id, nm]) => `<button class="${id === subTab ? "active" : ""}" data-sub="${id}">${nm}</button>`).join("")}</div>
      </div>
      ${Object.entries(sec).map(([id, h]) => `<div class="subsec ${id === subTab ? "active" : ""}" data-sub="${id}">${h}</div>`).join("")}`;
    gambarS2(k);
    flyIsland(k);
  }
  function gambarS2(k) {
    const s = s2t[k];
    if (subTab !== "ringkasan" || !document.getElementById("ch-pulau")) return;
    if (s) {
      const ser = S.s2sr_tahunan[k], dig = S.luas_digitasi_2025[k];
      const ds = ["lebat", "sedang", "jarang"].map((c, i) => ({ type: "bar", label: c, stack: "s", backgroundColor: KELAS_S2[c],
        data: ser.map(r => r[{ jarang: 2, sedang: 3, lebat: 4 }[c]]) }));
      if (dig != null) ds.push({ type: "line", label: "Digitasi 2025", data: ser.map(() => dig), borderColor: "#c8662b", borderDash: [5, 4], borderWidth: 2, pointRadius: 0 });
      chart("ch-pulau", { data: { labels: ser.map(r => r[0]), datasets: ds },
        options: { maintainAspectRatio: false, scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, title: { display: true, text: "ha" } } },
          plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } } } } });
    }
  }
  function flyIsland(k) {
    const ll = S.pusat[k]; if (!ll) return;
    const z = window.innerWidth < 860 ? 14 : 15;
    map.flyTo(ll, z, { duration: .8 });
  }
  $("#tab-pulau").addEventListener("click", e => {
    const c = e.target.closest(".chip"); if (c) return selectIsland(c.dataset.k);
    const sb = e.target.closest(".subtabs button");
    if (sb) {
      subTab = sb.dataset.sub;
      document.querySelectorAll("#tab-pulau .subtabs button").forEach(b => b.classList.toggle("active", b === sb));
      document.querySelectorAll("#tab-pulau .subsec").forEach(d => d.classList.toggle("active", d.dataset.sub === subTab));
      $("#panel").scrollTop = 0; gambarS2(current);
      if (subTab === "gelombang") { ensureOn("gelombang"); ensureOn("angin"); ensureOn("struktur"); }
      if (subTab === "pemulihan") { ensureOn("kesesuaian"); ensureOn("prioritas"); }
      return;
    }
    const a = e.target.closest("a[data-ll]"); if (a) { e.preventDefault(); const [la, lo] = a.dataset.ll.split(",").map(Number); map.flyTo([la, lo], 17); ensureOn("prioritas"); }
    if (e.target.id === "btn-layers") { ["plot", "air", "lai", "transek"].forEach(ensureOn); flyIsland(current); }
    if (e.target.id === "lnk-rencana") { e.preventDefault(); ensureOn("rencana"); flyIsland(current); }
    if (e.target.id === "lnk-strategi") { e.preventDefault(); showTab("strategi"); }
    if (e.target.id === "lnk-infra") { e.preventDefault(); ensureOn("struktur"); ensureOn("jalur"); flyIsland(current); }
    if (e.target.id === "lnk-gel") { e.preventDefault(); ensureOn("gelombang"); ensureOn("angin"); flyIsland(current); }
    if (e.target.id === "lnk-setuju") {
      e.preventDefault(); ensureOn("setuju");
      getGeo("persetujuan_masyarakat").then(gj => {
        const fs = gj.features.filter(f => f.properties.pulau === current);
        if (fs.length) map.flyToBounds(L.geoJSON({ type: "FeatureCollection", features: fs }).getBounds(), { padding: [30, 30], duration: .8 });
      });
    }
  });
  selectIsland("LCG", false); showTab("progres", false); map.setView([-5.62, 106.58], 10);

  /* ---------------- Analisis ---------------- */
  const t13 = S.tabel["13"].baris, t11 = S.tabel["11"].baris, t6 = S.tabel["6"].baris, t10 = S.tabel["10"].baris;
  const AP = AN.pulau || {}, sumHa = o => Object.values(o || {}).reduce((x, y) => x + (+y || 0), 0);
  const lrrOf = k => (t11.find(r => r[0] === PULAU[k]) || [])[4];
  const NM_KRIT = { gelombang: "gelombang", substrat: "substrat", jarak_mangrove: "jarak mangrove", garis_pantai: "LRR", salinitas: "salinitas", elevasi: "elevasi" };
  $("#tab-analisis").innerHTML = `
    <h2>Hasil analisis terbaru</h2>
    <p class="cap">Kesesuaian &amp; prioritas ${esc(AN.versi || S.kesesuaian.versi)} · gelombang 4 musim v03 · luas mangrove Sentinel-2 SR ${S.s2sr_tahun[0]}–${S.s2sr_tahun.at(-1)} · garis pantai DSAS 1990–2025.</p>
    <h3>Ringkasan per pulau</h3>
    <div class="dtable-wrap"><table class="dtable"><thead><tr><th>Pulau</th><th>Sesuai S1–S3 = prioritas AHP (ha)</th><th>Disetujui FGD (ha)</th><th>Mangrove 2025 (ha)</th><th>Hs maks (m)</th></tr></thead>
    <tbody>${KODE.map(k => { const a = AP[k] || {}, ks = a.kesesuaian_ha || {}, g = (GL.pulau || {})[k];
      return `<tr><td>${PULAU[k]}</td><td>${fmt((ks.S1 || 0) + (ks.S2 || 0) + (ks.S3 || 0))}</td>
        <td>${SO.persetujuan && SO.persetujuan[k] ? fmt(sumHa(a.prioritas_masyarakat_ha)) : "<span class=muted>–</span>"}</td>
        <td>${fmt(S.luas_digitasi_2025[k])}</td><td>${g ? fmt(g.ekstrem.Hs_maks) : "–"}</td></tr>`; }).join("")}
      <tr><td><b>Total</b></td><td><b>${fmt(AN.total?.sesuai_ha)}</b></td><td><b>${fmt(AN.total?.prioritas_masyarakat_ha)}</b></td>
        <td><b>${fmt(KODE.reduce((x, k) => x + (S.luas_digitasi_2025[k] || 0), 0))}</b></td><td></td></tr></tbody></table></div>
    <p class="cap">Seluruh area S1–S3 masuk prioritas AHP (tinggi/sedang/rendah). "Disetujui FGD" = bagian prioritas yang berada di area setuju ditanami menurut FGD; Hs maks = tinggi gelombang ekstrem pesisir 4 musim (HHWS).</p>
    <h3>Kesesuaian lahan pemulihan (ha)</h3>
    <div class="chartbox" style="height:280px"><canvas id="ch-sesuai"></canvas></div>
    <h3>Prioritas pemulihan: AHP vs disetujui masyarakat (ha)</h3>
    <div class="chartbox" style="height:340px"><canvas id="ch-prior"></canvas></div>
    <p class="cap">Batang pudar = prioritas AHP; batang penuh = bagian yang juga disetujui masyarakat dalam FGD.</p>
    <h3>Data masukan kesesuaian tiap pulau</h3>
    <div class="dtable-wrap"><table class="dtable left"><thead><tr><th>Pulau</th><th>Elevasi</th><th>Titik · RMSE</th><th>Krit.</th><th>Valid.*</th></tr></thead>
    <tbody>${KODE.map(k => { const m = (AP[k] || {}).masukan; if (!m) return "";
      const src = [/DTM/.test(m.sumber_elevasi) && "DTM", /batimetri/.test(m.sumber_elevasi) && "bati", /IDW/.test(m.sumber_elevasi) && "IDW"].filter(Boolean).join("+");
      return `<tr><td>${PULAU[k]}</td><td style="white-space:nowrap">${esc(m.topobati || "–")}<br><small class="muted">${src}</small></td>
        <td style="white-space:nowrap">n ${m.n_titik_kalibrasi} · ${fmt(m.rmse_m, 2)} m${m.r_bati_lapangan != null ? `<br><small class="muted">r ${fmt(m.r_bati_lapangan)}</small>` : ""}</td>
        <td>${m.jumlah_kriteria}${m.tanpa_kriteria.length ? `<br><small class="muted">tanpa ${m.tanpa_kriteria.map(c => ({ gelombang: "gel." })[c] || NM_KRIT[c] || c).join(", ")}</small>` : ""}</td>
        <td>${m.mangrove_S1S2_pct == null ? "<span class=muted>–</span>" : fmt(m.mangrove_S1S2_pct, 0) + " %"}</td></tr>`; }).join("")}</tbody></table></div>
    <p class="cap">Elevasi: versi topo-batimetri · sumber (DTM = DTM LiDAR daratan, bati = batimetri terkoreksi pasut, IDW = interpolasi elevasi dasar lapangan di bawah tajuk). RMSE = galat elevasi setelah koreksi datum; r = korelasi batimetri vs kedalaman lapangan (hanya batimetri baru). Krit. = jumlah kriteria AHP (gel. = gelombang). *Valid. = % sel mangrove eksisting yang jatuh di elevasi S1/S2.</p>
    ${KODE.some(k => ((AP[k] || {}).masukan || {}).struktur_ha != null) ? `<h3>Gelombang, breakwater &amp; jalur kapal dalam analisis</h3>
    <div class="dtable-wrap"><table class="dtable"><thead><tr><th>Pulau</th><th>Hs maks (m)</th><th>Terlindung BW (ha)</th><th>Sesuai di situ (ha)</th><th>Struktur + jalur (ha)</th></tr></thead>
    <tbody>${KODE.map(k => { const m = (AP[k] || {}).masukan || {}, g = (GL.pulau || {})[k];
      return `<tr><td>${PULAU[k]}</td><td>${g ? fmt(g.ekstrem.Hs_maks) : "–"}</td><td>${fmt(m.terlindung_ha)}</td><td>${fmt(m.sesuai_terlindung_ha)}</td><td>${fmt((m.struktur_ha || 0) + (m.jalur_ha || 0))}</td></tr>`; }).join("")}</tbody></table></div>
    <ul class="cap" style="padding-left:16px">${Object.values(AN.metode || {}).map(t => `<li>${esc(t)}</li>`).join("")}</ul>` : ""}
    <p class="muted" style="font-size:.8rem">Kesesuaian ${esc(S.kesesuaian.versi)}: elevasi terhadap zona pasut (MSL lokal; S1 = MLW–MHW, S2 = LLWS–MLW / MHW–HHWS, S3 = batas bawah–LLWS / HHWS–HAT + 0,2; batas bawah mengikuti dasar tempat mangrove eksisting tumbuh, dasar di bawah LLWS paling tinggi S3), batimetri dikoreksi dengan kedalaman terukur di lapangan (c = koreksi datum). AHP 6 kriteria untuk semua pulau: ${S.kesesuaian.bobot.map(b => `${esc(({ elevasi: "elevasi", gelombang: "gelombang Hs", substrat: "substrat", jarak_mangrove: "jarak ke mangrove", garis_pantai: "LRR", salinitas: "salinitas" })[b.kode] || b.kriteria)} ${fmt(b.bobot * 100, 1)} %`).join(", ")} (CR = ${fmt(S.kesesuaian.cr, 3)}). Grid 10 m; 300 m ke laut, 30 m ke darat.</p>
    <h3>Luas mangrove total Kepulauan Seribu</h3>
    <div class="chartbox"><canvas id="ch-total"></canvas></div>
    <p class="muted" style="font-size:.8rem">Sentinel-2 super-resolusi 2,5 m, dipotong AOI tiap pulau (daratan + 150 m ∪ mangrove acuan + 30 m ∪ plot + 30 m). Tahun 2022 tidak tersedia. ${S.s2sr_total.some(r => r.n_pulau < 10) ? `Jumlah pulau terhitung: ${S.s2sr_total.at(-1).n_pulau} dari 10.` : ""}</p>
    <h3>Perubahan luas mangrove per pulau (S2SR ${S.s2sr_tahun[0]}–${S.s2sr_tahun.at(-1)})</h3>
    <div class="chartbox" style="height:240px"><canvas id="ch-tren"></canvas></div>
    <h3>Perubahan garis pantai 1990–2025</h3>
    <div class="chartbox"><canvas id="ch-lrr"></canvas></div>
    <h3>Stok karbon batas bawah (t C/ha)</h3>
    <div class="chartbox"><canvas id="ch-karbon"></canvas></div>
    <div class="note">Batas bawah = individu terukur saja.</div>
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

  const sc = [["S1", KES.S1], ["S2", KES.S2], ["S3", KES.S3]];
  chart("ch-sesuai", { type: "bar", data: { labels: KODE.map(nm), datasets: sc.map(([l, c]) => ({ label: l, data: KODE.map(k => ((AP[k] || {}).kesesuaian_ha || {})[l] || 0), backgroundColor: c })) },
    options: { indexAxis: "y", maintainAspectRatio: false, scales: { x: { stacked: true, title: { display: true, text: "ha" } }, y: { stacked: true } },
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } } } } });

  chart("ch-prior", { type: "bar", data: { labels: KODE.map(nm), datasets: ["Tinggi", "Sedang", "Rendah"].flatMap(c => [
      { label: `${c} – AHP`, data: KODE.map(k => ((AP[k] || {}).prioritas_ahp_ha || {})[c] || 0), backgroundColor: PRIOR[c] + "55", stack: "ahp" },
      { label: `${c} – + FGD`, data: KODE.map(k => ((AP[k] || {}).prioritas_masyarakat_ha || {})[c] || 0), backgroundColor: PRIOR[c], stack: "fgd" }]) },
    options: { indexAxis: "y", maintainAspectRatio: false, scales: { x: { stacked: true, title: { display: true, text: "ha" } }, y: { stacked: true } },
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 10 } } } } } });

  chart("ch-lrr", { type: "bar", data: { labels: t11.map(r => r[0]), datasets: [
      { label: "LRR rerata (m/th)", data: t11.map(r => r[4]), backgroundColor: t11.map(r => r[4] < 0 ? "#ef8a62" : "#67a9cf"), yAxisID: "y" },
      { label: "Transek abrasi (%)", data: t11.map(r => r[6]), type: "line", borderColor: "#b2182b", backgroundColor: "#b2182b", showLine: false, pointRadius: 4, yAxisID: "y2" }] },
    options: { maintainAspectRatio: false, scales: { y: { title: { display: true, text: "m/th" } }, y2: { position: "right", min: 0, max: 100, grid: { drawOnChartArea: false }, title: { display: true, text: "% abrasi" } } },
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } } } } });

  chart("ch-karbon", { type: "bar", data: { labels: t6.map(r => r[0]), datasets: [{ label: "t C/ha", data: t6.map(r => r[1]), backgroundColor: "#1f5f4a" }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } } } });

  /* ---------------- Strategi ---------------- */
  if (ST.versi) {
    const rt = ST.rekap_pulau.TOTAL || {}, ag = ST.anggaran, ie = ST.ifas_efas || {}, rs = ie.ringkasan || {};
    const agRow = nm => (ag.baris.find(r => r[0] === nm) || []);
    const totDasar = agRow("TOTAL ANGGARAN DASAR"), totBers = agRow("Total bersyarat termasuk kontinjensi");
    const tbl = (t, cols) => `<div class="dtable-wrap"><table class="dtable left"><thead><tr>${cols.map(i => `<th>${esc(t.kolom[i])}</th>`).join("")}</tr></thead>
      <tbody>${t.baris.map(r => `<tr>${cols.map(i => `<td>${esc(fmt(r[i]))}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    const ak = ST.arah_kebijakan || { butir: [], teks: [] };
    const tows = ST.tows.baris, grpT = { SO: "Kekuatan–Peluang (SO)", ST: "Kekuatan–Ancaman (ST)", WO: "Kelemahan–Peluang (WO)", WT: "Kelemahan–Ancaman (WT)" };
    $("#tab-strategi").innerHTML = `
      <h2>Strategi &amp; rencana aksi pemulihan</h2>
      <p class="cap">Versi ${esc(ST.versi)} · ${esc(ST.dasar_data)}</p>
      <div class="kpis">
        <div class="kpi"><div class="v">${fmt(rt["Total dasar+pilot (ha)"])} ha</div><div class="l">luas tanam 2027–2030 (dasar + pilot)</div></div>
        <div class="kpi"><div class="v">${fmt(rt["Bibit dasar+pilot (batang)"], 0)}</div><div class="l">bibit (batang, belum termasuk sulaman)</div></div>
        <div class="kpi"><div class="v">${fmtRp(totDasar[6])}</div><div class="l">anggaran dasar 2027–2031 (termasuk kontinjensi)</div></div>
        <div class="kpi"><div class="v">${fmt(rt["Bersyarat (ha)"])} ha</div><div class="l">perluasan guludan bersyarat (${fmtRp(totBers[6])})</div></div>
      </div>
      <p><button class="btn" id="btn-rencana">Tampilkan lokasi rencana aksi di peta</button></p>
      <h3>Arah kebijakan</h3>
      <ul class="lst">${ak.butir.map(t => { const [a, ...b] = t.split(". "); return `<li><b>${esc(a)}.</b> ${esc(b.join(". "))}</li>`; }).join("")}</ul>
      ${ak.teks.slice(1).map(t => `<p style="font-size:.88rem">${esc(t)}</p>`).join("")}
      <h3>Posisi strategi (IFAS–EFAS)</h3>
      <table class="kv"><tr><td>Kekuatan (S) / Kelemahan (W)</td><td>${fmt(rs["Skor Kekuatan (S)"])} / ${fmt(rs["Skor Kelemahan (W)"])}</td></tr>
        <tr><td>Peluang (O) / Ancaman (T)</td><td>${fmt(rs["Skor Peluang (O)"])} / ${fmt(rs["Skor Ancaman (T)"])}</td></tr>
        <tr><td>Sumbu X (S − W) · Y (O − T)</td><td>${fmt(rs["Sumbu X = S − W"])} · ${fmt(rs["Sumbu Y = O − T"])}</td></tr>
        <tr><td><b>Kuadran</b></td><td><b>${esc(rs["Kuadran / arah strategi"])}</b></td></tr></table>
      <details class="exp"><summary>Faktor internal &amp; eksternal (${ie.faktor.length})</summary>
        <table class="kv">${ie.faktor.map(f => `<tr><td><b>${esc(f.kode)}</b> ${esc(f.faktor)}</td><td>${fmt(f.skor)}</td></tr>`).join("")}</table></details>
      <h3>Strategi TOWS</h3>
      ${Object.entries(grpT).map(([g, nm]) => { const r = tows.filter(x => x[1] === g); return r.length ? `<div class="qs"><div class="ql">${nm}</div><ul class="lst">${r.map(x => `<li><b>${esc(x[0])}</b> ${esc(x[2])} <small class="muted">(${esc(x[4])})</small></li>`).join("")}</ul></div>` : ""; }).join("")}
      ${ST.tipologi ? `<h3>Tipologi pulau</h3>${ST.tipologi.baris.map(r => `<div class="qs"><div class="ql">${esc(r[0])} — ${esc(r[1])}</div>
        <p style="font-size:.84rem;margin:2px 0">${esc(r[3])}</p><p class="cap" style="margin:0">${esc(r[2])}</p></div>`).join("")}` : ""}
      <h3>Tahapan pelaksanaan</h3>
      ${ST.tahapan ? `<ul class="lst">${ST.tahapan.butir.map(t => { const [a, ...b] = t.split(": "); return `<li><b>${esc(a)}:</b> ${esc(b.join(": "))}</li>`; }).join("")}</ul>` : ""}
      <div class="chartbox" style="height:300px"><canvas id="ch-tanam"></canvas></div>
      <p class="cap">Luas tanam per pulau per tahun (ha), lokasi dasar + pilot.</p>
      <h3>Teknik penanaman</h3>
      ${tbl(ST.teknik, [0, 1, 2, 3, 5])}
      <h3>Anggaran 2027–2031</h3>
      <div class="chartbox" style="height:280px"><canvas id="ch-anggaran"></canvas></div>
      <p class="cap">Harga satuan indikatif; perlu disesuaikan dengan SSH/HSPK DKI Jakarta tahun anggaran berjalan. Perluasan bersyarat di luar anggaran dasar.</p>
      <h3>Matriks rencana aksi</h3>
      ${ST.matriks.baris.map(r => `<details class="exp"><summary><b>${esc(r[0])}</b> — ${esc(r[1])}</summary><table class="kv">
        ${[[2, "Lokasi"], [3, "2027"], [4, "2028–2029"], [5, "2030–2031"], [6, "Indikator"], [7, "Penanggung jawab"], [8, "Mitra"], [9, "Anggaran"]].map(([i, l]) =>
          `<tr><td>${l}</td><td style="text-align:left">${esc(typeof r[i] === "number" ? fmtRp(r[i]) : fmt(r[i]))}</td></tr>`).join("")}</table></details>`).join("")}
      <h3>Indikator keberhasilan &amp; monev</h3>
      ${tbl(ST.indikator, [1, 2, 3, 4, 5, 6])}
      ${ST.peran ? `<h3>Peran pelaksana</h3><table class="kv">${ST.peran.baris.map(r => `<tr><td><b>${esc(r[0])}</b><br><span class="muted">${esc(r[1])}</span></td><td></td></tr>`).join("")}</table>` : ""}
      ${ST.peta ? `<h3>Peta tahap rencana aksi</h3><a href="${ST.peta}" target="_blank"><img src="${ST.peta}" alt="Peta tahap rencana aksi" style="width:100%;border:1px solid var(--line);border-radius:6px"></a>` : ""}
      ${ST.keterbatasan ? `<h3>Keterbatasan</h3><ul class="lst">${ST.keterbatasan.butir.map(t => `<li>${esc(t)}</li>`).join("")}</ul>` : ""}`;
    $("#tab-strategi").addEventListener("click", e => { if (e.target.id === "btn-rencana") { ensureOn("rencana"); map.setView([-5.62, 106.58], 10); } });
    const thn = [2027, 2028, 2029, 2030];
    chart("ch-tanam", { type: "bar", data: { labels: KODE.map(k => PULAU[k]), datasets: thn.map((y, i) => ({ label: String(y), data: KODE.map(k => (ST.rekap_pulau[k] || {})[`Luas tanam ${y} (ha)`] || 0),
        backgroundColor: ["#b2182b", "#ef8a62", "#f4a582", "#f6c85f"][i] })) },
      options: { indexAxis: "y", maintainAspectRatio: false, scales: { x: { stacked: true, title: { display: true, text: "ha" } }, y: { stacked: true } }, plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } } } } });
    const KEL = [["Penanaman & rangka rumpun", /^(Penanaman|Rangka)/, "#1f5f4a"], ["APO bambu & guludan", /^(APO|Guludan)/, "#c8662b"],
      ["Penyulaman & pemeliharaan", /^(Penyulaman|Pemeliharaan 3)/, "#5aa77f"], ["Kebun bibit", /^Kebun bibit/, "#93c9a5"],
      ["Kelembagaan & perlindungan", /^(Sosialisasi|Perlindungan)/, "#2c7fb8"], ["Data, DED, monitoring & evaluasi", /^(Survei detail|Pelengkapan|Monitoring|Pemetaan|Evaluasi)/, "#8e6c8a"],
      ["Kontinjensi", /^Kontinjensi/, "#bbb"]];
    const seri = KEL.map(([nm, re, c]) => ({ label: nm, backgroundColor: c, stack: "a",
      data: [1, 2, 3, 4, 5].map(i => ag.baris.filter(r => r[0] && re.test(r[0])).reduce((x, r) => x + (r[i] || 0), 0) / 1e9) }));
    chart("ch-anggaran", { type: "bar", data: { labels: ["2027", "2028", "2029", "2030", "2031"], datasets: seri },
      options: { maintainAspectRatio: false, scales: { x: { stacked: true }, y: { stacked: true, title: { display: true, text: "miliar Rp" } } },
        plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 10 } } }, tooltip: { callbacks: { label: c => `${c.dataset.label}: Rp ${fmt(c.raw, 2)} M` } } } } });
  } else { $("#tab-strategi").innerHTML = `<h2>Strategi &amp; rencana aksi</h2><div class="note">Belum tersedia.</div>`; }

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
      <tr><td>Kesesuaian &amp; prioritas (AHP, elevasi berdatum pasut)</td><td>${S.kesesuaian.versi}</td></tr>
    </table>
    <p class="muted" style="font-size:.85rem">Semua lapisan ditampilkan dalam WGS84; sumber asli dalam UTM 48S (EPSG:32748). Geometri disederhanakan (toleransi 0,5–4 m) untuk tampilan web, sehingga luas di peta bisa sedikit berbeda dari tabel.</p>
    <h3>Unduh data</h3>
    <p style="font-size:.88rem">${["mangrove_eksisting", "plot_vegetasi", "titik_kualitas_air", "sumur_air_tanah", "foto_lai", "transek_garis_pantai", "kesesuaian_ahp", "prioritas_masyarakat", "angin", "gelombang_DJF", "struktur_pantai", "jalur_kapal", "rencana_aksi", "lokasi_prioritas", "persetujuan_masyarakat", `mangrove_s2sr_${S.s2sr_tahun.at(-1)}`]
      .map(f => `<a href="data/${f}.geojson" download>${f}.geojson</a>`).join(" · ")}</p>
    <p class="muted" style="font-size:.8rem">Data dibangun: ${esc(S.dibangun)}</p>`;
})();
