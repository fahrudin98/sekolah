from sqlalchemy import event
from flask import Flask
from datetime import datetime
from config import Config
from penilaiansiswa import db, mail
from penilaiansiswa.models import LogAktivitas


app = Flask(__name__)
app.config.from_object(Config)

# init extension
db.init_app(app)
mail.init_app(app)

def log_activity(mapper, connection, target, action):
    """
    Catat aktivitas otomatis ke tabel LogAktivitas.
    """
    user_id = getattr(g, "current_user_id", None)  # diisi dari session/login
    tabel = target.__tablename__
    entri_id = getattr(target, "id", None)

    connection.execute(
        LogAktivitas.__table__.insert(),
        {
            "user_id": user_id,
            "aksi": action,
            "tabel": tabel,
            "entri_id": entri_id,
            "keterangan": f"{action} on {tabel} id={entri_id}",
            "timestamp": datetime.utcnow(),
        },
    )


def register_listeners(models):
    """
    Daftarkan listener ke semua model yang perlu dicatat.
    models = [Provinsi, Kabupaten, Kecamatan, Sekolah, Pegawai, TahunAjaran, Kelas, Siswa, Kebiasaan]
    """
    for cls in models:
        event.listen(cls, "after_insert", lambda m, c, t: log_activity(m, c, t, "CREATE"))
        event.listen(cls, "after_update", lambda m, c, t: log_activity(m, c, t, "UPDATE"))
        event.listen(cls, "after_delete", lambda m, c, t: log_activity(m, c, t, "DELETE"))
