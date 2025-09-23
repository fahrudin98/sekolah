import os
from dotenv import load_dotenv
from penilaiansiswa import db
from penilaiansiswa.models.users import User
from werkzeug.security import generate_password_hash

# Load environment variables first
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from passlib.hash import bcrypt
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail
import calendar

# Import config
from config import config

# =============================
# PASSWORD HELPER FUNCTIONS
# =============================
def generate_password_hash(password):
    """Generate bcrypt hash untuk password"""
    return bcrypt.hash(password)

def check_password_hash(hashed_password, password):
    """Verifikasi password dengan bcrypt"""
    return bcrypt.verify(password, hashed_password)

def create_app(config_name="default"):
    # Determine config based on environment
    if os.environ.get("FLASK_ENV") == "production":
        config_name = "production"
    else:
        config_name = "development"
    
    # ✅ HAPUS template_folder dan static_folder
    # Flask otomatis akan mencari di ./templates dan ./static
    app = Flask(__name__)
    
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    from penilaiansiswa import db, login_manager, mail, migrate
    
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    
    # Setup login manager
    login_manager.login_view = "index"
    login_manager.login_message = "Silakan login untuk mengakses halaman ini."
    login_manager.login_message_category = "warning"
    
    from penilaiansiswa.models.users import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # =============================
    # BASIC ROUTES
    # =============================
    @app.route("/")
    def index():
        return render_template("landing.html")
    
    @app.route("/signup", methods=["POST"])
    def signup():
        nama = request.form.get("nama")
        email = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")

        if not all([nama, email, username, password]):
            flash("Semua field harus diisi!", "danger")
            return redirect(url_for("index"))

        from penilaiansiswa.models.users import User
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            flash("Username atau email sudah digunakan!", "danger")
            return redirect(url_for("index"))

        new_user = User(
            nama_lengkap=nama,
            email=email,
            username=username,
            password=generate_password_hash(password),
            role="user"
        )
        
        db.session.add(new_user)
        try:
            db.session.commit()
            flash("Registrasi berhasil! Silakan login.", "success")
        except Exception as e:
            db.session.rollback()
            flash("Terjadi error saat registrasi. Silakan coba lagi.", "danger")
            app.logger.error(f"Signup error: {str(e)}")
        
        return redirect(url_for("index"))
    
    @app.route("/login", methods=["POST"])
    def login():
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("Username dan password harus diisi!", "danger")
            return redirect(url_for("index"))

        from penilaiansiswa.models.users import User
        from flask_login import login_user
        
        user = User.query.filter_by(username=username).first()
        
        if user:
            try:
                # Verifikasi password dengan bcrypt
                if check_password_hash(user.password, password):
                    login_user(user)
                   # flash(f"Selamat datang, {user.nama_lengkap}!", "success")
                    
                    if hasattr(user, 'pegawai') and user.pegawai:
                        return redirect(url_for("tahun_ajaran.dashboard"))
                    else:
                        return redirect(url_for("home"))
                else:
                    flash("Username atau password salah!", "danger")
            except Exception as e:
                # Handle kemungkinan hash corrupted
                flash("Password hash bermasalah. Silakan reset password atau hubungi admin.", "danger")
                app.logger.error(f"Login error for user {username}: {e}")
        else:
            flash("Username atau password salah!", "danger")
        
        return redirect(url_for("index"))
    
    @app.route("/home")
    @login_required
    def home():
        from penilaiansiswa.models.sekolah import Provinsi
        from penilaiansiswa.models.users import Pegawai
        
        provinsi_list = Provinsi.query.all()
        pegawai = Pegawai.query.filter_by(user_id=current_user.id).first()

        return render_template(
            "home.html",
            user=current_user,
            username=current_user.username,
            provinsi_list=provinsi_list,
            pegawai=pegawai,
        )
    
    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        #flash("Anda berhasil logout!", "info")
        return redirect(url_for("index"))
    
    @app.route("/change-password", methods=["POST"])
    @login_required
    def change_password():
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Data tidak valid"})
            
        current_pw = data.get("current_password")
        new_pw = data.get("new_password")
        
        if not current_pw or not new_pw:
            return jsonify({"success": False, "message": "Data tidak lengkap"})

        try:
            if not check_password_hash(current_user.password, current_pw):
                return jsonify({"success": False, "message": "Password saat ini salah"})

            current_user.password = generate_password_hash(new_pw)
            db.session.commit()
            
            return jsonify({"success": True, "message": "Password berhasil diubah"})
        except Exception as e:
            return jsonify({"success": False, "message": f"Error: {str(e)}"})
    
    # =============================
    # PASSWORD MIGRATION ENDPOINT (Optional)
    # =============================
    @app.route("/admin/migrate-passwords")
    def migrate_passwords():
        """Endpoint untuk migrasi password yang rusak ke bcrypt"""
        from penilaiansiswa.models.users import User
        
        users = User.query.all()
        migrated_count = 0
        
        for user in users:
            try:
                # Coba verifikasi dengan dummy password
                bcrypt.verify("dummy", user.password)
            except:
                # Hash rusak, reset ke default
                user.password = generate_password_hash("default123")
                migrated_count += 1
                app.logger.info(f"Migrated user: {user.username}")
        
        if migrated_count > 0:
            db.session.commit()
            return f"Migrated {migrated_count} passwords to bcrypt"
        else:
            return "No passwords need migration"
    
    # =============================
    # BLUEPRINT REGISTRATION
    # =============================
    try:
        from penilaiansiswa.routes.routes import pegawai_bp
        app.register_blueprint(pegawai_bp)
    except ImportError as e:
        app.logger.warning(f"Pegawai blueprint not found: {e}")
    
    try:
        from penilaiansiswa.routes.tahun_ajaran_routes import tahun_ajaran_bp
        app.register_blueprint(tahun_ajaran_bp, url_prefix="/tahun_ajaran")
    except ImportError as e:
        app.logger.warning(f"Tahun ajaran blueprint not found: {e}")
    
    try:
        from penilaiansiswa.routes.kelas_routes import kelas_bp
        app.register_blueprint(kelas_bp)
    except ImportError as e:
        app.logger.warning(f"Kelas blueprint not found: {e}")
    
    try:
        from penilaiansiswa.routes import siswa_routes
        app.register_blueprint(siswa_routes.siswa_bp)
    except ImportError as e:
        app.logger.warning(f"Siswa blueprint not found: {e}")
    
    try:
        from penilaiansiswa.routes.penilaian_routes import penilaian_bp
        app.register_blueprint(penilaian_bp)
    except ImportError as e:
        app.logger.warning(f"Penilaian blueprint not found: {e}")
    
    try:
        from penilaiansiswa.routes.lupa_password_routes import lupa_password_bp
        app.register_blueprint(lupa_password_bp)
    except ImportError as e:
        app.logger.warning(f"Lupa password blueprint not found: {e}")
    
    try:
        from penilaiansiswa.routes.laporan import laporan_bp
        app.register_blueprint(laporan_bp)
    except ImportError as e:
        app.logger.warning(f"Laporan blueprint not found: {e}")
    
    # =============================
    # JINJA2 FILTERS
    # =============================
    @app.template_filter('month_name')
    def month_name_filter(month_number):
        try:
            return calendar.month_name[int(month_number)]
        except (ValueError, IndexError):
            return ""
    
    return app

# Create application instance
app = create_app()

if __name__ == "__main__":
    env = os.environ.get("FLASK_ENV", "development")
    
    if env == "production":
        print("🚀 Running in PRODUCTION mode")
        from waitress import serve
        serve(app, host="0.0.0.0", port=5000)
    else:
        print("🔧 Running in DEVELOPMENT mode")
        app.run(debug=True, host="0.0.0.0", port=5000)

