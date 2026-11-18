"""Lapisan persetujuan masyarakat (hasil FGD) untuk WebGIS MGV-KS.

Pakai:  python scripts/build_sosek.py <folder_Mangrove>
Sumber: 02_DATA_PRIMER/<PULAU>/09_Sosek/Rekomendasi_<KODE>.shp
        kolom Keterangan: "Masyarakat S" (setuju ditanami mangrove) / "Masyarakat TS" (tidak setuju),
        teks tambahan dalam kurung disimpan sebagai catatan.
Keluaran: data/persetujuan_masyarakat.geojson, data/sosek.json (luas per pulau).
Data responden (nama, telepon, koordinat rumah) TIDAK dibaca/diterbitkan.
"""
import json, re, sys, datetime
from pathlib import Path
import geopandas as gpd
import pandas as pd

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/Mangrove")
OUT = Path(__file__).resolve().parent.parent / "data"
PRIMER = SRC / "02_DATA_PRIMER"
FOLDER = {"UTJ": "UTJ_Untung_Jawa", "PAR": "PAR_Pari", "LCG": "LCG_Lancang", "TDG": "TDG_Tidung",
          "PRM": "PRM_Pramuka", "PGG": "PGG_Panggang", "KLP": "KLP_Kelapa", "KLD": "KLD_Kelapa_Dua",
          "HRP": "HRP_Harapan", "SBR": "SBR_Sebira"}
UTM = 32748


def status_of(ket):
    if ket is None or (isinstance(ket, float) and pd.isna(ket)) or not str(ket).strip():
        return "Belum ada keterangan", None
    t = str(ket).strip()
    m = re.match(r"(?i)masyarakat\s+(TS|S)\b\s*(.*)", t)
    if not m:
        return "Belum ada keterangan", t
    st = "Tidak setuju" if m.group(1).upper() == "TS" else "Setuju"
    cat = m.group(2).strip().strip("()").strip() or None
    return st, cat


def main():
    parts, ring = [], {}
    for k, fol in FOLDER.items():
        f = PRIMER / fol / "09_Sosek" / f"Rekomendasi_{k}.shp"
        if not f.exists():
            continue
        g = gpd.read_file(f)
        if g.crs is None:
            # tanpa .prj: tebak dari rentang koordinat
            g = g.set_crs(4326 if g.total_bounds[0] < 180 else UTM)
        g = g[g.geometry.notna() & ~g.geometry.is_empty].to_crs(UTM)
        g["geometry"] = g.geometry.make_valid()
        st = g["Keterangan"].map(status_of) if "Keterangan" in g else pd.Series([("Belum ada keterangan", None)] * len(g), index=g.index)
        out = gpd.GeoDataFrame({
            "pulau": k,
            "status": [s for s, _ in st],
            "catatan": [c for _, c in st],
            "luas_ha": (g.geometry.area / 1e4).round(3).values,
        }, geometry=g.geometry.values, crs=UTM)
        parts.append(out)
        r = out.groupby("status").luas_ha.agg(["sum", "count"])
        ring[k] = {s: {"luas_ha": round(float(r.loc[s, "sum"]), 2), "n": int(r.loc[s, "count"])} for s in r.index}
        print(f"{k}: {len(out)} poligon", {s: v["luas_ha"] for s, v in ring[k].items()})
    if not parts:
        print("Tidak ada berkas Rekomendasi_*.shp — lapisan persetujuan masyarakat dilewati")
        return
    allg = pd.concat(parts, ignore_index=True)
    allg["id"] = [f"{p}-{i + 1}" for i, p in zip(allg.groupby("pulau").cumcount(), allg.pulau)]
    allg["geometry"] = allg.geometry.simplify(0.5, preserve_topology=True)
    allg = allg.to_crs(4326)
    feats = []
    for _, r in allg.iterrows():
        props = {c: (None if pd.isna(r[c]) else r[c]) for c in ["id", "pulau", "status", "catatan", "luas_ha"]}
        props["luas_ha"] = float(props["luas_ha"])
        geom = json.loads(gpd.GeoSeries([r.geometry]).to_json())["features"][0]["geometry"]
        feats.append({"type": "Feature", "properties": props, "geometry": geom})
    txt = json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, separators=(",", ":"))
    txt = re.sub(r"(-?\d+\.\d{6})\d+", r"\1", txt)
    (OUT / "persetujuan_masyarakat.geojson").write_text(txt, encoding="utf-8")
    print(f"persetujuan_masyarakat: {len(feats)} fitur, {len(txt) / 1e3:.0f} kB")
    tot = allg.groupby("status").luas_ha.sum().round(2).to_dict()
    (OUT / "sosek.json").write_text(json.dumps({
        "persetujuan": ring, "total_ha": tot,
        "dibangun": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("total:", tot)


if __name__ == "__main__":
    main()
