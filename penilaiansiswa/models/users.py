from datetime import datetime
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
from penilaiansiswa import db  # gunakan db yang di-init di __init__.py

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    nama_lengkap = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # superadmin, user biasa

    pegawai = db.relationship("Pegawai", back_populates="user", uselist=False, foreign_keys="Pegawai.user_id")  
    @property
    def is_superadmin(self):
        return self.role == "superadmin"

#TAMBAHAN UNTUK RESET PASSWORD

    # 🔹 hash password baru
    def set_password(self, password):
        self.password = generate_password_hash(password)

    # 🔹 verifikasi password saat login
    def check_password(self, password):
        return check_password_hash(self.password, password)

    # 🔹 generate token untuk reset password
    def get_reset_token(self, expires_sec=None):
        expires = expires_sec or current_app.config.get("PASSWORD_RESET_TOKEN_EXPIRATION", 3600)
        s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        return s.dumps({"user_id": self.id}, salt="password-reset-salt")

    # 🔹 verifikasi token dan kembalikan user
    @staticmethod
    def verify_reset_token(token, max_age=None):
        s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        max_age = max_age or current_app.config.get("PASSWORD_RESET_TOKEN_EXPIRATION", 3600)
        try:
            data = s.loads(token, salt="password-reset-salt", max_age=max_age)
        except Exception:
            return None
        user_id = data.get("user_id")
        return User.query.get(user_id)
#TAMBAHAN UNTUK RESET PASSWORD

class LogMixin:
    """Mixin untuk mencatat created/updated + user"""
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"))

class Pegawai(db.Model, LogMixin):
    __tablename__ = "pegawai"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    sekolah_id = db.Column(db.Integer, db.ForeignKey("sekolah.id"))
    nip = db.Column(db.String(50), unique=True)

    user = db.relationship("User", back_populates="pegawai", foreign_keys=[user_id])
    sekolah = db.relationship("Sekolah", back_populates="pegawai")
    
    # property menjelaskan p.nama = p.user.nama
    @property
    def nama(self):
        return self.user.nama_lengkap if self.user else None
    
