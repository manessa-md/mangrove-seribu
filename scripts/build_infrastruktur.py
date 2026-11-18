"""Struktur pelindung pantai (breakwater, jetty, tanggul) dan jalur kapal per pulau untuk WebGIS MGV-KS.

Pakai:  python scripts/build_infrastruktur.py <folder_Mangrove>
Sumber: 01_DATA_SEKUNDER/12_Break_Water/SHP_Breakwater_Per_Pulau/<NN_Pulau_X>/Breakwater_*.shp  (PULAU, KATEGORI, TIPE_STR, TAHUN)
        01_DATA_SEKUNDER/11_Jalur_Kapal/01_Per_Pulau/<NN_Pulau_X>/Jalur_Kapal_*.shp             (JALUR_ID, NAMA_JALUR, TIPE_JALUR, ASAL, TUJUAN)
Keluaran: data/struktur_pantai.geojson, data/jalur_kapal.geojson, data/infrastruktur.json (ringkasan per pulau).
"""
import json, re, sys, glob, datetime
from pathlib import Path
import pandas as pd, geopandas as gpd

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/Mangrove")
OUT = Path(__file__).resolve().parent.parent / "data"
SEK = SRC / "01_DATA_SEKUNDER"
KODE = {"Untung Jawa": "UTJ", "Pari": "PAR", "Lancang": "LCG", "Tidung": "TDG", "Pramuka": "PRM", "Panggang": "PGG",
        "Kelapa": "KLP", "Kelapa Dua": "KLD", "Harapan": "HRP", "Sabira": "SBR", "Sebira": "SBR"}
# KATEGORI sumber → kelompok tampilan
KELOMPOK = {"BW_Dangkal": "Breakwater laut dangkal", "Breakwater": "Breakwater lepas pantai",
            "Jetty": "Jetty / dermaga", "Beton": "Tanggul beton / seawall"}


def kode(nama):
    n = re.sub(r"(?i)^pulau\s+", "", str(nama)).strip()
    return KODE.get(n)


def baca(pola):
    fs = sorted(glob.glob(str(SEK / pola), recursive=True))
    if not fs:
        return None
    g = pd.concat([gpd.read_file(f).to_crs(32748).assign(_pulau=kode(re.sub(r"^.*_\d\d_Pulau_", "", Path(f).stem).replace("_", " "))) for f in fs],
                  ignore_index=True)
    return gpd.GeoDataFrame(g, crs=32748)


def tulis(g, name):
    g = g.to_crs(4326)
    feats = [{"type": "Feature", "properties": {k: (None if pd.isna(v) else v) for k, v in r.items() if k != "geometry"},
              "geometry": json.loads(gpd.GeoSeries([r.geometry]).to_json())["features"][0]["geometry"]} for _, r in g.iterrows()]
    txt = json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, separators=(",", ":"))
    txt = re.sub(r"(-?\d+\.\d{6})\d+", r"\1", txt)
    (OUT / f"{name}.geojson").write_text(txt, encoding="utf-8")
    print(f"{name}: {len(feats)} fitur, {len(txt) / 1e3:.0f} kB")


def main():
    ring = {}
    bw = baca("12_Break_Water/**/Breakwater_*.shp")
    if bw is not None:
        bw["pulau"] = bw.PULAU.map(kode).fillna(bw._pulau)
        bw["kelompok"] = bw.KATEGORI.map(KELOMPOK).fillna(bw.TIPE_STR).fillna("Struktur lain (tanpa atribut)")
        bw["panjang_m"] = bw.length.round(1)
        bw["tahun"] = bw.TAHUN.where(bw.TAHUN > 0)
        out = bw[["pulau", "kelompok", "TIPE_STR", "tahun", "panjang_m", "geometry"]].rename(columns={"TIPE_STR": "tipe"})
        out["geometry"] = out.geometry.simplify(0.3)
        tulis(out, "struktur_pantai")
        for k, g in bw.groupby("pulau"):
            r = g.groupby("kelompok").panjang_m.agg(["count", "sum"])
            ring.setdefault(k, {})["struktur"] = {i: {"n": int(v["count"]), "panjang_m": round(float(v["sum"]))} for i, v in r.iterrows()}
    jk = baca("11_Jalur_Kapal/**/Jalur_Kapal_*.shp")
    if jk is not None:
        jk["pulau"] = jk.PULAU.map(kode).fillna(jk._pulau)
        jk["panjang_km"] = (jk.length / 1e3).round(2)
        out = jk[["JALUR_ID", "pulau", "NAMA_JALUR", "TIPE_JALUR", "ASAL", "TUJUAN", "panjang_km", "geometry"]]
        out.columns = ["id", "pulau", "nama", "tipe", "asal", "tujuan", "panjang_km", "geometry"]
        out = out.assign(geometry=out.geometry.simplify(2))
        tulis(out, "jalur_kapal")
        for k, g in out.groupby("pulau"):
            ring.setdefault(k, {})["jalur"] = [{"id": r.id, "nama": r.nama, "tipe": r.tipe, "panjang_km": float(r.panjang_km)} for _, r in g.iterrows()]
    if ring:
        (OUT / "infrastruktur.json").write_text(json.dumps({"pulau": ring, "dibangun": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")},
                                                           ensure_ascii=False, indent=1), encoding="utf-8")
        print("infrastruktur.json:", {k: sum(x["n"] for x in v.get("struktur", {}).values()) for k, v in ring.items()})


if __name__ == "__main__":
    main()
