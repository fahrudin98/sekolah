from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from penilaiansiswa.models import Kebiasaan, Kelas, Siswa, TahunAjaran
from datetime import datetime
import calendar
from penilaiansiswa import db

penilaian_bp = Blueprint("penilaian", __name__, url_prefix="/penilaian")


# =========================
# FILTER CUSTOM JINJA
# =========================
def register_filters():
    def month_name_filter(month_number):
        try:
            return calendar.month_name[int(month_number)]
        except (ValueError, IndexError):
            return ""
    current_app.jinja_env.filters['month_name'] = month_name_filter


# =========================
# SAVE / UPDATE KEBIASAAN PER ROW
# =========================
@penilaian_bp.route("/kebiasaan/save_row", methods=["POST"])
@login_required
def save_kebiasaan_row():
    siswa_id = request.form.get("siswa_id")
    kelas_id = request.form.get("kelas_id")
    bulan = request.form.get("bulan")
    
    if not (siswa_id and kelas_id and bulan):
        return jsonify({"success": False, "message": "Data tidak lengkap"}), 400

    # ✅ cek apakah kelas valid dan wali_kelas_id = current_user.pegawai.id
    kelas = Kelas.query.get(kelas_id)
    if not kelas or kelas.wali_kelas_id != current_user.pegawai.id:
        return jsonify({"success": False, "message": "Anda bukan wali kelas dari kelas ini"}), 403

    # ✅ cek apakah siswa memang ada di kelas tersebut
    siswa = Siswa.query.filter_by(id=siswa_id, kelas_id=kelas.id).first()
    if not siswa:
        return jsonify({"success": False, "message": "Siswa tidak ditemukan di kelas ini"}), 404

    # ✅ lanjutkan simpan/update
    kebiasaan = Kebiasaan.query.filter_by(
        siswa_id=siswa.id, kelas_id=kelas.id, bulan=bulan
    ).first()

    if not kebiasaan:
        kebiasaan = Kebiasaan(siswa_id=siswa_id, kelas_id=kelas_id, bulan=bulan)
        db.session.add(kebiasaan)

    # Update nilai
    for field in ["bangun_pagi", "beribadah", "berolahraga", "sehat_dan_lemar",
                  "belajar", "bermasyarakat", "tidur_cepat", "catatan"]:
        setattr(kebiasaan, field, request.form.get(field) or None)

    db.session.commit()
    return jsonify({"success": True, "message": "Data berhasil disimpan"})


# =========================
# DELETE KEBIASAAN PER ROW (HAPUS ISI)
# =========================
@penilaian_bp.route("/kebiasaan/delete_row/<int:siswa_id>/<bulan>", methods=["POST"])
@login_required
def delete_kebiasaan_row(siswa_id, bulan):
    kebiasaan = Kebiasaan.query.filter_by(
        siswa_id=siswa_id,
        bulan=bulan
    ).first()
    if kebiasaan:
        for field in ["bangun_pagi", "beribadah", "berolahraga", "sehat_dan_lemar",
                      "belajar", "bermasyarakat", "tidur_cepat", "catatan"]:
            setattr(kebiasaan, field, None)
        db.session.commit()
        return jsonify({"success": True, "message": "Data kebiasaan dihapus"})
    return jsonify({"success": False, "message": "Data kebiasaan tidak ditemukan"}), 404


# =========================
# HALAMAN KEBIASAAN
# =========================
@penilaian_bp.route("/kebiasaan")
@login_required
def kebiasaan():
    active_tahun_ajaran = TahunAjaran.query.filter_by(aktif=True).first()
    sekolah = current_user.pegawai.sekolah if current_user.pegawai else None
    kelas_list = []
    if sekolah and active_tahun_ajaran:
        kelas_list = Kelas.query.filter_by(
            sekolah_id=sekolah.id,
            tahun_ajaran_id=active_tahun_ajaran.id,
            wali_kelas_id=current_user.pegawai.id
        ).all()

    # DEBUG
    print("=== DEBUG ===")
    print("Login User ID:", current_user.id)
    print("Login Pegawai ID:", current_user.pegawai.id if current_user.pegawai else None)
    print("Kelas list hasil filter:")
    for k in kelas_list:
        print(f"- {k.nama_kelas} (wali={k.wali_kelas_id})")

    return render_template(
        "penilaian/kebiasaan.html",
        active_tahun_ajaran=active_tahun_ajaran,
        sekolah=sekolah,
        kelas_list=kelas_list,
        current_year=datetime.now().year,
        current_user=current_user
    )
# =========================
# GET KELAS UNTUK PENILAIAN (tahun ajaran aktif)
# =========================
@penilaian_bp.route("/get_kelas")
@login_required
def get_kelas():
    """Return semua kelas yang dipegang oleh wali kelas saat ini pada tahun ajaran aktif"""
    # Pastikan user punya pegawai
    if not getattr(current_user, "pegawai", None):
        return jsonify({"success": False, "message": "User tidak terkait pegawai"}), 403

    sekolah = getattr(current_user.pegawai, "sekolah", None)
    if not sekolah:
        return jsonify({"success": False, "message": "Pegawai tidak terkait sekolah"}), 403

    # Ambil tahun ajaran aktif
    active_ta = TahunAjaran.query.filter_by(aktif=True, sekolah_id=sekolah.id).first()
    if not active_ta:
        return jsonify({"success": False, "message": "Tidak ada tahun ajaran aktif"}), 404

    # Ambil semua kelas yang wali_kelas = current_user.pegawai.id
    kelas_list = Kelas.query.filter_by(
        tahun_ajaran_id=active_ta.id,
        wali_kelas_id=current_user.pegawai.id
    ).order_by(Kelas.nama_kelas).all()

    return jsonify({
        "success": True,
        "kelas_list": [{"id": k.id, "nama_kelas": k.nama_kelas} for k in kelas_list],
        "tahun_ajaran_id": active_ta.id
    })


# =========================
# GET SISWA PER KELAS
# =========================
@penilaian_bp.route("/siswa/list/<int:kelas_id>")
@login_required
def get_siswa(kelas_id):
    kelas = Kelas.query.get_or_404(kelas_id)

    # Pastikan user adalah wali kelas dari kelas ini
    if kelas.wali_kelas_id != current_user.pegawai.id:
        return jsonify({"success": False, "message": "Anda bukan wali kelas dari kelas ini"}), 403

    siswa_list = Siswa.query.filter_by(kelas_id=kelas.id).order_by(Siswa.nama_siswa).all()
    return jsonify([
        {"id": s.id, "nama_siswa": s.nama_siswa} for s in siswa_list
    ])


# =========================
# GET NILAI KEBIASAAN PER KELAS + BULAN
# =========================
@penilaian_bp.route("/kebiasaan/get/<int:kelas_id>/<bulan>")
@login_required
def get_kebiasaan(kelas_id, bulan):
    kelas = Kelas.query.get_or_404(kelas_id)
    if kelas.wali_kelas_id != current_user.pegawai.id:
        return jsonify({"success": False, "message": "Anda bukan wali kelas dari kelas ini"}), 403

    siswa_list = Siswa.query.filter_by(kelas_id=kelas.id).order_by(Siswa.nama_siswa).all()
    kebiasaan_map = {
        k.siswa_id: k
        for k in Kebiasaan.query.filter_by(kelas_id=kelas.id, bulan=bulan).all()
    }

    data = []
    for idx, s in enumerate(siswa_list, 1):
        k = kebiasaan_map.get(s.id)
        data.append({
            "no": idx,
            "siswa_id": s.id,
            "nama_siswa": s.nama_siswa,
            "bangun_pagi": k.bangun_pagi if k else None,
            "beribadah": k.beribadah if k else None,
            "berolahraga": k.berolahraga if k else None,
            "sehat_dan_lemar": k.sehat_dan_lemar if k else None,
            "belajar": k.belajar if k else None,
            "bermasyarakat": k.bermasyarakat if k else None,
            "tidur_cepat": k.tidur_cepat if k else None,
            "catatan": k.catatan if k else None
        })
    return jsonify(data)