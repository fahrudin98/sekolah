from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from penilaiansiswa import db
from penilaiansiswa.models import Kelas, TahunAjaran, Pegawai, Sekolah, User, Kelas, Siswa

siswa_bp = Blueprint("siswa", __name__, url_prefix="/siswa")
@siswa_bp.route("/create", methods=["POST"])
@login_required
def create_siswa():
    nama = (request.form.get("nama_siswa") or "").strip()
    jk = request.form.get("jenis_kelamin")
    kelas_id = request.form.get("kelas_id")
    status = request.form.get("status") or "Aktif"

    if not nama or not jk or not kelas_id:
        return jsonify({"success": False, "message": "Data tidak lengkap."}), 400

    kelas = Kelas.query.get(kelas_id)
    if not kelas:
        return jsonify({"success": False, "message": "Kelas tidak ditemukan."}), 404

    # Pastikan wali kelas yg login punya hak
    if not current_user.pegawai or kelas.wali_kelas_id != current_user.pegawai.id:
        return jsonify({"success": False, "message": "Anda bukan wali kelas dari kelas ini."}), 403

    siswa = Siswa(
        nama_siswa=nama,
        jenis_kelamin=jk,
        kelas_id=kelas.id,
        status=status
    )
    db.session.add(siswa)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Siswa berhasil ditambahkan.",
        "siswa": {
            "id": siswa.id,
            "nama_siswa": siswa.nama_siswa,
            "jenis_kelamin": siswa.jenis_kelamin,
            "kelas": siswa.kelas.nama_kelas,
            "status": siswa.status,
            "sekolah": siswa.kelas.sekolah.nama_sekolah,
            "kecamatan": siswa.kelas.sekolah.kecamatan.nama if siswa.kelas.sekolah.kecamatan else None,
            "kabupaten": siswa.kelas.sekolah.kecamatan.kabupaten.nama if siswa.kelas.sekolah.kecamatan and siswa.kelas.sekolah.kecamatan.kabupaten else None,
            "provinsi": siswa.kelas.sekolah.kecamatan.kabupaten.provinsi.nama if siswa.kelas.sekolah.kecamatan and siswa.kelas.sekolah.kecamatan.kabupaten and siswa.kelas.sekolah.kecamatan.kabupaten.provinsi else None
        }
    })
@siswa_bp.route("/list/<int:kelas_id>")
@login_required
def list_siswa(kelas_id):
    kelas = Kelas.query.get_or_404(kelas_id)

    # cek wali kelas
    if not current_user.pegawai or kelas.wali_kelas_id != current_user.pegawai.id:
        return jsonify({"success": False, "message": "Anda bukan wali kelas kelas ini."}), 403

    siswa = Siswa.query.filter_by(kelas_id=kelas.id).all()
    return jsonify({
        "success": True,
        "siswa": [
            {
                "id": s.id,
                "nama_siswa": s.nama_siswa,
                "jenis_kelamin": s.jenis_kelamin,
                "status": s.status
            } for s in siswa
        ]
    })

@siswa_bp.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete_siswa(id):
    siswa = Siswa.query.get_or_404(id)
    kelas = siswa.kelas

    if not current_user.pegawai or kelas.wali_kelas_id != current_user.pegawai.id:
        return jsonify({"success": False, "message": "Anda bukan wali kelas kelas ini."}), 403

    db.session.delete(siswa)
    db.session.commit()
    return jsonify({"success": True, "message": "Siswa berhasil dihapus."})



@siswa_bp.route("/update/<int:id>", methods=["POST"])
@login_required
def update_siswa(id):
    siswa = Siswa.query.get_or_404(id)
    kelas = siswa.kelas

    # cek apakah wali kelas yang login punya hak
    if not current_user.pegawai or kelas.wali_kelas_id != current_user.pegawai.id:
        return jsonify({"success": False, "message": "Anda bukan wali kelas kelas ini."}), 403

    # ambil data dari form
    nama = (request.form.get("nama_siswa") or "").strip()
    jk = request.form.get("jenis_kelamin")
    status = request.form.get("status") or "Aktif"

    if not nama or not jk:
        return jsonify({"success": False, "message": "Data tidak lengkap."}), 400

    # update data siswa
    siswa.nama_siswa = nama
    siswa.jenis_kelamin = jk
    siswa.status = status
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Siswa berhasil diupdate.",
        "siswa": {
            "id": siswa.id,
            "nama_siswa": siswa.nama_siswa,
            "jenis_kelamin": siswa.jenis_kelamin,
            "status": siswa.status
        }
    })