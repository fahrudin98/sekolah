# tahun_ajaran_routes.py
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, abort
from flask_login import login_required, current_user
from penilaiansiswa.models import TahunAjaran, Pegawai, Sekolah, User, Kelas, Siswa, Kebiasaan
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
# Dashboard route
# ----------------------
@tahun_ajaran_bp.route("/dashboard")
@login_required
def dashboard():
    sekolah = None
    kelas_list = []
    existing_tahun = None
    nonaktif_tahun = []

    # coba ambil sekolah dari pegawai user
    if getattr(current_user, "pegawai", None) and current_user.pegawai.sekolah_id:
        sekolah = current_user.pegawai.sekolah

    if sekolah:
        existing_tahun = TahunAjaran.query.filter_by(sekolah_id=sekolah.id, aktif=True).first()
        nonaktif_tahun = TahunAjaran.query.filter_by(sekolah_id=sekolah.id, aktif=False).order_by(TahunAjaran.id.desc()).all()

    # pegawai list (profil)
    pegawai_q = []
    if sekolah:
        pegawai_q = (
            Pegawai.query
            .join(User, User.id == Pegawai.user_id)
            .filter(Pegawai.sekolah_id == sekolah.id)
            .order_by(User.nama_lengkap)
            .all()
        )

    # kelas hanya yang dimiliki user (wali) pada tahun ajaran aktif
    if existing_tahun and sekolah:
        # ✅ pakai helper filter kelas sesuai role (wali/superadmin)
        kelas_list = get_kelas_for_current_user(sekolah, existing_tahun)
        # ✅ generate bulan sesuai semester (ganjil/genap)
        bulan_list = generate_bulan_list_for_semester(existing_tahun)
    else:
        bulan_list = []

    return render_template(
        "dashboard.html",
        username=current_user.username,
        sekolah=sekolah,
        active_tahun_ajaran=existing_tahun,
        nonaktif_tahun_ajaran=nonaktif_tahun,
        pegawai_dengan_profil=pegawai_q,
        kelas_list=kelas_list,
        bulan_list=bulan_list,
        current_user=current_user
    )


# ----------------------
# Add / toggle Tahun Ajaran (tetap seperti Anda punya)
# ----------------------
@tahun_ajaran_bp.route("/add_tahun_ajaran", methods=["POST"])
@login_required
def add_tahun_ajaran():
    if not current_user.pegawai or not current_user.pegawai.sekolah_id:
        return jsonify({"success": False, "message": "User tidak terkait sekolah."}), 400

    sekolah_id = current_user.pegawai.sekolah_id

    tahun_ajaran = (request.form.get("tahun_ajaran") or "").strip()
    semester = (request.form.get("semester") or "").strip().lower()
    kepala_sekolah_id = request.form.get("kepala_sekolah_id")

    if not tahun_ajaran or not semester or not kepala_sekolah_id:
        return jsonify({"success": False, "message": "Data tidak lengkap."}), 400

    if semester not in ["ganjil", "genap"]:
        return jsonify({"success": False, "message": "Semester tidak valid."}), 400

    kepala = Pegawai.query.filter_by(id=kepala_sekolah_id, sekolah_id=sekolah_id).first()
    if not kepala:
        return jsonify({"success": False, "message": "Kepala sekolah tidak valid atau belum mengisi profil."}), 400

    # Validasi duplikat (case-insensitive)
    existing = TahunAjaran.query.filter(
        TahunAjaran.sekolah_id == sekolah_id,
        func.lower(TahunAjaran.tahun_ajaran) == tahun_ajaran.lower(),
        func.lower(TahunAjaran.semester) == semester
    ).first()

    if existing:
        return jsonify({
            "success": False,
            "message": f"Tahun ajaran {tahun_ajaran} semester {semester} sudah ada."
        }), 409

    # Pastikan tidak ada tahun ajaran aktif lain
    existing_active = TahunAjaran.query.filter_by(sekolah_id=sekolah_id, aktif=True).first()
    if existing_active:
        return jsonify({"success": False, "message": "Masih ada tahun ajaran aktif. Nonaktifkan dulu."}), 400

    # Buat baru
    t = TahunAjaran(
        sekolah_id=sekolah_id,
        tahun_ajaran=tahun_ajaran,
        semester=semester,
        kepala_sekolah_id=kepala.id,
        aktif=True
    )
    db.session.add(t)
    db.session.commit()

    return jsonify({"success": True, "message": "Tahun ajaran baru berhasil dibuat & diaktifkan."}), 200


@tahun_ajaran_bp.route("/toggle_tahun_ajaran", methods=["POST"])
@login_required
def toggle_tahun_ajaran():
    if not current_user.pegawai or not current_user.pegawai.sekolah_id:
        return jsonify({"success": False, "message": "User tidak terkait sekolah."}), 400

    sekolah_id = current_user.pegawai.sekolah_id
    tahun_id = request.form.get("id")
    tahun = TahunAjaran.query.filter_by(id=tahun_id, sekolah_id=sekolah_id).first()
    if not tahun:
        return jsonify({"success": False, "message": "Tahun ajaran tidak ditemukan."}), 404

    if not tahun.aktif:
        # aktifkan -> pastikan hanya 1 aktif
        TahunAjaran.query.filter_by(sekolah_id=sekolah_id, aktif=True).update({TahunAjaran.aktif: False})
        tahun.aktif = True
    else:
        tahun.aktif = False

    db.session.commit()
    return jsonify({"success": True, "aktif": tahun.aktif, "message": "Status diperbarui."})
