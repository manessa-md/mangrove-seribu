# WebGIS Mangrove Kepulauan Seribu (MGV-KS)

WebGIS perkembangan data dan hasil analisis **Kajian Pemulihan Ekosistem Mangrove di Kepulauan Seribu** (2026).

Situs: https://manessa-md.github.io/mangrove-seribu/

## Isi

| Panel | Isi |
|---|---|
| Progres | Jumlah data terkumpul, tahapan kegiatan, kelengkapan data per pulau, catatan mutu data |
| Per pulau | Indikator vegetasi, karbon, garis pantai, sosek; grafik seri waktu Sentinel-2 super-resolusi 2018–2026 per kelas kerapatan; kesesuaian & lokasi prioritas |
| Analisis | Luas total S2SR, tren Mann-Kendall, kesesuaian AHP, DSAS, karbon, akurasi peta |
| Tabel | 14 tabel laporan (bisa diunduh CSV; tabel seri Landsat tidak ditampilkan) |

Lapisan peta: daratan 2025, kontur topo-batimetri, mangrove eksisting (digitasi 2025), Sentinel-2 SR 2,5 m (2018–2026, tanpa 2022), RBI 2022, plot vegetasi, titik kualitas air/groundcheck, sumur, foto hemispherical, transek DSAS, garis pantai tahunan, lokasi prioritas.

## Memperbarui data

1. Perbarui berkas sumber di folder proyek (`03_DATABASE_MANGROVE/05_Basis_Data_Spasial`, `04_PENGOLAHAN_ANALISIS`).
2. Jalankan:
   ```
   pip install geopandas pyogrio openpyxl rasterio scipy
   python scripts/build_data.py "D:/06_Work/12_SUDIN/Mangrove"
   ```
   Skrip membaca `MGV-KS_HasilAnalisis_KS_v03.gpkg`, kesesuaian & prioritas v04 (`08_Kesesuaian_Pemulihan/MGV-KS_Kesesuaian_KS_v04.xlsx`, `09_Lokasi_Prioritas/MGV-KS_LokasiPrioritas_KS_v04.gpkg`; elevasi berdatum pasut), raster kelas `MGV-KS_S2SR_2018-2026/<KODE>/*_Kerapatan.tif`, `MGV-KS_DigitasiMangrove2025_*.shp` dan tabel `*_v03.xlsx`, angin & gelombang 4 musim (`13_Oseanografi_Fisik/MGV-KS_Gelombang4Musim_v03/MGV-KS_Gelombang4Musim_KS_v03.xlsx`, 10 pulau) serta kontur batimetri SDB untuk Pari, Panggang, Kelapa (`MGV-KS_Batimetri_<KODE>_v01.tif`), lalu menulis ulang `data/*.geojson` dan `data/statistik.json`. Jika versi naik (v04), ganti nama berkas di bagian atas skrip.
3. Data primer baru yang belum masuk basis data v03 (titik kualitas air, sumur) dibaca dari `02_DATA_PRIMER/<PULAU>/` sesuai daftar `PRIMER_BARU` di awal skrip. Titik v03 dipertahankan; titik tambahan dari survei digabungkan sebagai data biasa. Groundcheck vegetasi (`05_Groundcheck/MGV-KS_Survei_<KODE>_Groundcheck.shp`) untuk pulau di daftar `veg` (belum ada di v03) ditambahkan ke lapisan foto hemispherical; jumlah plot = kombinasi transek–jarak, LAI/tutupan dihitung dari foto yang sudah diolah (LAI dan keterbukaan 0 = belum diolah). Kosongkan daftar ini setelah basis data v04 terbit.
4. Untuk panel tahapan, edit langsung `data/progres.json` (status: `selesai` / `berjalan` / `belum`).
5. Commit & push — GitHub Pages memperbarui situs dalam 1–2 menit.

## Teknis

HTML + [Leaflet 1.9.4](https://leafletjs.com) + [Chart.js 4.4.1](https://www.chartjs.org), tanpa build. Data asli UTM 48S (EPSG:32748) dikonversi ke WGS84 dan disederhanakan 0,5–4 m.

## Pembaruan otomatis

Tugas terjadwal Claude mengecek folder Mangrove setiap sore. `scripts/cek_sumber.py` membandingkan waktu ubah berkas sumber dengan `data/_manifest_sumber.json`; bila ada yang berubah, berkas yang diperlukan diambil, `build_data.py` dijalankan, lalu hasilnya di-commit & push ke GitHub. Pulau dengan data survei kualitas air/sumur yang lebih baru dari basis data diatur di `scripts/primer_baru.json`. Nilai di luar rentang wajar (`RENTANG` di `build_data.py`) otomatis tidak ditampilkan.
