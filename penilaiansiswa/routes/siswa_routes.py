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
    nisn = (request.form.get("nisn") or "").strip()
    jk = request.form.get("jenis_kelamin")
    kelas_id = request.form.get("kelas_id")
    status = request.form.get("status") or "Aktif"

    # ✅ VALIDASI WAJIB NISN
    if not nama or not jk or not kelas_id or not nisn:
        return jsonify({"success": False, "message": "Semua field harus diisi, termasuk NISN."}), 400

    kelas = Kelas.query.get(kelas_id)
    if not kelas:
        return jsonify({"success": False, "message": "Kelas tidak ditemukan."}), 404

    # Pastikan wali kelas yg login punya hak
    if not current_user.pegawai or kelas.wali_kelas_id != current_user.pegawai.id:
        return jsonify({"success": False, "message": "Anda bukan wali kelas dari kelas ini."}), 403

    # ✅ VALIDASI NISN UNIK: Cek apakah sudah ada siswa dengan NISN yang sama 
    # di SEKOLAH YANG SAMA dan TAHUN AJARAN YANG SAMA (di kelas mana pun)
    existing_siswa = Siswa.query.join(Kelas).filter(
        Siswa.nisn == nisn,
        Kelas.sekolah_id == kelas.sekolah_id,
        Kelas.tahun_ajaran_id == kelas.tahun_ajaran_id
    ).first()
    
    if existing_siswa:
        return jsonify({
            "success": False, 
            "message": f"NISN {nisn} sudah digunakan oleh siswa {existing_siswa.nama_siswa} di kelas {existing_siswa.kelas.nama_kelas} pada tahun ajaran yang sama."
        }), 400

    try:
        siswa = Siswa(
            nama_siswa=nama,
            nisn=nisn,  # ✅ SEKARANG WAJIB, TIDAK ADA NULL
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
                "nisn": siswa.nisn,
                "jenis_kelamin": siswa.jenis_kelamin,
                "kelas": siswa.kelas.nama_kelas,
                "status": siswa.status,
                "sekolah": siswa.kelas.sekolah.nama_sekolah,
                "kecamatan": siswa.kelas.sekolah.kecamatan.nama if siswa.kelas.sekolah.kecamatan else None,
                "kabupaten": siswa.kelas.sekolah.kecamatan.kabupaten.nama if siswa.kelas.sekolah.kecamatan and siswa.kelas.sekolah.kecamatan.kabupaten else None,
                "provinsi": siswa.kelas.sekolah.kecamatan.kabupaten.provinsi.nama if siswa.kelas.sekolah.kecamatan and siswa.kelas.sekolah.kecamatan.kabupaten and siswa.kelas.sekolah.kecamatan.kabupaten.provinsi else None
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"}), 500

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
                "nisn": s.nisn,
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
    nisn = (request.form.get("nisn") or "").strip() 
    jk = request.form.get("jenis_kelamin")
    status = request.form.get("status") or "Aktif"

    # ✅ VALIDASI WAJIB NISN
    if not nama or not jk or not nisn:
        return jsonify({"success": False, "message": "Semua field harus diisi, termasuk NISN."}), 400

    # ✅ VALIDASI NISN UNIK: Cek apakah sudah ada siswa lain dengan NISN yang sama 
    # di SEKOLAH YANG SAMA dan TAHUN AJARAN YANG SAMA (di kelas mana pun)
    if nisn != siswa.nisn:  # Hanya validasi jika NISN berubah
        existing_siswa = Siswa.query.join(Kelas).filter(
            Siswa.nisn == nisn,
            Kelas.sekolah_id == kelas.sekolah_id,
            Kelas.tahun_ajaran_id == kelas.tahun_ajaran_id,
            Siswa.id != id  # Kecuali siswa yang sedang diupdate
        ).first()
        
        if existing_siswa:
            return jsonify({
                "success": False, 
                "message": f"NISN {nisn} sudah digunakan oleh siswa {existing_siswa.nama_siswa} di kelas {existing_siswa.kelas.nama_kelas} pada tahun ajaran yang sama."
            }), 400

    try:
        # update data siswa
        siswa.nama_siswa = nama
        siswa.nisn = nisn  # ✅ SEKARANG WAJIB, TIDAK ADA NULL
        siswa.jenis_kelamin = jk
        siswa.status = status
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Siswa berhasil diupdate.",
            "siswa": {
                "id": siswa.id,
                "nama_siswa": siswa.nama_siswa,
                "nisn": siswa.nisn,
                "jenis_kelamin": siswa.jenis_kelamin,
                "status": siswa.status
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"}), 500

@siswa_bp.route("/search", methods=["GET"])
@login_required
def search_siswa():
    query = request.args.get("q", "").strip()
    kelas_id = request.args.get("kelas_id")
    
    if not query:
        return jsonify({"success": False, "message": "Masukkan kata kunci pencarian"})
    
    # Cari siswa berdasarkan nama atau NISN
    siswa_list = Siswa.query.filter(
        db.or_(
            Siswa.nama_siswa.ilike(f"%{query}%"),
            Siswa.nisn.ilike(f"%{query}%")
        )
    )
    
    # Filter: cari siswa yang TIDAK di kelas mana pun di SEKOLAH YANG SAMA dan TAHUN AJARAN YANG SAMA
    if kelas_id:
        kelas = Kelas.query.get(kelas_id)
        if kelas:
            # Cari siswa yang tidak ada di sekolah yang sama dan tahun ajaran yang sama
            siswa_list = siswa_list.filter(
                ~Siswa.kelas_id.in_(
                    db.session.query(Kelas.id).filter(
                        Kelas.sekolah_id == kelas.sekolah_id,
                        Kelas.tahun_ajaran_id == kelas.tahun_ajaran_id
                    )
                )
            )
    
    siswa_list = siswa_list.limit(20).all()
    
    results = []
    for siswa in siswa_list:
        results.append({
            "id": siswa.id,
            "nama_siswa": siswa.nama_siswa,
            "nisn": siswa.nisn,
            "jenis_kelamin": siswa.jenis_kelamin,
            "status": siswa.status,
            "kelas_id": siswa.kelas_id,
            "kelas": {
                "nama_kelas": siswa.kelas.nama_kelas if siswa.kelas else None
            } if siswa.kelas else None,
            "sekolah": {
                "nama_sekolah": siswa.kelas.sekolah.nama_sekolah if siswa.kelas and siswa.kelas.sekolah else None
            } if siswa.kelas else None
        })
    
    return jsonify({
        "success": True,
        "siswa": results,
        "total": len(results)
    })

@siswa_bp.route("/add_to_class", methods=["POST"])
@login_required
def add_siswa_to_class():
    data = request.get_json()
    siswa_id = data.get("siswa_id")
    kelas_id = data.get("kelas_id")
    
    if not siswa_id or not kelas_id:
        return jsonify({"success": False, "message": "Data tidak lengkap"})
    
    # Cek apakah siswa sudah ada di kelas ini
    existing = Siswa.query.filter_by(id=siswa_id, kelas_id=kelas_id).first()
    if existing:
        return jsonify({"success": False, "message": "Siswa sudah ada di kelas ini"})
    
    # Update kelas_id siswa
    siswa = Siswa.query.get(siswa_id)
    if not siswa:
        return jsonify({"success": False, "message": "Siswa tidak ditemukan"})
    
    siswa.kelas_id = kelas_id
    db.session.commit()
    
    return jsonify({
        "success": True, 
        "message": "Siswa berhasil ditambahkan ke kelas"
    })