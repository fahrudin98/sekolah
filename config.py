import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "ganti_dengan_secret_key_kuat"

    # Flask-Mail
    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME") or "youremail@gmail.com"
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD") or "app-password-atau-smtp-password"
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER") or ("MyApp", "no-reply@example.com")

    # Token reset password
    PASSWORD_RESET_TOKEN_EXPIRATION = 3600

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///sekolah.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False