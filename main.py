import os
from dotenv import load_dotenv
from penilaiansiswa import db
from penilaiansiswa.models.users import User
from flask_mail import Mail
mail = Mail()

# Load environment variables first
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail
import calendar

# Import config
from config import config

bcrypt = Bcrypt()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()

# =============================
# PASSWORD HELPER FUNCTIONS
# =============================
def generate_password_hash(password):
    """Generate bcrypt hash untuk password"""
    return bcrypt.generate_password_hash(password).decode('utf-8')

def check_password_hash(hashed_password, password):
    """Verifikasi password dengan bcrypt"""
    return bcrypt.check_password_hash(hashed_password, password)

def create_app(config_name="default"):
    # Determine config based on environment
    if os.environ.get("FLASK_ENV") == "production":
        config_name = "production"
    else:
        config_name = "development"
    
    app = Flask(__name__)
    
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    
    # Setup login manager
    login_manager.login_view = "index"
    login_manager.login_message = "Silakan login untuk mengakses halaman ini."
    login_manager.login_message_category = "warning"
    
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

        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            
            # Clear session lama
            session.pop('kepala_sekolah_tahun_ajaran_id', None)
            session.pop('kepala_sekolah_sekolah_id', None)
            session.pop('is_plt', None)
            
            # ========== UPDATE BAGIAN INI ==========
            # Redirect berdasarkan role
            if user.is_superadmin:
                return redirect(url_for("superadmin.dashboard"))
            
            elif user.is_kepala_dinas:
                return redirect(url_for("dinas.dashboard"))
            
            elif user.is_kepala_sekolah():
                # Cek apakah user kepala sekolah di satu atau lebih sekolah
                from penilaiansiswa.models.sekolah import TahunAjaran
                pegawai = user.pegawai
                
                if pegawai:
                    sekolah_kepala_list = TahunAjaran.query.filter_by(
                        kepala_sekolah_id=pegawai.id,
                        aktif=True
                    ).all()
                    
                    if len(sekolah_kepala_list) == 1:
                        # Hanya 1 sekolah -> langsung set session & redirect
                        ta = sekolah_kepala_list[0]
                        session['kepala_sekolah_tahun_ajaran_id'] = ta.id
                        session['kepala_sekolah_sekolah_id'] = ta.sekolah_id
                        session['is_plt'] = (ta.sekolah_id != pegawai.sekolah_id)
                        return redirect(url_for("tahun_ajaran.dashboard_kepala_sekolah"))
                    elif len(sekolah_kepala_list) > 1:
                        # Multiple sekolah -> redirect ke pilihan
                        return redirect(url_for("tahun_ajaran.dashboard_multi_sekolah"))
            
            else:
                # Guru / Wali Kelas biasa
                return redirect(url_for("tahun_ajaran.dashboard"))
            # =======================================
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
        # Clear semua session
        session.clear()
        
        logout_user()
        flash("Anda telah berhasil logout.", "info")
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
            db.session.rollback()
            return jsonify({"success": False, "message": f"Error: {str(e)}"})
    
    # =============================
    # PASSWORD MIGRATION ENDPOINT (Optional)
    # =============================
    @app.route("/admin/migrate-passwords")
    def migrate_passwords():
        """Endpoint untuk migrasi password yang rusak ke bcrypt"""
        users = User.query.all()
        migrated_count = 0
        
        for user in users:
            try:
                # Coba verifikasi dengan dummy password
                check_password_hash(user.password, "dummy")
            except Exception:
                # Hash rusak, reset ke default
                user.password = generate_password_hash("default123")
                migrated_count += 1
                app.logger.info(f"Migrated user: {user.username}")
        
        if migrated_count > 0:
            db.session.commit()
            return f"Migrated {migrated_count} passwords to bcrypt"
        else:
            return "No passwords need migration"
    
    @app.route("/submit_contact", methods=["POST"])
    def submit_contact():
        from flask_mail import Message

        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        address = request.form.get("address")
        phone = request.form.get("phone")
        message = request.form.get("message")

        # Validasi sederhana
        if not first_name or not email:
            flash("Nama depan dan email harus diisi!", "danger")
            return redirect(url_for("index"))

        # Siapkan subject dan body email
        subject = f"Pesan Kontak dari {first_name} {last_name}"
        body = f"""
        <h2>Pesan dari Landing Page</h2>
        <p><strong>Nama:</strong> {first_name} {last_name}</p>
        <p><strong>Email:</strong> {email}</p>
        <p><strong>Alamat:</strong> {address or '-'}</p>
        <p><strong>Telepon:</strong> {phone or '-'}</p>
        """

        try:
            msg = Message(
                subject=subject,
                recipients=[app.config['CONTACT_RECIPIENT']],
                html=body,
                sender=app.config['MAIL_DEFAULT_SENDER']
            )
            mail.send(msg)
            flash("Pesan Anda berhasil dikirim. Terima kasih!", "success")
        except Exception as e:
            app.logger.error(f"Gagal kirim email kontak: {e}")
            flash("Maaf, terjadi kesalahan. Silakan coba lagi nanti.", "danger")

        return redirect(url_for("index"))

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
    except Exception as e:
        app.logger.error(f"Error registering tahun_ajaran blueprint: {e}")
    
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

    try:
        from penilaiansiswa.routes.superadmin_routes import superadmin_bp
        app.register_blueprint(superadmin_bp)
    except ImportError as e:
        app.logger.warning(f"Superadmin blueprint not found: {e}")
    
    try:
        from penilaiansiswa.routes.dinas_routes import dinas_bp
        app.register_blueprint(dinas_bp)
    except ImportError as e:
        app.logger.warning(f"Dinas blueprint not found: {e}")
    
    # =============================
    # JINJA2 FILTERS
    # =============================
    @app.template_filter('month_name')
    def month_name_filter(month_number):
        try:
            return calendar.month_name[int(month_number)]
        except (ValueError, IndexError):
            return ""
    # =============================
    # CONTEXT PROCESSOR UNTUK STATISTIK LANDING PAGE
    # =============================
    @app.context_processor
    def inject_stats():
        from penilaiansiswa import db
        from penilaiansiswa.models.sekolah import Sekolah, Kabupaten, Siswa
        from penilaiansiswa.models.users import Pegawai
        
        # Sekolah terdaftar
        stat_sekolah = Sekolah.query.count()
        # Guru terdaftar (semua pegawai)
        stat_guru = Pegawai.query.count()
        # Siswa terdaftar (semua siswa)
        stat_siswa = db.session.query(Siswa.nisn).distinct().count()
        # Kabupaten terdaftar
        stat_kabupaten = Kabupaten.query.count()
        
        return {
            'stat_sekolah': stat_sekolah,
            'stat_guru': stat_guru,
            'stat_siswa': stat_siswa,
            'stat_kabupaten': stat_kabupaten
        }
    
    return app

# Create application instance
app = create_app()

# Alias untuk passenger_wsgi.py
application = app

if __name__ == "__main__":
    env = os.environ.get("FLASK_ENV", "development")
    
    if env == "production":
        print("🚀 Running in PRODUCTION mode")
        from waitress import serve
        serve(app, host="0.0.0.0", port=5000)
    else:
        print("🔧 Running in DEVELOPMENT mode")
        app.run(debug=True, host="0.0.0.0", port=5000)