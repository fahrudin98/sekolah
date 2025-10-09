from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from penilaiansiswa.models.users import Pegawai, User
from penilaiansiswa.models.sekolah import Sekolah, Kabupaten, Kecamatan, Provinsi
from flask_login import current_user, login_required
from penilaiansiswa import db

pegawai_bp = Blueprint("pegawai_bp", __name__, url_prefix="/pegawai")

# ===== AJAX cascading dropdown =====
@pegawai_bp.route("/get_kabupaten/<int:provinsi_id>")
@login_required
def get_kabupaten(provinsi_id):
    kabupaten_list = Kabupaten.query.filter_by(provinsi_id=provinsi_id).all()
    return jsonify([{"id": k.id, "nama": k.nama} for k in kabupaten_list])

@pegawai_bp.route("/get_kecamatan/<int:kabupaten_id>")
@login_required
def get_kecamatan(kabupaten_id):
    kecamatan_list = Kecamatan.query.filter_by(kabupaten_id=kabupaten_id).all()
    return jsonify([{"id": k.id, "nama": k.nama} for k in kecamatan_list])

@pegawai_bp.route("/get_sekolah/<int:kecamatan_id>")
@login_required
def get_sekolah(kecamatan_id):
    sekolah_list = Sekolah.query.filter_by(kecamatan_id=kecamatan_id).all()
    return jsonify([{"id": s.id, "nama_sekolah": s.nama_sekolah} for s in sekolah_list])

# ===== CEK NIP UNIK =====
@pegawai_bp.route("/check_nip", methods=["GET"])
@login_required
def check_nip():
    nip = request.args.get("nip", "").strip()
    
    if not nip:
        return jsonify({"exists": False})
    
    # Cari pegawai dengan NIP ini
    existing_pegawai = Pegawai.query.filter_by(nip=nip).first()
    
    if not existing_pegawai:
        return jsonify({"exists": False})
    
    # Cek apakah NIP ini milik user yang sedang login
    if existing_pegawai.user_id == current_user.id:
        return jsonify({"exists": False})  # NIP sendiri - BOLEH
    else:
        # Dapatkan nama user dari existing pegawai
        existing_user = User.query.get(existing_pegawai.user_id)
        nama_pegawai = existing_user.nama_lengkap if existing_user else "Unknown"
        return jsonify({"exists": True, "nama_pegawai": nama_pegawai})

# ===== CREATE Pegawai =====
@pegawai_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_pegawai():
    user = current_user

    if Pegawai.query.filter_by(user_id=user.id).first():
        flash("Profile pegawai sudah ada. Gunakan Update jika ingin mengubah.", "warning")
        return redirect(url_for("pegawai_bp.update_pegawai", pegawai_id=user.pegawai.id))

    if request.method == "POST":
        nip = request.form.get("nip", "").strip()
        sekolah_id = request.form.get("sekolah_id")
        nama_lengkap = request.form.get("nama_lengkap", "").strip()

        if not nip or not sekolah_id:
            flash("NIP dan Sekolah wajib diisi!", "danger")
            return redirect(url_for("pegawai_bp.create_pegawai"))

        # ✅ VALIDASI NIP UNIK - CREATE
        existing_pegawai = Pegawai.query.filter_by(nip=nip).first()
        if existing_pegawai:
            flash(f"NIP {nip} sudah digunakan oleh {existing_pegawai.user.nama_lengkap}. Silakan gunakan NIP yang berbeda.", "danger")
            return redirect(url_for("pegawai_bp.create_pegawai"))

        # update nama lengkap user juga
        if nama_lengkap:
            user.nama_lengkap = nama_lengkap

        # buat pegawai baru
        try:
            new_pegawai = Pegawai(user_id=user.id, nip=nip, sekolah_id=sekolah_id)
            db.session.add(new_pegawai)
            db.session.commit()
            
            flash("Profile pegawai berhasil dibuat!", "success")
            return redirect(url_for("tahun_ajaran.dashboard"))
        except Exception as e:
            db.session.rollback()
            flash(f"Terjadi kesalahan saat menyimpan: {str(e)}", "danger")
            return redirect(url_for("pegawai_bp.create_pegawai"))

    provinsi_list = Provinsi.query.all()
    return render_template(
        "home.html",
        user=user,
        pegawai=None,
        provinsi_list=provinsi_list,
        kabupaten_list=[],
        kecamatan_list=[],
        sekolah_list=[]
    )

# ===== UPDATE Pegawai =====
@pegawai_bp.route("/update/<int:pegawai_id>", methods=["GET", "POST"])
@login_required
def update_pegawai(pegawai_id):
    pegawai = Pegawai.query.get_or_404(pegawai_id)
    if pegawai.user_id != current_user.id:
        flash("Anda tidak memiliki akses untuk mengubah profile ini!", "danger")
        return redirect(url_for("tahun_ajaran.dashboard"))

    if request.method == "POST":
        nip = request.form.get("nip", "").strip()
        sekolah_id = request.form.get("sekolah_id")
        nama_lengkap = request.form.get("nama_lengkap", "").strip()

        if not nip or not sekolah_id:
            flash("NIP dan Sekolah wajib diisi!", "danger")
            return redirect(url_for("pegawai_bp.update_pegawai", pegawai_id=pegawai.id))

        # ✅ VALIDASI NIP UNIK - UPDATE (kecuali untuk diri sendiri)
        if nip != pegawai.nip:  # Hanya validasi jika NIP berubah
            existing_pegawai = Pegawai.query.filter(
                Pegawai.nip == nip,
                Pegawai.id != pegawai_id
            ).first()
            
            if existing_pegawai:
                flash(f"NIP {nip} sudah digunakan oleh {existing_pegawai.user.nama_lengkap}. Silakan gunakan NIP yang berbeda.", "danger")
                return redirect(url_for("pegawai_bp.update_pegawai", pegawai_id=pegawai.id))

        # Update data Pegawai dan User
        try:
            pegawai.nip = nip
            pegawai.sekolah_id = sekolah_id
            if nama_lengkap:
                pegawai.user.nama_lengkap = nama_lengkap

            db.session.commit()
            flash("Profile pegawai berhasil diperbarui!", "success")
            return redirect(url_for("tahun_ajaran.dashboard"))
        except Exception as e:
            db.session.rollback()
            flash(f"Terjadi kesalahan saat memperbarui: {str(e)}", "danger")
            return redirect(url_for("pegawai_bp.update_pegawai", pegawai_id=pegawai.id))

    # Pre-fill cascading dropdown
    selected_sekolah = Sekolah.query.get(pegawai.sekolah_id)
    selected_kecamatan = Kecamatan.query.get(selected_sekolah.kecamatan_id)
    selected_kabupaten = Kabupaten.query.get(selected_kecamatan.kabupaten_id)
    selected_provinsi = Provinsi.query.get(selected_kabupaten.provinsi_id)

    provinsi_list = Provinsi.query.all()
    kabupaten_list = Kabupaten.query.filter_by(provinsi_id=selected_provinsi.id).all()
    kecamatan_list = Kecamatan.query.filter_by(kabupaten_id=selected_kabupaten.id).all()
    sekolah_list = Sekolah.query.filter_by(kecamatan_id=selected_kecamatan.id).all()

    return render_template(
        "home.html",
        user=pegawai.user,
        pegawai=pegawai,
        provinsi_list=provinsi_list,
        kabupaten_list=kabupaten_list,
        kecamatan_list=kecamatan_list,
        sekolah_list=sekolah_list,
        selected_provinsi=selected_provinsi,
        selected_kabupaten=selected_kabupaten,
        selected_kecamatan=selected_kecamatan,
        selected_sekolah=selected_sekolah
    )

