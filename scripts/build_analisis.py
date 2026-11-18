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
    prio = gpd.read_file(AN / f"09_Lokasi_Prioritas/MGV-KS_LokasiPrioritas_KS_{V}.gpkg", layer="lokasi_prioritas").to_crs(UTM)
    tulis(prio[["id_lokasi", "pulau", "prioritas", "luas_ha", "skor_rerata", "elevasi_median_m", "lintang", "bujur", "geometry"]]
          .assign(geometry=lambda d: d.geometry.simplify(1, preserve_topology=True)), "lokasi_prioritas")
    fgd = gpd.read_file(OUT / "persetujuan_masyarakat.geojson").to_crs(UTM)
    setuju = fgd[fgd.status == "Setuju"]
    parts = []
    for k in PULAU:
        p, s = prio[prio.pulau == k], setuju[setuju.pulau == k]
        if not len(p) or not len(s):
            continue
        x = gpd.overlay(p[["id_lokasi", "pulau", "prioritas", "skor_rerata", "geometry"]], s[["id", "geometry"]].rename(columns={"id": "id_fgd"}),
                        how="intersection", keep_geom_type=True)
        x = x.dissolve(["id_lokasi", "pulau", "prioritas", "skor_rerata"], as_index=False, aggfunc={"id_fgd": lambda v: ", ".join(sorted(set(v)))})
        parts.append(x)
    pm = pd.concat(parts, ignore_index=True) if parts else gpd.GeoDataFrame(columns=["id_lokasi", "pulau", "prioritas", "geometry"], crs=UTM)
    pm = gpd.GeoDataFrame(pm, crs=UTM)
    pm["luas_ha"] = (pm.area / 1e4).round(3)
    pm = pm[pm.luas_ha >= 0.01].copy()
    pm["_u"] = pm.prioritas.map({"Tinggi": 1, "Sedang": 2, "Rendah": 3})
    pm = pm.sort_values(["pulau", "_u", "luas_ha"], ascending=[True, True, False]).drop(columns="_u").reset_index(drop=True)
    pm["id"] = pm.groupby("pulau").cumcount().add(1).map("{:02d}".format).radd(pm.pulau + "-P")
    ll = pm.representative_point().to_crs(4326)
    pm["lintang"], pm["bujur"] = ll.y.round(6), ll.x.round(6)
    tulis(pm[["id", "pulau", "prioritas", "luas_ha", "skor_rerata", "id_lokasi", "id_fgd", "lintang", "bujur", "geometry"]], "prioritas_masyarakat")

    # (3) ringkasan per pulau
    lk = pd.read_excel(AN / f"08_Kesesuaian_Pemulihan/MGV-KS_Kesesuaian_KS_{V}.xlsx", sheet_name="LUAS_KELAS")
    lk = lk.set_index(lk.columns[0])
    an = {"versi": V, "pulau": {}, "dibangun": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
    for k in PULAU:
        d = {}
        if k in lk.index:
            r = lk.loc[k]
            d["kesesuaian_ha"] = {c: round(float(r[c]), 2) for c in ["S1", "S2", "S3", "N"]}
            d["prioritas_ahp_ha"] = {c: round(float(r[f"Prioritas {c}"]), 2) for c in ["Tinggi", "Sedang", "Rendah"]}
        sub = pm[pm.pulau == k]
        d["prioritas_masyarakat_ha"] = {c: round(float(sub[sub.prioritas == c].luas_ha.sum()), 2) for c in ["Tinggi", "Sedang", "Rendah"]}
        sf = setuju[setuju.pulau == k]
        if len(sf):
            ks = kes[kes.pulau == k]
            d["setuju_tidak_sesuai_ha"] = round(float((sf.union_all().area - sf.union_all().intersection(ks.union_all()).area) / 1e4), 2) if len(ks) else round(float(sf.area.sum() / 1e4), 2)
        an["pulau"][k] = d
    an["total"] = {
        "sesuai_ha": round(float(lk[["S1", "S2", "S3"]].sum().sum()), 2),
        "prioritas_ahp_ha": round(float(lk[["Prioritas Tinggi", "Prioritas Sedang", "Prioritas Rendah"]].sum().sum()), 2),
        "prioritas_masyarakat_ha": round(float(pm.luas_ha.sum()), 2)}
    (OUT / "analisis.json").write_text(json.dumps(an, ensure_ascii=False, indent=1), encoding="utf-8")
    print("total", an["total"])

    # (4) statistik.json: Tabel 13/14, ringkasan, blok kesesuaian
    fs = OUT / "statistik.json"
    st = json.loads(fs.read_text(encoding="utf-8"))
    t13 = st["tabel"]["13"]
    t13["baris"] = [[PULAU[k], *[round(float(r[c]), 2) for c in ["S1", "S2", "S3", "N", "Mangrove eksisting", "Prioritas Tinggi", "Prioritas Sedang", "Prioritas Rendah"]],
                     r.sumber_elevasi] for k, r in lk.iterrows()]
    t13["catatan"] = [f"Sumber: Analisis kesesuaian multikriteria MGV-KS 2026 {V} (grid 10 m; 300 m ke laut, 30 m ke darat)",
                      "Catatan: S1 sangat sesuai, S2 sesuai, S3 sesuai bersyarat, N tidak sesuai. Elevasi terhadap MSL pasut lokal; "
                      "S1 = MLW–MHW, S2 = LLWS–MLW atau MHW–HHWS, S3 = HHWS–(HAT + 0,2); dasar di bawah LLWS = N."]
    pt = prio[prio.prioritas == "Tinggi"].sort_values("id_lokasi")
    st["tabel"]["14"]["baris"] = [[r.id_lokasi, PULAU[r.pulau], round(float(r.luas_ha), 2), round(float(r.skor_rerata), 4), round(float(r.x_utm), 1),
                                   round(float(r.y_utm), 1), round(float(r.lintang), 4), round(float(r.bujur), 4)] for _, r in pt.iterrows()]
    st["tabel"]["14"]["catatan"] = [f"Sumber: Analisis kesesuaian & prioritas MGV-KS 2026 {V}",
                                    "Catatan: Koordinat titik tengah poligon; WGS 1984 UTM Zona 48S dan geografis."]
    for k, r in lk.iterrows():
        if k in st["ringkasan"]:
            g = st["ringkasan"][k]
            for c in ["S1", "S2", "S3", "N"]:
                g[f"{c} (ha)"] = round(float(r[c]), 2)
            for c in ["Tinggi", "Sedang", "Rendah"]:
                g[f"Prioritas {c} (ha)"] = round(float(r[f"Prioritas {c}"]), 2)
            g["Elevasi dari"] = r.sumber_elevasi
            g["Jumlah lokasi prioritas tinggi"] = int((pt.pulau == k).sum())
    st["kesesuaian"]["versi"] = V
    fs.write_text(json.dumps(st, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
