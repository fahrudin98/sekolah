from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from penilaiansiswa import db
from penilaiansiswa.models import Kelas, TahunAjaran, Pegawai

kelas_bp = Blueprint("kelas", __name__, url_prefix="/kelas")

@kelas_bp.route("/create", methods=["POST"])
@login_required
def create_kelas():
    # Ambil pegawai yang login
    pegawai = current_user.pegawai
    if not pegawai:
        return jsonify({"success": False, "message": "Pegawai tidak ditemukan."}), 400

    sekolah_id = pegawai.sekolah_id
    wali_kelas_id = pegawai.id

    # Ambil tahun ajaran aktif
    active_tahun_ajaran = TahunAjaran.query.filter_by(
        sekolah_id=sekolah_id,
        aktif=True
    ).first()
    if not active_tahun_ajaran:
        return jsonify({"success": False, "message": "Tidak ada tahun ajaran aktif."}), 400

    # Ambil nama kelas dari form
    nama_kelas = (request.form.get("nama_kelas") or "").strip()
    if not nama_kelas:
        return jsonify({"success": False, "message": "Nama kelas wajib diisi."}), 400

    # Cek duplikat (case-insensitive)
    existing = Kelas.query.filter(
        Kelas.tahun_ajaran_id == active_tahun_ajaran.id,
        Kelas.sekolah_id == sekolah_id,
        func.lower(Kelas.nama_kelas) == nama_kelas.lower()
    ).first()
    if existing:
        return jsonify({"success": False, "message": "Kelas ini sudah ada di tahun ajaran aktif."}), 409

    # Tambah kelas baru
    kelas = Kelas(
        tahun_ajaran_id=active_tahun_ajaran.id,
        nama_kelas=nama_kelas,
        wali_kelas_id=current_user.pegawai.id,
        sekolah_id=current_user.pegawai.sekolah_id
    )
    db.session.add(kelas)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Kelas berhasil ditambahkan",
        "kelas": {
        "id": kelas.id,
        "nama_kelas": kelas.nama_kelas,
        "wali_kelas": {
            "nama": kelas.wali_kelas.nama,
            "nip": kelas.wali_kelas.nip
        }
    }
    }), 200

@kelas_bp.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete_kelas(id):
    kelas = Kelas.query.get_or_404(id)

    # pastikan user berhak menghapus (misal: harus satu sekolah)
    if not current_user.pegawai or kelas.sekolah_id != current_user.pegawai.sekolah_id:
        return jsonify({"success": False, "message": "Tidak bisa menghapus kelas ini."}), 403

    db.session.delete(kelas)
    db.session.commit()
    return jsonify({"success": True, "message": "Kelas berhasil dihapus."})




@kelas_bp.route("/edit/<int:id>", methods=["POST"])
@login_required
def edit_kelas(id):
    kelas = Kelas.query.get_or_404(id)

    # Pastikan user hanya bisa edit kelas di sekolahnya
    if not current_user.pegawai or kelas.sekolah_id != current_user.pegawai.sekolah_id:
        return jsonify({"success": False, "message": "Tidak bisa mengedit kelas ini."}), 403

    data = request.get_json() or {}
    nama_kelas = (data.get("nama_kelas") or "").strip()

    if not nama_kelas:
        return jsonify({"success": False, "message": "Nama kelas wajib diisi."}), 400

    # Cek duplikat (case-insensitive) tapi abaikan kelas yang sedang diedit
    existing = Kelas.query.filter(
        Kelas.tahun_ajaran_id == kelas.tahun_ajaran_id,
        Kelas.sekolah_id == kelas.sekolah_id,
        func.lower(Kelas.nama_kelas) == nama_kelas.lower(),
        Kelas.id != kelas.id
    ).first()
    if existing:
        return jsonify({"success": False, "message": "Nama kelas sudah digunakan."}), 409

    # Update nama kelas
    kelas.nama_kelas = nama_kelas
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Kelas berhasil diperbarui.",
        "kelas": {
            "id": kelas.id,
            "nama_kelas": kelas.nama_kelas,
            "wali_kelas": {
                "nama": kelas.wali_kelas.nama,
                "nip": kelas.wali_kelas.nip
            }
        }
    })
