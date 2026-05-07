# sekolah/utils/import_excel.py
import pandas as pd
from penilaiansiswa import db
from penilaiansiswa.models import Provinsi, Kabupaten, Kecamatan, Sekolah

def import_data_sekolah_from_excel(filepath):
    """
    Import data provinsi, kabupaten, kecamatan, sekolah dari file Excel.
    Kolom yang diharapkan:
    Provinsi, Kabupaten, KECAMATAN, NAMA SATUAN PENDIDIKAN, NPSN, BENTUK PENDIDIKAN
    """
    df = pd.read_excel(filepath)
    
    hasil = {
        'provinsi_baru': 0,
        'kabupaten_baru': 0,
        'kecamatan_baru': 0,
        'sekolah_baru': 0,
        'duplikat': 0
    }
    
    for _, row in df.iterrows():
        # Bersihkan data
        provinsi_nama = str(row['Provinsi']).strip()
        kabupaten_nama = str(row['Kabupaten']).strip()
        kecamatan_nama = str(row['KECAMATAN']).strip()
        nama_sekolah = str(row['NAMA SATUAN PENDIDIKAN']).strip()
        npsn = str(row['NPSN']).strip() if pd.notna(row['NPSN']) else None
        jenjang = str(row['BENTUK PENDIDIKAN']).strip() if pd.notna(row['BENTUK PENDIDIKAN']) else None
        
        # 1. Provinsi
        provinsi = Provinsi.query.filter_by(nama=provinsi_nama).first()
        if not provinsi:
            provinsi = Provinsi(nama=provinsi_nama)
            db.session.add(provinsi)
            db.session.flush()
            hasil['provinsi_baru'] += 1
        
        # 2. Kabupaten
        kabupaten = Kabupaten.query.filter_by(nama=kabupaten_nama, provinsi_id=provinsi.id).first()
        if not kabupaten:
            kabupaten = Kabupaten(nama=kabupaten_nama, provinsi_id=provinsi.id)
            db.session.add(kabupaten)
            db.session.flush()
            hasil['kabupaten_baru'] += 1
        
        # 3. Kecamatan
        kecamatan = Kecamatan.query.filter_by(nama=kecamatan_nama, kabupaten_id=kabupaten.id).first()
        if not kecamatan:
            kecamatan = Kecamatan(nama=kecamatan_nama, kabupaten_id=kabupaten.id)
            db.session.add(kecamatan)
            db.session.flush()
            hasil['kecamatan_baru'] += 1
        
        # 4. Sekolah - cek berdasarkan NPSN atau nama_sekolah + kecamatan
        existing_sekolah = None
        if npsn and npsn != 'nan':
            existing_sekolah = Sekolah.query.filter_by(npsn=npsn).first()
        if not existing_sekolah:
            existing_sekolah = Sekolah.query.filter_by(
                nama_sekolah=nama_sekolah,
                kecamatan_id=kecamatan.id
            ).first()
        
        if not existing_sekolah:
            sekolah = Sekolah(
                nama_sekolah=nama_sekolah,
                npsn=npsn if npsn != 'nan' else None,
                jenjang=jenjang,
                kecamatan_id=kecamatan.id
            )
            db.session.add(sekolah)
            hasil['sekolah_baru'] += 1
        else:
            hasil['duplikat'] += 1
    
    db.session.commit()
    return hasil