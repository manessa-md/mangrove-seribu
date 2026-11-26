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

Lapisan peta: daratan 2025, kontur topo-batimetri, mangrove eksisting (digitasi 2025), Sentinel-2 SR 2,5 m (2018–2026, tanpa 2022), RBI 2022, plot vegetasi, titik kualitas air/groundcheck, sumur, foto hemispherical, transek DSAS, garis pantai tahunan, lokasi prioritas, persetujuan masyarakat (FGD).

## Memperbarui data

1. Perbarui berkas sumber di folder proyek (`03_DATABASE_MANGROVE/05_Basis_Data_Spasial`, `04_PENGOLAHAN_ANALISIS`).
2. Jalankan:
   ```
   pip install geopandas pyogrio openpyxl rasterio scipy
   python scripts/build_data.py "D:/06_Work/12_SUDIN/Mangrove"
   ```
   Skrip membaca `MGV-KS_HasilAnalisis_KS_v03.gpkg`, kesesuaian & prioritas v04 (`08_Kesesuaian_Pemulihan/MGV-KS_Kesesuaian_KS_v04.xlsx`, `09_Lokasi_Prioritas/MGV-KS_LokasiPrioritas_KS_v04.gpkg`; elevasi berdatum pasut), raster kelas `MGV-KS_S2SR_2018-2026/<KODE>/*_Kerapatan.tif`, `MGV-KS_DigitasiMangrove2025_*.shp` dan tabel `*_v03.xlsx`, angin & gelombang 4 musim (`13_Oseanografi_Fisik/MGV-KS_Gelombang4Musim_v03/MGV-KS_Gelombang4Musim_KS_v03.xlsx`, 10 pulau) serta kontur batimetri SDB untuk Pari, Panggang, Kelapa (`MGV-KS_Batimetri_<KODE>_v01.tif`), lalu menulis ulang `data/*.geojson` dan `data/statistik.json`. Jika versi naik (v04), ganti nama berkas di bagian atas skrip.
3. Data primer baru yang belum masuk basis data v03 (titik kualitas air, sumur) dibaca dari `02_DATA_PRIMER/<PULAU>/` sesuai daftar `PRIMER_BARU` di awal skrip. Titik v03 dipertahankan; titik tambahan dari survei digabungkan sebagai data biasa. Groundcheck vegetasi (`05_Groundcheck/MGV-KS_Survei_<KODE>_Groundcheck.shp`) untuk pulau di daftar `veg` (belum ada di v03) ditambahkan ke lapisan foto hemispherical; jumlah plot = kombinasi transek–jarak, LAI/tutupan dihitung dari foto yang sudah diolah (LAI dan keterbukaan 0 = belum diolah). Kosongkan daftar ini setelah basis data v04 terbit.
4. Batimetri Lancang belum punya versi olahan `MGV-KS_Batimetri_LCG_v01.tif`; sementara kontur LCG dibuat oleh `scripts/bati_sekunder.py` (dipanggil di akhir `build_data.py`) dari `01_DATA_SEKUNDER/05_Oseanografi/Batimetri/batimetri_Lancang.tif` (10 m, datum tidak tertulis) yang digeser ke MSL pasut lokal sebesar median selisihnya terhadap `MGV-KS_TopoBatimetri_LCG_v04.tif`. Bila v01 terbit, tambahkan `LCG` ke daftar v01 di `build_data.py` dan skrip ini otomatis tidak dipakai.
5. Analisis pemulihan ditampilkan sebagai dua lapisan oleh `scripts/build_analisis.py` (dipanggil di akhir `build_data.py`; versi kesesuaian = `MGV-KS_Kesesuaian_KS_v*.xlsx` tertinggi, kini v08; versi prioritas = `MGV-KS_LokasiPrioritas_KS_v*.gpkg` tertinggi secara terpisah, kini v09, layer `lokasi_prioritas[_vNN]`, kelas Tinggi/Sedang/Rendah/Rekayasa): (1) **kesesuaian lahan AHP** dari `08_Kesesuaian_Pemulihan/MGV-KS_Kesesuaian_<KODE>_vNN.tif` (S1–S3) → `data/kesesuaian_ahp.geojson`; (2) **prioritas pemulihan** = poligon prioritas AHP (`09_Lokasi_Prioritas/MGV-KS_LokasiPrioritas_KS_vNN.gpkg`, Tinggi/Sedang/Rendah) dipotong dengan area FGD "Setuju" → `data/prioritas_masyarakat.geojson`; area "Tidak setuju" dan area tanpa FGD tidak menjadi prioritas. Ringkasan per pulau di `data/analisis.json`; Tabel 13 & 14 diperbarui dari versi yang sama. Kesesuaian v05 (18 Nov 2026): batas bawah elevasi sesuai = min(LLWS, P05 elevasi mangrove eksisting), dasar di bawah LLWS paling tinggi S3, sel mangrove eksisting tidak pernah N; Lancang, Panggang, Kelapa memakai batimetri baru (kontur PGG/KLP/TDG dari topo-batimetri v05 dan Sebira dari topo-batimetri v04 oleh `bati_sekunder.py`). Tidung v05: sel 'daratan' palsu dari DTM LiDAR di laut (> 20 m dari daratan 2025) diganti batimetri atau dikosongkan (skrip di `04_PENGOLAHAN_ANALISIS/10_Skrip/Python_R/v05_kesesuaian`). Kesesuaian v06: kriteria gelombang dari model 4 musim v03 (Hs maks HHWS, diredam breakwater Kt 0,5/0,6/0,8; ambang dari Hs di sel mangrove eksisting) untuk 10 pulau; sel ≤ 25 m dari jalur kapal dan ≤ 5 m dari struktur pantai dikeluarkan (skrip di `10_Skrip/Python_R/v06_kesesuaian`). Kesesuaian v07 (24 Nov 2026): sama dengan v06 kecuali kriteria substrat (Allen Coral Atlas + titik lapangan); prioritas v08 dibangun darinya dan dipakai rencana aksi v05. Kesesuaian v08 (26 Nov 2026): bobot AHP & ambang tetap; ACA hanya dipakai sebagai pembatas karang/lamun (validasi ACA lemah), koreksi DEM Panggang & Tidung, daratan 2025 dikeluarkan; prioritas v09 dan rencana aksi v08 (Laporan Akhir v10) dibangun darinya.
6. Area yang disetujui / tidak disetujui masyarakat untuk ditanami mangrove (hasil FGD) dibaca dari `02_DATA_PRIMER/<PULAU>/09_Sosek/Rekomendasi_<KODE>.shp` (kolom `Keterangan`: `Masyarakat S` / `Masyarakat TS`, teks tambahan dalam kurung jadi catatan) oleh `scripts/build_sosek.py` (dipanggil otomatis di akhir `build_data.py`, bisa juga dijalankan sendiri) → `data/persetujuan_masyarakat.geojson` dan `data/sosek.json`. Kuesioner `09_Sosek/MGV-KS_Survei_<KODE>_Sosek.xlsx` diringkas per pulau (jumlah jawaban per kategori, `data/sosek.json` → panel Per pulau) dan Tabel 15 dihitung ulang darinya; nama, telepon, lokasi rumah, dan jawaban isian bebas tidak diterbitkan.
7. Angin & gelombang per pulau (arah angin, arah gelombang, Hs P90 dan Hs maks/ekstrem per musim, muka air HHWS) dan lapisan panah gelombang/angin dibuat oleh `scripts/build_gelombang.py` dari `13_Oseanografi_Fisik/MGV-KS_Gelombang4Musim_v03` (RINGKASAN + `*_<MUSIM>_HHWS_50m_v03.tif`) → `data/gelombang.json`, `data/gelombang_<MUSIM>.geojson`, `data/angin.geojson`.
8. Untuk panel tahapan, edit langsung `data/progres.json` (status: `selesai` / `berjalan` / `belum`).
   Struktur pantai & jalur kapal: `scripts/build_infrastruktur.py` membaca `01_DATA_SEKUNDER/12_Break_Water/SHP_Breakwater_Per_Pulau/*/Breakwater_*.shp` dan `01_DATA_SEKUNDER/11_Jalur_Kapal/01_Per_Pulau/*/Jalur_Kapal_*.shp` → `data/struktur_pantai.geojson`, `data/jalur_kapal.geojson`, `data/infrastruktur.json` (ditampilkan di sub-tab Pesisir).
   Strategi & rencana aksi: `scripts/build_strategi.py` membaca versi tertinggi `06_STRATEGI_RENCANA_AKSI/03_Rencana_Aksi/MGV-KS_RencanaAksi_KS_vNN.xlsx`, `MGV-KS_LokasiAksi_KS_vNN.gpkg`, `MGV-KS_PetaTahapRencanaAksi_KS_vNN.png` dan bab strategi `02_Strategi_Pemulihan/MGV-KS_StrategiRencanaAksi_KS_vNN.docx` → `data/strategi.json`, `data/rencana_aksi.geojson`, `data/peta_rencana_aksi.png` (tab Strategi, lapisan "Lokasi rencana aksi", ringkasan per pulau di sub-tab Pemulihan).
   Plot vegetasi pulau yang belum ada di basis data v03 (`primer_baru.json["veg"]`, kini Sebira): `scripts/veg_primer.py` membaca `02_DATA_PRIMER/<PULAU>/05_Groundcheck/MGV-KS_Survei_<KODE>_Groundcheck.shp` (Transek + jarak = plot; Grid 10×10/5×5/2×2 = pohon/pancang/semai; DBH = keliling/π) dan menambahkannya ke `data/plot_vegetasi.geojson` serta Tabel 1–6 & ringkasan dengan metode yang sama dengan v03.
9. Commit & push — GitHub Pages memperbarui situs dalam 1–2 menit.

## Teknis

HTML + [Leaflet 1.9.4](https://leafletjs.com) + [Chart.js 4.4.1](https://www.chartjs.org), tanpa build. Data asli UTM 48S (EPSG:32748) dikonversi ke WGS84 dan disederhanakan 0,5–4 m.

## Pembaruan otomatis

Tugas terjadwal Claude mengecek folder Mangrove setiap sore. `scripts/cek_sumber.py` membandingkan waktu ubah berkas sumber dengan `data/_manifest_sumber.json`; bila ada yang berubah, berkas yang diperlukan diambil, `build_data.py` dijalankan, lalu hasilnya di-commit & push ke GitHub. Pulau dengan data survei kualitas air/sumur yang lebih baru dari basis data diatur di `scripts/primer_baru.json`. Nilai di luar rentang wajar (`RENTANG` di `build_data.py`) otomatis tidak ditampilkan.
