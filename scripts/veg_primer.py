"""Plot vegetasi dari groundcheck primer (05_Groundcheck) untuk pulau yang belum ada di basis data v03 (saat ini: Sebira).

Pakai:  python scripts/veg_primer.py <folder_Mangrove>
Dipanggil di akhir build_data.py. Pulau = primer_baru.json["veg"].
Sumber: 02_DATA_PRIMER/<PULAU>/05_Groundcheck/MGV-KS_Survei_<KODE>_Groundcheck.shp
  baris berisi Spesies = satu individu terukur; ID_Transek + Jarak_Tran = plot (10 m → P01, 20 m → P02, …);
  Grid 10 x 10 = pohon, 5 x 5 = pancang, 2 x 2 = semai; Total_Indi = jumlah individu pada subpetak itu;
  Diameter = keliling batang (cm), DBH = keliling/π (kolom DBH); LAI_Ring4/5 & Canopy_Ope dari foto hemispherical (0 = belum diolah).
Metode sama dengan basis data v03 (MGV-KS_Analisis_Terpadu): kerapatan per subpetak, Komiyama et al. (2005), C = 0,47,
kelas Kepmen LH 201/2004 (kerapatan batang dan tutupan kanopi; kelas kondisi = terendah dari keduanya).
Memperbarui data/plot_vegetasi.geojson dan Tabel 1–6, ringkasan, kelengkapan di data/statistik.json.
"""
import json, math, re, sys
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/Mangrove")
OUT = Path(__file__).resolve().parent.parent / "data"
FOLDER = {"UTJ": "UTJ_Untung_Jawa", "PAR": "PAR_Pari", "LCG": "LCG_Lancang", "TDG": "TDG_Tidung", "PRM": "PRM_Pramuka",
          "PGG": "PGG_Panggang", "KLP": "KLP_Kelapa", "KLD": "KLD_Kelapa_Dua", "HRP": "HRP_Harapan", "SBR": "SBR_Sebira"}
LUAS = {"pohon": 100, "pancang": 25, "semai": 4}
GRID = {"10 x 10": "pohon", "5 x 5": "pancang", "2 x 2": "semai"}
RHO = {"Rhizophora apiculata": 0.77, "Rhizophora mucronata": 0.70, "Rhizophora stylosa": 0.77, "Rhizophora sp.": 0.75,
       "Bruguiera gymnorhiza": 0.70, "Bruguiera sp.": 0.70, "Ceriops tagal": 0.75, "Avicennia marina": 0.65,
       "Sonneratia alba": 0.47, "Lumnitzera racemosa": 0.71, "Pemphis acidula": 0.90, "Xylocarpus granatum": 0.53,
       "Excoecaria agallocha": 0.42}
POLA = [(r"stylosa|stilosa", "Rhizophora stylosa"), (r"mucronata|mukronata", "Rhizophora mucronata"),
        (r"apiculata|apikulata", "Rhizophora apiculata"), (r"bru?g.?u?i?era|tancang", "Bruguiera sp."), (r"ceriops", "Ceriops tagal"),
        (r"avicennia", "Avicennia marina"), (r"sonneratia|pedada", "Sonneratia alba"), (r"lumnitzera", "Lumnitzera racemosa"),
        (r"pemphis", "Pemphis acidula"), (r"xylocarpus", "Xylocarpus granatum"), (r"excoecaria", "Excoecaria agallocha"),
        (r"rhizophora|bakau", "Rhizophora sp.")]
KELAS = ("Baik - sangat padat", "Baik - sedang", "Rusak - jarang")


def jenis(s):
    t = str(s).lower()
    return next((n for p, n in POLA if re.search(p, t)), str(s).strip())


def kelas(v, b):
    return None if v is None or pd.isna(v) else KELAS[0] if v >= b[0] else KELAS[1] if v >= b[1] else KELAS[2]


def tanggal(v):
    m = re.search(r"(\d{1,2})-(\d{1,2})-(\d{4})", str(v))   # format alat: BB-HH-TTTT (sesuai nama foto hemispherical)
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else None


def koreksi_lai(g):
    """Isi LAI/keterbukaan kanopi yang 0 di .shp dari scripts/lai_koreksi.csv (salinan Google Sheet; desimal koma hilang saat ekspor)."""
    f = Path(__file__).with_name("lai_koreksi.csv")
    if not f.exists():
        return g
    k = pd.read_csv(f, comment="#").set_index("ID_Titik")
    for c in ["LAI_Ring4", "LAI_Ring5", "Canopy_Ope"]:
        kosong = g.ID_Titik.isin(k.index) & (pd.to_numeric(g[c], errors="coerce").fillna(0) == 0)
        g.loc[kosong, c] = g.loc[kosong, "ID_Titik"].map(k[c])
    return g


def plot_pulau(k):
    f = SRC / "02_DATA_PRIMER" / FOLDER[k] / "05_Groundcheck" / f"MGV-KS_Survei_{k}_Groundcheck.shp"
    if not f.exists():
        return None, None
    g = koreksi_lai(gpd.read_file(f).to_crs(32748))
    g = g[g.Spesies.notna() & (g.ID_Transek > 0)].copy()
    if not len(g):
        return None, None
    g["t"] = g.ID_Transek.astype(int); g["p"] = (g.Jarak_Tran / 10).round().astype(int).clip(lower=1)
    g["kode_plot"] = [f"{k}-T{t:02d}-P{p:02d}" for t, p in zip(g.t, g.p)]
    g["tingkat"] = g.Grid.astype(str).str.replace(" ", "").map({a.replace(" ", ""): b for a, b in GRID.items()})
    g["jenis"] = g.Spesies.map(jenis)
    ind = g[g.tingkat.isin(["pohon", "pancang"]) & (g.DBH > 0)].copy()
    ind["dbh_cm"] = ind.DBH.astype(float)
    ind["rho"] = ind.jenis.map(RHO).fillna(0.70)
    ind["ba_m2"] = math.pi * (ind.dbh_cm / 200) ** 2
    ind["agb_kg"] = 0.251 * ind.rho * ind.dbh_cm ** 2.46
    ind["bgb_kg"] = 0.199 * ind.rho ** 0.899 * ind.dbh_cm ** 2.22
    gi = ind.groupby("kode_plot")
    rows = []
    for kp, d in g.groupby("kode_plot"):
        n = {t: float(d[d.tingkat == t].Total_Indi.iloc[0]) if (d.tingkat == t).any() else 0.0 for t in LUAS}
        r = {"kode_plot": kp, "pulau": k, "no_transek": int(d.t.iloc[0]), "no_plot": int(d.p.iloc[0]), "tanggal": tanggal(d.Tanggal.iloc[0]),
             "x_utm": round(float(d.geometry.x.mean()), 1), "y_utm": round(float(d.geometry.y.mean()), 1),
             "jml_pohon_10x10": n["pohon"], "jml_pancang_5x5": n["pancang"], "jml_semai_2x2": n["semai"]}
        r["kerapatan_pohon_ha"] = n["pohon"] * 1e4 / LUAS["pohon"]
        r["kerapatan_pancang_ha"] = n["pancang"] * 1e4 / LUAS["pancang"]
        r["kerapatan_semai_ha"] = n["semai"] * 1e4 / LUAS["semai"]
        r["kerapatan_batang_ha"] = r["kerapatan_pohon_ha"] + r["kerapatan_pancang_ha"]
        if kp in gi.groups:
            x = gi.get_group(kp)
            r.update(n_diukur=len(x), dbh_rerata_cm=round(x.dbh_cm.mean(), 1), jenis_dominan=x.jenis.value_counts().index[0],
                     ba_m2_ha=round(x.ba_m2.mean() * r["kerapatan_batang_ha"], 2),
                     karbon_t_ha=round((x.agb_kg.mean() + x.bgb_kg.mean()) * r["kerapatan_batang_ha"] / 1000 * 0.47, 1),
                     ba_min_m2_ha=round(x.ba_m2.sum() * 100, 2), karbon_min_t_ha=round((x.agb_kg.sum() + x.bgb_kg.sum()) * 100 / 1000 * 0.47, 1))
            r["co2e_min_t_ha"] = round(r["karbon_min_t_ha"] * 44 / 12, 1); r["ba_tidak_wajar"] = bool(r["ba_m2_ha"] > 60)
        else:
            r.update(n_diukur=0, jenis_dominan=d.jenis.value_counts().index[0])
        r["kelas_kerapatan_pohon"] = kelas(r["kerapatan_pohon_ha"], (1500, 1000))
        r["kelas_kerapatan_batang"] = kelas(r["kerapatan_batang_ha"], (1500, 1000))
        h = d[(d.LAI_Ring4 > 0) | (d.Canopy_Ope > 0)]
        if len(h):
            tut = 100 - h.Canopy_Ope
            r.update(n_foto_hemi=float(len(h)), LAI_ring4=round(h.LAI_Ring4.mean(), 2), LAI_ring5=round(h.LAI_Ring5.mean(), 2),
                     tutupan_kanopi_pct=round(tut.mean(), 2), tutupan_kanopi_sd=round(tut.std(), 2) if len(h) > 1 else None)
            r["kelas_tutupan"] = kelas(r["tutupan_kanopi_pct"], (75, 50))
            u = {KELAS[0]: 3, KELAS[1]: 2, KELAS[2]: 1}
            r["kelas_kondisi"] = min([r["kelas_kerapatan_batang"], r["kelas_tutupan"]], key=lambda c: u[c])
            r["dasar_kelas_kondisi"] = "kerapatan + tutupan"
        else:
            r["kelas_kondisi"] = r["kelas_kerapatan_batang"]; r["dasar_kelas_kondisi"] = "kerapatan saja"
        r["geometry"] = d.geometry.union_all().centroid
        rows.append(r)
    return gpd.GeoDataFrame(rows, crs=32748), ind


def bersih(v):
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else round(float(v), 4)
    if isinstance(v, np.integer):
        return int(v)
    return v


def main():
    veg = json.loads((Path(__file__).with_name("primer_baru.json")).read_text(encoding="utf-8")).get("veg", [])
    fp, fs = OUT / "plot_vegetasi.geojson", OUT / "statistik.json"
    pv = json.loads(fp.read_text(encoding="utf-8")); st = json.loads(fs.read_text(encoding="utf-8"))
    nama = st["pulau"]
    for k in veg:
        R, ind = plot_pulau(k)
        if R is None:
            continue
        if any(f["properties"]["pulau"] == k and not str(f["properties"].get("sumber", "")).startswith("groundcheck") for f in pv["features"]):
            print(f"  {k}: plot sudah ada di basis data — dilewati"); continue
        R4 = R.to_crs(4326)
        pv["features"] = [f for f in pv["features"] if f["properties"]["pulau"] != k] + [
            {"type": "Feature", "properties": {**{c: bersih(v) for c, v in r.items() if c != "geometry"}, "sumber": "groundcheck 05_Groundcheck (belum QA/QC)"},
             "geometry": {"type": "Point", "coordinates": [round(r.geometry.x, 6), round(r.geometry.y, 6)]}} for _, r in R4.iterrows()]
        nm = nama.get(k, k); n = len(R)
        T = st["tabel"]
        # Tabel 1 & kelengkapan & ringkasan
        i_p = T["1"]["kolom"].index("Plot vegetasi")
        for b in T["1"]["baris"]:
            if b[0] in (k, nm):
                b[i_p] = n
        for r in st["kelengkapan"]:
            if (r.get(None) or r.get("null") or next(iter(r.values()))) == k:
                r["plot_vegetasi"] = n
        # Tabel 2 struktur
        t2 = [nm, n, int(R.n_diukur.sum()), round(R.kerapatan_pohon_ha.mean(), 1), round(R.kerapatan_pancang_ha.mean(), 1),
              round(R.kerapatan_semai_ha.mean(), 1), round(float(R.dbh_rerata_cm.mean()), 1)]
        T["2"]["baris"] = [b for b in T["2"]["baris"] if b[0] != nm] + [t2]
        # Tabel 3 INP
        J = ind.groupby("jenis").agg(n=("dbh_cm", "size"), n_plot=("kode_plot", "nunique"), ba=("ba_m2", "sum")).reset_index()
        J["KR"] = J.n / J.n.sum() * 100; J["FR"] = (J.n_plot / n) / (J.n_plot / n).sum() * 100; J["DR"] = J.ba / J.ba.sum() * 100
        J["INP"] = J.KR + J.FR + J.DR; J = J.sort_values("INP", ascending=False)
        T["3"]["baris"] = [b for b in T["3"]["baris"] if b[0] != nm] + [[nm, r.jenis, int(r.n), int(r.n_plot), round(r.KR, 2), round(r.FR, 2), round(r.DR, 2), round(r.INP, 2)] for r in J.itertuples()]
        # Tabel 4 keanekaragaman
        c = ind.jenis.value_counts().values.astype(float); p = c / c.sum(); S = len(c); H = float(-(p * np.log(p)).sum())
        t4 = [nm, S, round(abs(H), 3), round(H / math.log(S), 3) if S > 1 else "–", round(float((p ** 2).sum()), 3), "Rendah" if H < 1 else "Sedang" if H <= 3 else "Tinggi"]
        T["4"]["baris"] = [t4 if b[0] == nm else b for b in T["4"]["baris"]] if any(b[0] == nm for b in T["4"]["baris"]) else T["4"]["baris"] + [t4]
        # Tabel 5: persen plot rusak-jarang gabungan
        rj = round((R.kelas_kondisi == "Rusak - jarang").mean() * 100, 1)
        for b in T["5"]["baris"]:
            if b[0] == nm:
                b[2] = int(R.tutupan_kanopi_pct.notna().sum()) if "tutupan_kanopi_pct" in R else b[2]; b[-1] = rj
        # Tabel 6 karbon
        kr = R.dropna(subset=["karbon_min_t_ha"])
        t6 = [nm, round(kr.karbon_min_t_ha.mean(), 1), round(kr.karbon_min_t_ha.mean() * 44 / 12, 1), round(kr.karbon_t_ha.mean(), 1), round(kr.ba_tidak_wajar.mean() * 100, 1)]
        T["6"]["baris"] = [b for b in T["6"]["baris"] if b[0] != nm] + [t6]
        for t in ["2", "3", "6"]:
            cat = f"{nm}: groundcheck 05_Groundcheck (survei Nov 2026), belum QA/QC."
            if cat not in T[t]["catatan"]:
                T[t]["catatan"].append(cat)
        g = st["ringkasan"].get(k)
        if g is not None:
            g["Plot vegetasi"] = n; g["Jenis dominan"] = ind.jenis.value_counts().index[0]
            g["Kerapatan batang rerata (ind/ha)"] = round(R.kerapatan_batang_ha.mean()); g["DBH rerata (cm)"] = t2[-1]
            g["Karbon batas bawah (t C/ha)"] = t6[1]; g["H' Shannon"] = t4[2]
            g["% plot rusak-jarang (kerapatan+tutupan)"] = rj
        print(f"  plot vegetasi {k}: {n} plot, {len(ind)} individu terukur, jenis {dict(ind.jenis.value_counts())}")
    txt = json.dumps(pv, ensure_ascii=False, separators=(",", ":"))
    fp.write_text(txt, encoding="utf-8")
    fs.write_text(json.dumps(st, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
