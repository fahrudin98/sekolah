# email_utils.py
from flask import render_template, url_for, current_app
from flask_mail import Message
from penilaiansiswa import mail

def send_reset_email(user):
    """
    Mengirim email reset password kepada user.
    """
    try:
        # Generate token dan buat URL (harus pakai lupa_password, bukan auth)
        token = user.get_reset_token()
        reset_url = url_for("lupa_password.reset_token", token=token, _external=True)
        
        # Buat pesan email
        msg = Message(
            subject="Permintaan Reset Password",
            sender="noreply@domainkamu.com",  # pastikan sesuai MAIL_DEFAULT_SENDER
            recipients=[user.email]
        )
        msg.body = render_template("email/reset_password.txt", user=user, reset_url=reset_url)
        msg.html = render_template("email/reset_password.html", user=user, reset_url=reset_url)
        
        mail.send(msg)
        current_app.logger.info(f"Email reset berhasil dikirim ke {user.email}")
        return True
        
    except Exception as e:
        current_app.logger.error(
            f"GAGAL mengirim email reset password ke {user.email}. Error: {str(e)}"
        )
        return False
