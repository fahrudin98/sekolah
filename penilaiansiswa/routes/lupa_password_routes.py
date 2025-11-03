from flask import Blueprint, render_template, flash, redirect, url_for, current_app
from flask_login import current_user
from penilaiansiswa import db
from penilaiansiswa.models.users import User
from penilaiansiswa.forms import RequestResetForm, ResetPasswordForm
from penilaiansiswa.email_utils import send_reset_email
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask_bcrypt import Bcrypt  # ✅ GUNAKAN FLAKS-BCRYPT

# Definisikan blueprint
lupa_password_bp = Blueprint("lupa_password", __name__)

# ✅ INISIALISASI BCRYPT
bcrypt = Bcrypt()

def verify_reset_token(token):
    """Function terpisah untuk verify token reset password"""
    try:
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        data = s.loads(token, salt='password-reset-salt', max_age=3600)
        user_id = data.get('user_id')
        if user_id:
            return User.query.get(user_id)
    except (SignatureExpired, BadSignature):
        current_app.logger.warning("Token reset password invalid or expired")
        return None
    except Exception as e:
        current_app.logger.error(f"Error verifying token: {str(e)}")
        return None
    return None

@lupa_password_bp.route("/reset_password", methods=["GET", "POST"])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    
    form = RequestResetForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user:
            try:
                send_reset_email(user)
                flash("Link reset password telah dikirim ke email Anda. Silakan cek inbox atau folder spam.", "info")
            except Exception as e:
                current_app.logger.error(f"Error sending reset email: {e}")
                flash("Terjadi error saat mengirim email reset. Silakan coba lagi atau hubungi administrator.", "danger")
        else:
            flash("Jika email terdaftar, link reset sudah dikirim. Silakan cek inbox atau folder spam email Anda.", "info")
        
        return redirect(url_for("index"))
    
    return render_template("auth/reset_request.html", form=form)

@lupa_password_bp.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    
    user = None
    try:
        user = User.verify_reset_token(token)
    except AttributeError:
        user = verify_reset_token(token)
    
    if not user:
        flash("Link reset tidak valid atau sudah kedaluwarsa.", "warning")
        return redirect(url_for("lupa_password.reset_request"))
    
    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        try:
            # ✅ GUNAKAN FLAKS-BCRYPT - SAMA DENGAN USERS.PY
            user.password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
            db.session.commit()
            
            flash("Password berhasil diubah. Silakan login dengan password baru Anda.", "success")
            return redirect(url_for("index"))
            
        except Exception as e:
            db.session.rollback()
            flash("Error reset password. Silakan hubungi administrator.", "danger")
            current_app.logger.error(f"Error resetting password: {e}")
    
    return render_template("auth/reset_token.html", form=form, token=token)