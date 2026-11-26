"""Strategi & rencana aksi pemulihan untuk WebGIS MGV-KS (tab Strategi + lapisan lokasi rencana aksi).

Pakai:  python scripts/build_strategi.py <folder_Mangrove>
Sumber (versi tertinggi vNN):
  06_STRATEGI_RENCANA_AKSI/03_Rencana_Aksi/MGV-KS_RencanaAksi_KS_vNN.xlsx   (TEKNIK, LOKASI_AKSI, REKAP_PULAU, ANGGARAN_TAHUNAN,
                                                                           IFAS_EFAS, TOWS, MATRIKS_RENCANA_AKSI, INDIKATOR_MONEV)
  06_STRATEGI_RENCANA_AKSI/03_Rencana_Aksi/MGV-KS_LokasiAksi_KS_vNN.gpkg    (layer lokasi_aksi)
  06_STRATEGI_RENCANA_AKSI/03_Rencana_Aksi/MGV-KS_PetaTahapRencanaAksi_KS_vNN.png
  06_STRATEGI_RENCANA_AKSI/02_Strategi_Pemulihan/MGV-KS_StrategiRencanaAksi_KS_vNN.docx (arah kebijakan, tipologi, tahapan, peran)
Keluaran: data/strategi.json, data/rencana_aksi.geojson, data/peta_rencana_aksi.png
"""
import json, re, sys, shutil, datetime
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/Mangrove")
OUT = Path(__file__).resolve().parent.parent / "data"
SR = SRC / "06_STRATEGI_RENCANA_AKSI"


def terbaru(folder, pola):
    fs = [(int(m.group(1)), f) for f in (SR / folder).glob(pola) if (m := re.search(r"_v(\d+)\.\w+$", f.name))]
    return max(fs)[1] if fs else None


def bersih(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return round(float(v), 4)
    return str(v).strip() if isinstance(v, str) else v


def tabel(df):
    df = df.dropna(how="all")
    return {"kolom": [str(c) for c in df.columns], "baris": [[bersih(v) for v in r] for r in df.itertuples(index=False)]}


def docx_bagian(f):
    import docx
    d = docx.Document(f)
    sek, cur = {}, None
    for p in d.paragraphs:
        if p.style.name.startswith("Heading"):
            cur = p.text.split(" ")[0]; sek[cur] = {"judul": p.text, "teks": [], "butir": []}
        elif cur and p.text.strip() and not p.text.startswith(("Tabel ", "Gambar ")):
            (sek[cur]["butir"] if p.style.name.startswith("List") else sek[cur]["teks"]).append(p.text.strip())
    tab = {}
    for t in d.tables:
        h = [c.text.strip() for c in t.rows[0].cells]
        tab[h[0] + "|" + h[1]] = {"kolom": h, "baris": [[c.text.strip() for c in r.cells] for r in t.rows[1:]]}
    return sek, tab


ZONA_NM = {"Z1": "di atas MHW", "Z2": "MLW–MHW", "Z3": "LLWS–MLW", "Z4": "di bawah LLWS"}


def angka(v, d=2):
    return f"{v:.{d}f}".replace("-", "−").replace(".", ",")


def aturan_teknik(r, nama):
    """Telusuri aturan penetapan teknik (sheet PETUNJUK RencanaAksi v08) untuk satu lokasi.
    Hasil: (kode teknik menurut aturan, kalimat dasar penetapan)."""
    z, pap, rb, lrr = r.get("Zona pasut"), r.get("Paparan gelombang"), r.get("% sel rubble"), r.get("LRR min (m/th)")
    rb = 0 if rb is None or pd.isna(rb) else rb
    if z == "Z4":
        return "P-1", "Dasar di bawah LLWS → P-1 saja (peredam gelombang biologis), status bersyarat: redam dulu dan pantau elevasi dasar; belum dijadwalkan tanam."
    if z == "Z1":
        return "T-E", "Zona Z1 (di atas MHW) → T-E " + nama.get("T-E", "") + "."
    if rb >= 50:
        return "T-F", f"Substrat rubble {angka(rb, 0)}% sel (≥ 50%) → T-F " + nama.get("T-F", "") + "."
    if lrr is not None and pd.notna(lrr) and lrr < -1.5:
        return "T-C", f"Abrasi kuat: LRR minimum {angka(lrr)} m/th (< −1,5) → T-C " + nama.get("T-C", "") + "."
    if pap == "Terpapar":
        return "T-B", "Paparan terpapar → P-1 dibangun lebih dulu, tanam paling cepat 2 tahun kemudian dengan T-B " + nama.get("T-B", "") + "."
    k = {("Terlindung", "Z2"): "T-A", ("Terlindung", "Z3"): "T-B", ("Sedang", "Z2"): "T-B", ("Sedang", "Z3"): "T-C"}.get((pap, z))
    if k is None:
        return None, None
    return k, f"Paparan {str(pap).lower()} di zona {z} ({ZONA_NM.get(z, '')}) → {k} {nama.get(k, '')}."


def main():
    fx = terbaru("03_Rencana_Aksi", "MGV-KS_RencanaAksi_KS_v*.xlsx")
    if fx is None:
        print("Rencana aksi belum ada — dilewati"); return
    V = re.search(r"_(v\d+)\.xlsx$", fx.name).group(1)
    X = pd.ExcelFile(fx)
    st = {"versi": V, "dibangun": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
    st["dasar_data"] = str(X.parse("PETUNJUK", header=None).iloc[1, 0])
    tk = X.parse("TEKNIK")
    st["teknik"] = tabel(tk[["Kode", "Teknik", "Syarat lokasi", "Bibit/ha", "Jarak / pola", "Jenis yang dianjurkan", "Catatan pelaksanaan"]])
    rk = X.parse("REKAP_PULAU").dropna(subset=["Pulau"])
    st["rekap_pulau"] = {}
    for r in rk.itertuples(index=False):
        k = r.Kode if isinstance(r.Kode, str) else "TOTAL"
        d = {c: bersih(v) for c, v in zip(rk.columns, r) if c not in ("Kode",)}
        st["rekap_pulau"][k] = d
    ag = X.parse("ANGGARAN_TAHUNAN")
    st["anggaran"] = tabel(ag[[c for c in ag.columns if c != "Dasar perhitungan"]])
    ie = X.parse("IFAS_EFAS")
    st["ifas_efas"] = {"faktor": [{"kode": r.Kode, "faktor": r[1], "bobot": bersih(r.Bobot), "rating": bersih(r.Rating), "skor": bersih(r.Skor)}
                                  for r in ie.itertuples(index=False) if isinstance(r.Kode, str) and re.match(r"^[SWOT]\d", r.Kode)],
                       "ringkasan": {str(r[1]): bersih(r.Skor) for r in ie.itertuples(index=False)
                                     if not isinstance(r.Kode, str) and isinstance(r[1], str) and pd.notna(r.Skor)}}
    st["tows"] = tabel(X.parse("TOWS"))
    st["matriks"] = tabel(X.parse("MATRIKS_RENCANA_AKSI").dropna(subset=["Program"]))
    st["indikator"] = tabel(X.parse("INDIKATOR_MONEV"))

    fd = terbaru("02_Strategi_Pemulihan", "MGV-KS_StrategiRencanaAksi_KS_v*.docx")
    if fd is not None:
        sek, tab = docx_bagian(fd)
        st["arah_kebijakan"] = sek.get("9.4")
        st["tahapan"] = sek.get("10.3")
        st["tipologi"] = next((v for k, v in tab.items() if k.startswith("Tipologi|")), None)
        st["peran"] = next((v for k, v in tab.items() if k.startswith("Pihak|")), None)
        # v04+: penetapan lokasi = potensi prioritas -> sabuk pantai -> kendala sosial-ruang -> blok kerja (dicari menurut judul, bukan nomor)
        cari = lambda awal: next((v for v in sek.values() if v["judul"].lower().startswith(awal)), None)
        pen = {"penyaringan": cari("penyaringan operasional"), "kendala": cari("kendala sosial"),
               "corong": next((v for k, v in tab.items() if k.startswith("Kelas|Prioritas")), None),
               "kendala_pulau": next((v for k, v in tab.items() if k.startswith("Pulau|Sabuk")), None)}
        st["penetapan_lokasi"] = pen if pen["penyaringan"] or pen["corong"] else None

    # lokasi rencana aksi
    fg = terbaru("03_Rencana_Aksi", "MGV-KS_LokasiAksi_KS_v*.gpkg")
    la = X.parse("LOKASI_AKSI").set_index("ID lokasi")
    if fg is not None:
        g = gpd.read_file(fg, layer="lokasi_aksi")
        g["geometry"] = g.geometry.simplify(1, preserve_topology=True)
        j = la.reindex(g.id_lokasi)
        g["bibit"] = j["Kebutuhan bibit (batang)"].values
        g["biaya_rp"] = j["Total biaya pembangunan (Rp)"].values
        g["apo_m"] = j["Panjang APO (m)"].values
        # analisis teknik per lokasi: kondisi lokasi + aturan penetapan teknik
        nama = dict(zip(tk["Kode"], tk["Teknik"]))
        kol = {"blok": "Blok kerja", "paparan": "Paparan gelombang", "hs_m": "Hs median (m)", "rubble_pct": "% sel rubble",
               "jarak_darat_m": "Jarak ke daratan, median (m)", "substrat_pct": "% luas dengan data substrat ≤150 m",
               "p1": "P-1 (1/0)", "tahun_p1": "Tahun P-1", "p1_m": "Panjang P-1 (m)", "catatan": "Catatan"}
        for a, b in kol.items():
            if b in j.columns:
                g[a] = j[b].values
        atr = [aturan_teknik(r, nama) for r in j.to_dict("records")]
        g["teknik"] = j["Teknik"].values      # teknik final menurut LOKASI_AKSI (boleh diubah per lokasi)
        g["aturan"] = [t for _, t in atr]
        g["sesuai_aturan"] = [int(k == tkn) if k else None for (k, _), tkn in zip(atr, g["teknik"])]
        st["teknik_pulau"] = {}
        for (pl, tkn), d in g.groupby(["pulau", "teknik"]):
            st["teknik_pulau"].setdefault(pl, {})[tkn] = {"n": int(len(d)), "ha": round(float(d.luas_ha.sum()), 2)}
        pt = X.parse("PETUNJUK", header=None)[0].dropna().astype(str).tolist()
        st["aturan_teknik"] = [t for t in pt if t.startswith("Z1 >") or t.startswith("5. Paparan")]
        lrr = [c for c in ("LRR_min_m_th", "LRR_min_150m") if c in g.columns]  # v02: LRR_min_150m -> LRR_min_m_th
        g = g[["id_lokasi", "pulau", "prioritas", "luas_ha", "zona", "teknik", "status", "tahap", "tahun", "elevasi_median_m",
               *lrr[:1], "bibit", "apo_m", "biaya_rp", *[c for c in [*kol, "aturan", "sesuai_aturan"] if c in g.columns], "geometry"]].to_crs(4326)
        feats = []
        for _, r in g.iterrows():
            p = {k: bersih(v) for k, v in r.items() if k != "geometry"}
            feats.append({"type": "Feature", "properties": p, "geometry": json.loads(gpd.GeoSeries([r.geometry]).to_json())["features"][0]["geometry"]})
        txt = json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, separators=(",", ":"))
        txt = re.sub(r"(-?\d+\.\d{6})\d+", r"\1", txt)
        (OUT / "rencana_aksi.geojson").write_text(txt, encoding="utf-8")
        print(f"rencana_aksi: {len(feats)} lokasi, {len(txt) / 1e3:.0f} kB")
    fp = terbaru("03_Rencana_Aksi", "MGV-KS_PetaTahapRencanaAksi_KS_v*.png")
    if fp is not None:
        shutil.copy(fp, OUT / "peta_rencana_aksi.png"); st["peta"] = "data/peta_rencana_aksi.png"
    (OUT / "strategi.json").write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    print("strategi.json", V, "| total:", st["rekap_pulau"].get("TOTAL", {}).get("Total dasar+pilot (ha)"), "ha")


if __name__ == "__main__":
    main()
