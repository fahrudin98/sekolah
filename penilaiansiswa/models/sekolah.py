from penilaiansiswa import db
from sqlalchemy import Enum
from .users import LogMixin  # hanya LogMixin, hindari circular import
from datetime import datetime, timedelta

# =============================================================
# ⭐ BARU: MASTER TAHUN AJARAN (dibuat oleh super admin)
# =============================================================
class MasterTahunAjaran(db.Model):
    """Master tahun ajaran yang dikelola oleh super admin"""
    __tablename__ = "master_tahun_ajaran"
    
    id = db.Column(db.Integer, primary_key=True)
    tahun_ajaran = db.Column(db.String(20), nullable=False)  # "2025/2026"
    semester = db.Column(db.String(10), nullable=False)      # "ganjil" / "genap"
    
    # Status
    is_active = db.Column(db.Boolean, default=True)           # Tampil di pilihan sekolah?
    is_global_active = db.Column(db.Boolean, default=False)   # Untuk report kabupaten
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relasi
    creator = db.relationship("User", foreign_keys=[created_by])
    
    __table_args__ = (
        db.UniqueConstraint('tahun_ajaran', 'semester', name='uq_master_tahun_semester'),
    )
    
    @property
    def display_name(self):
        return f"{self.tahun_ajaran} - {self.semester.capitalize()}"
    
    def __repr__(self):
        return self.display_name


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
    
    status_aktif = db.Column(db.Boolean, nullable=False, default=False)
    tanggal_aktivasi = db.Column(db.DateTime, nullable=True)
    tanggal_kadaluarsa = db.Column(db.DateTime, nullable=True)
    last_warning_sent = db.Column(db.Date, nullable=True)
    
    # ========== HELPER ==========
    
    def aktivasi(self, masa_berlaku_hari=365):
        """Aktivasi sekolah (dipanggil dari form aktivasi)"""
        self.status_aktif = True
        self.tanggal_aktivasi = datetime.utcnow()
        self.tanggal_kadaluarsa = self.tanggal_aktivasi + timedelta(days=masa_berlaku_hari)
        self.last_warning_sent = None
        
    def nonaktifkan(self):
        """Nonaktifkan sekolah"""
        self.status_aktif = False
        
    def perpanjang(self, tambahan_hari=365):
        """Perpanjang masa aktif (dipanggil dari form perpanjangan)"""
        if self.tanggal_kadaluarsa and self.tanggal_kadaluarsa > datetime.utcnow():
            # Jika masih aktif, tambah dari kadaluarsa lama
            self.tanggal_kadaluarsa = self.tanggal_kadaluarsa + timedelta(days=tambahan_hari)
        else:
            # Jika sudah kadaluarsa atau belum pernah aktif, mulai dari sekarang
            self.tanggal_kadaluarsa = datetime.utcnow() + timedelta(days=tambahan_hari)
        self.status_aktif = True
        self.last_warning_sent = None
    def cek_dan_nonaktifkan_jika_kadaluarsa(self):
        """Cek apakah sekolah sudah melewati tanggal kadaluarsa.
        Jika ya, nonaktifkan otomatis.
        Return True jika masih aktif, False jika tidak aktif.
        """
        if not self.status_aktif:
            return False
            
        if self.tanggal_kadaluarsa and self.tanggal_kadaluarsa.date() < datetime.utcnow().date():
            self.status_aktif = False
            db.session.commit()
            return False
            
        return True
    @property
    def is_active(self):
        """Cek apakah sekolah aktif dan belum kadaluarsa"""
        if not self.status_aktif:
            return False
        if self.tanggal_kadaluarsa is None:
            return True
        return self.tanggal_kadaluarsa.date() >= datetime.utcnow().date()
    
    @property
    def sisa_hari(self):
        """Sisa hari aktif (None jika tidak terbatas atau belum aktif)"""
        if not self.status_aktif or self.tanggal_kadaluarsa is None:
            return None
        return (self.tanggal_kadaluarsa.date() - datetime.utcnow().date()).days

class TahunAjaran(db.Model, LogMixin):
    __tablename__ = "tahun_ajaran"
    id = db.Column(db.Integer, primary_key=True)
    sekolah_id = db.Column(db.Integer, db.ForeignKey("sekolah.id"))
    
    # ⭐ KOLOM BARU: foreign key ke master
    master_ta_id = db.Column(db.Integer, db.ForeignKey("master_tahun_ajaran.id"), nullable=True)
    
    # ⭐ Kolom ini jadi nullable=True (karena nanti bisa ambil dari master)
    tahun_ajaran = db.Column(db.String(20), nullable=True)
    
    # ⭐ Kolom ini jadi nullable=True (karena nanti bisa ambil dari master)
    semester = db.Column(db.String(20), nullable=True)
    
    kepala_sekolah_id = db.Column(db.Integer, db.ForeignKey("pegawai.id"))
    aktif = db.Column(db.Boolean, default=False)

    # Relasi
    sekolah = db.relationship("Sekolah", back_populates="tahun_ajaran")
    kepala_sekolah = db.relationship("Pegawai", backref="tahun_ajaran_kepala")
    kelas = db.relationship("Kelas", back_populates="tahun_ajaran")
    
    # ⭐ RELASI KE MASTER
    master = db.relationship("MasterTahunAjaran", foreign_keys=[master_ta_id], backref="tahun_ajaran_list")
    
    # ========== PROPERTY UNTUK AKSES DATA ==========
    
    @property
    def tahun_ajaran_display(self):
        """Ambil tahun ajaran - prioritas dari master jika ada"""
        if self.master:
            return self.master.tahun_ajaran
        return self.tahun_ajaran or "-"
    
    @property
    def semester_display(self):
        """Ambil semester - prioritas dari master jika ada"""
        if self.master:
            return self.master.semester
        return self.semester or "-"
    
    @property
    def full_display(self):
        """Tampilan lengkap: '2025/2026 - Ganjil'"""
        sem = self.semester_display
        return f"{self.tahun_ajaran_display} - {sem.capitalize() if sem else '-'}"
    
    @property
    def nama_kepala_sekolah(self):
        """Ambil nama kepala sekolah (dari relasi ke pegawai, lalu ke user)"""
        if self.kepala_sekolah and self.kepala_sekolah.user:
            return self.kepala_sekolah.user.nama_lengkap
        return "-"
    
    @property 
    def nip_kepala_sekolah(self):
        """Ambil NIP kepala sekolah"""
        if self.kepala_sekolah:
            return self.kepala_sekolah.nip or "-"
        return "-"

class Kelas(db.Model, LogMixin):
    __tablename__ = "kelas"
    id = db.Column(db.Integer, primary_key=True)
    tahun_ajaran_id = db.Column(db.Integer, db.ForeignKey("tahun_ajaran.id"), nullable=False)
    nama_kelas = db.Column(db.String(50))
    tingkat = db.Column(db.Integer, default=1)
    wali_kelas_id = db.Column(db.Integer, db.ForeignKey("pegawai.id"))

    sekolah_id = db.Column(db.Integer, db.ForeignKey("sekolah.id"), nullable=False)

    tahun_ajaran = db.relationship("TahunAjaran", back_populates="kelas")
    wali_kelas = db.relationship("Pegawai")
    sekolah = db.relationship("Sekolah")

class Siswa(db.Model, LogMixin):
    __tablename__ = "siswa"
    id = db.Column(db.Integer, primary_key=True)
    nama_siswa = db.Column(db.String(100), nullable=False)
    nisn = db.Column(db.String(20), unique=False, nullable=False)  # ✅ TAMBAH INI
    jenis_kelamin = db.Column(db.Enum('L', 'P'), nullable=False)
    status = db.Column(db.String(20), default='Aktif')
    kelas_id = db.Column(db.Integer, db.ForeignKey('kelas.id'))
    
    kelas = db.relationship('Kelas', backref='siswa')
    __table_args__ = (
        db.UniqueConstraint('nisn', 'kelas_id', name='uq_nisn_per_kelas'),
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

    siswa = db.relationship("Siswa", backref="kebiasaan_list")
    kelas = db.relationship("Kelas")


# ====================== RIWAYAT PEGAWAI SEKOLAH ===========================
class PegawaiSekolahHistory(db.Model, LogMixin):
    __tablename__ = "pegawai_sekolah_history"
    id = db.Column(db.Integer, primary_key=True)
    pegawai_id = db.Column(db.Integer, db.ForeignKey("pegawai.id"), nullable=False)
    sekolah_id = db.Column(db.Integer, db.ForeignKey("sekolah.id"), nullable=False)
    tahun_ajaran_id = db.Column(db.Integer, db.ForeignKey("tahun_ajaran.id"))
    aktif = db.Column(db.Boolean, default=True)  # True = sekolah saat ini, False = sebelumnya