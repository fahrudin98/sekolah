import pandas as pd
from main import app
from penilaiansiswa import db
from penilaiansiswa.models import Provinsi, Kabupaten, Kecamatan, Sekolah

app.app_context().push()

# Baca Excel
df = pd.read_excel("data_sekolah.xlsx")

for _, row in df.iterrows():
    # --- NPSN di-cast string biar aman ---
    npsn = str(row["NPSN"]).strip()

    # === PROVINSI ===
    provinsi = Provinsi.query.filter_by(nama=row["Provinsi"]).first()
    if not provinsi:
        provinsi = Provinsi(nama=row["Provinsi"])
        db.session.add(provinsi)
        db.session.flush()

    # === KABUPATEN ===
    kabupaten = Kabupaten.query.filter_by(
        nama=row["Kabupaten"], provinsi_id=provinsi.id
    ).first()
    if not kabupaten:
        kabupaten = Kabupaten(nama=row["Kabupaten"], provinsi=provinsi)
        db.session.add(kabupaten)
        db.session.flush()

    # === KECAMATAN ===
    kecamatan = Kecamatan.query.filter_by(
        nama=row["KECAMATAN"], kabupaten_id=kabupaten.id
    ).first()
    if not kecamatan:
        kecamatan = Kecamatan(nama=row["KECAMATAN"], kabupaten=kabupaten)
        db.session.add(kecamatan)
        db.session.flush()

    # === SEKOLAH ===
    sekolah = Sekolah.query.filter_by(npsn=npsn).first()
    if not sekolah:
        sekolah = Sekolah(
            nama_sekolah=row["NAMA SATUAN PENDIDIKAN"],
            npsn=npsn,
            jenjang=row["BENTUK PENDIDIKAN"],
            kecamatan=kecamatan
        )
        db.session.add(sekolah)

# Commit semua
db.session.commit()
print("✅ Data berhasil diimport ke MySQL")