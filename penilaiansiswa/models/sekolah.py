from penilaiansiswa import db
from sqlalchemy import Enum
from .users import LogMixin  # hanya LogMixin, hindari circular import

# =============================================================
# Wilayah Administratif
# =============================================================
class Provinsi(db.Model):
    __tablename__ = "provinsi"
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(50), nullable=False)

class Kabupaten(db.Model):
    __tablename__ = "kabupaten"
    id = db.Column(db.Integer, primary_key=True)
    provinsi_id = db.Column(db.Integer, db.ForeignKey("provinsi.id"))
    nama = db.Column(db.String(50), nullable=False)

    provinsi = db.relationship("Provinsi", backref="kabupaten_list")
    
class Kecamatan(db.Model):
    __tablename__ = "kecamatan"
    id = db.Column(db.Integer, primary_key=True)
    kabupaten_id = db.Column(db.Integer, db.ForeignKey("kabupaten.id"))
    nama = db.Column(db.String(50), nullable=False)

    kabupaten = db.relationship("Kabupaten", backref="kecamatan_list")
# =============================================================
# Sekolah dan Akademik
# =============================================================
class Sekolah(db.Model, LogMixin):
    __tablename__ = "sekolah"
    id = db.Column(db.Integer, primary_key=True)
    kecamatan_id = db.Column(db.Integer, db.ForeignKey("kecamatan.id"))
    nama_sekolah = db.Column(db.String(100), nullable=False)
    npsn = db.Column(db.String(50), unique=True)
    jenjang = db.Column(db.String(20))

    pegawai = db.relationship("Pegawai", back_populates="sekolah")
    tahun_ajaran = db.relationship("TahunAjaran", back_populates="sekolah")

    kecamatan = db.relationship("Kecamatan", backref="sekolah_list")
    

class TahunAjaran(db.Model, LogMixin):
    __tablename__ = "tahun_ajaran"
    id = db.Column(db.Integer, primary_key=True)
    sekolah_id = db.Column(db.Integer, db.ForeignKey("sekolah.id"))
    tahun_ajaran = db.Column(db.String(20), nullable=False)  # contoh: 2025/2026
    semester = db.Column(db.String(20), nullable=False)
    kepala_sekolah_id = db.Column(db.Integer, db.ForeignKey("pegawai.id"))
    aktif = db.Column(db.Boolean, default=False) 

    sekolah = db.relationship("Sekolah", back_populates="tahun_ajaran")
    kepala_sekolah = db.relationship("Pegawai")
    kelas = db.relationship("Kelas", back_populates="tahun_ajaran")


class Kelas(db.Model, LogMixin):
    __tablename__ = "kelas"
    id = db.Column(db.Integer, primary_key=True)
    tahun_ajaran_id = db.Column(db.Integer, db.ForeignKey("tahun_ajaran.id"), nullable=False)
    nama_kelas = db.Column(db.String(50))
    wali_kelas_id = db.Column(db.Integer, db.ForeignKey("pegawai.id"))

    sekolah_id = db.Column(db.Integer, db.ForeignKey("sekolah.id"), nullable=False)

    tahun_ajaran = db.relationship("TahunAjaran", back_populates="kelas")
    wali_kelas = db.relationship("Pegawai")
    sekolah = db.relationship("Sekolah")

class Siswa(db.Model, LogMixin):
    __tablename__ = "siswa"
    id = db.Column(db.Integer, primary_key=True)
    kelas_id = db.Column(db.Integer, db.ForeignKey("kelas.id"))
    nama_siswa = db.Column(db.String(100))
    jenis_kelamin = db.Column(Enum("L", "P", name="jenis_kelamin_enum"), nullable=False)
    status = db.Column(db.String(50))

    kelas = db.relationship("Kelas")
    kebiasaans = db.relationship(
        "Kebiasaan",
        backref="siswa",
        cascade="all, delete-orphan"
    )
class Kebiasaan(db.Model, LogMixin):
    __tablename__ = "kebiasaan"
    id = db.Column(db.Integer, primary_key=True)
    siswa_id = db.Column(db.Integer, db.ForeignKey("siswa.id"))
    kelas_id = db.Column(db.Integer, db.ForeignKey("kelas.id"))
    bulan = db.Column(db.String(7), nullable=False)  # format YYYY-MM

    # Nilai 7 kebiasaan
    bangun_pagi = db.Column(db.Integer)
    beribadah = db.Column(db.Integer)
    berolahraga = db.Column(db.Integer)
    sehat_dan_lemar = db.Column(db.Integer)
    belajar = db.Column(db.Integer)
    bermasyarakat = db.Column(db.Integer)
    tidur_cepat = db.Column(db.Integer)

    catatan = db.Column(db.Text)

    siswa_id = db.Column(db.Integer, db.ForeignKey("siswa.id"))
    kelas = db.relationship("Kelas")


# ====================== RIWAYAT PEGAWAI SEKOLAH ===========================
class PegawaiSekolahHistory(db.Model, LogMixin):
    __tablename__ = "pegawai_sekolah_history"
    id = db.Column(db.Integer, primary_key=True)
    pegawai_id = db.Column(db.Integer, db.ForeignKey("pegawai.id"), nullable=False)
    sekolah_id = db.Column(db.Integer, db.ForeignKey("sekolah.id"), nullable=False)
    tahun_ajaran_id = db.Column(db.Integer, db.ForeignKey("tahun_ajaran.id"))
    aktif = db.Column(db.Boolean, default=True)  # True = sekolah saat ini, False = sebelumnya