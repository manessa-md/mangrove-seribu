"""Angin & gelombang 4 musim untuk WebGIS MGV-KS: ringkasan per pulau + lapisan panah.

Pakai:  python scripts/build_gelombang.py <folder_Mangrove>
Sumber: 04_PENGOLAHAN_ANALISIS/13_Oseanografi_Fisik/MGV-KS_Gelombang4Musim_v03/
          MGV-KS_Gelombang4Musim_KS_v03.xlsx (RINGKASAN)
          MGV-KS_Gelombang4Musim_<KODE>_<MUSIM>_HHWS_50m_v03.tif (band Hs, Tp, Dir[arah datang])
Muka air HHWS (pasang tertinggi) = kondisi terburuk untuk tegakan mangrove.
Keluaran: data/gelombang.json, data/gelombang_<MUSIM>.geojson (panah gelombang tiap 200 m, ≤ 1,5 km dari pulau),
          data/angin.geojson (panah angin per pulau per musim).
"""
import json, re, sys, warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.features import rasterize
from scipy import ndimage
from shapely.geometry import MultiLineString, mapping
from shapely.ops import transform as stransform
from pyproj import Transformer

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/Mangrove")
OUT = Path(__file__).resolve().parent.parent / "data"
G4 = SRC / "04_PENGOLAHAN_ANALISIS/13_Oseanografi_Fisik/MGV-KS_Gelombang4Musim_v03"
GPKG = SRC / "03_DATABASE_MANGROVE/05_Basis_Data_Spasial/MGV-KS_HasilAnalisis_KS_v03.gpkg"
MUSIM = {"DJF": "Musim Barat (Des–Feb)", "MAM": "Peralihan I (Mar–Mei)", "JJA": "Musim Timur (Jun–Agu)", "SON": "Peralihan II (Sep–Nov)"}
PULAU = ["UTJ", "PAR", "LCG", "TDG", "PRM", "PGG", "KLP", "KLD", "HRP", "SBR"]
UTM = "EPSG:32748"
to84 = Transformer.from_crs(UTM, 4326, always_xy=True).transform


def mata_angin(d):
    if d is None or not np.isfinite(d):
        return None
    return ["U", "TL", "T", "TG", "S", "BD", "B", "BL"][int(((d % 360) + 22.5) // 45) % 8]


def panah(x, y, dari, L, kepala=0.35, sudut=25):
    """Panah ke arah rambat (dari + 180°), berpusat di (x, y), panjang L meter."""
    t = np.radians((dari + 180) % 360)
    dx, dy = np.sin(t), np.cos(t)
    x0, y0, x1, y1 = x - dx * L / 2, y - dy * L / 2, x + dx * L / 2, y + dy * L / 2
    h = []
    for s in (-sudut, sudut):
        a = t + np.radians(180 + s)
        h.append([(x1, y1), (x1 + np.sin(a) * L * kepala, y1 + np.cos(a) * L * kepala)])
    return MultiLineString([[(x0, y0), (x1, y1)], *h])


def tulis(feats, name):
    txt = json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, separators=(",", ":"))
    txt = re.sub(r"(-?\d+\.\d{5})\d+", r"\1", txt)
    (OUT / f"{name}.geojson").write_text(txt, encoding="utf-8")
    print(f"{name}: {len(feats)} fitur, {len(txt) / 1e3:.0f} kB")


def main():
    R = pd.read_excel(G4 / "MGV-KS_Gelombang4Musim_KS_v03.xlsx", sheet_name="RINGKASAN")
    R = R[R.pasut == "HHWS"]
    rnd = lambda v, d=2: None if pd.isna(v) else round(float(v), d)
    ring = {}
    for k, g in R.groupby("kode"):
        rows = []
        for _, r in g.iterrows():
            rows.append({"musim": r.musim, "nama": MUSIM.get(r.musim, r.nama_musim), "U10_ms": rnd(r.U10_ms, 1),
                         "angin_dari": rnd(r.arah_angin_dari, 0), "angin_dari_ma": mata_angin(r.arah_angin_dari),
                         "gelombang_dari": rnd(r.pesisir_Dir_from, 0), "gelombang_dari_ma": mata_angin(r.pesisir_Dir_from),
                         "Hs_p90": rnd(r.pesisir_Hs_p90), "Hs_maks": rnd(r.pesisir_Hs_max), "Hs_p90_mgv": rnd(r.depanMGV_Hs_p90),
                         "Hs_maks_mgv": rnd(r.depanMGV_Hs_max), "Tp_s": rnd(r.pesisir_Tp_med, 1)})
        rows.sort(key=lambda x: list(MUSIM).index(x["musim"]))
        e = max(rows, key=lambda x: x["Hs_maks"] or 0)
        ring[k] = {"musim": rows, "ekstrem": {"Hs_maks": e["Hs_maks"], "musim": e["musim"], "nama": e["nama"],
                                              "gelombang_dari": e["gelombang_dari"], "gelombang_dari_ma": e["gelombang_dari_ma"]}}
    (OUT / "gelombang.json").write_text(json.dumps({"muka_air": "HHWS", "pulau": ring}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("gelombang.json:", {k: v["ekstrem"]["Hs_maks"] for k, v in ring.items()})

    dar = gpd.read_file(GPKG, layer="daratan_2025").to_crs(UTM)
    angin = []
    for m in MUSIM:
        feats = []
        for k in PULAU:
            f = G4 / f"MGV-KS_Gelombang4Musim_{k}_{m}_HHWS_50m_v03.tif"
            if not f.exists():
                continue
            with rasterio.open(f) as r:
                hs, tp, dr = r.read(1), r.read(2), r.read(3); T = r.transform
            pol = dar[dar.pulau == k]
            if len(pol):
                md = rasterize([(g, 1) for g in pol.geometry], out_shape=hs.shape, transform=T).astype(bool)
                jarak = ndimage.distance_transform_edt(~md) * abs(T.a)
            else:
                jarak = np.zeros(hs.shape)
            step = 4   # panah tiap 200 m
            ii, jj = np.mgrid[step // 2:hs.shape[0]:step, step // 2:hs.shape[1]:step]
            ok = (hs[ii, jj] > 0.02) & np.isfinite(dr[ii, jj]) & (jarak[ii, jj] <= 1500) & (jarak[ii, jj] > 0)
            for i, j in zip(ii[ok], jj[ok]):
                x, y = T.c + (j + .5) * T.a, T.f + (i + .5) * T.e
                g = stransform(to84, panah(x, y, float(dr[i, j]), 110))
                feats.append({"type": "Feature", "properties": {"pulau": k, "musim": m, "hs": round(float(hs[i, j]), 2),
                              "tp": round(float(tp[i, j]), 1), "dari": int(round(float(dr[i, j])))}, "geometry": mapping(g)})
            row = next((x for x in ring.get(k, {}).get("musim", []) if x["musim"] == m), None)
            if row and len(pol) and row["angin_dari"] is not None:
                c = pol.union_all().centroid
                b = pol.total_bounds
                L = float(np.clip(max(b[2] - b[0], b[3] - b[1]) * 0.6, 500, 1500))
                g = stransform(to84, panah(c.x, c.y, row["angin_dari"], L, kepala=0.25, sudut=28))
                angin.append({"type": "Feature", "properties": {"pulau": k, "musim": m, "U10_ms": row["U10_ms"], "dari": row["angin_dari"],
                              "dari_ma": row["angin_dari_ma"]}, "geometry": mapping(g)})
        tulis(feats, f"gelombang_{m}")
    tulis(angin, "angin")


if __name__ == "__main__":
    main()
