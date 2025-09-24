from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .users import User, Pegawai
from .sekolah import Provinsi, Kabupaten, Kecamatan, Sekolah, TahunAjaran, Kelas, Siswa, Kebiasaan
from .log import LogAktivitas