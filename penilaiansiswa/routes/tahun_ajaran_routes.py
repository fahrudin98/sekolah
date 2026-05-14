# tahun_ajaran_routes.py
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, abort, flash, session
from flask_login import login_required, current_user
from penilaiansiswa.models import TahunAjaran, Pegawai, Sekolah, User, Kelas, Siswa, Kebiasaan, Kecamatan
from penilaiansiswa.models.sekolah import MasterTahunAjaran
from sqlalchemy.orm import joinedload
from sqlalchemy import func, case
from penilaiansiswa import db

import calendar
from datetime import date

tahun_ajaran_bp = Blueprint("tahun_ajaran", __name__)

# ----------------------
# Helper util functions
# ----------------------
def extract_years_from_ta(tahun_ajaran_obj):
    """Return (start_year:int, end_year:int) from object.
    Try attributes tahun_mulai/tahun_selesai first, else parse tahun_ajaran string '2025/2026'.
    Fallback to current year/current+1.
    """
    if not tahun_ajaran_obj:
        y = date.today().year
        return y, y + 1

    # prefer explicit fields if present
    if hasattr(tahun_ajaran_obj, "tahun_mulai") and hasattr(tahun_ajaran_obj, "tahun_selesai"):
        try:
            return int(tahun_ajaran_obj.tahun_mulai), int(tahun_ajaran_obj.tahun_selesai)
        except Exception:
            pass

    # fallback parse string "2025/2026"
    ta_str = getattr(tahun_ajaran_obj, "tahun_ajaran", None)
    if ta_str and "/" in ta_str:
        parts = ta_str.split("/")
        try:
            y1 = int(parts[0].strip()[:4])
            y2 = int(parts[1].strip()[:4])
            return y1, y2
        except Exception:
            pass

    # final fallback
    y = date.today().year
    return y, y + 1


def generate_bulan_list_for_semester(tahun_ajaran_obj, semester=None):
    """Return list of months dicts for a given semester of the tahun ajaran.
    Each dict: {'value': 'YYYY-MM', 'label': 'Bulan YYYY'}.
    If semester is None, use tahun_ajaran_obj.semester (lowercased).
    """
    start_year, end_year = extract_years_from_ta(tahun_ajaran_obj)
    sem = semester or (getattr(tahun_ajaran_obj, "semester", None) or "ganjil")
    sem = sem.lower()

    bulan_list = []
    if sem == "ganjil":
        # Juli - Desember -> tahun mulai
        for m in range(7, 13):
            val = f"{start_year}-{m:02d}"
            label = f"{calendar.month_name[m]} {start_year}"
            bulan_list.append({"value": val, "label": label})
    elif sem == "genap":
        # Januari - Juni -> tahun selesai
        for m in range(1, 7):
            val = f"{end_year}-{m:02d}"
            label = f"{calendar.month_name[m]} {end_year}"
            bulan_list.append({"value": val, "label": label})
    else:
        # unknown semester -> give full academic year (Juli - Juni)
        for m in range(7, 13):
            val = f"{start_year}-{m:02d}"
            label = f"{calendar.month_name[m]} {start_year}"
            bulan_list.append({"value": val, "label": label})
        for m in range(1, 7):
            val = f"{end_year}-{m:02d}"
            label = f"{calendar.month_name[m]} {end_year}"
            bulan_list.append({"value": val, "label": label})

    return bulan_list


def get_kelas_for_current_user(sekolah, tahun_ajaran):
    """Return kelas list filtered:
    - jika current_user.is_superadmin -> semua kelas di tahun ajaran
    - else -> kelas where wali_kelas_id == current_user.pegawai.id
    """
    if not tahun_ajaran or not sekolah:
        return []

    q = Kelas.query.filter_by(tahun_ajaran_id=tahun_ajaran.id, sekolah_id=sekolah.id)

    # if user has pegawai and not superadmin, filter to kelas yg dia pegang (wali)
    if hasattr(current_user, "is_superadmin") and current_user.is_superadmin:
        kelas_list = q.all()
    else:
        if not getattr(current_user, "pegawai", None):
            kelas_list = []
        else:
            kelas_list = q.filter_by(wali_kelas_id=current_user.pegawai.id).all()
    return kelas_list

# ----------------------
# Helper functions baru untuk API
# ----------------------
def get_habits_data_by_kelas_terbaik(sekolah_id, tahun_ajaran_id, bulan_filter=''):
    """Ambil data kebiasaan untuk 10 KELAS TERBAIK"""
    # Query untuk mendapatkan kelas dengan rata-rata tertinggi
    subquery = db.session.query(
        Kelas.id,
        Kelas.nama_kelas,
        func.avg(
            (Kebiasaan.bangun_pagi + Kebiasaan.beribadah + Kebiasaan.berolahraga + 
             Kebiasaan.sehat_dan_lemar + Kebiasaan.belajar + Kebiasaan.bermasyarakat + 
             Kebiasaan.tidur_cepat) / 7.0
        ).label('rata_rata')
    ).join(Siswa, Kelas.id == Siswa.kelas_id)\
     .join(Kebiasaan, Siswa.id == Kebiasaan.siswa_id)\
     .filter(
        Kelas.sekolah_id == sekolah_id,
        Kelas.tahun_ajaran_id == tahun_ajaran_id
    )
    
    if bulan_filter:
        subquery = subquery.filter(Kebiasaan.bulan == bulan_filter)
    
    subquery = subquery.group_by(Kelas.id, Kelas.nama_kelas)\
                      .order_by(db.desc('rata_rata'))\
                      .limit(10)\
                      .subquery()
    
    # Ambil data detail untuk 10 kelas terbaik
    kelas_terbaik = db.session.query(
        subquery.c.id,
        subquery.c.nama_kelas,
        subquery.c.rata_rata
    ).all()
    
    habits = {
        'bangun_pagi': {'labels': [], 'data': []},
        'beribadah': {'labels': [], 'data': []},
        'berolahraga': {'labels': [], 'data': []},
        'sehat_dan_lemar': {'labels': [], 'data': []},
        'belajar': {'labels': [], 'data': []},
        'bermasyarakat': {'labels': [], 'data': []},
        'tidur_cepat': {'labels': [], 'data': []}
    }
    
    for kelas in kelas_terbaik:
        # Hitung rata-rata per kebiasaan untuk kelas ini
        avg_query = db.session.query(
            func.avg(Kebiasaan.bangun_pagi).label('bangun_pagi'),
            func.avg(Kebiasaan.beribadah).label('beribadah'),
            func.avg(Kebiasaan.berolahraga).label('berolahraga'),
            func.avg(Kebiasaan.sehat_dan_lemar).label('sehat_dan_lemar'),
            func.avg(Kebiasaan.belajar).label('belajar'),
            func.avg(Kebiasaan.bermasyarakat).label('bermasyarakat'),
            func.avg(Kebiasaan.tidur_cepat).label('tidur_cepat')
        ).join(Siswa).filter(Siswa.kelas_id == kelas.id)
        
        if bulan_filter:
            avg_query = avg_query.filter(Kebiasaan.bulan == bulan_filter)
        
        result = avg_query.first()
        
        if result:
            for habit in habits.keys():
                habits[habit]['labels'].append(kelas.nama_kelas)
                habits[habit]['data'].append(round(result._asdict()[habit] or 0, 1))
    
    return habits

def get_siswa_stats(sekolah_id, tahun_ajaran_id, bulan_filter='', kelas_filter='all'):
    """Ambil data statistik per siswa dengan filter"""
    query = db.session.query(
        Siswa.id,
        Siswa.nama_siswa,
        Kelas.nama_kelas.label('kelas'),
        Kelas.id.label('kelas_id'),
        Kebiasaan.bulan,
        Kebiasaan.bangun_pagi,
        Kebiasaan.beribadah,
        Kebiasaan.berolahraga,
        Kebiasaan.sehat_dan_lemar.label('sehat_dan_bergizi'),
        Kebiasaan.belajar,
        Kebiasaan.bermasyarakat,
        Kebiasaan.tidur_cepat
    ).join(Kelas, Siswa.kelas_id == Kelas.id)\
     .join(Kebiasaan, Siswa.id == Kebiasaan.siswa_id)\
     .filter(
        Kelas.sekolah_id == sekolah_id,
        Kelas.tahun_ajaran_id == tahun_ajaran_id
    )
    
    if bulan_filter:
        query = query.filter(Kebiasaan.bulan == bulan_filter)
    
    if kelas_filter != 'all':
        query = query.filter(Kelas.id == kelas_filter)
    
    results = query.all()
    
    siswa_data = []
    for row in results:
        # Hitung rata-rata per siswa
        totals = [
            float(row.bangun_pagi or 0),
            float(row.beribadah or 0),
            float(row.berolahraga or 0),
            float(row.sehat_dan_bergizi or 0),
            float(row.belajar or 0),
            float(row.bermasyarakat or 0),
            float(row.tidur_cepat or 0)
        ]
        rata_rata = sum(totals) / len(totals)
        
        siswa_data.append({
            'id': row.id,
            'nama_siswa': row.nama_siswa,
            'kelas': row.kelas,
            'kelas_id': row.kelas_id,
            'bulan': row.bulan,
            'bangun_pagi': float(row.bangun_pagi or 0),
            'beribadah': float(row.beribadah or 0),
            'berolahraga': float(row.berolahraga or 0),
            'sehat_dan_bergizi': float(row.sehat_dan_bergizi or 0),
            'belajar': float(row.belajar or 0),
            'bermasyarakat': float(row.bermasyarakat or 0),
            'tidur_cepat': float(row.tidur_cepat or 0),
            'rata_rata': float(rata_rata)
        })
    
    return siswa_data

def get_kelas_list(sekolah_id, tahun_ajaran_id):
    """Ambil list semua kelas untuk filter - DIPERBAIKI"""
    kelas_list = Kelas.query.filter_by(
        sekolah_id=sekolah_id,
        tahun_ajaran_id=tahun_ajaran_id
    ).options(
        db.joinedload(Kelas.wali_kelas)
    ).all()
    
    return [{'id': k.id, 'nama_kelas': k.nama_kelas} for k in kelas_list]

def calculate_rata_rata_sekolah(sekolah_id, tahun_ajaran_id, bulan_filter=''):
    """Hitung rata-rata seluruh sekolah"""
    query = db.session.query(
        func.avg(
            (Kebiasaan.bangun_pagi + Kebiasaan.beribadah + Kebiasaan.berolahraga + 
             Kebiasaan.sehat_dan_lemar + Kebiasaan.belajar + Kebiasaan.bermasyarakat + 
             Kebiasaan.tidur_cepat) / 7.0
        )
    ).join(Siswa, Kebiasaan.siswa_id == Siswa.id)\
     .join(Kelas, Siswa.kelas_id == Kelas.id)\
     .filter(
        Kelas.sekolah_id == sekolah_id,
        Kelas.tahun_ajaran_id == tahun_ajaran_id
    )
    
    if bulan_filter:
        query = query.filter(Kebiasaan.bulan == bulan_filter)
    
    result = query.scalar()
    return result or 0


def get_trend_data_kepala_sekolah(sekolah_id, tahun_ajaran_id):
    """Ambil data trend perkembangan per bulan untuk 7 kebiasaan"""
    # Ambil bulan-bulan dalam tahun ajaran
    tahun_ajaran = TahunAjaran.query.get(tahun_ajaran_id)
    bulan_list = generate_bulan_list_for_semester(tahun_ajaran)
    
    labels = [bulan['label'] for bulan in bulan_list]
    bulan_values = [bulan['value'] for bulan in bulan_list]
    
    # Data untuk 7 kebiasaan
    datasets = []
    
    # Warna untuk setiap kebiasaan
    colors = [
        '#FF6384',  # Bangun Pagi - Merah
        '#36A2EB',  # Beribadah - Biru
        '#FFCE56',  # Berolahraga - Kuning
        '#4BC0C0',  # Sehat & Bergizi - Hijau Muda
        '#9966FF',  # Belajar - Ungu
        '#FF9F40',  # Bermasyarakat - Oranye
        '#2E8B57'   # Tidur Cepat - Hijau
    ]
    
    # Mapping nama kebiasaan untuk label
    habit_names = {
        'bangun_pagi': 'Bangun Pagi',
        'beribadah': 'Beribadah',
        'berolahraga': 'Gemar Berolahraga',
        'sehat_dan_lemar': 'Makan Sehat & Bergizi',
        'belajar': 'Gemar Belajar',
        'bermasyarakat': 'Bermasyarakat',
        'tidur_cepat': 'Tidur Cepat'
    }
    
    habits = ['bangun_pagi', 'beribadah', 'berolahraga', 'sehat_dan_lemar', 'belajar', 'bermasyarakat', 'tidur_cepat']
    
    for i, habit in enumerate(habits):
        data_per_bulan = []
        
        for bulan_value in bulan_values:
            # Hitung rata-rata nilai untuk kebiasaan tertentu di bulan tertentu
            # Untuk semua siswa di sekolah tersebut
            avg_query = db.session.query(
                func.avg(getattr(Kebiasaan, habit))
            ).join(Siswa).join(Kelas).filter(
                Kelas.sekolah_id == sekolah_id,
                Kelas.tahun_ajaran_id == tahun_ajaran_id,
                Kebiasaan.bulan == bulan_value
            )
            
            result = avg_query.scalar()
            data_per_bulan.append(round(result or 0, 1))
        
        datasets.append({
            'label': habit_names[habit],
            'data': data_per_bulan,
            'borderColor': colors[i],
            'backgroundColor': colors[i] + '20',
            'tension': 0.4,
            'fill': False
        })
    
    return {
        'labels': labels,
        'datasets': datasets
    }

def get_kelas_stats(sekolah_id, tahun_ajaran_id):
    """Ambil statistik detail per kelas"""
    kelas_list = Kelas.query.filter_by(
        sekolah_id=sekolah_id, 
        tahun_ajaran_id=tahun_ajaran_id
    ).all()
    
    stats = []
    
    for kelas in kelas_list:
        # Hitung jumlah siswa
        jumlah_siswa = Siswa.query.filter_by(kelas_id=kelas.id).count()
        
        # Hitung rata-rata per kebiasaan
        avg_query = db.session.query(
            func.avg(Kebiasaan.bangun_pagi).label('bangun_pagi'),
            func.avg(Kebiasaan.beribadah).label('beribadah'),
            func.avg(Kebiasaan.berolahraga).label('berolahraga'),
            func.avg(Kebiasaan.sehat_dan_lemar).label('sehat_dan_lemar'),
            func.avg(Kebiasaan.belajar).label('belajar'),
            func.avg(Kebiasaan.bermasyarakat).label('bermasyarakat'),
            func.avg(Kebiasaan.tidur_cepat).label('tidur_cepat')
        ).join(Siswa).filter(Siswa.kelas_id == kelas.id)
        
        result = avg_query.first()
        
        if result:
            # Konversi semua nilai ke float sebelum perhitungan
            totals = [
                float(result.bangun_pagi or 0), 
                float(result.beribadah or 0), 
                float(result.berolahraga or 0),
                float(result.sehat_dan_lemar or 0), 
                float(result.belajar or 0), 
                float(result.bermasyarakat or 0),
                float(result.tidur_cepat or 0)
            ]
            rata_rata = sum(totals) / len(totals)
            
            stats.append({
                'kelas': kelas.nama_kelas,
                'wali_kelas': kelas.wali_kelas.nama if kelas.wali_kelas else '-',
                'jumlah_siswa': jumlah_siswa,
                'bangun_pagi': float(result.bangun_pagi or 0),
                'beribadah': float(result.beribadah or 0),
                'berolahraga': float(result.berolahraga or 0),
                'sehat_dan_lemar': float(result.sehat_dan_lemar or 0),
                'belajar': float(result.belajar or 0),
                'bermasyarakat': float(result.bermasyarakat or 0),
                'tidur_cepat': float(result.tidur_cepat or 0),
                'rata_rata': float(rata_rata)
            })
    
    return stats

def is_kepala_sekolah(user):
    """
    Cek apakah user adalah kepala sekolah (bisa multiple sekolah)
    """
    if not hasattr(user, 'pegawai') or not user.pegawai:
        return False
    
    # Cek apakah user kepala sekolah di SATU ATAU LEBIH sekolah
    count = TahunAjaran.query.filter_by(
        kepala_sekolah_id=user.pegawai.id,
        aktif=True
    ).count()
    
    return count > 0

def get_sekolah_kepala_aktif(user):
    """
    Get sekolah aktif untuk kepala sekolah (dari session)
    """
    # PERBAIKAN: Gunakan session keys yang sama dengan set_sekolah_aktif
    tahun_ajaran_id = session.get('kepala_sekolah_tahun_ajaran_id')
    sekolah_id = session.get('kepala_sekolah_sekolah_id')
    is_plt = session.get('is_plt', False)
    
    if not tahun_ajaran_id or not sekolah_id:
        return None
    
    tahun_ajaran = TahunAjaran.query.get(tahun_ajaran_id)
    sekolah = Sekolah.query.get(sekolah_id)
    
    # Validasi: pastikan user memang kepala sekolah di sekolah ini
    if tahun_ajaran and sekolah:
        if tahun_ajaran.kepala_sekolah_id == user.pegawai.id:
            return {
                'tahun_ajaran': tahun_ajaran,
                'sekolah': sekolah,
                'is_plt': is_plt
            }
    return None

# ----------------------
# Dashboard route
# ----------------------
@tahun_ajaran_bp.route("/dashboard", methods=["GET","POST"])
@login_required
def dashboard():
    if request.method == "POST":
        return redirect(url_for("tahun_ajaran.dashboard"))
    
    # Refresh session untuk data terbaru
    db.session.expire_all()
    
    sekolah = None
    kelas_list = []
    existing_tahun = None
    nonaktif_tahun = []

    # Ambil sekolah dari pegawai user
    if getattr(current_user, "pegawai", None) and current_user.pegawai.sekolah_id:
        sekolah = current_user.pegawai.sekolah

    if sekolah:
        # Eager loading untuk performa dan data ter-update
        existing_tahun = TahunAjaran.query\
            .filter_by(sekolah_id=sekolah.id, aktif=True)\
            .options(
                db.joinedload(TahunAjaran.kepala_sekolah).joinedload(Pegawai.user)
            )\
            .first()
            
        nonaktif_tahun = TahunAjaran.query\
            .filter_by(sekolah_id=sekolah.id, aktif=False)\
            .options(
                db.joinedload(TahunAjaran.kepala_sekolah).joinedload(Pegawai.user)
            )\
            .order_by(TahunAjaran.id.desc())\
            .all()

    # Pegawai list (profil)
    pegawai_q = []
    if sekolah and sekolah.kecamatan_id:
        pegawai_q = (
            Pegawai.query
            .join(User, User.id == Pegawai.user_id)
            .join(Sekolah, Sekolah.id == Pegawai.sekolah_id)
            .filter(Sekolah.kecamatan_id == sekolah.kecamatan_id)
            .order_by(Pegawai.id)
            .all()
        )

    # Kelas hanya yang dimiliki user (wali) pada tahun ajaran aktif
    if existing_tahun and sekolah:
        kelas_list = get_kelas_for_current_user(sekolah, existing_tahun)
        bulan_list = generate_bulan_list_for_semester(existing_tahun)
    else:
        bulan_list = []

    # Cek apakah user adalah kepala sekolah
    is_kepala_sekolah_flag = is_kepala_sekolah(current_user)

    # ⭐ TAMBAH: Ambil master TA yang tersedia untuk dipilih sekolah
    available_masters = MasterTahunAjaran.query.filter_by(
        is_active=True
    ).order_by(
        MasterTahunAjaran.tahun_ajaran.desc(),
        MasterTahunAjaran.semester.desc()
    ).all()
    
    # ⭐ TAMBAH: Ambil semua TA yang sudah dipilih sekolah ini (history)
    sekolah_tahun_ajaran_list = []
    if sekolah:
        sekolah_tahun_ajaran_list = TahunAjaran.query.filter_by(
            sekolah_id=sekolah.id
        ).order_by(TahunAjaran.id.desc()).all()
    # ⭐ TAMBAHKAN INI DI BAWAHNYA
    # Pegawai SATU SEKOLAH (bukan sekecamatan)
    pegawai_satu_sekolah = []
    if sekolah:
        pegawai_satu_sekolah = Pegawai.query.filter_by(
            sekolah_id=sekolah.id
        ).order_by(Pegawai.id).all()
    
    # Pegawai SEKECAMATAN (untuk tombol "lihat lebih banyak")
    pegawai_sekecamatan = []
    if sekolah and sekolah.kecamatan_id:
        pegawai_sekecamatan = (
            Pegawai.query
            .join(User, User.id == Pegawai.user_id)
            .join(Sekolah, Sekolah.id == Pegawai.sekolah_id)
            .filter(Sekolah.kecamatan_id == sekolah.kecamatan_id)
            .order_by(Pegawai.id)
            .all()
        )

    return render_template(
        "dashboard.html",
        username=current_user.username,
        sekolah=sekolah,
        active_tahun_ajaran=existing_tahun,
        nonaktif_tahun_ajaran=nonaktif_tahun,
        pegawai_dengan_profil=pegawai_q,
        pegawai_satu_sekolah=pegawai_satu_sekolah,
        pegawai_sekecamatan=pegawai_sekecamatan,
        kelas_list=kelas_list,
        bulan_list=bulan_list,
        current_user=current_user,
        is_kepala_sekolah=is_kepala_sekolah_flag,
        available_masters=available_masters,
        sekolah_tahun_ajaran_list=sekolah_tahun_ajaran_list
    )

# =============================================================
# ⭐ BARU: SEKOLAH PILIH TAHUN AJARAN DARI MASTER
# =============================================================

@tahun_ajaran_bp.route("/pilih_tahun_ajaran", methods=["POST"])
@login_required
def pilih_tahun_ajaran():
    """Sekolah memilih tahun ajaran dari master - LANGSUNG AKTIF"""
    if not current_user.pegawai or not current_user.pegawai.sekolah_id:
        return jsonify({'success': False, 'message': 'User tidak terkait sekolah'}), 400
    
    sekolah_id = current_user.pegawai.sekolah_id
    master_id = request.form.get('master_id', type=int)
    kepala_sekolah_id = request.form.get('kepala_sekolah_id', type=int)
    
    if not master_id:
        return jsonify({'success': False, 'message': 'Pilih tahun ajaran terlebih dahulu'}), 400
    
    if not kepala_sekolah_id:
        return jsonify({'success': False, 'message': 'Pilih kepala sekolah terlebih dahulu'}), 400
    
    master = MasterTahunAjaran.query.get(master_id)
    if not master:
        return jsonify({'success': False, 'message': 'Master tahun ajaran tidak ditemukan'}), 404
    
    kepala = Pegawai.query.filter_by(id=kepala_sekolah_id, sekolah_id=sekolah_id).first()
    if not kepala:
        return jsonify({'success': False, 'message': 'Kepala sekolah tidak valid'}), 400
    
    existing = TahunAjaran.query.filter_by(
        sekolah_id=sekolah_id,
        master_ta_id=master_id
    ).first()
    
    if existing:
        return jsonify({
            'success': False,
            'message': f'Tahun ajaran "{master.display_name}" sudah pernah dipilih sebelumnya'
        }), 400
    
    # ⭐ NONAKTIFKAN SEMUA TAHUN AJARAN SEKOLAH INI DAHULU
    TahunAjaran.query.filter_by(sekolah_id=sekolah_id, aktif=True).update({'aktif': False})
    
    # ⭐ BUAT DAN LANGSUNG AKTIFKAN
    ta_baru = TahunAjaran(
        sekolah_id=sekolah_id,
        master_ta_id=master.id,
        tahun_ajaran=master.tahun_ajaran,
        semester=master.semester,
        kepala_sekolah_id=kepala.id,
        aktif=True  # ⭐ LANGSUNG AKTIF
    )
    
    db.session.add(ta_baru)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Berhasil memilih dan mengaktifkan tahun ajaran "{master.display_name}"',
        'data': {
            'id': ta_baru.id,
            'tahun_ajaran': master.tahun_ajaran,
            'semester': master.semester,
            'nama_kepala_sekolah': kepala.nama,
            'aktif': ta_baru.aktif
        }
    })


@tahun_ajaran_bp.route("/aktifkan_tahun_ajaran", methods=["POST"])
@login_required
def aktifkan_tahun_ajaran():
    """Sekolah mengaktifkan tahun ajaran yang sudah dipilih"""
    if not current_user.pegawai or not current_user.pegawai.sekolah_id:
        flash("User tidak terkait sekolah", "danger")
        return redirect(url_for("tahun_ajaran.dashboard"))
    
    sekolah_id = current_user.pegawai.sekolah_id
    tahun_ajaran_id = request.form.get('tahun_ajaran_id', type=int)
    
    if not tahun_ajaran_id:
        flash("ID tahun ajaran tidak ditemukan", "danger")
        return redirect(url_for("tahun_ajaran.dashboard"))
    
    # Nonaktifkan semua tahun ajaran sekolah ini
    TahunAjaran.query.filter_by(sekolah_id=sekolah_id, aktif=True).update({'aktif': False})
    
    # Aktifkan yang dipilih
    ta = TahunAjaran.query.filter_by(id=tahun_ajaran_id, sekolah_id=sekolah_id).first()
    if not ta:
        flash("Tahun ajaran tidak ditemukan", "danger")
        return redirect(url_for("tahun_ajaran.dashboard"))
    
    ta.aktif = True
    db.session.commit()
    
    flash(f'Tahun ajaran "{ta.tahun_ajaran_display}" berhasil diaktifkan', "success")
    
    # Redirect ke dashboard
    return redirect(url_for("tahun_ajaran.dashboard"))


@tahun_ajaran_bp.route("/toggle_tahun_ajaran", methods=["POST"])
@login_required
def toggle_tahun_ajaran():
    if not current_user.pegawai or not current_user.pegawai.sekolah_id:
        flash("User tidak terkait sekolah.", "danger")
        return redirect(url_for("tahun_ajaran.dashboard"))

    sekolah_id = current_user.pegawai.sekolah_id
    tahun_id = request.form.get("id")
    tahun = TahunAjaran.query.filter_by(id=tahun_id, sekolah_id=sekolah_id).first()
    if not tahun:
        flash("Tahun ajaran tidak ditemukan.", "danger")
        return redirect(url_for("tahun_ajaran.dashboard"))

    # Toggle status
    tahun.aktif = not tahun.aktif
    
    # Jika mengaktifkan, pastikan hanya 1 yang aktif
    if tahun.aktif:
        TahunAjaran.query.filter_by(sekolah_id=sekolah_id, aktif=True).filter(TahunAjaran.id != tahun_id).update({TahunAjaran.aktif: False})

    db.session.commit()
    
    status = "diaktifkan" if tahun.aktif else "dinonaktifkan"
    flash(f"Tahun ajaran berhasil {status}.", "success")
    
    # Redirect kembali ke dashboard
    return redirect(url_for("tahun_ajaran.dashboard"))

@tahun_ajaran_bp.route('/update_kepala_sekolah', methods=['POST'])
@login_required
def update_kepala_sekolah():
    tahun_ajaran_id = request.form.get('tahun_ajaran_id')
    kepala_sekolah_id = request.form.get('kepala_sekolah_id')
    
    print(f"Debug: tahun_ajaran_id={tahun_ajaran_id}, kepala_sekolah_id={kepala_sekolah_id}")
    
    tahun_ajaran = TahunAjaran.query.get(tahun_ajaran_id)
    if not tahun_ajaran:
        return jsonify({'success': False, 'message': 'Tahun ajaran tidak ditemukan'})
    
    pegawai = Pegawai.query.get(kepala_sekolah_id)
    if not pegawai:
        return jsonify({'success': False, 'message': 'Pegawai tidak ditemukan'})
    
    try:
        # Hanya update kepala_sekolah_id saja
        # Property nama_kepala_sekolah dan nip_kepala_sekolah akan otomatis ter-update

        # **MODIFIKASI: Cek apakah kepala sekolah dari kecamatan yang sama**
        is_plt = False
        if tahun_ajaran.sekolah.kecamatan_id != pegawai.sekolah.kecamatan_id:
            is_plt = True
        
        # Update kepala_sekolah_id
        tahun_ajaran.kepala_sekolah_id = kepala_sekolah_id

        # **MODIFIKASI: Tambahkan field is_plt jika ada di model**
        if hasattr(tahun_ajaran, 'is_plt'):
            tahun_ajaran.is_plt = is_plt
        
        db.session.commit()
        
        # **MODIFIKASI: Tambahkan status PLT dalam response**
        response_data = {
            'success': True, 
            'message': 'Kepala sekolah berhasil diperbarui',
            'data': {
                'nama_kepala_sekolah': tahun_ajaran.nama_kepala_sekolah,
                'nip_kepala_sekolah': tahun_ajaran.nip_kepala_sekolah,
                'is_plt': is_plt
            }
        }

        return jsonify(response_data)
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating kepala sekolah: {str(e)}")
        return jsonify({'success': False, 'message': f'Terjadi kesalahan: {str(e)}'})

@tahun_ajaran_bp.route("/dashboard_kepala_sekolah")
@login_required
def dashboard_kepala_sekolah():
    """Dashboard khusus untuk kepala sekolah - DIPERBAIKI"""
    # Cek session untuk sekolah aktif
    sekolah_aktif = get_sekolah_kepala_aktif(current_user)
    
    if not sekolah_aktif:
        # Jika belum pilih sekolah, redirect ke multi sekolah
        flash('Silakan pilih sekolah terlebih dahulu', 'warning')
        return redirect(url_for("tahun_ajaran.dashboard_multi_sekolah"))
    
    # **PERBAIKAN: Jangan hitung statistik di sini, biarkan API yang handle**
    # Karena data akan di-load via JavaScript dan bisa berubah dengan filter
    
    # Tentukan status kepala sekolah
    status_kepala_sekolah = "Kepala Sekolah PLT" if sekolah_aktif['is_plt'] else "Kepala Sekolah"
    
    return render_template(
        "dashboard_kepala_sekolah.html",
        tahun_ajaran=sekolah_aktif['tahun_ajaran'].tahun_ajaran,
        tahun_ajaran_id=sekolah_aktif['tahun_ajaran'].id,  # **PERBAIKAN: Pastikan ID benar**
        sekolah_aktif=sekolah_aktif['sekolah'],
        status_kepala_sekolah=status_kepala_sekolah,
        pegawai=current_user.pegawai,
        # **PERBAIKAN: Hapus total_kelas, total_siswa, total_pegawai dari sini**
        # Biarkan JavaScript yang mengambil dari API
        current_user=current_user
    )

# ----------------------
# API untuk Dashboard Kepala Sekolah (YANG DIPERBAIKI)
# ----------------------
@tahun_ajaran_bp.route("/api/kepala_sekolah/statistik", methods=["GET"])
@login_required
def api_kepala_sekolah_statistik():
    """API untuk data statistik kepala sekolah - DIPERBAIKI"""
    try:
        sekolah_id = request.args.get('sekolah_id')
        tahun_ajaran_id = request.args.get('tahun_ajaran_id')
        bulan_filter = request.args.get('bulan', '')
        kelas_filter = request.args.get('kelas', 'all')
        
        print(f"Debug API: sekolah_id={sekolah_id}, tahun_ajaran_id={tahun_ajaran_id}")
        
        # Validasi parameter
        if not sekolah_id or not tahun_ajaran_id:
            return jsonify({'error': 'Parameter sekolah_id dan tahun_ajaran_id diperlukan'}), 400
        
        # Ambil data sekolah dan tahun ajaran
        sekolah = Sekolah.query.get(sekolah_id)
        tahun_ajaran_aktif = TahunAjaran.query.get(tahun_ajaran_id)
        
        if not sekolah or not tahun_ajaran_aktif:
            return jsonify({'error': 'Data sekolah atau tahun ajaran tidak ditemukan'}), 404
        
        # **PERBAIKAN 1: Hitung statistik dengan query yang lebih akurat**
        total_kelas = Kelas.query.filter_by(
            sekolah_id=sekolah_id, 
            tahun_ajaran_id=tahun_ajaran_id
        ).count()
        
        total_siswa = Siswa.query.join(Kelas).filter(
            Kelas.sekolah_id == sekolah_id, 
            Kelas.tahun_ajaran_id == tahun_ajaran_id
        ).count()
        
        # **PERBAIKAN 2: Hitung total pegawai/guru dengan cara yang aman**
        # Cek dulu struktur model Pegawai
        total_guru = 0
        
        # Cara 1: Jika ada kolom jabatan
        if hasattr(Pegawai, 'jabatan'):
            total_guru = Pegawai.query.filter_by(
                sekolah_id=sekolah_id
            ).filter(
                Pegawai.jabatan.ilike('%guru%') | 
                Pegawai.jabatan.ilike('%wali%') |
                Pegawai.jabatan.ilike('%pengajar%')
            ).count()
        
        # Cara 2: Jika tidak ada kolom jabatan, hitung semua pegawai kecuali kepala sekolah
        if total_guru == 0:
            total_guru = Pegawai.query.filter_by(sekolah_id=sekolah_id).filter(
                Pegawai.id != tahun_ajaran_aktif.kepala_sekolah_id
            ).count()
            
            # Jika masih 0, hitung semua pegawai di sekolah
            if total_guru == 0:
                total_guru = Pegawai.query.filter_by(sekolah_id=sekolah_id).count()
        
        print(f"Debug Statistik: Kelas={total_kelas}, Siswa={total_siswa}, Guru={total_guru}")
        
        # Data untuk grafik kebiasaan per kelas (10 KELAS TERBAIK)
        habits_data = get_habits_data_by_kelas_terbaik(sekolah_id, tahun_ajaran_id, bulan_filter)
        
        # Data trend perkembangan (SATU SEKOLAH - SEMESTER)
        trend_data = get_trend_data_kepala_sekolah(sekolah_id, tahun_ajaran_id)
        
        # Data statistik per siswa dengan filter
        siswa_data = get_siswa_stats(sekolah_id, tahun_ajaran_id, bulan_filter, kelas_filter)
        
        # Data list kelas untuk filter
        kelas_list = get_kelas_list(sekolah_id, tahun_ajaran_id)
        
        # Hitung rata-rata sekolah
        rata_rata_sekolah = calculate_rata_rata_sekolah(sekolah_id, tahun_ajaran_id, bulan_filter)
        
        return jsonify({
            "success": True,
            "tahun_ajaran": tahun_ajaran_aktif.tahun_ajaran,
            "sekolah_nama": sekolah.nama_sekolah,
            "data": {
                "total_kelas": total_kelas,
                "total_siswa": total_siswa,
                "total_pegawai": total_guru,
                "rata_rata_sekolah": round(rata_rata_sekolah, 1)
            },
            "habits_data": habits_data,
            "trend_data": trend_data,
            "siswa_data": siswa_data,
            "kelas_list": kelas_list
        })
        
    except Exception as e:
        print(f"Error in api_kepala_sekolah_statistik: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Terjadi kesalahan server'}), 500


@tahun_ajaran_bp.route("/api/kepala_sekolah/bulan", methods=["GET"])
@login_required
def api_kepala_sekolah_bulan():
    """API untuk mendapatkan list bulan dalam tahun ajaran"""
    try:
        tahun_ajaran_id = request.args.get('tahun_ajaran_id')
        
        if not tahun_ajaran_id:
            return jsonify({'error': 'Parameter tahun_ajaran_id diperlukan'}), 400
        
        tahun_ajaran = TahunAjaran.query.get(tahun_ajaran_id)
        if not tahun_ajaran:
            return jsonify({'error': 'Tahun ajaran tidak ditemukan'}), 404
        
        bulan_list = generate_bulan_list_for_semester(tahun_ajaran)
        
        return jsonify({
            "success": True,
            "bulan_list": bulan_list
        })
        
    except Exception as e:
        print(f"Error in api_kepala_sekolah_bulan: {str(e)}")
        return jsonify({'error': 'Terjadi kesalahan server'}), 500

@tahun_ajaran_bp.route("/dashboard_multi_sekolah")
@login_required
def dashboard_multi_sekolah():
    """Dashboard untuk kepala sekolah yang memimpin multiple sekolah"""
    pegawai = current_user.pegawai
    
    # Ambil semua sekolah dimana user adalah kepala sekolah
    sekolah_kepala_list = TahunAjaran.query.filter_by(
        kepala_sekolah_id=pegawai.id,
        aktif=True
    ).join(Sekolah).all()
    
    # Kategorikan: Tetap vs PLT
    sekolah_data = []
    for ta in sekolah_kepala_list:
        is_plt = ta.sekolah_id != pegawai.sekolah_id
        status = "PLT" if is_plt else "Kepala Sekolah Tetap"
        status_color = "warning" if is_plt else "success"
        
        sekolah_data.append({
            'tahun_ajaran_id': ta.id,
            'tahun_ajaran': ta.tahun_ajaran,
            'sekolah_id': ta.sekolah_id,
            'sekolah_nama': ta.sekolah.nama_sekolah,
            'is_plt': is_plt,
            'status': status,
            'status_color': status_color
        })
    
    return render_template(
        "dashboard_multi_sekolah.html",
        sekolah_data=sekolah_data,
        current_user=current_user,
        pegawai=pegawai
    )

@tahun_ajaran_bp.route("/set_sekolah_aktif", methods=["POST"])
@login_required
def set_sekolah_aktif():
    """Set sekolah aktif untuk session kepala sekolah"""
    tahun_ajaran_id = request.form.get("tahun_ajaran_id")
    sekolah_id = request.form.get("sekolah_id")
    
    # Validasi: pastikan user memang kepala sekolah di sekolah ini
    ta = TahunAjaran.query.filter_by(
        id=tahun_ajaran_id,
        kepala_sekolah_id=current_user.pegawai.id,
        aktif=True
    ).first()
    
    if not ta:
        flash("Akses ditolak!", "danger")
        return redirect(url_for("tahun_ajaran.dashboard"))
    
    # Simpan di session
    session['kepala_sekolah_tahun_ajaran_id'] = tahun_ajaran_id
    session['kepala_sekolah_sekolah_id'] = sekolah_id
    session['is_plt'] = (int(sekolah_id) != current_user.pegawai.sekolah_id)
    
    flash("Mode kepala sekolah diaktifkan!", "success")
    return redirect(url_for("tahun_ajaran.dashboard_kepala_sekolah"))

@tahun_ajaran_bp.route("/switch_to_wali_kelas")
@login_required
def switch_to_wali_kelas():
    """Switch dari mode kepala sekolah ke mode wali kelas"""
    session.pop('kepala_sekolah_tahun_ajaran_id', None)
    session.pop('kepala_sekolah_sekolah_id', None)
    session.pop('is_plt', None)
    
    flash("Berhasil beralih ke mode Wali Kelas", "info")
    return redirect(url_for("tahun_ajaran.dashboard"))

@tahun_ajaran_bp.route("/switch_sekolah")
@login_required
def switch_sekolah():
    """Switch ke sekolah lain (untuk kepala sekolah multi-sekolah)"""
    # Clear session untuk memaksa pilih sekolah lagi
    session.pop('kepala_sekolah_tahun_ajaran_id', None)
    session.pop('kepala_sekolah_sekolah_id', None)
    session.pop('is_plt', None)
    
    return redirect(url_for("tahun_ajaran.dashboard_multi_sekolah"))