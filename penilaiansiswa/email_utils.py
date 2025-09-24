from flask_mail import Message
from flask import current_app, url_for
from itsdangerous import URLSafeTimedSerializer
from penilaiansiswa import mail

def send_reset_email(user):
    """Send password reset email to user"""
    try:
        # Generate reset token
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = s.dumps({'user_id': user.id}, salt='password-reset-salt')
        
        # ✅ PASTIKAN NAMA BLUEPRINT BENAR
        reset_url = url_for('lupa_password.reset_token', token=token, _external=True)
        
        # Create email message
        msg = Message(
            subject='Reset Password - Aplikasi Penilaian Siswa',
            sender=current_app.config.get('MAIL_USERNAME', 'noreply@example.com'),
            recipients=[user.email]
        )
        
        # Email content
        msg.html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .button {{ 
                    background-color: #007bff; 
                    color: white; 
                    padding: 12px 24px; 
                    text-decoration: none; 
                    border-radius: 5px; 
                    display: inline-block;
                    margin: 10px 0;
                }}
                .code {{ 
                    background-color: #f8f9fa; 
                    padding: 10px; 
                    border-radius: 5px; 
                    font-family: monospace;
                    word-break: break-all;
                    border: 1px solid #dee2e6;
                }}
                .warning {{ color: #856404; background-color: #fff3cd; padding: 10px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>🔐 Reset Password</h2>
                <p>Halo <strong>{user.username}</strong>,</p>
                <p>Anda menerima email ini karena meminta reset password untuk akun <strong>Aplikasi Penilaian Siswa</strong>.</p>
                
                <p><strong>Klik tombol di bawah untuk reset password:</strong></p>
                <p>
                    <a href="{reset_url}" class="button">🔄 Reset Password Sekarang</a>
                </p>
                
                <p><strong>Atau copy link berikut ke browser Anda:</strong></p>
                <div class="code">{reset_url}</div>
                
                <div class="warning">
                    <p><strong>⏰ Penting:</strong> Link ini akan kedaluwarsa dalam 1 jam.</p>
                </div>
                
                <p>Jika Anda <strong>tidak meminta</strong> reset password, abaikan email ini - password Anda tetap aman.</p>
                
                <hr>
                <p><small>Email ini dikirim secara otomatis, jangan dibalas.</small></p>
            </div>
        </body>
        </html>
        """
        
        # Send email
        mail.send(msg)
        current_app.logger.info(f"Reset email successfully sent to {user.email}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error sending reset email to {user.email}: {str(e)}")
        return False