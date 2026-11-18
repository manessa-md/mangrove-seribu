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


PULAU = {"UTJ": "Untung Jawa", "PAR": "Pari", "LCG": "Lancang", "TDG": "Tidung", "PRM": "Pramuka", "PGG": "Panggang",
         "KLP": "Kelapa", "KLD": "Kelapa Dua", "HRP": "Harapan", "SBR": "Sebira"}
# Pertanyaan kuesioner yang diringkas (awalan judul kolom → label, urutan kategori; None = pilihan ganda berkode huruf)
TANYA = [
    ("1. Dibandingkan", "kelebatan", "Kelebatan mangrove dibanding 2020",
     {"Jauh lebih lebat": "Lebih lebat", "Lebih lebat": "Lebih lebat", "Tidak ada perubahan": "Tidak berubah",
      "Berkurang/mulai gundul": "Berkurang", "Jauh berkurang/gundul": "Berkurang"}),
    ("4. Bagaimana", "kondisi", "Kondisi mangrove 6 tahun terakhir", None),
    ("3. Apakah IBS mengetahui fungsi", "tahu_fungsi", "Mengetahui fungsi mangrove", None),
    ("2. Seberapa sering", "pemanfaatan", "Memanfaatkan mangrove 2020–2026",
     {"Tidak pernah": "Tidak pernah", "Jarang (Sebulan 1X)": "Jarang", "Kadang-kadang (Seminggu 1X)": "Kadang-kadang",
      "Sering (3-4x/minggu)": "Sering", "Sangat sering (Setiap hari)": "Sering"}),
    ("6. Apakah IBS", "program", "Program rehabilitasi mangrove", None),
    ("6E.", "pelibatan", "Masyarakat dilibatkan dalam program", None),
    ("18. Seberapa", "kesediaan", "Kesediaan berpartisipasi",
     {"Sangat bersedia": "Sangat bersedia", "Bersedia": "Bersedia", "Ragu-ragu": "Ragu-ragu",
      "Tidak bersedia": "Tidak bersedia", "Tidak bersedia sama sekali": "Tidak bersedia"}),
    ("18D.", "peran", "Peran yang paling bersedia dijalani", "kode"),
    ("18C.", "dukungan", "Dukungan agar mau berpartisipasi (boleh > 1)", "multi"),
    ("17. Menurut", "pengaruh_ikan", "Pengaruh mangrove pada kelimpahan ikan/kepiting/udang", None),
    ("16C.", "perilaku", "Perubahan perilaku warga menjaga mangrove", None),
    ("CK1.", "sektor_laut", "Bekerja di sektor kelautan/perikanan", None),
]


def ringkas_survei():
    """Ringkasan agregat kuesioner sosek per pulau (tanpa data pribadi responden)."""
    import glob
    rows = []
    for f in sorted(glob.glob(str(PRIMER / "*" / "09_Sosek" / "MGV-KS_Survei_*_Sosek.xlsx"))):
        k = re.search(r"_Survei_([A-Z]{3})_", f).group(1)
        rows.append(pd.read_excel(f).assign(_kode=k))
    if not rows:
        return {}, None
    D = pd.concat(rows, ignore_index=True)
    kol = {}
    for awal, key, *_ in TANYA:
        m = [c for c in D.columns if str(c).startswith(awal)]
        if m:
            kol[key] = m[0]
    out = {}
    for k, g in D.groupby("_kode"):
        n = len(g); r = {"n": n, "pertanyaan": {}}
        for awal, key, label, peta in TANYA:
            if key not in kol:
                continue
            s = g[kol[key]].dropna().astype(str).str.strip()
            s = s[s != ""]
            if peta == "multi":
                items = s.str.findall(r"(?:^|,\s*)[a-eA-E]\.\s*([^,]+)").explode().dropna().str.strip()
                vc = items.str.replace("Insenstif", "Insentif").value_counts()
            elif peta == "kode":
                vc = s[s.str.match(r"^[A-Fa-f]\.\s")].str.replace(r"^[A-Fa-f]\.\s*", "", regex=True).value_counts()
            elif isinstance(peta, dict):
                vc = s.map(lambda v: peta.get(v, "Lainnya")).value_counts()
                urut = list(dict.fromkeys(peta.values())) + ["Lainnya"]
                vc = vc.reindex([u for u in urut if u in vc.index])
            else:
                vc = s.value_counts()
            r["pertanyaan"][key] = {"label": label, "n": int(len(s)), "jawaban": {a: int(b) for a, b in vc.items()}}
        q = r["pertanyaan"]
        pct = lambda key, vals: round(100 * sum(q.get(key, {}).get("jawaban", {}).get(v, 0) for v in vals) / n, 1)
        r["indikator"] = {
            "Bersedia berpartisipasi (%)": pct("kesediaan", ["Sangat bersedia", "Bersedia"]),
            "Pernah terlibat program (%)": pct("program", ["Tahu dan terlibat"]),
            "Menilai mangrove berkurang (%)": pct("kelebatan", ["Berkurang"]),
            "Dilibatkan sejak perencanaan (%)": pct("pelibatan", ["Sejak tahap perencanaan awal"]),
        }
        out[k] = r
    return out, D


def main():
    survei, _ = ringkas_survei()
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
        "persetujuan": ring, "total_ha": tot, "survei": survei,
        "dibangun": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("total:", tot)
    # Tabel 15 & ringkasan per pulau dihitung ulang dari kuesioner (semua pulau yang punya MGV-KS_Survei_<KODE>_Sosek.xlsx)
    fs = OUT / "statistik.json"
    if survei and fs.exists():
        st = json.loads(fs.read_text(encoding="utf-8"))
        t15 = st["tabel"].get("15")
        if t15:
            kol = t15["kolom"]
            baris = []
            for k, nama in PULAU.items():
                s = survei.get(k)
                baris.append([nama, s["n"], *[s["indikator"][c] for c in kol[2:]]] if s else [nama, "–", *["–"] * (len(kol) - 2)])
            t15["baris"] = baris
            t15["catatan"] = ["Sumber: Survei sosial ekonomi-kelembagaan MGV-KS 2026 (MGV-KS_Survei_<KODE>_Sosek.xlsx)",
                              "Catatan: % dari seluruh responden pulau. 'Menilai mangrove berkurang' = jawaban berkurang/mulai gundul atau jauh berkurang/gundul dibanding 2020."]
        for k, s in survei.items():
            if k in st.get("ringkasan", {}):
                st["ringkasan"][k]["Responden sosek"] = s["n"]
                st["ringkasan"][k]["% bersedia berpartisipasi"] = s["indikator"]["Bersedia berpartisipasi (%)"]
        fs.write_text(json.dumps(st, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print("Tabel 15:", {k: (s["n"], s["indikator"]) for k, s in survei.items()})


if __name__ == "__main__":
    main()
