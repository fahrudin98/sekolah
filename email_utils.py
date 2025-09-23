# Di email_utils.py - GANTI dengan ini
from flask import render_template, url_for, current_app
from flask_mail import Message
from penilaiansiswa import mail
import threading

def send_async_email(app, msg):
    """Kirim email di thread terpisah untuk menghindari blocking"""
    with app.app_context():
        try:
            mail.send(msg)
            current_app.logger.info(f"Email reset berhasil dikirim ke {msg.recipients}")
        except Exception as e:
            current_app.logger.error(f"GAGAL mengirim email: {str(e)}")

def send_reset_email(user):
    """
    Mengirim email reset password kepada user secara asynchronous
    """
    try:
        # Generate token dan buat URL
        token = user.get_reset_token()
        reset_url = url_for("lupa_password.reset_token", token=token, _external=True)
        
        # Buat pesan email
        msg = Message(
            subject="Permintaan Reset Password - Aplikasi Penilaian Siswa",
            sender=current_app.config.get("MAIL_DEFAULT_SENDER", "admin@7kebiasaan.com"),
            recipients=[user.email]
        )
        
        msg.body = render_template("email/reset_password.txt", user=user, reset_url=reset_url)
        msg.html = render_template("email/reset_password.html", user=user, reset_url=reset_url)
        
        # Kirim email di thread terpisah untuk menghindari timeout
        thread = threading.Thread(target=send_async_email, args=(current_app._get_current_object(), msg))
        thread.start()
        
        current_app.logger.info(f"Proses pengiriman email ke {user.email} dimulai")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error preparing email untuk {user.email}: {str(e)}")
        return False