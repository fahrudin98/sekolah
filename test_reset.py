from penilaiansiswa import create_app, db
from penilaiansiswa.models.users import User
from passlib.hash import bcrypt

# Create application context
app = create_app()  # Ganti dengan cara Anda membuat Flask app

with app.app_context():
    # Cari user fahrudin
    user = User.query.filter_by(username='fahrudin').first()
    
    if user:
        print(f"User ditemukan: {user.username}")
        print(f"Password lama: {user.password}")
        
        # Reset password
        new_password = "password123"  # Ganti dengan password yang diinginkan
        user.password = bcrypt.hash(new_password)
        db.session.commit()
        
        print(f"Password baru telah di-set untuk user {user.username}")
        print(f"Password baru: {new_password}")
    else:
        print("User fahrudin tidak ditemukan")