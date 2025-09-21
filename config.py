# config.py
import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # 🔐 KEAMANAN - HARUS di-set via environment variable
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable is required!")
    
    # 🗄️ DATABASE - Ambil SEMUA dari environment variables
    DB_HOST = os.environ.get("DB_HOST", "localhost")  # Biasanya localhost untuk shared hosting
    DB_NAME = os.environ.get("DB_NAME", "kebiasaa_sekolah_app")
    DB_USER = os.environ.get("DB_USER", "kebiasaa_fahrudin98")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "Nurulfarida02102011")
    
    # ✅ STRING KONEKSI YANG BENAR untuk MySQL
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 📧 EMAIL - Ambil SEMUA dari environment variables
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "mail.7kebiasaan.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 465))
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "True").lower() == "true"
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "False").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "admin@7kebiasaan.com")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "admin@7kebiasaan.com")
    
    # 📁 Template & Static Files
    TEMPLATES_FOLDER = os.path.join(basedir, 'penilaiansiswa', 'templates')
    STATIC_FOLDER = os.path.join(basedir, 'penilaiansiswa', 'static')
    
    # ⏰ Token expiration
    PASSWORD_RESET_TOKEN_EXPIRATION = 3600
    
    # 👤 Flask-Login
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    SESSION_PROTECTION = "strong"

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}