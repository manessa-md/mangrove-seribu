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
S2DIR = DB / "MGV-KS_S2SR_2018-2026"   # raster kelas kerapatan per pulau-tahun (sudah dipotong AOI)
DIGIT = DB                              # MGV-KS_DigitasiMangrove2025_<KODE>.shp
KELAS = {1: "jarang", 2: "sedang", 3: "lebat"}

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
# Mangrove eksisting = digitasi citra resolusi tinggi 2025 (tim MGV-KS)
dg = []
for f in sorted(DIGIT.glob("MGV-KS_DigitasiMangrove2025_*.shp")):
    g = gpd.read_file(f).to_crs(32748)
    g = g[g.geometry.notna()]
    k = f.stem.split("_")[-1]
    dg.append({"pulau": k, "n_poligon": len(g), "geometry": g.union_all()})
dg = gpd.GeoDataFrame(dg, crs=32748)
dg["luas_ha"] = (dg.area / 1e4).round(3)
write_geo(dg, "mangrove_eksisting", simplify_m=0.3)
LUAS_DIGIT = dict(zip(dg.pulau, dg.luas_ha))
sms = L("sebaran_mangrove_sumber")
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

# Sebaran mangrove Sentinel-2 super-resolusi 2,5 m per tahun, langsung dari raster kelas
import rasterio, rasterio.features
from shapely.geometry import shape
from scipy.stats import kendalltau, linregress
s2rows, s2polys, s2meta = [], [], {}
for f in sorted(S2DIR.glob("*/MGV-KS_S2SR_*_Kerapatan.tif")):
    _, _, k, y, _ = f.stem.split("_")
    y = int(y)
    with rasterio.open(f) as r:
        a = r.read(1); tr = r.transform; px = abs(r.res[0] * r.res[1])
    luas = {KELAS[c]: round((a == c).sum() * px / 1e4, 3) for c in KELAS}
    meta = json.loads(f.with_name(f.name.replace("Kerapatan.tif", "meta.json")).read_text())
    s2rows.append({"kode": k, "tahun": y, **luas, "total": round(sum(luas.values()), 3),
                   "valid_pct": meta.get("valid_pct"), "luas_aoi_ha": meta.get("luas_aoi_ha"),
                   "n_citra": len(meta.get("scenes", []))})
    m = (a >= 1) & (a <= 3)
    for geom, v in rasterio.features.shapes(a, mask=m, transform=tr):
        s2polys.append({"kode": k, "tahun": y, "kelas": KELAS[int(v)], "geometry": shape(geom)})
s2df = pd.DataFrame(s2rows).sort_values(["kode", "tahun"])
s2g = gpd.GeoDataFrame(s2polys, crs=32748).dissolve(["kode", "tahun", "kelas"]).reset_index()
s2g["luas_ha"] = (s2g.area / 1e4).round(3)
for y, g in s2g.groupby("tahun"):
    write_geo(g, f"mangrove_s2sr_{y}", simplify_m=1, keep=["kode", "kelas", "tahun", "luas_ha"])
S2_YEARS = sorted(s2df.tahun.unique().tolist())

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
stats["tabel"] = {str(n): report_table(n) for n in range(1, 16) if n != 9}  # Tabel 9 = seri Landsat, tidak dipakai

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
DROP = {"Luas mangrove Landsat 2025 (ha)", "Tren luas 1996–2025", "Perubahan luas (ha)", "Kappa peta Landsat"}
for c in ring:
    for d_ in DROP:
        ring[c].pop(d_, None)
    ring[c]["Luas mangrove eksisting (ha)"] = LUAS_DIGIT.get(c)
stats["ringkasan"] = ring
stats["catatan_mutu"] = [r[0] for r in ws["CATATAN_MUTU_DATA"].iter_rows(min_row=2, values_only=True) if r[0]]
stats["kelengkapan"] = sheet_rows(AN / "15_Ringkasan_Per_Pulau/MGV-KS_Ringkasan_KS_v03.xlsx", "KELENGKAPAN_DATA")

# Seri waktu luas mangrove S2SR (satu-satunya sumber seri waktu)
stats["s2sr_tahun"] = [int(y) for y in S2_YEARS]
stats["s2sr_tahunan"] = {k: [[int(r[0])] + [float(x) for x in r[1:]] for r in g[["tahun", "total", "jarang", "sedang", "lebat"]].values.tolist()] for k, g in s2df.groupby("kode")}
tren = []
for k, g in s2df.groupby("kode"):
    t, p = kendalltau(g.tahun, g.total) if g.total.nunique() > 1 else (0.0, 1.0)
    lr = linregress(g.tahun, g.total)
    first, last = g.iloc[0], g.iloc[-1]
    tren.append({"pulau": k, "tahun_awal": int(first.tahun), "tahun_akhir": int(last.tahun),
                 "luas_awal_ha": first.total, "luas_akhir_ha": last.total,
                 "perubahan_ha": round(last.total - first.total, 3),
                 "laju_ha_th": round(lr.slope, 3), "tau": round(t, 3), "p": round(p, 3),
                 "tren": ("Naik" if t > 0 else "Turun") if p < 0.05 else "Tidak nyata",
                 "digitasi_2025_ha": LUAS_DIGIT.get(k)})
stats["s2sr_tren"] = tren
stats["s2sr_total"] = [{"tahun": int(y), "luas_ha": round(g.total.sum(), 3), "n_pulau": int(g.kode.nunique()),
                        "jarang": round(g.jarang.sum(), 3), "sedang": round(g.sedang.sum(), 3), "lebat": round(g.lebat.sum(), 3)}
                       for y, g in s2df.groupby("tahun")]
stats["luas_digitasi_2025"] = LUAS_DIGIT
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
