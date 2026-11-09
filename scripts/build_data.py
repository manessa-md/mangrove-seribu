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
# ---------- Tambahan data primer (02_DATA_PRIMER) yang belum masuk basis data v03 ----------
# Titik v03 dipertahankan; titik survei (sudah QC tim) yang tidak berjarak < 1 m dari
# titik v03 ditambahkan sebagai bagian dari data.
PRIMER = SRC / "02_DATA_PRIMER"
FOLDER = {"UTJ": "UTJ_Untung_Jawa", "PAR": "PAR_Pari", "LCG": "LCG_Lancang", "TDG": "TDG_Tidung",
          "PRM": "PRM_Pramuka", "PGG": "PGG_Panggang", "KLP": "KLP_Kelapa", "KLD": "KLD_Kelapa_Dua",
          "HRP": "HRP_Harapan", "SBR": "SBR_Sebira"}
PRIMER_BARU = {  # pulau yang punya pembaruan data primer setelah v03 (8 Nov 2026)
    "air": ["PAR", "KLD"],
    "sumur": ["PAR", "HRP", "KLP"],
}


def num(v):
    if v is None:
        return None
    try:
        x = float(str(v).replace(",", ".").strip())
        return None if math.isnan(x) else x
    except ValueError:
        return None


def tgl(v):
    s = str(v or "").replace("DATE:", "").strip()
    for fmt in ("%m-%d-%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def kelas_sal(s):
    if s is None:
        return None
    return "Tawar" if s < 0.5 else "Payau ringan" if s < 5 else "Payau" if s < 18 else "Payau tinggi"


def qc_flag(r):
    f = []
    if r.get("do_mg_l") is not None and not (0 < r["do_mg_l"] <= 20):
        f.append("DO di luar 0–20 mg/L")
    if r.get("ph") is not None and not (5 <= r["ph"] <= 10):
        f.append("pH di luar 5–10")
    if r.get("salinitas_ppt") is not None and not (0 <= r["salinitas_ppt"] <= 45):
        f.append("salinitas di luar 0–45 ppt")
    return "; ".join(f) or None


def tambah_primer(old, jenis, key):
    """Gabungkan titik v03 dengan titik baru dari shapefile survei mentah."""
    old = old.copy()
    old["status_data"] = "v03 (QA/QC)"
    baru = []
    for k in PRIMER_BARU[jenis]:
        sub = "06_Sampel_Substrat_WaterQuality/MGV-KS_Survei_{k}_Substrat_WaterQuality.shp" if jenis == "air" \
            else "07_GroundWaterQuality/MGV-KS_Survei_{k}_AirTanah.shp"
        f = PRIMER / FOLDER[k] / sub.format(k=k)
        if not f.exists():
            print("  (lewati, tidak ada)", f.name)
            continue
        r = gpd.read_file(f).to_crs(old.crs)
        ref = old[old.kode_pulau == k]
        if len(ref):
            d = r.geometry.apply(lambda p: ref.distance(p).min())
            r = r[d >= 1.0]
        for _, x in r.iterrows():
            g = lambda *names: next((x[n] for n in names if n in x and x[n] is not None), None)
            rec = {key: str(x["ID_Titik"]), "kode_pulau": k, "pulau": k, "tanggal": tgl(g("Tanggal")),
                   "kedalaman_cm": num(g("Kedalaman", "Kedalaman_")),
                   "suhu_c": num(g("Temp_", "Suhu_C")), "ph": num(g("pH")),
                   "salinitas_ppt": num(g("Sal", "Salinitas_")), "do_mg_l": num(g("DO_", "DO_mg_l")),
                   "tds_ppt": num(g("TDS", "TDS_ppt")), "ec_ms_cm": num(g("EC", "EC_mS_cm")),
                   "status_data": "baru – belum QA/QC", "geometry": x.geometry}
            if jenis == "air":
                ket = str(g("Ket") or "").strip()
                rec["keterangan"] = {"non mangrove": "Non-mangrove", "non-mangrove": "Non-mangrove",
                                     "mangrove": "Mangrove", "laut": "Laut"}.get(ket.lower(), ket or None)
                rec["substrat"] = (g("Substrat") or "").lower() or None
            else:
                rec["kelas_salinitas"] = kelas_sal(rec["salinitas_ppt"])
            rec["catatan_qc"] = qc_flag(rec)
            baru.append(rec)
        print(f"  {jenis} {k}: +{len(r)} titik baru (v03: {len(ref)})")
    if baru:
        old = pd.concat([old, gpd.GeoDataFrame(baru, crs=old.crs)], ignore_index=True)
    return gpd.GeoDataFrame(old, crs=old.crs)


AIR = tambah_primer(L("titik_kualitas_air"), "air", "kode_titik")
SUMUR = tambah_primer(L("sumur_air_tanah"), "sumur", "kode_sumur")

# Rentang wajar parameter; nilai di luar rentang dianggap salah input dan tidak ditampilkan
RENTANG = {"ph": (4, 10), "salinitas_ppt": (0, 45), "do_mg_l": (0, 20), "suhu_c": (20, 40),
           "tds_ppt": (0, 45), "ec_ms_cm": (0, 80)}


def buang_salah(df, nama):
    df = df.copy()
    # baris yang semua parameternya 0 = tidak diukur (kode isian kosong)
    par = [c for c in ["salinitas_ppt", "do_mg_l", "tds_ppt", "ec_ms_cm"] if c in df]
    nol = (df[par].apply(pd.to_numeric, errors="coerce").fillna(-1) == 0).all(axis=1)
    if nol.any():
        print(f"  {nama}: {int(nol.sum())} titik tanpa pengukuran (semua 0) dikosongkan")
        for c in par + ["ph", "suhu_c", "kedalaman_cm"]:
            if c in df:
                df.loc[nol, c] = None
    for c, (lo, hi) in RENTANG.items():
        if c in df:
            v = pd.to_numeric(df[c], errors="coerce")
            bad = v.notna() & ((v < lo) | (v > hi))
            for _, r in df[bad].iterrows():
                print(f"  {nama}: {r.iloc[0]} {c}={r[c]} disembunyikan")
            df.loc[bad, c] = None
    if "kelas_salinitas" in df:
        df["kelas_salinitas"] = pd.to_numeric(df["salinitas_ppt"], errors="coerce").map(
            lambda x: kelas_sal(x) if pd.notna(x) else None)
    return df


AIR = buang_salah(AIR, "air")
SUMUR = buang_salah(SUMUR, "sumur")
write_geo(AIR, "titik_kualitas_air",
          keep=["kode_titik", "kode_pulau", "pulau", "tanggal", "keterangan", "substrat",
                "kedalaman_cm", "suhu_c", "ph", "salinitas_ppt", "do_mg_l", "tds_ppt",
                "ec_ms_cm", "elevasi_m"])
write_geo(SUMUR, "sumur_air_tanah",
          keep=["kode_sumur", "kode_pulau", "pulau", "tanggal", "kedalaman_cm", "suhu_c", "ph",
                "salinitas_ppt", "do_mg_l", "tds_ppt", "ec_ms_cm", "kelas_salinitas"])
N_AIR = AIR.groupby("kode_pulau").size().to_dict()
N_SUMUR = SUMUR.groupby("kode_pulau").size().to_dict()
N_BARU = {"air": AIR[AIR.status_data != "v03 (QA/QC)"].groupby("kode_pulau").size().to_dict(),
          "sumur": SUMUR[SUMUR.status_data != "v03 (QA/QC)"].groupby("kode_pulau").size().to_dict()}
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
# perbarui jumlah titik dengan data primer terbaru
for b in stats["tabel"]["1"]["baris"]:
    if b[0] in N_AIR:
        b[3] = N_AIR[b[0]]
    b[4] = N_SUMUR.get(b[0], b[4])
for c in ring:
    ring[c]["Titik kualitas air"] = N_AIR.get(c, 0)
    ring[c]["Sumur air tanah"] = N_SUMUR.get(c, 0)
for r in stats["kelengkapan"]:
    k = r.get(None) or r.get("null") or next(iter(r.values()))
    if k in N_AIR:
        r["kualitas_air"] = N_AIR[k]
    if k in N_SUMUR:
        r["air_tanah"] = N_SUMUR[k]


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
