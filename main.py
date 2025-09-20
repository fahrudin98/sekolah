from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from penilaiansiswa.models.sekolah import Provinsi
from penilaiansiswa.models.users import Pegawai, User
from penilaiansiswa import db, mail



# =============================
# APP CONFIG
# =============================
app = Flask(__name__)
app.secret_key = "supersecretkey"  # ganti dengan key yang lebih aman
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:@localhost/sekolah_app"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Inisialisasi SQLAlchemy dan Migrate
db.init_app(app)
migrate = Migrate(app, db)

# =============================
# FLASK-LOGIN SETUP
# =============================
login_manager = LoginManager()
login_manager.login_view = "index"   # halaman login default
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Pastikan model User punya mixin UserMixin
# (tambah `from flask_login import UserMixin` lalu class User(UserMixin, db.Model) di models/users.py)

# =============================
# ROUTES
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

    # Cek apakah username/email sudah ada
    existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing_user:
        flash("Username atau email sudah digunakan!", "danger")
        return redirect(url_for("index"))

    # Hash password
    hashed_password = generate_password_hash(password)

    # Simpan user baru
    new_user = User(
        nama_lengkap=nama,
        email=email,
        username=username,
        password=hashed_password,
        role="user"
    )
    db.session.add(new_user)
    db.session.commit()

    flash("User berhasil didaftarkan!", "success")
    return redirect(url_for("index"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        # kalau dibuka langsung pakai GET → kembali ke landing
        return redirect(url_for("index"))

    # ---- kalau POST (proses login) ----
    username = request.form.get("username")
    password = request.form.get("password")

    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        login_user(user)
        flash(f"Selamat datang, {user.username}!", "success")

        if user.pegawai:
            return redirect(url_for("tahun_ajaran.dashboard"))
        else:
            return redirect(url_for("home"))
    else:
        flash("Username atau password salah!", "danger")
        return redirect(url_for("index"))

    # 👇 tambahan safety, supaya TIDAK ADA jalur kosong
    return redirect(url_for("index"))


@app.route("/home")
@login_required
def home():
    """Halaman isi/update profil"""
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
    flash("Anda berhasil logout!", "info")
    return redirect(url_for("index"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        # TODO: kirim link reset password via email
        flash(f"Link reset password dikirim ke {email} (simulasi)", "info")
        return redirect(url_for("index"))

    # Form sementara untuk lupa password
    return """
        <form method="POST">
            <input type="email" name="email" placeholder="Masukkan email" required>
            <button type="submit">Kirim link reset</button>
        </form>
    """


# =============================
# CHANGE PASSWORD
# =============================
@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "GET":
        # redirect ke dashboard saja
        return redirect(url_for("home"))

    # POST = ganti password via AJAX
    data = request.get_json()
    current = data.get("current_password")
    new = data.get("new_password")

    if not current or not new:
        return jsonify({"success": False, "message": "Data tidak lengkap"})

    user = current_user
    if not check_password_hash(user.password, current):
        return jsonify({"success": False, "message": "Password saat ini salah"})

    user.password = generate_password_hash(new)
    db.session.commit()
    return jsonify({"success": True, "message": "Password berhasil diubah"})

# =============================
# REGISTER BLUEPRINTS
# =============================
from penilaiansiswa.routes.routes import pegawai_bp
from penilaiansiswa.routes.tahun_ajaran_routes import tahun_ajaran_bp
from penilaiansiswa.routes.kelas_routes import kelas_bp
from penilaiansiswa.routes import siswa_routes
from penilaiansiswa.routes.penilaian_routes import penilaian_bp
import calendar
from penilaiansiswa.routes.lupa_password_routes import lupa_password_bp
from penilaiansiswa.routes.laporan import laporan_bp


# Daftarkan filter Jinja global


app.register_blueprint(pegawai_bp)
app.register_blueprint(tahun_ajaran_bp, url_prefix="/tahun_ajaran")
app.register_blueprint(kelas_bp)
app.register_blueprint(siswa_routes.siswa_bp)
app.register_blueprint(penilaian_bp)
app.register_blueprint(lupa_password_bp)
app.register_blueprint(laporan_bp)

app.jinja_env.filters['month_name'] = lambda month_number: calendar.month_name[int(month_number)] if 1 <= int(month_number) <= 12 else ""
# =============================
# RUN APP
# =============================
if __name__ == "__main__":
    app.run(debug=True)

