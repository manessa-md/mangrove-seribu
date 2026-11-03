# WebGIS Mangrove Kepulauan Seribu (MGV-KS)

WebGIS perkembangan data dan hasil analisis **Kajian Pemulihan Ekosistem Mangrove di Kepulauan Seribu** (2026).

Situs: https://manessa-md.github.io/mangrove-seribu/

## Isi

| Panel | Isi |
|---|---|
| Progres | Jumlah data terkumpul, tahapan kegiatan, kelengkapan data per pulau, catatan mutu data |
| Per pulau | Indikator vegetasi, karbon, garis pantai, sosek; grafik luas Landsat 1996–2025 + Sentinel-2 2019–2026; kesesuaian & lokasi prioritas |
| Analisis | Luas total, tren Mann-Kendall, kesesuaian AHP, DSAS, karbon, akurasi peta |
| Tabel | 15 tabel laporan (bisa diunduh CSV) |

Lapisan peta: daratan 2025, kontur topo-batimetri, mangrove eksisting, Sentinel-2 SR (2019/2021/2023/2025/2026), Landsat 2025, RBI 2022, plot vegetasi, titik kualitas air/groundcheck, sumur, foto hemispherical, transek DSAS, garis pantai tahunan, lokasi prioritas.

## Memperbarui data

1. Perbarui berkas sumber di folder proyek (`03_DATABASE_MANGROVE/05_Basis_Data_Spasial`, `04_PENGOLAHAN_ANALISIS`).
2. Jalankan:
   ```
   pip install geopandas pyogrio openpyxl
   python scripts/build_data.py "D:/06_Work/12_SUDIN/Mangrove"
   ```
   Skrip membaca `MGV-KS_HasilAnalisis_KS_v03.gpkg`, `MGV-KS_SebaranMangroveS2SR_KS_2019-2026_v01.gpkg` dan tabel `*_v03.xlsx`, lalu menulis ulang `data/*.geojson` dan `data/statistik.json`. Jika versi naik (v04), ganti nama berkas di bagian atas skrip.
3. Untuk panel tahapan, edit langsung `data/progres.json` (status: `selesai` / `berjalan` / `belum`).
4. Commit & push — GitHub Pages memperbarui situs dalam 1–2 menit.

## Teknis

HTML + [Leaflet 1.9.4](https://leafletjs.com) + [Chart.js 4.4.1](https://www.chartjs.org), tanpa build. Data asli UTM 48S (EPSG:32748) dikonversi ke WGS84 dan disederhanakan 0,5–4 m.
