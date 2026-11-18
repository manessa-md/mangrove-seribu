"""Kontur batimetri dari berkas sekunder yang belum punya versi olahan v01 (saat ini: Lancang).

Pakai:  python scripts/bati_sekunder.py <folder_Mangrove>
Dipanggil otomatis di akhir build_data.py; menambah/mengganti garis LCG di
data/kontur_batimetri.geojson dan memperbarui data/statistik.json (Tabel 1, kelengkapan, catatan mutu).

Sumber 01_DATA_SEKUNDER/05_Oseanografi/Batimetri/batimetri_Lancang.tif (10 m, datum tidak tertulis)
digeser ke MSL pasut lokal dengan median selisih terhadap MGV-KS_TopoBatimetri_LCG_v04.tif di sel
yang bertampalan (keputusan pengguna 18 Nov 2026). Bila MGV-KS_TopoBatimetri_LCG_v05.tif ada, dipakai koreksi
datum c dari berkas itu (kalibrasi dengan titik kedalaman lapangan + prediksi pasut, sama dengan pulau lain).
Hapus berkas ini bila MGV-KS_Batimetri_LCG_v01.tif terbit.
"""
import json, re, sys
from pathlib import Path
import numpy as np

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/Mangrove")
OUT = Path(__file__).resolve().parent.parent / "data"
DB = SRC / "03_DATABASE_MANGROVE/05_Basis_Data_Spasial"
SUMBER = {"LCG": (SRC / "01_DATA_SEKUNDER/05_Oseanografi/Batimetri/batimetri_Lancang.tif",
                  DB / "MGV-KS_TopoBatimetri_LCG_v05.tif" if (DB / "MGV-KS_TopoBatimetri_LCG_v05.tif").exists()
                  else DB / "MGV-KS_TopoBatimetri_LCG_v04.tif")}


def kontur(kode, f, ref):
    import rasterio, contourpy
    from rasterio.warp import reproject, Resampling
    from shapely.geometry import LineString, mapping
    from shapely.ops import transform as stransform
    from pyproj import Transformer
    from scipy.ndimage import uniform_filter
    with rasterio.open(f) as r:
        e, T, crs = r.read(1).astype("float64"), r.transform, r.crs
        b = np.full(e.shape, np.nan, "float32")
        with rasterio.open(ref) as v:
            reproject(v.read(1), b, src_transform=v.transform, src_crs=v.crs, dst_transform=T, dst_crs=crs,
                      resampling=Resampling.average, src_nodata=np.nan, dst_nodata=np.nan)
    c_tag = None
    with rasterio.open(ref) as v:
        try:
            c_tag = float(v.tags().get("koreksi_datum_c_m", "nan"))
        except ValueError:
            pass
    m = np.isfinite(e) & np.isfinite(b)
    if c_tag is not None and np.isfinite(c_tag):
        m = np.ones_like(m)   # koreksi datum dari kalibrasi lapangan (v05)
    elif m.sum() < 100:
        print(f"  {kode}: tampalan dengan TopoBatimetri v04 terlalu sedikit ({m.sum()} sel) — dilewati")
        return None, None
    geser = c_tag if (c_tag is not None and np.isfinite(c_tag)) else float(np.median(b[m] - e[m]))
    sumber = (f"batimetri 10 m terkoreksi pasut (c = {geser:+.2f} m, kalibrasi titik lapangan; topo-batimetri {ref.stem[-3:]})"
              if (c_tag is not None and np.isfinite(c_tag)) else f"batimetri sekunder 10 m, digeser {geser:+.2f} m ke MSL pasut lokal (TopoBatimetri v04)")
    e = e + geser
    # penghalusan ringan 3x3 (abaikan NaN) agar kontur tidak bergerigi
    ok = np.isfinite(e)
    num = uniform_filter(np.where(ok, e, 0), 3)
    den = uniform_filter(ok.astype(float), 3)
    es = np.where(ok, num / np.maximum(den, 1e-9), np.nan)
    cg = contourpy.contour_generator(z=np.ma.masked_invalid(es), line_type="SeparateCode")
    to84 = Transformer.from_crs(crs, 4326, always_xy=True).transform
    feats = []
    for lv in range(-10, 0):
        for seg in cg.lines(lv)[0]:
            if len(seg) < 4:
                continue
            xs = T.c + (seg[:, 0] + .5) * T.a
            ys = T.f + (seg[:, 1] + .5) * T.e
            ln = LineString(np.c_[xs, ys]).simplify(4)
            if ln.length < 100:
                continue
            feats.append({"type": "Feature", "properties": {
                "pulau": kode, "elevasi_m": float(lv),
                "interval_sumber": sumber.replace(".", ",")},
                "geometry": mapping(stransform(to84, ln))})
    return feats, geser


# Pulau yang batimetrinya diganti (Batimetri_<Pulau>_v02.tif) → kontur dari topo-batimetri v05 (sudah terkoreksi pasut)
TOPO_V05 = ["PGG", "KLP"]


def kontur_topo(kode, f, B=4):
    """Kontur 1 m (−10…−1 m) dari sel batimetri (band 2 = 2) topo-batimetri v05; rerata blok B×B agar tidak bergerigi."""
    import rasterio, contourpy, warnings
    from shapely.geometry import LineString, mapping
    from shapely.ops import transform as stransform
    from pyproj import Transformer
    with rasterio.open(f) as r:
        e, src, T, crs = r.read(1), r.read(2), r.transform, r.crs
        c = r.tags().get("koreksi_datum_c_m", "")
    e = np.where(src == 2, e, np.nan)
    h, w = (e.shape[0] // B) * B, (e.shape[1] // B) * B
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        eb = np.nanmean(e[:h, :w].reshape(h // B, B, w // B, B), axis=(1, 3))
    cg = contourpy.contour_generator(z=np.ma.masked_invalid(eb), line_type="SeparateCode")
    to84 = Transformer.from_crs(crs, 4326, always_xy=True).transform
    lab = f"batimetri v02 2,5 m terkoreksi pasut (c = {float(c):+.2f} m; topo-batimetri v05)".replace(".", ",", 1) if c else "batimetri v02 (topo-batimetri v05)"
    feats = []
    for lv in range(-10, 0):
        for seg in cg.lines(lv)[0]:
            if len(seg) < 4:
                continue
            ln = LineString(np.c_[T.c + (seg[:, 0] * B + B / 2) * T.a, T.f + (seg[:, 1] * B + B / 2) * T.e]).simplify(4)
            if ln.length >= 100:
                feats.append({"type": "Feature", "properties": {"pulau": kode, "elevasi_m": float(lv), "interval_sumber": lab},
                              "geometry": mapping(stransform(to84, ln))})
    return feats


def main():
    fk = OUT / "kontur_batimetri.geojson"
    fs = OUT / "statistik.json"
    kb = json.loads(fk.read_text(encoding="utf-8"))
    st = json.loads(fs.read_text(encoding="utf-8"))
    for kode, (f, ref) in SUMBER.items():
        if not f.exists() or not ref.exists():
            print(f"  batimetri sekunder {kode}: berkas tidak ada — dilewati")
            continue
        if any(p["pulau"] == kode and "v01" in str(p.get("interval_sumber", "")) for p in (x["properties"] for x in kb["features"])):
            continue  # sudah ada versi olahan v01
        feats, geser = kontur(kode, f, ref)
        if not feats:
            continue
        kb["features"] = [x for x in kb["features"]
                          if not (x["properties"]["pulau"] == kode and "10 m" in str(x["properties"].get("interval_sumber", "")))] + feats
        print(f"  kontur batimetri sekunder {kode}: {len(feats)} garis, geser {geser:+.2f} m")
        i_b = st["tabel"]["1"]["kolom"].index("Batimetri")
        for b in st["tabel"]["1"]["baris"]:
            if b[0] == kode:
                b[i_b] = "Ada"
        for r in st["kelengkapan"]:
            if (r.get("null") or r.get(None) or next(iter(r.values()))) == kode:
                r["batimetri"] = 1
        nama = st["pulau"].get(kode, kode)
        g_ = f"{geser:+.2f}".replace(".", ",")
        catat = (f"Batimetri {nama} ({f.name}, 10 m): datum tidak tertulis; dikoreksi {g_} m ke MSL pasut lokal "
                 + (f"dengan kalibrasi titik kedalaman lapangan ({ref.name})." if "v05" in ref.name else
                    f"(median selisih terhadap TopoBatimetri {kode} v04). Kontur bersifat indikatif sampai versi olahan v01 tersedia."))
        st["catatan_mutu"] = [c for c in st["catatan_mutu"]
                              if not (c.startswith("Batimetri") and (nama in c or kode in c))] + [catat]
    for kode in TOPO_V05:
        f = DB / f"MGV-KS_TopoBatimetri_{kode}_v05.tif"
        if not f.exists():
            continue
        feats = kontur_topo(kode, f)
        if feats:
            kb["features"] = [x for x in kb["features"] if x["properties"]["pulau"] != kode or float(x["properties"]["elevasi_m"]) >= 0] + feats
            print(f"  kontur batimetri v05 {kode}: {len(feats)} garis")
    txt = json.dumps(kb, ensure_ascii=False, separators=(",", ":"))
    txt = re.sub(r"(-?\d+\.\d{5})\d+", r"\1", txt)
    fk.write_text(txt, encoding="utf-8")
    fs.write_text(json.dumps(st, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
