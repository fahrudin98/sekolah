from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func, and_, or_
from penilaiansiswa import db
from penilaiansiswa.models import Kelas, TahunAjaran, Pegawai, Sekolah, User, Kelas, Siswa
from datetime import datetime

siswa_bp = Blueprint("siswa", __name__, url_prefix="/siswa")

@siswa_bp.route("/create", methods=["POST"])
@login_required
def create_siswa():
    nama = (request.form.get("nama_siswa") or "").strip()
    nisn = (request.form.get("nisn") or "").strip()
    jk = request.form.get("jenis_kelamin")
    kelas_id = request.form.get("kelas_id")
    status = request.form.get("status") or "Aktif"

    # ✅ VALIDASI WAJIB
    if not nama or not jk or not kelas_id or not nisn:
        return jsonify({"success": False, "message": "Semua field harus diisi, termasuk NISN."}), 400

    try:
        kelas = Kelas.query.get(kelas_id)
        if not kelas:
            return jsonify({"success": False, "message": "Kelas tidak ditemukan."}), 404

        # Pastikan wali kelas yg login punya hak
        if not current_user.pegawai or kelas.wali_kelas_id != current_user.pegawai.id:
            return jsonify({"success": False, "message": "Anda bukan wali kelas dari kelas ini."}), 403

        # 🔧 PERBAIKAN: Cek siswa dengan NISN yang sama di SEKOLAH YANG SAMA (bukan cuma tahun ajaran)
        existing_siswa = Siswa.query.join(Kelas).filter(
            Siswa.nisn == nisn,
            Kelas.sekolah_id == kelas.sekolah_id
        ).first()
        
        if existing_siswa:
            # Cek apakah di tahun ajaran yang sama
            if existing_siswa.kelas.tahun_ajaran_id == kelas.tahun_ajaran_id:
                # ❌ SISWA SUDAH ADA DI TAHUN AJARAN INI
                return jsonify({
                    "success": False, 
                    "message": f"⚠️ NISN <strong>{nisn}</strong> sudah digunakan oleh siswa <strong>{existing_siswa.nama_siswa}</strong> di kelas <strong>{existing_siswa.kelas.nama_kelas}</strong> pada tahun ajaran <strong>{existing_siswa.kelas.tahun_ajaran.tahun_ajaran_display}</strong>. Silakan gunakan NISN yang berbeda.",
                    "type": "warning",
                    "existing_data": {
                        "nama_siswa": existing_siswa.nama_siswa,
                        "kelas": existing_siswa.kelas.nama_kelas,
                        "nisn": existing_siswa.nisn,
                        "tahun_ajaran": existing_siswa.kelas.tahun_ajaran.tahun_ajaran_display
                    }
                }), 200
            else:
                # ✅ SISWA DARI TAHUN AJARAN SEBELUMNYA (NAIK KELAS)
                # Nonaktifkan yang lama
                existing_siswa.status = "Tidak Aktif (Naik Kelas)"
                db.session.add(existing_siswa)
                
                # Buat record baru untuk tahun ajaran sekarang
                siswa_baru = Siswa(
                    nama_siswa=nama,
                    nisn=nisn,
                    jenis_kelamin=jk,
                    kelas_id=kelas.id,
                    status="Aktif"
                )
                db.session.add(siswa_baru)
                db.session.commit()
                
                return jsonify({
                    "success": True,
                    "message": f"✅ Siswa <strong>{nama}</strong> berhasil dipindahkan dari <strong>{existing_siswa.kelas.nama_kelas}</strong> ke <strong>{kelas.nama_kelas}</strong> untuk tahun ajaran <strong>{kelas.tahun_ajaran.tahun_ajaran_display}</strong>",
                    "type": "success",
                    "siswa": {
                        "id": siswa_baru.id,
                        "nama_siswa": siswa_baru.nama_siswa,
                        "nisn": siswa_baru.nisn,
                        "jenis_kelamin": siswa_baru.jenis_kelamin,
                        "kelas": siswa_baru.kelas.nama_kelas,
                        "status": siswa_baru.status,
                        "tahun_ajaran": kelas.tahun_ajaran.tahun_ajaran_display
                    }
                })

        # ✅ SISWA BARU (BELUM PERNAH ADA SAMA SEKALI)
        siswa = Siswa(
            nama_siswa=nama,
            nisn=nisn,
            jenis_kelamin=jk,
            kelas_id=kelas.id,
            status=status
        )
        db.session.add(siswa)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "✅ Siswa berhasil ditambahkan!",
            "type": "success",
            "siswa": {
                "id": siswa.id,
                "nama_siswa": siswa.nama_siswa,
                "nisn": siswa.nisn,
                "jenis_kelamin": siswa.jenis_kelamin,
                "kelas": siswa.kelas.nama_kelas,
                "status": siswa.status,
                "tahun_ajaran": kelas.tahun_ajaran.tahun_ajaran_display
            }
        })
        
    except Exception as e:
        db.session.rollback()
        
        # ✅ TANGANI ERROR DUPLIKASI DARI DATABASE
        error_msg = str(e)
        if "Duplicate entry" in error_msg and "nisn" in error_msg:
            # Cari data existing yang menyebabkan conflict
            try:
                conflicting_siswa = Siswa.query.join(Kelas).filter(
                    Siswa.nisn == nisn,
                    Kelas.sekolah_id == kelas.sekolah_id
                ).first()
                
                if conflicting_siswa:
                    message = f"⚠️ NISN <strong>{nisn}</strong> sudah digunakan oleh siswa <strong>{conflicting_siswa.nama_siswa}</strong> di kelas <strong>{conflicting_siswa.kelas.nama_kelas}</strong>. Silakan gunakan NISN yang berbeda."
                else:
                    message = f"⚠️ NISN <strong>{nisn}</strong> sudah digunakan. Silakan gunakan NISN yang berbeda."
            except:
                message = f"⚠️ NISN <strong>{nisn}</strong> sudah digunakan. Silakan gunakan NISN yang berbeda."
                
            return jsonify({
                "success": False, 
                "message": message,
                "type": "warning"
            }), 200
            
        else:
            # Error lainnya
            return jsonify({
                "success": False, 
                "message": f"❌ Terjadi kesalahan sistem: {error_msg}",
                "type": "error"
            }), 500


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
    return jsonify({
        "success": True, 
        "message": "✅ Siswa berhasil dihapus.",
        "type": "success"
    })

@siswa_bp.route("/update/<int:id>", methods=["POST"])
@login_required
def update_siswa(id):
    try:
        siswa = Siswa.query.get_or_404(id)
        kelas = siswa.kelas

        if not current_user.pegawai or kelas.wali_kelas_id != current_user.pegawai.id:
            return jsonify({"success": False, "message": "Anda bukan wali kelas kelas ini."}), 403

        nama = (request.form.get("nama_siswa") or "").strip()
        nisn = (request.form.get("nisn") or "").strip() 
        jk = request.form.get("jenis_kelamin")
        status = request.form.get("status") or "Aktif"

        if not nama or not jk or not nisn:
            return jsonify({"success": False, "message": "Semua field harus diisi, termasuk NISN."}), 400

        # ✅ VALIDASI NISN UNIK DENGAN LOCK
        if nisn != siswa.nisn:
            existing_siswa = Siswa.query.join(Kelas).filter(
                Siswa.nisn == nisn,
                Kelas.sekolah_id == kelas.sekolah_id,
                Kelas.tahun_ajaran_id == kelas.tahun_ajaran_id,
                Siswa.id != id
            ).with_for_update().first()
            
            if existing_siswa:
                return jsonify({
                    "success": False, 
                    "message": f"⚠️ NISN <strong>{nisn}</strong> sudah digunakan oleh siswa <strong>{existing_siswa.nama_siswa}</strong> di kelas <strong>{existing_siswa.kelas.nama_kelas}</strong>. Silakan gunakan NISN yang berbeda.",
                    "type": "warning",
                    "existing_data": {
                        "nama_siswa": existing_siswa.nama_siswa,
                        "kelas": existing_siswa.kelas.nama_kelas,
                        "nisn": existing_siswa.nisn
                    }
                }), 200

        # ✅ UPDATE DATA
        siswa.nama_siswa = nama
        siswa.nisn = nisn
        siswa.jenis_kelamin = jk
        siswa.status = status
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "✅ Data siswa berhasil diperbarui!",
            "type": "success",
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
        
        # ✅ HANDLE DATABASE DUPLICATE ERROR
        error_msg = str(e)
        if "Duplicate entry" in error_msg and "nisn" in error_msg:
            return jsonify({
                "success": False, 
                "message": f"⚠️ NISN <strong>{nisn}</strong> sudah digunakan. Silakan gunakan NISN yang berbeda.",
                "type": "warning"
            }), 200
        else:
            return jsonify({
                "success": False, 
                "message": f"❌ Terjadi kesalahan: {error_msg}",
                "type": "error"
            }), 500

# Route lainnya tetap sama...
# ============================================================
# 🔧 PERBAIKAN 2: SEARCH SISWA (dengan filter sekolah)
# ============================================================
@siswa_bp.route("/search", methods=["GET"])
@login_required
def search_siswa():
    """
    Pencarian untuk menambahkan siswa ke kelas.
    HANYAMenampilkan siswa dari SEKOLAH YANG SAMA.
    Untuk siswa dari sekolah lain, gunakan fitur Pindah Sekolah.
    """
    query = request.args.get("q", "").strip()
    kelas_id = request.args.get("kelas_id")
    
    if not query:
        return jsonify({"success": False, "message": "Masukkan kata kunci pencarian"}), 400
    
    # 🔧 PERBAIKAN: Validasi user memiliki sekolah
    if not current_user.pegawai or not current_user.pegawai.sekolah_id:
        return jsonify({"success": False, "message": "User tidak terdaftar di sekolah mana pun"}), 403
    
    user_sekolah_id = current_user.pegawai.sekolah_id
    kelas_tujuan = Kelas.query.get(kelas_id) if kelas_id else None
    
    # 🔧 PERBAIKAN: Query dengan filter sekolah
    siswa_list = Siswa.query.join(Kelas).filter(
        or_(
            Siswa.nama_siswa.ilike(f"%{query}%"),
            Siswa.nisn.ilike(f"%{query}%")
        ),
        Kelas.sekolah_id == user_sekolah_id  # 🔑 HANYA SEKOLAH USER
    )
    
    # 🔧 PERBAIKAN: Filter siswa yang SUDAH ADA di tahun ajaran yang sama
    # (menampilkan siswa yang belum terdaftar di tahun ajaran ini)
    if kelas_tujuan:
        siswa_list = siswa_list.filter(
            ~Siswa.kelas_id.in_(
                db.session.query(Kelas.id).filter(
                    Kelas.sekolah_id == user_sekolah_id,
                    Kelas.tahun_ajaran_id == kelas_tujuan.tahun_ajaran_id
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
            "kelas_sebelumnya": siswa.kelas.nama_kelas if siswa.kelas else None,
            "tahun_ajaran_sebelumnya": siswa.kelas.tahun_ajaran.tahun_ajaran_display if siswa.kelas and siswa.kelas.tahun_ajaran else None
        })
    
    return jsonify({
        "success": True,
        "siswa": results,
        "total": len(results),
        "catatan": "Hanya menampilkan siswa dari sekolah yang sama. Untuk pindah sekolah, gunakan fitur Pindah Sekolah."
    })


# ============================================================
# 🔧 PERBAIKAN 3: ADD TO CLASS (aman dengan validasi)
# ============================================================
@siswa_bp.route("/add_to_class", methods=["POST"])
@login_required
def add_siswa_to_class():
    """
    Memindahkan siswa ke kelas lain (dalam satu sekolah)
    - Siswa akan dinonaktifkan di kelas lama
    - Dibuat record baru di kelas baru
    """
    data = request.get_json()
    siswa_id = data.get("siswa_id")
    kelas_id = data.get("kelas_id")
    
    if not siswa_id or not kelas_id:
        return jsonify({"success": False, "message": "Data tidak lengkap"}), 400
    
    kelas_tujuan = Kelas.query.get(kelas_id)
    if not kelas_tujuan:
        return jsonify({"success": False, "message": "Kelas tujuan tidak ditemukan"}), 404
    
    # 🔧 PERBAIKAN 1: Validasi wali kelas dari kelas tujuan
    if not current_user.pegawai or kelas_tujuan.wali_kelas_id != current_user.pegawai.id:
        return jsonify({"success": False, "message": "Anda bukan wali kelas dari kelas tujuan"}), 403
    
    siswa = Siswa.query.get(siswa_id)
    if not siswa:
        return jsonify({"success": False, "message": "Siswa tidak ditemukan"}), 404
    
    # 🔧 PERBAIKAN 2: Validasi siswa dari sekolah yang sama
    if siswa.kelas.sekolah_id != kelas_tujuan.sekolah_id:
        return jsonify({
            "success": False, 
            "message": "❌ Siswa dari sekolah lain. Gunakan fitur Pindah Sekolah untuk memindahkan siswa antar sekolah."
        }), 400
    
    # 🔧 PERBAIKAN 3: Cek apakah siswa sudah terdaftar di tahun ajaran yang sama
    existing = Siswa.query.filter(
        Siswa.nisn == siswa.nisn,
        Siswa.kelas.has(
            Kelas.tahun_ajaran_id == kelas_tujuan.tahun_ajaran_id,
            Kelas.sekolah_id == kelas_tujuan.sekolah_id
        ),
        Siswa.id != siswa_id
    ).first()
    
    if existing:
        return jsonify({
            "success": False,
            "message": f"⚠️ Siswa {siswa.nama_siswa} sudah terdaftar di {existing.kelas.nama_kelas} pada tahun ajaran {kelas_tujuan.tahun_ajaran.tahun_ajaran_display}"
        }), 400
    
    # 🔧 PERBAIKAN 4: Jangan pindah ke kelas yang sama
    if siswa.kelas_id == kelas_tujuan.id:
        return jsonify({
            "success": False,
            "message": "Siswa sudah berada di kelas ini"
        }), 400
    
    # ✅ Proses pindah: nonaktifkan lama, buat baru
    siswa_lama_id = siswa.id
    siswa_lama_nama = siswa.nama_siswa
    
    # Nonaktifkan record lama
    siswa.status = f"Tidak Aktif (Pindah ke {kelas_tujuan.nama_kelas})"
    
    # Buat record baru
    siswa_baru = Siswa(
        nama_siswa=siswa.nama_siswa,
        nisn=siswa.nisn,
        jenis_kelamin=siswa.jenis_kelamin,
        kelas_id=kelas_tujuan.id,
        status="Aktif"
    )
    
    db.session.add(siswa_baru)
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": f"✅ Siswa {siswa_lama_nama} berhasil dipindahkan ke {kelas_tujuan.nama_kelas}",
        "siswa_baru": {
            "id": siswa_baru.id,
            "nama_siswa": siswa_baru.nama_siswa,
            "nisn": siswa_baru.nisn,
            "kelas": kelas_tujuan.nama_kelas
        }
    })

# ============================================================
# ➕ TAMBAHAN: HISTORI SISWA (lihat riwayat pindah/naik kelas)
# ============================================================
@siswa_bp.route("/histori/<int:siswa_id>", methods=["GET"])
@login_required
def histori_siswa(siswa_id):
    """
    Menampilkan histori lengkap seorang siswa berdasarkan NISN
    (semua record dengan NISN yang sama)
    """
    siswa = Siswa.query.get(siswa_id)
    if not siswa:
        return jsonify({"success": False, "message": "Siswa tidak ditemukan"}), 404
    
    # Validasi akses: user harus dari sekolah yang sama
    if not current_user.pegawai or siswa.kelas.sekolah_id != current_user.pegawai.sekolah_id:
        if not current_user.is_superadmin:
            return jsonify({"success": False, "message": "Anda tidak memiliki akses ke histori siswa ini"}), 403
    
    # Cari semua record dengan NISN yang sama
    semua_record = Siswa.query.filter_by(nisn=siswa.nisn).join(
        Kelas
    ).join(
        TahunAjaran, Kelas.tahun_ajaran_id == TahunAjaran.id
    ).order_by(
        TahunAjaran.tahun_ajaran.desc(), 
        TahunAjaran.semester.desc()
    ).all()
    
    histori = []
    for record in semua_record:
        histori.append({
            "id": record.id,
            "nama_siswa": record.nama_siswa,
            "status": record.status,
            "kelas": record.kelas.nama_kelas,
            "tahun_ajaran": record.kelas.tahun_ajaran.tahun_ajaran_display,
            "sekolah": record.kelas.sekolah.nama_sekolah,
            "is_active": record.status == "Aktif"
        })
    
    return jsonify({
        "success": True,
        "siswa": {
            "nama": siswa.nama_siswa,
            "nisn": siswa.nisn,
            "jenis_kelamin": siswa.jenis_kelamin
        },
        "histori": histori,
        "total_record": len(histori)
    })


# ============================================================
# ➕ TAMBAHAN: NAIK KELAS MASSAL (opsional)
# ============================================================
@siswa_bp.route("/naik_kelas_massal", methods=["POST"])
@login_required
def naik_kelas_massal():
    """
    Menghandle kenaikan kelas untuk semua siswa di suatu kelas
    (misal: semua siswa kelas 1 naik ke kelas 2 di tahun ajaran baru)
    """
    data = request.get_json()
    dari_kelas_id = data.get("dari_kelas_id")
    ke_kelas_id = data.get("ke_kelas_id")
    
    if not dari_kelas_id or not ke_kelas_id:
        return jsonify({"success": False, "message": "Data tidak lengkap"}), 400
    
    dari_kelas = Kelas.query.get(dari_kelas_id)
    if not dari_kelas:
        return jsonify({"success": False, "message": "Kelas asal tidak ditemukan"}), 404
    
    # Validasi wali kelas
    if not current_user.pegawai or dari_kelas.wali_kelas_id != current_user.pegawai.id:
        if not current_user.is_superadmin:
            return jsonify({"success": False, "message": "Anda bukan wali kelas dari kelas asal"}), 403
    
    ke_kelas = Kelas.query.get(ke_kelas_id)
    if not ke_kelas:
        return jsonify({"success": False, "message": "Kelas tujuan tidak ditemukan"}), 404
    
    # Validasi: tahun ajaran harus berbeda
    if dari_kelas.tahun_ajaran_id == ke_kelas.tahun_ajaran_id:
        return jsonify({"success": False, "message": "Kelas tujuan harus berada di tahun ajaran yang berbeda"}), 400
    
    # Ambil semua siswa aktif di kelas asal
    siswa_list = Siswa.query.filter_by(
        kelas_id=dari_kelas_id,
        status="Aktif"
    ).all()
    
    if not siswa_list:
        return jsonify({"success": False, "message": "Tidak ada siswa aktif di kelas asal"}), 400
    
    hasil = {
        "berhasil": [],
        "gagal": [],
        "total": len(siswa_list)
    }
    
    for siswa_lama in siswa_list:
        try:
            # Cek apakah siswa sudah ada di tahun ajaran tujuan
            existing = Siswa.query.join(Kelas).filter(
                Siswa.nisn == siswa_lama.nisn,
                Kelas.tahun_ajaran_id == ke_kelas.tahun_ajaran_id,
                Kelas.sekolah_id == ke_kelas.sekolah_id
            ).first()
            
            if existing:
                hasil["gagal"].append({
                    "nama": siswa_lama.nama_siswa,
                    "nisn": siswa_lama.nisn,
                    "alasan": f"Sudah terdaftar di {existing.kelas.nama_kelas}"
                })
                continue
            
            # Nonaktifkan siswa lama
            siswa_lama.status = "Tidak Aktif (Naik Kelas)"
            
            # Buat siswa baru di kelas tujuan
            siswa_baru = Siswa(
                nama_siswa=siswa_lama.nama_siswa,
                nisn=siswa_lama.nisn,
                jenis_kelamin=siswa_lama.jenis_kelamin,
                kelas_id=ke_kelas.id,
                status="Aktif"
            )
            db.session.add(siswa_baru)
            
            hasil["berhasil"].append({
                "nama": siswa_lama.nama_siswa,
                "nisn": siswa_lama.nisn,
                "dari_kelas": dari_kelas.nama_kelas,
                "ke_kelas": ke_kelas.nama_kelas
            })
            
        except Exception as e:
            hasil["gagal"].append({
                "nama": siswa_lama.nama_siswa,
                "nisn": siswa_lama.nisn,
                "alasan": str(e)
            })
    
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": f"Naik kelas selesai: {len(hasil['berhasil'])} berhasil, {len(hasil['gagal'])} gagal",
        "data": hasil
    })