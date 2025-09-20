from datetime import datetime
from penilaiansiswa import db




class LogAktivitas(db.Model):
    __tablename__ = "log_aktivitas"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    aksi = db.Column(db.String(50))  # CREATE, UPDATE, DELETE
    tabel = db.Column(db.String(50))
    entri_id = db.Column(db.Integer)  # ID dari entri yg dimodifikasi
    keterangan = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)