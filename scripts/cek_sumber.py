"""Deteksi perubahan berkas sumber di folder Mangrove untuk pembaruan otomatis WebGIS.

Masukan: hasil device_list_dir (JSON) dari beberapa subfolder Mangrove, masing-masing dengan
awalan path relatifnya, misalnya:

  python scripts/cek_sumber.py cek \
      --listing 03_DATABASE_MANGROVE/05_Basis_Data_Spasial=/tmp/db.json \
      --listing 04_PENGOLAHAN_ANALISIS=/tmp/an.json \
      --listing 02_DATA_PRIMER/PAR_Pari=/tmp/par.json ...

Keluaran (stdout, JSON):
  berubah      : berkas yang dipantau dan mtime-nya berbeda dari manifest (atau baru)
  versi_baru   : berkas versi lebih tinggi (mis. *_v04.*) dari yang dipakai skrip
  pulau_primer : kode pulau yang survei kualitas air/sumurnya berubah
  stage        : daftar path relatif yang perlu diambil (device_stage_files) untuk build

Setelah build & push berhasil:
  python scripts/cek_sumber.py simpan --listing ... (sama)   -> menulis data/_manifest_sumber.json
"""
import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "_manifest_sumber.json"

DB = "03_DATABASE_MANGROVE/05_Basis_Data_Spasial/"
AN = "04_PENGOLAHAN_ANALISIS/"
SHP = ("shp", "shx", "dbf", "prj", "cpg")

# Pola berkas yang dibaca build_data.py (path relatif terhadap folder Mangrove)
PANTAU = (
    [DB + "MGV-KS_HasilAnalisis_KS_v*.gpkg"]
    + [DB + f"MGV-KS_DigitasiMangrove2025_*.{e}" for e in SHP]
    + [DB + "MGV-KS_S2SR_2018-2026/*/MGV-KS_S2SR_*_Kerapatan.tif",
       DB + "MGV-KS_S2SR_2018-2026/*/MGV-KS_S2SR_*_meta.json"]
    + [AN + "15_Ringkasan_Per_Pulau/MGV-KS_Ringkasan_KS_v*.xlsx",
       AN + "16_Bahan_Laporan/MGV-KS_TabelLaporan_KS_v*.xlsx",
       AN + "13_Oseanografi_Fisik/MGV-KS_KriteriaFisik_KS_v*.xlsx"]
    + [f"02_DATA_PRIMER/*/06_Sampel_Substrat_WaterQuality/MGV-KS_Survei_*_Substrat_WaterQuality.{e}" for e in SHP]
    + [f"02_DATA_PRIMER/*/07_GroundWaterQuality/MGV-KS_Survei_*_AirTanah.{e}" for e in SHP]
)


def baca_listing(args):
    out = {}
    for item in args:
        prefix, f = item.split("=", 1)
        prefix = prefix.strip("/\\").replace("\\", "/")
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for e in d.get("entries", []):
            if e.get("type") == "file":
                rel = f"{prefix}/{e['name']}".replace("\\", "/")
                out[rel] = e.get("mtimeMs")
    return out


def dipantau(rel):
    return any(fnmatch.fnmatch(rel, p) for p in PANTAU)


def versi_dipakai():
    s = (ROOT / "scripts" / "build_data.py").read_text(encoding="utf-8")
    return {m.group(1): int(m.group(2)) for m in re.finditer(r'"(MGV-KS_[A-Za-z]+_KS)_v(\d+)\.(?:gpkg|xlsx)"', s)}


def primer_baru():
    return json.loads((ROOT / "scripts" / "primer_baru.json").read_text(encoding="utf-8"))


def daftar_stage(files, pulau_tambahan=()):
    """Semua berkas yang perlu di-stage agar build_data.py bisa berjalan penuh."""
    vers = versi_dipakai()
    pb = primer_baru()
    pulau_air = set(pb["air"]) | set(pulau_tambahan)
    pulau_sumur = set(pb["sumur"]) | set(pulau_tambahan)
    st = []
    for rel in files:
        if not dipantau(rel):
            continue
        m = re.search(r"(MGV-KS_[A-Za-z]+_KS)_v(\d+)\.", rel)
        if m and m.group(1) in vers and int(m.group(2)) != vers[m.group(1)]:
            continue  # hanya versi yang dipakai skrip
        if rel.startswith("02_DATA_PRIMER/"):
            k = re.search(r"MGV-KS_Survei_([A-Z]{3})_", rel).group(1)
            if "_AirTanah." in rel and k not in pulau_sumur:
                continue
            if "_Substrat_WaterQuality." in rel and k not in pulau_air:
                continue
        st.append(rel)
    return sorted(st)


def cek(listing):
    lama = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    files = {r: t for r, t in listing.items() if dipantau(r)}
    berubah = sorted(r for r, t in files.items() if lama.get(r) != t)
    vers = versi_dipakai()
    versi_baru = sorted({r for r in files
                         for m in [re.search(r"(MGV-KS_[A-Za-z]+_KS)_v(\d+)\.", r)]
                         if m and m.group(1) in vers and int(m.group(2)) > vers[m.group(1)]})
    pulau = sorted({re.search(r"MGV-KS_Survei_([A-Z]{3})_", r).group(1)
                    for r in berubah if r.startswith("02_DATA_PRIMER/")})
    return {
        "manifest_ada": bool(lama),
        "berubah": berubah,
        "versi_baru": versi_baru,
        "pulau_primer": pulau,
        "stage": daftar_stage(files, pulau) if (berubah or not lama) else [],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("aksi", choices=["cek", "simpan"])
    ap.add_argument("--listing", action="append", default=[])
    a = ap.parse_args()
    listing = baca_listing(a.listing)
    if a.aksi == "cek":
        json.dump(cek(listing), sys.stdout, ensure_ascii=False, indent=1)
    else:
        files = {r: t for r, t in sorted(listing.items()) if dipantau(r)}
        MANIFEST.write_text(json.dumps(files, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"manifest disimpan: {len(files)} berkas")


if __name__ == "__main__":
    main()
