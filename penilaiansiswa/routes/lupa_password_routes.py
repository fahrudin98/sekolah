from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import current_user
from penilaiansiswa import db
from penilaiansiswa.models import User
from forms import RequestResetForm, ResetPasswordForm  # <-- Perhatikan penambahan 'penilaiansiswa.'
from email_utils import send_reset_email  # <-- Import dari modul yang benar

# Definisikan blueprint
lupa_password_bp = Blueprint("lupa_password", __name__)

@lupa_password_bp.route("/reset_password", methods=["GET", "POST"])
def reset_request():
    # Jika user sudah login, arahkan ke home
    if current_user.is_authenticated:
        return redirect(url_for("index"))  # Ganti "index" dengan endpoint home Anda
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_reset_email(user)  # <- Ini akan memanggil fungsi dari email_utils.py
        # Pesan sukses generik (untuk keamanan)
        flash("Jika email terdaftar, link reset sudah dikirim. Silakan cek inbox atau folder spam email Anda.", "info")
        return redirect(url_for("login"))  # <- Redirect ke LOGIN setelah request
    return render_template("auth/reset_request.html", form=form)

@lupa_password_bp.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_token(token):
    # Jika user sudah login, arahkan ke home
    if current_user.is_authenticated:
        return redirect(url_for("index"))  # Ganti "index" dengan endpoint home Anda
    # Verifikasi token
    user = User.verify_reset_token(token)
    if not user:
        flash("Link reset tidak valid atau sudah kedaluwarsa.", "warning")
        return redirect(url_for("lupa_password.reset_request"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        # Hash password baru dan simpan
        user.set_password(form.password.data)
        db.session.commit()
        flash("Password berhasil diubah. Silakan login dengan password baru Anda.", "success")
        return redirect(url_for("login"))  # <- PASTIKAN redirect ke LOGIN
    return render_template("auth/reset_token.html", form=form)

# 🔥 HAPUS SELURUH FUNGSI send_reset_email() YANG DIBUAT DI BAWAH INI 🔥
# Jangan ada fungsi send_reset_email di file ini lagi