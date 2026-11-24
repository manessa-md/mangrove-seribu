"""Lapisan analisis WebGIS MGV-KS: (1) kesesuaian AHP, (2) prioritas pemulihan = prioritas AHP ∩ area disetujui masyarakat.

Pakai:  python scripts/build_analisis.py <folder_Mangrove>
Dipanggil di akhir build_data.py (setelah build_sosek.py). Versi kesesuaian = versi tertinggi
MGV-KS_Kesesuaian_KS_v*.xlsx di 04_PENGOLAHAN_ANALISIS/08_Kesesuaian_Pemulihan.

Sumber:
  08_Kesesuaian_Pemulihan/MGV-KS_Kesesuaian_<KODE>_vNN.tif   (1 S1, 2 S2, 3 S3, 4 N, 5 mangrove eksisting, 6 permukiman)
  08_Kesesuaian_Pemulihan/MGV-KS_Kesesuaian_KS_vNN.xlsx      (LUAS_KELAS, BOBOT_AHP, ZONA_PASUT_ELEVASI)
  09_Lokasi_Prioritas/MGV-KS_LokasiPrioritas_KS_vNN.gpkg      (poligon prioritas AHP: Tinggi/Sedang/Rendah)
  data/persetujuan_masyarakat.geojson                          (hasil build_sosek.py; status Setuju/Tidak setuju)
Keluaran:
  data/kesesuaian_ahp.geojson, data/prioritas_masyarakat.geojson, data/lokasi_prioritas.geojson,
  data/analisis.json; memperbarui Tabel 13, 14, ringkasan & blok "kesesuaian" di data/statistik.json.
"""
import json, re, sys, datetime
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio import features
from shapely.geometry import shape

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/Mangrove")
OUT = Path(__file__).resolve().parent.parent / "data"
AN = SRC / "04_PENGOLAHAN_ANALISIS"
UTM = 32748
PULAU = {"UTJ": "Untung Jawa", "PAR": "Pari", "LCG": "Lancang", "TDG": "Tidung", "PRM": "Pramuka", "PGG": "Panggang",
         "KLP": "Kelapa", "KLD": "Kelapa Dua", "HRP": "Harapan", "SBR": "Sebira"}
KELAS = {1: "S1", 2: "S2", 3: "S3"}


def versi_terbaru():
    v = [int(m.group(1)) for f in (AN / "08_Kesesuaian_Pemulihan").glob("MGV-KS_Kesesuaian_KS_v*.xlsx")
         if (m := re.search(r"_v(\d+)\.xlsx$", f.name))]
    return f"v{max(v):02d}"


KELAS_P = ["Tinggi", "Sedang", "Rendah", "Rekayasa"]   # Rekayasa (v07+): S3 di bawah LLWS, perlu guludan


def prioritas_terbaru(an_dir=None):
    """Poligon prioritas versi tertinggi (09_Lokasi_Prioritas/MGV-KS_LokasiPrioritas_KS_vNN.gpkg).
    Versi prioritas berjalan sendiri (v08 dibangun dari kesesuaian v07). Nama layer: lokasi_prioritas[_vNN]."""
    import pyogrio
    d = Path(an_dir or AN) / "09_Lokasi_Prioritas"
    v, f = max((int(m.group(1)), f) for f in d.glob("MGV-KS_LokasiPrioritas_KS_v*.gpkg") if (m := re.search(r"_v(\d+)\.gpkg$", f.name)))
    lyr = next(n for n, _ in pyogrio.list_layers(f) if str(n).startswith("lokasi_prioritas"))
    g = gpd.read_file(f, layer=lyr).to_crs(UTM)
    c = g.representative_point()
    if "x_utm" not in g.columns:
        g["x_utm"], g["y_utm"] = c.x.round(1), c.y.round(1)
    if "lintang" not in g.columns:
        ll = c.to_crs(4326); g["lintang"], g["bujur"] = ll.y.round(6), ll.x.round(6)
    return f"v{v:02d}", g


def tulis(gdf, name, precision=6):
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].to_crs(4326)
    feats = []
    for _, r in gdf.iterrows():
        props = {k: (None if (isinstance(v, float) and np.isnan(v)) else (round(v, 4) if isinstance(v, float) else v))
                 for k, v in r.items() if k != "geometry"}
        feats.append({"type": "Feature", "properties": props,
                      "geometry": json.loads(gpd.GeoSeries([r.geometry]).to_json())["features"][0]["geometry"]})
    txt = json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, separators=(",", ":"))
    txt = re.sub(r"(-?\d+\.\d{%d})\d+" % precision, r"\1", txt)
    (OUT / f"{name}.geojson").write_text(txt, encoding="utf-8")
    print(f"{name}: {len(feats)} fitur, {len(txt) / 1e3:.0f} kB")


def main():
    V = versi_terbaru()
    print("kesesuaian versi", V)
    # (1) kesesuaian AHP — poligon S1/S2/S3 per pulau
    rows = []
    for k in PULAU:
        f = AN / f"08_Kesesuaian_Pemulihan/MGV-KS_Kesesuaian_{k}_{V}.tif"
        if not f.exists():
            continue
        with rasterio.open(f) as r:
            a = r.read(1); T = r.transform
        for g, v in features.shapes(a, mask=np.isin(a, list(KELAS)), transform=T):
            rows.append({"pulau": k, "kelas": KELAS[int(v)], "geometry": shape(g)})
    kes = gpd.GeoDataFrame(rows, crs=UTM).dissolve(["pulau", "kelas"]).reset_index()
    kes["luas_ha"] = (kes.area / 1e4).round(2)
    kes["geometry"] = kes.geometry.simplify(2, preserve_topology=True)
    tulis(kes, "kesesuaian_ahp")

    # (2) prioritas AHP & prioritas ∩ setuju masyarakat
    PV, prio = prioritas_terbaru()
    print("prioritas versi", PV, "|", prio.groupby("prioritas").luas_ha.sum().round(2).to_dict())
    kol = [c for c in ["id_lokasi", "pulau", "prioritas", "luas_ha", "skor_rerata", "elevasi_median_m", "LRR_min_m_th", "jarak_permukiman_min_m",
                       "pct_S1", "pct_S2", "pct_S3", "lintang", "bujur"] if c in prio.columns]
    tulis(prio[kol + ["geometry"]].assign(geometry=lambda d: d.geometry.simplify(1, preserve_topology=True)), "lokasi_prioritas")
    kp = ["id_lokasi", "pulau", "prioritas"] + (["skor_rerata"] if "skor_rerata" in prio.columns else [])
    fgd = gpd.read_file(OUT / "persetujuan_masyarakat.geojson").to_crs(UTM)
    setuju = fgd[fgd.status == "Setuju"]
    parts = []
    for k in PULAU:
        p, s = prio[prio.pulau == k], setuju[setuju.pulau == k]
        if not len(p) or not len(s):
            continue
        x = gpd.overlay(p[kp + ["geometry"]], s[["id", "geometry"]].rename(columns={"id": "id_fgd"}),
                        how="intersection", keep_geom_type=True)
        x = x.dissolve(kp, as_index=False, aggfunc={"id_fgd": lambda v: ", ".join(sorted(set(v)))})
        parts.append(x)
    pm = pd.concat(parts, ignore_index=True) if parts else gpd.GeoDataFrame(columns=["id_lokasi", "pulau", "prioritas", "geometry"], crs=UTM)
    pm = gpd.GeoDataFrame(pm, crs=UTM)
    pm["luas_ha"] = (pm.area / 1e4).round(3)
    pm = pm[pm.luas_ha >= 0.01].copy()
    pm["_u"] = pm.prioritas.map({c: i for i, c in enumerate(KELAS_P)})
    pm = pm.sort_values(["pulau", "_u", "luas_ha"], ascending=[True, True, False]).drop(columns="_u").reset_index(drop=True)
    pm["id"] = pm.groupby("pulau").cumcount().add(1).map("{:02d}".format).radd(pm.pulau + "-P")
    ll = pm.representative_point().to_crs(4326)
    pm["lintang"], pm["bujur"] = ll.y.round(6), ll.x.round(6)
    tulis(pm[[c for c in ["id", "pulau", "prioritas", "luas_ha", "skor_rerata", "id_lokasi", "id_fgd", "lintang", "bujur"] if c in pm.columns] + ["geometry"]],
          "prioritas_masyarakat")
    kelas_p = [c for c in KELAS_P if (prio.prioritas == c).any()]

    # (3) ringkasan per pulau
    lk = pd.read_excel(AN / f"08_Kesesuaian_Pemulihan/MGV-KS_Kesesuaian_KS_{V}.xlsx", sheet_name="LUAS_KELAS")
    lk = lk.set_index(lk.columns[0])
    an = {"versi": V, "versi_prioritas": PV, "kelas_prioritas": kelas_p, "pulau": {}, "dibangun": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
    for k in PULAU:
        d = {}
        if k in lk.index:
            r = lk.loc[k]
            d["kesesuaian_ha"] = {c: round(float(r[c]), 2) for c in ["S1", "S2", "S3", "N"]}
        pp = prio[prio.pulau == k]
        d["prioritas_ahp_ha"] = {c: round(float(pp[pp.prioritas == c].luas_ha.sum()), 2) for c in kelas_p}
        sub = pm[pm.pulau == k]
        d["prioritas_masyarakat_ha"] = {c: round(float(sub[sub.prioritas == c].luas_ha.sum()), 2) for c in kelas_p}
        sf = setuju[setuju.pulau == k]
        if len(sf):
            ks = kes[kes.pulau == k]
            d["setuju_tidak_sesuai_ha"] = round(float((sf.union_all().area - sf.union_all().intersection(ks.union_all()).area) / 1e4), 2) if len(ks) else round(float(sf.area.sum() / 1e4), 2)
        an["pulau"][k] = d
    # (3b) data masukan yang dipakai tiap pulau (dibaca dari buku kerja kesesuaian versi terbaru)
    X = AN / f"08_Kesesuaian_Pemulihan/MGV-KS_Kesesuaian_KS_{V}.xlsx"
    lk2 = pd.read_excel(X, sheet_name="LUAS_KELAS").set_index("pulau")
    dt = pd.read_excel(X, sheet_name="DATUM_BATIMETRI").set_index("pulau")
    vm = pd.read_excel(X, sheet_name="VALIDASI_MANGROVE_EKSISTING").set_index("pulau")
    xs = pd.ExcelFile(X).sheet_names
    gs = pd.read_excel(X, sheet_name="GELOMBANG_STRUKTUR_JALUR").set_index("pulau") if "GELOMBANG_STRUKTUR_JALUR" in xs else None
    met = pd.read_excel(X, sheet_name=next(n for n in xs if n.startswith("METODE")))
    an["metode"] = {r.butir: r.uraian for r in met.itertuples() if str(r.butir).endswith(f"({V})")}
    num = lambda v, d=3: None if pd.isna(v) else round(float(v), d)
    for k in PULAU:
        if k not in lk2.index:
            continue
        r = lk2.loc[k]; m = {}
        krit = [c.strip() for c in str(r.kriteria_dipakai).split(",")]
        m["stasiun_pasut"] = r.stasiun_pasut
        m["jumlah_kriteria"] = len(krit)
        m["tanpa_kriteria"] = [c for c in ["elevasi", "gelombang", "substrat", "jarak_mangrove", "garis_pantai", "salinitas"] if c not in krit]
        m["sumber_elevasi"] = r.sumber_elevasi
        m["cakupan_elevasi_pct"] = num(r["cakupan_elevasi_zona_%"], 1)
        m["tanpa_data_ha"] = num(r["Tanpa data (zona tak terklasifikasi)"], 2)
        if k in dt.index:
            d = dt.loc[k]
            m["topobati"] = re.search(r"_(v\d+)\.tif$", str(d.berkas_keluaran)).group(1) if re.search(r"_(v\d+)\.tif$", str(d.berkas_keluaran)) else None
            m["n_titik_kalibrasi"] = int(d.n_titik_kalibrasi); m["koreksi_c_m"] = num(d.koreksi_datum_c_m)
            m["rmse_m"] = num(d.RMSE_setelah_koreksi_m); m["r_bati_lapangan"] = num(d.get("r_bati_lapangan"), 2)
        if k in vm.index:
            v = vm.loc[k]
            m["mangrove_sel"] = int(v.sel_mangrove_eksisting_10m)
            m["mangrove_S1S2_pct"] = None if pd.isna(v.iloc[3]) else round(float(v.iloc[3]) + float(v.iloc[4]), 1)
        if gs is not None and k in gs.index:
            g = gs.loc[k]
            m["struktur_ha"] = num(g["struktur pantai (ha)"], 2); m["jalur_ha"] = num(g["jalur kapal ≤ 25 m (ha)"], 2)
            m["terlindung_ha"] = num(g["zona terlindung breakwater (ha)"], 2); m["sesuai_terlindung_ha"] = num(g["sesuai S1–S3 di zona terlindung (ha)"], 2)
        an["pulau"][k]["masukan"] = m
    an["total"] = {
        "sesuai_ha": round(float(lk[["S1", "S2", "S3"]].sum().sum()), 2),
        "prioritas_ahp_ha": round(float(prio.luas_ha.sum()), 2),
        "prioritas_masyarakat_ha": round(float(pm.luas_ha.sum()), 2)}
    (OUT / "analisis.json").write_text(json.dumps(an, ensure_ascii=False, indent=1), encoding="utf-8")
    print("total", an["total"])

    # (4) statistik.json: Tabel 13/14, ringkasan, blok kesesuaian
    fs = OUT / "statistik.json"
    st = json.loads(fs.read_text(encoding="utf-8"))
    t13 = st["tabel"]["13"]
    t13["kolom"] = ["Pulau", "S1 (ha)", "S2 (ha)", "S3 (ha)", "N (ha)", "Mangrove eksisting (ha)", *[f"Prioritas {c.lower()} (ha)" for c in kelas_p], "Sumber elevasi"]
    pl = lambda k, c: round(float(prio[(prio.pulau == k) & (prio.prioritas == c)].luas_ha.sum()), 2)
    t13["baris"] = [[PULAU[k], *[round(float(r[c]), 2) for c in ["S1", "S2", "S3", "N", "Mangrove eksisting"]], *[pl(k, c) for c in kelas_p],
                     r.sumber_elevasi] for k, r in lk.iterrows()]
    t13["catatan"] = [f"Sumber: Analisis kesesuaian multikriteria MGV-KS 2026 {V}, lokasi prioritas {PV} (grid 10 m; 300 m ke laut, 30 m ke darat)",
                      "Catatan: S1 sangat sesuai, S2 sesuai, S3 sesuai bersyarat, N tidak sesuai. Elevasi terhadap MSL pasut lokal; "
                      "S1 = MLW–MHW, S2 = LLWS–MLW atau MHW–HHWS, S3 = batas bawah–LLWS atau HHWS–(HAT + 0,2); batas bawah per pulau = min(LLWS, P05 elevasi "
                      "mangrove eksisting), tidak lebih dalam dari LAT − 0,2; dasar di bawah LLWS paling tinggi S3."]
    if gs is not None:
        t13["catatan"].append("v06: gelombang dari model 4 musim v03 (Hs maks, HHWS, diredam breakwater); sel ≤ 25 m dari jalur kapal dan ≤ 5 m dari struktur pantai dikeluarkan dari kesesuaian.")
    pt = prio[prio.prioritas == "Tinggi"].sort_values("id_lokasi")
    ks_ = "skor_rerata" if "skor_rerata" in pt.columns else "elevasi_median_m"   # v07+: skor tidak lagi ada di poligon
    st["tabel"]["14"]["kolom"] = ["ID lokasi", "Pulau", "Luas (ha)", "Skor rerata" if ks_ == "skor_rerata" else "Elevasi median (m MSL)",
                                  "X (UTM 48S)", "Y (UTM 48S)", "Lintang", "Bujur"]
    st["tabel"]["14"]["baris"] = [[r.id_lokasi, PULAU[r.pulau], round(float(r.luas_ha), 2), None if pd.isna(r[ks_]) else round(float(r[ks_]), 3), round(float(r.x_utm), 1),
                                   round(float(r.y_utm), 1), round(float(r.lintang), 4), round(float(r.bujur), 4)] for _, r in pt.iterrows()]
    st["tabel"]["14"]["catatan"] = [f"Sumber: Analisis kesesuaian MGV-KS 2026 {V} & lokasi prioritas {PV}",
                                    "Catatan: Koordinat titik tengah poligon; WGS 1984 UTM Zona 48S dan geografis."]
    for k, r in lk.iterrows():
        if k in st["ringkasan"]:
            g = st["ringkasan"][k]
            for c in ["S1", "S2", "S3", "N"]:
                g[f"{c} (ha)"] = round(float(r[c]), 2)
            for c in kelas_p:
                g[f"Prioritas {c} (ha)"] = pl(k, c)
            g["Elevasi dari"] = r.sumber_elevasi
            g["Jumlah lokasi prioritas tinggi"] = int((pt.pulau == k).sum())
    st["kesesuaian"]["versi"] = V
    st["kesesuaian"]["versi_prioritas"] = PV
    bb = pd.read_excel(X, sheet_name="BOBOT_AHP")
    st["kesesuaian"]["bobot"] = [{"kode": r.iloc[0], "kriteria": r.kriteria, "bobot": round(float(r.bobot), 3)} for _, r in bb.iterrows()]
    st["kesesuaian"]["cr"] = round(float(bb.CR.iloc[0]), 3)
    fs.write_text(json.dumps(st, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
