from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import current_user
from penilaiansiswa import db, mail
from penilaiansiswa.models import User
from forms import RequestResetForm, ResetPasswordForm
from email_utils import send_reset_email
from flask_mail import Message
from penilaiansiswa.models import User


# definisi blueprint
lupa_password_bp = Blueprint("lupa_password", __name__)

@lupa_password_bp.route("/reset_password", methods=["GET", "POST"])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_reset_email(user)
        flash("Jika email terdaftar, link reset sudah dikirim. Cek inbox/spam.", "info")
        return redirect(url_for("index"))  # sesuaikan route login Anda
    return render_template("auth/reset_request.html", form=form)

@lupa_password_bp.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    user = User.verify_reset_token(token)
    if not user:
        flash("Link reset tidak valid atau sudah kedaluwarsa.", "warning")
        return redirect(url_for("lupa_password.reset_request"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Password berhasil diubah. Silakan login.", "success")
        return redirect(url_for("index"))  # sesuaikan route login Anda
    return render_template("auth/reset_token.html", form=form)

def send_reset_email(user):
    token = user.get_reset_token()
    reset_url = url_for("auth.reset_token", token=token, _external=True)
    msg = Message("Permintaan Reset Password", recipients=[user.email])
    msg.body = render_template("email/reset_password.txt", user=user, reset_url=reset_url)
    msg.html = render_template("email/reset_password.html", user=user, reset_url=reset_url)
    mail.send(msg)
