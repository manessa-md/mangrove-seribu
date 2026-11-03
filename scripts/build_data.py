"""Bangun data web (GeoJSON WGS84 + JSON statistik) untuk WebGIS MGV-KS.

Pakai:  python scripts/build_data.py <folder_Mangrove>
Sumber utama: 03_DATABASE_MANGROVE/05_Basis_Data_Spasial (*.gpkg) dan
04_PENGOLAHAN_ANALISIS (*.xlsx, versi v03).
"""
import json, sys, math, datetime
from pathlib import Path
import geopandas as gpd
import pandas as pd
import openpyxl

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/Mangrove")
OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)
DB = SRC / "03_DATABASE_MANGROVE/05_Basis_Data_Spasial"
AN = SRC / "04_PENGOLAHAN_ANALISIS"
GPKG = DB / "MGV-KS_HasilAnalisis_KS_v03.gpkg"
S2 = DB / "MGV-KS_SebaranMangroveS2SR_KS_2019-2026_v01.gpkg"

PULAU = {
    "UTJ": "Untung Jawa", "PAR": "Pari", "LCG": "Lancang", "TDG": "Tidung",
    "PRM": "Pramuka", "PGG": "Panggang", "KLP": "Kelapa", "KLD": "Kelapa Dua",
    "HRP": "Harapan", "SBR": "Sebira",
}
NAME2CODE = {v: k for k, v in PULAU.items()}
NAME2CODE["Sabira"] = "SBR"


def clean(v):
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return round(v, 4)
    if isinstance(v, (pd.Timestamp, datetime.date, datetime.datetime)):
        return str(v)[:10]
    if hasattr(v, "item"):
        return clean(v.item())
    return v


def write_geo(gdf, name, simplify_m=None, keep=None, precision=6):
    gdf = gdf.copy()
    if simplify_m:
        gdf["geometry"] = gdf.geometry.simplify(simplify_m, preserve_topology=True)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
    gdf = gdf.to_crs(4326)
    if keep:
        gdf = gdf[[c for c in keep if c in gdf.columns] + ["geometry"]]
    feats = []
    for _, r in gdf.iterrows():
        props = {k: clean(r[k]) for k in gdf.columns if k != "geometry"}
        geom = json.loads(gpd.GeoSeries([r.geometry]).to_json())["features"][0]["geometry"]
        feats.append({"type": "Feature", "properties": props, "geometry": geom})
    fc = {"type": "FeatureCollection", "features": feats}
    txt = json.dumps(fc, ensure_ascii=False, separators=(",", ":"))
    # potong presisi koordinat
    import re
    txt = re.sub(r"(-?\d+\.\d{%d})\d+" % precision, r"\1", txt)
    (OUT / f"{name}.geojson").write_text(txt, encoding="utf-8")
    print(f"{name}: {len(feats)} fitur, {len(txt)/1e3:.0f} kB")


def code_of(p):
    p = str(p)
    return p.split("_")[0] if "_" in p else p


# ---------- Layer spasial ----------
L = lambda n: gpd.read_file(GPKG, layer=n)

write_geo(L("daratan_2025"), "daratan_2025", simplify_m=2)
write_geo(L("mangrove_eksisting"), "mangrove_eksisting", simplify_m=0.5)
sms = L("sebaran_mangrove_sumber")
write_geo(sms[sms.sumber.str.startswith("Landsat")], "mangrove_landsat2025", simplify_m=1)
write_geo(sms[sms.sumber.str.startswith("RBI")], "mangrove_rbi2022", simplify_m=1)

pv = L("plot_vegetasi")
write_geo(pv, "plot_vegetasi")
write_geo(L("titik_kualitas_air"), "titik_kualitas_air",
          keep=["kode_titik", "kode_pulau", "pulau", "tanggal", "keterangan", "substrat",
                "kedalaman_cm", "suhu_c", "ph", "salinitas_ppt", "do_mg_l", "tds_ppt",
                "ec_ms_cm", "elevasi_m"])
write_geo(L("sumur_air_tanah"), "sumur_air_tanah",
          keep=["kode_sumur", "kode_pulau", "pulau", "tanggal", "kedalaman_cm", "suhu_c", "ph",
                "salinitas_ppt", "do_mg_l", "tds_ppt", "ec_ms_cm", "kelas_salinitas"])
write_geo(L("foto_hemispherical_lai"), "foto_lai",
          keep=["pulau", "id_titik", "Tanggal", "ID_Transek", "Spesies", "LAI_Ring4",
                "Canopy_Openness_pct", "tutupan_kanopi_pct", "kode_plot"])
write_geo(L("transek_garis_pantai"), "transek_garis_pantai",
          keep=["pulau", "id_transek", "n_tahun", "NSM_m", "EPR_m_th", "LRR_m_th", "LRR_R2", "kelas_LRR"])
gp = L("garis_pantai_tahunan")
write_geo(gp, "garis_pantai_tahunan", simplify_m=3)
write_geo(L("lokasi_prioritas"), "lokasi_prioritas", simplify_m=1,
          keep=["id_lokasi", "pulau", "prioritas", "luas_ha", "skor_rerata", "lintang", "bujur"])
kb = L("kontur_batimetri_gabungan")
kb = kb[(kb.elevasi_m % 1 == 0)]  # kontur tiap 1 m saja untuk web
write_geo(kb, "kontur_batimetri", simplify_m=4, precision=5)

# Sebaran mangrove Sentinel-2 SR per tahun
s2 = pd.concat([gpd.read_file(S2, layer=f"mangrove_{y}") for y in (2019, 2021, 2023, 2025, 2026)])
s2 = gpd.GeoDataFrame(s2, crs="EPSG:32748")
s2["kode"] = s2.pulau.map(code_of)
for y, g in s2.groupby("tahun"):
    write_geo(g, f"mangrove_s2sr_{y}", simplify_m=2, keep=["kode", "kelas", "tahun", "luas_ha"])

# ---------- Statistik / tabel ----------
def sheet_rows(path, sheet, header_row=1):
    ws = openpyxl.load_workbook(path, data_only=True)[sheet]
    rows = list(ws.iter_rows(values_only=True))
    hdr = rows[header_row - 1]
    return [dict(zip(hdr, [clean(v) for v in r])) for r in rows[header_row:] if any(v is not None for v in r)]


def report_table(n):
    ws = openpyxl.load_workbook(AN / "16_Bahan_Laporan/MGV-KS_TabelLaporan_KS_v03.xlsx", data_only=True)[f"Tabel {n}"]
    rows = [[clean(v) for v in r] for r in ws.iter_rows(values_only=True)]
    title = rows[0][0]
    hdr = rows[2]
    body, notes = [], []
    for r in rows[3:]:
        if r[0] and isinstance(r[0], str) and (r[0].startswith("Sumber") or r[0].startswith("Catatan")) and all(v is None for v in r[1:]):
            notes.append(r[0])
        elif any(v is not None for v in r):
            body.append(r[: len(hdr)])
    return {"judul": title, "kolom": hdr, "baris": body, "catatan": notes}


stats = {}
stats["tabel"] = {str(n): report_table(n) for n in range(1, 16)}

# Ringkasan per pulau (lembar RINGKASAN_PULAU, berorientasi baris=indikator)
ws = openpyxl.load_workbook(AN / "15_Ringkasan_Per_Pulau/MGV-KS_Ringkasan_KS_v03.xlsx", data_only=True)
rp = [[clean(v) for v in r] for r in ws["RINGKASAN_PULAU"].iter_rows(values_only=True)]
codes = rp[0][1:]
ring = {c: {} for c in codes if c}
for r in rp[1:]:
    if not r[0]:
        continue
    for c, v in zip(codes, r[1:]):
        if c:
            ring[c][r[0]] = v
stats["ringkasan"] = ring
stats["catatan_mutu"] = [r[0] for r in ws["CATATAN_MUTU_DATA"].iter_rows(min_row=2, values_only=True) if r[0]]
stats["kelengkapan"] = sheet_rows(AN / "15_Ringkasan_Per_Pulau/MGV-KS_Ringkasan_KS_v03.xlsx", "KELENGKAPAN_DATA")

# Seri luas Landsat tahunan
lt = sheet_rows(AN / "07_Perubahan_Tutupan/MGV-KS_PerubahanTutupan_KS_v03.xlsx", "LUAS_TAHUNAN")
series = {}
for r in lt:
    series.setdefault(r["kode_pulau"], []).append([r["tahun"], round(r["luas_ha"], 3)])
stats["landsat_tahunan"] = series
stats["landsat_tren"] = sheet_rows(AN / "07_Perubahan_Tutupan/MGV-KS_PerubahanTutupan_KS_v03.xlsx", "TREN")

s2x = AN / "07_Perubahan_Tutupan/MGV-KS_AnalisisS2SR_KS_v01.xlsx"
stats["s2sr_ringkasan"] = sheet_rows(s2x, "RINGKASAN_PULAU")
stats["s2sr_total"] = sheet_rows(s2x, "TOTAL_KS")
stats["s2sr_catatan"] = [r["catatan"] for r in sheet_rows(s2x, "CATATAN")]
s2c = pd.read_csv(AN / "07_Perubahan_Tutupan/MGV-KS_LuasMangroveS2SR_KS_2019-2026_v01.csv")
s2c["kode"] = s2c.pulau.map(code_of)
stats["s2sr_tahunan"] = {k: g[["tahun", "luas_mangrove_ha", "jarang_ha", "sedang_ha", "lebat_ha"]].round(3).values.tolist()
                         for k, g in s2c.groupby("kode")}
stats["gelombang"] = sheet_rows(AN / "13_Oseanografi_Fisik/MGV-KS_KriteriaFisik_KS_v03.xlsx", "GELOMBANG")
stats["pulau"] = PULAU

# Titik pusat pulau dari daratan
d = L("daratan_2025")
d["kode"] = d.pulau
c = d[d.kode.isin(PULAU)].dissolve("kode").to_crs(4326)
stats["pusat"] = {k: [round(g.centroid.y, 5), round(g.centroid.x, 5)] for k, g in zip(c.index, c.geometry)}
# Panggang/Kelapa dst. tidak semua punya poligon daratan → pakai plot/titik
pts = pd.concat([pv.to_crs(4326)[["pulau", "geometry"]], L("titik_kualitas_air").to_crs(4326)[["kode_pulau", "geometry"]].rename(columns={"kode_pulau": "pulau"})])
for k in PULAU:
    if k not in stats["pusat"]:
        sub = pts[pts.pulau == k]
        if len(sub):
            stats["pusat"][k] = [round(sub.geometry.y.mean(), 5), round(sub.geometry.x.mean(), 5)]

stats["dibangun"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
(OUT / "statistik.json").write_text(json.dumps(stats, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("statistik.json", (OUT / "statistik.json").stat().st_size // 1000, "kB")
print(stats["pusat"])
