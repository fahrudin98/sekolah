# penilaiansiswa/__init__.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()  # ✅ Tambahkan ini
mail = Mail()
migrate = Migrate()

# Export extensions
__all__ = ['db', 'login_manager', 'mail', 'migrate']  # ✅ Tambahkan export