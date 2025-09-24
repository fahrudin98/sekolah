import os
print('DATABASE_URL:', os.environ.get('DATABASE_URL'))
from main import app, db
with app.app_context():
    from penilaiansiswa.models.users import User
    users = User.query.all()
    print(f'Database OK: {len(users)} users')
