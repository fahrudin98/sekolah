import imp
import os
import sys

# ✅ TAMBAHKAN KONFIGURASI INI DI ATAS
# Path ke virtual environment Jagoanhosting
VENV_PATH = '/home/kebiasaa/virtualenv/sekolah/3.10'

# Tambahkan path site-packages dari virtual environment
site_packages_path = os.path.join(VENV_PATH, 'lib', 'python3.10', 'site-packages')
if site_packages_path not in sys.path:
    sys.path.insert(0, site_packages_path)

# ✅ KONFIGURASI AWAL ANDA (tetap pertahankan)
sys.path.insert(0, os.path.dirname(__file__))

wsgi = imp.load_source('wsgi', 'app.py')
application = wsgi.application