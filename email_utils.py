from flask import render_template, url_for
from flask_mail import Message
from penilaiansiswa import mail   # sesuaikan dengan project Anda

def send_reset_email(user):
    token = user.get_reset_token()
    reset_url = url_for("auth.reset_token", token=token, _external=True)
    msg = Message("Permintaan Reset Password", recipients=[user.email])
    msg.body = render_template("email/reset_password.txt", user=user, reset_url=reset_url)
    msg.html = render_template("email/reset_password.html", user=user, reset_url=reset_url)
    mail.send(msg)