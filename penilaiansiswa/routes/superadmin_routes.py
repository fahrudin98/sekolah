from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from penilaiansiswa import db
from penilaiansiswa.models.users import User, Pegawai
from penilaiansiswa.models.sekolah import Sekolah, Kabupaten, Kecamatan, MasterTahunAjaran
from penilaiansiswa.models import Kebiasaan, Kelas, Siswa, TahunAjaran
from sqlalchemy import func, extract, distinct
from datetime import datetime
#from passlib.hash import bcrypt

from werkzeug.utils import secure_filename
import os
from penilaiansiswa.utils.import_excel import import_data_sekolah_from_excel



superadmin_bp = Blueprint("superadmin", __name__, url_prefix="/superadmin")

@superadmin_bp.route("/dashboard")
@login_required
def dashboard():
    if not current_user.is_superadmin:
        from flask import redirect, url_for, flash
        flash("Akses ditolak! Hanya untuk superadmin.", "danger")
        return redirect(url_for("tahun_ajaran.dashboard"))
    
    # Data statistik sederhana
    total_users = User.query.count()
    total_pegawai = Pegawai.query.count()
    total_sekolah = Sekolah.query.count()
    
    return render_template(
        "superadmin/dashboard.html",
        total_users=total_users,
        total_pegawai=total_pegawai,
        total_sekolah=total_sekolah,
        user=current_user
    )

# ========== ⭐ BARU: MASTER TAHUN AJARAN (SUPER ADMIN) ==========

@superadmin_bp.route("/master_tahun_ajaran")
@login_required
def master_tahun_ajaran():
    """Halaman manage master tahun ajaran"""
    if not current_user.is_superadmin:
        flash("Akses ditolak!", "danger")
        return redirect(url_for("tahun_ajaran.dashboard"))
    
    # Ambil semua master TA
    master_list = MasterTahunAjaran.query.order_by(
        MasterTahunAjaran.tahun_ajaran.desc(),
        MasterTahunAjaran.semester.desc()
    ).all()
    
    # Hitung penggunaan per master
    for master in master_list:
        master.usage_count = TahunAjaran.query.filter_by(master_ta_id=master.id).count()
    
    return render_template(
        "superadmin/master_tahun_ajaran.html",
        master_list=master_list
    )


@superadmin_bp.route("/api/master_tahun_ajaran/list")
@login_required
def api_master_tahun_ajaran_list():
    """API untuk mendapatkan daftar master tahun ajaran"""
    if not current_user.is_superadmin:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    masters = MasterTahunAjaran.query.order_by(
        MasterTahunAjaran.tahun_ajaran.desc(),
        MasterTahunAjaran.semester.desc()
    ).all()
    
    data = []
    for m in masters:
        data.append({
            'id': m.id,
            'tahun_ajaran': m.tahun_ajaran,
            'semester': m.semester,
            'display_name': m.display_name,
            'is_active': m.is_active,
            'is_global_active': m.is_global_active,
            'usage_count': TahunAjaran.query.filter_by(master_ta_id=m.id).count(),
            'created_at': m.created_at.strftime('%Y-%m-%d %H:%M') if m.created_at else None
        })
    
    return jsonify({"success": True, "data": data})


@superadmin_bp.route("/api/master_tahun_ajaran/add", methods=["POST"])
@login_required
def api_master_tahun_ajaran_add():
    """API untuk menambah master tahun ajaran"""
    if not current_user.is_superadmin:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    try:
        data = request.get_json()
        tahun_ajaran = data.get('tahun_ajaran', '').strip()
        semester = data.get('semester', '').strip().lower()
        
        if not tahun_ajaran:
            return jsonify({"success": False, "message": "Tahun ajaran tidak boleh kosong"}), 400
        
        if semester not in ['ganjil', 'genap']:
            return jsonify({"success": False, "message": "Semester harus ganjil atau genap"}), 400
        
        # Cek duplikat
        existing = MasterTahunAjaran.query.filter_by(
            tahun_ajaran=tahun_ajaran,
            semester=semester
        ).first()
        
        if existing:
            return jsonify({"success": False, "message": f"Master '{tahun_ajaran} - {semester}' sudah ada"}), 400
        
        master = MasterTahunAjaran(
            tahun_ajaran=tahun_ajaran,
            semester=semester,
            created_by=current_user.id
        )
        
        db.session.add(master)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Master '{tahun_ajaran} - {semester}' berhasil ditambahkan",
            "data": {
                'id': master.id,
                'tahun_ajaran': master.tahun_ajaran,
                'semester': master.semester,
                'display_name': master.display_name
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@superadmin_bp.route("/api/master_tahun_ajaran/edit/<int:id>", methods=["PUT"])
@login_required
def api_master_tahun_ajaran_edit(id):
    """API untuk mengedit master tahun ajaran"""
    if not current_user.is_superadmin:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    try:
        master = MasterTahunAjaran.query.get(id)
        if not master:
            return jsonify({"success": False, "message": "Master tidak ditemukan"}), 404
        
        data = request.get_json()
        
        if 'is_active' in data:
            # Cek apakah master adalah default global
            if master.is_global_active and not data['is_active']:
                return jsonify({
                    "success": False, 
                    "message": "Tidak dapat menonaktifkan master yang sedang menjadi default report!"
                }), 400
            
            master.is_active = data['is_active']
            master.updated_at = datetime.utcnow()
            db.session.commit()
            
            status_text = "diaktifkan" if data['is_active'] else "dinonaktifkan"
            return jsonify({
                "success": True,
                "message": f"Master '{master.display_name}' berhasil {status_text}"
            })
        
        tahun_ajaran = data.get('tahun_ajaran', '').strip()
        semester = data.get('semester', '').strip().lower()
        
        if not tahun_ajaran:
            return jsonify({"success": False, "message": "Tahun ajaran tidak boleh kosong"}), 400
        
        if semester not in ['ganjil', 'genap']:
            return jsonify({"success": False, "message": "Semester harus ganjil atau genap"}), 400
        
        # Cek duplikat dengan master lain
        existing = MasterTahunAjaran.query.filter(
            MasterTahunAjaran.tahun_ajaran == tahun_ajaran,
            MasterTahunAjaran.semester == semester,
            MasterTahunAjaran.id != id
        ).first()
        
        if existing:
            return jsonify({"success": False, "message": f"Master '{tahun_ajaran} - {semester}' sudah ada"}), 400
        
        master.tahun_ajaran = tahun_ajaran
        master.semester = semester
        master.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Master berhasil diupdate menjadi '{tahun_ajaran} - {semester}'",
            "data": {
                'id': master.id,
                'tahun_ajaran': master.tahun_ajaran,
                'semester': master.semester,
                'display_name': master.display_name
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@superadmin_bp.route("/api/master_tahun_ajaran/delete/<int:id>", methods=["DELETE"])
@login_required
def api_master_tahun_ajaran_delete(id):
    """API untuk menghapus master tahun ajaran"""
    if not current_user.is_superadmin:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    try:
        master = MasterTahunAjaran.query.get(id)
        if not master:
            return jsonify({"success": False, "message": "Master tidak ditemukan"}), 404
        
        # Cek apakah sedang digunakan
        usage_count = TahunAjaran.query.filter_by(master_ta_id=id).count()
        if usage_count > 0:
            return jsonify({
                "success": False, 
                "message": f"Master sedang digunakan oleh {usage_count} sekolah. Tidak bisa dihapus."
            }), 400
        
        db.session.delete(master)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Master '{master.display_name}' berhasil dihapus"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@superadmin_bp.route("/api/master_tahun_ajaran/set_global_active", methods=["POST"])
@login_required
def api_master_tahun_ajaran_set_global_active():
    """API untuk menetapkan master yang aktif secara global (untuk report)"""
    if not current_user.is_superadmin:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    try:
        data = request.get_json()
        master_id = data.get('master_id')
        
        if not master_id:
            return jsonify({"success": False, "message": "Master ID diperlukan"}), 400
        
        master = MasterTahunAjaran.query.get(master_id)
        if not master:
            return jsonify({"success": False, "message": "Master tidak ditemukan"}), 404
        
        # Nonaktifkan semua global active
        MasterTahunAjaran.query.update({'is_global_active': False})
        
        # Aktifkan yang dipilih
        master.is_global_active = True
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Master '{master.display_name}' ditetapkan sebagai default report"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


# ========== API UNTUK SEKOLAH (MENDAPATKAN MASTER YANG TERSEDIA) ==========

@superadmin_bp.route("/api/available_masters")
@login_required
def api_available_masters():
    """API untuk mendapatkan daftar master TA yang tersedia untuk dipilih sekolah"""
    # Bisa diakses oleh semua user yang login (superadmin, kepala sekolah, wali kelas)
    masters = MasterTahunAjaran.query.filter_by(
        is_active=True
    ).order_by(
        MasterTahunAjaran.tahun_ajaran.desc(),
        MasterTahunAjaran.semester.desc()
    ).all()
    
    data = [{
        'id': m.id,
        'tahun_ajaran': m.tahun_ajaran,
        'semester': m.semester,
        'display_name': m.display_name
    } for m in masters]
    
    return jsonify({"success": True, "data": data})

@superadmin_bp.route("/api/statistik")
@login_required
def api_statistik():
    if not current_user.is_superadmin:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Data statistik dasar
    total_users = User.query.count()
    total_pegawai = Pegawai.query.count()
    total_sekolah_aktif = Sekolah.query.count()
    
    # Ambil tahun ajaran terakhir
    tahun_ajaran_terakhir = TahunAjaran.query.order_by(TahunAjaran.id.desc()).first()
    tahun_ajaran_text = tahun_ajaran_terakhir.tahun_ajaran if tahun_ajaran_terakhir else "2025/2026"
    
    # Data untuk 7 grafik kebiasaan
    kebiasaan_fields = ['bangun_pagi', 'beribadah', 'berolahraga', 'sehat_dan_lemar', 'belajar', 'bermasyarakat', 'tidur_cepat']
    kebiasaan_labels = ['Bangun Pagi', 'Beribadah', 'Berolahraga', 'Sehat & Bergizi', 'Belajar', 'Bermasyarakat', 'Tidur Cepat']
    
    habits_data = {}
    
    # Ambil semua sekolah dari database
    semua_sekolah_db = Sekolah.query.all()
    
    # Untuk setiap kebiasaan, buat data untuk semua sekolah
    for i, field_name in enumerate(kebiasaan_fields):
        field_label = kebiasaan_labels[i]
        
        # Dictionary untuk menyimpan rata-rata per sekolah
        rata_rata_per_sekolah = {}
        
        # Query semua kebiasaan yang punya nilai untuk field ini
        try:
            results = db.session.query(
                Sekolah.nama_sekolah,
                func.avg(getattr(Kebiasaan, field_name)).label('rata_rata')
            ).join(Kelas, Kelas.id == Kebiasaan.kelas_id
            ).join(Sekolah, Sekolah.id == Kelas.sekolah_id
            ).filter(getattr(Kebiasaan, field_name).isnot(None)
            ).group_by(Sekolah.id, Sekolah.nama_sekolah
            ).all()
            
            for result in results:
                rata_rata_per_sekolah[result.nama_sekolah] = float(result.rata_rata or 0)
            
        except Exception as e:
            # Jika error, lanjutkan dengan data kosong
            continue
        
        # Siapkan data untuk grafik (maksimal 10 sekolah teratas)
        sekolah_dengan_data = []
        for sekolah in semua_sekolah_db:
            nilai = rata_rata_per_sekolah.get(sekolah.nama_sekolah, 0)
            if nilai > 0:  # Hanya tampilkan sekolah dengan nilai > 0
                sekolah_dengan_data.append((sekolah.nama_sekolah, nilai))
        
        # Jika tidak ada sekolah dengan data, coba tanpa filter nilai > 0
        if not sekolah_dengan_data:
            for sekolah in semua_sekolah_db:
                nilai = rata_rata_per_sekolah.get(sekolah.nama_sekolah, 0)
                sekolah_dengan_data.append((sekolah.nama_sekolah, nilai))
        
        # Urutkan berdasarkan nilai descending
        sekolah_dengan_data.sort(key=lambda x: x[1], reverse=True)
        
        # Ambil maksimal 10 teratas
        if len(sekolah_dengan_data) > 10:
            sekolah_dengan_data = sekolah_dengan_data[:10]
        
        labels = [item[0] for item in sekolah_dengan_data]
        data = [item[1] for item in sekolah_dengan_data]
        
        habits_data[field_label] = {
            'labels': labels,
            'data': data
        }
    
    # Data untuk line chart
    urutan_bulan_tahun_ajaran = [
        '2025-07', '2025-08', '2025-09', '2025-10', '2025-11', '2025-12',
        '2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06'
    ]
    
    nama_bulan_tampilan = {
        '2025-07': 'Jul 2025', '2025-08': 'Agust 2025', '2025-09': 'Sept 2025', 
        '2025-10': 'Okt 2025', '2025-11': 'Nop 2025', '2025-12': 'Des 2025',
        '2026-01': 'Jan 2026', '2026-02': 'Feb 2026', '2026-03': 'Mar 2026', 
        '2026-04': 'Apr 2026', '2026-05': 'Mei 2026', '2026-06': 'Jun 2026'
    }
    
    try:
        # Query trend data
        query_trend = db.session.query(
            Kebiasaan.bulan,
            func.avg(Kebiasaan.bangun_pagi).label('bangun_pagi'),
            func.avg(Kebiasaan.beribadah).label('beribadah'),
            func.avg(Kebiasaan.berolahraga).label('berolahraga'),
            func.avg(Kebiasaan.sehat_dan_lemar).label('sehat_dan_lemar'),
            func.avg(Kebiasaan.belajar).label('belajar'),
            func.avg(Kebiasaan.bermasyarakat).label('bermasyarakat'),
            func.avg(Kebiasaan.tidur_cepat).label('tidur_cepat')
        ).filter(Kebiasaan.bulan.isnot(None))
        
        bulan_stats = query_trend.group_by(Kebiasaan.bulan).all()
        
        bulan_data = {b.bulan: b for b in bulan_stats}
        
        trend_datasets = []
        for i, field in enumerate(kebiasaan_fields):
            data_per_bulan = []
            for bulan in urutan_bulan_tahun_ajaran:
                if bulan in bulan_data:
                    data_per_bulan.append(float(getattr(bulan_data[bulan], field) or 0))
                else:
                    data_per_bulan.append(None)
            
            trend_datasets.append({
                'label': kebiasaan_labels[i],
                'data': data_per_bulan,
                'borderColor': ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#2E8B57'][i],
                'tension': 0.3,
                'spanGaps': True
            })
        
        trend_data = {
            'labels': [nama_bulan_tampilan[b] for b in urutan_bulan_tahun_ajaran],
            'datasets': trend_datasets
        }
        
    except Exception as e:
        # Fallback trend data jika error
        trend_data = {
            'labels': ['Jul 2025', 'Agust 2025', 'Sept 2025'],
            'datasets': [{
                'label': 'Sample Data',
                'data': [20, 22, 24],
                'borderColor': '#FF6384',
                'tension': 0.3
            }]
        }
    
    # Data sekolah untuk tabel
    sekolah_stats = []
    
    for sekolah in semua_sekolah_db:
        try:
            # Query data sekolah
            stats_query = db.session.query(
                func.avg(Kebiasaan.bangun_pagi).label('bangun_pagi'),
                func.avg(Kebiasaan.beribadah).label('beribadah'),
                func.avg(Kebiasaan.berolahraga).label('berolahraga'),
                func.avg(Kebiasaan.sehat_dan_lemar).label('sehat_dan_lemar'),
                func.avg(Kebiasaan.belajar).label('belajar'),
                func.avg(Kebiasaan.bermasyarakat).label('bermasyarakat'),
                func.avg(Kebiasaan.tidur_cepat).label('tidur_cepat')
            ).join(Kelas, Kelas.id == Kebiasaan.kelas_id
            ).filter(Kelas.sekolah_id == sekolah.id)
            
            stats = stats_query.first()
            
            if stats:
                nilai_nilai = [
                    float(stats.bangun_pagi or 0),
                    float(stats.beribadah or 0),
                    float(stats.berolahraga or 0),
                    float(stats.sehat_dan_lemar or 0),
                    float(stats.belajar or 0),
                    float(stats.bermasyarakat or 0),
                    float(stats.tidur_cepat or 0)
                ]
                
                # Filter nilai yang valid (tidak None dan > 0)
                nilai_valid = [nilai for nilai in nilai_nilai if nilai is not None and nilai > 0]
                
                if nilai_valid:
                    rata_rata = sum(nilai_valid) / len(nilai_valid)
                    sekolah_stats.append({
                        'sekolah': sekolah.nama_sekolah,
                        'bangun_pagi': float(stats.bangun_pagi or 0),
                        'beribadah': float(stats.beribadah or 0),
                        'berolahraga': float(stats.berolahraga or 0),
                        'sehat_dan_lemar': float(stats.sehat_dan_lemar or 0),
                        'belajar': float(stats.belajar or 0),
                        'bermasyarakat': float(stats.bermasyarakat or 0),
                        'tidur_cepat': float(stats.tidur_cepat or 0),
                        'rata_rata': rata_rata
                    })
                else:
                    # Semua nilai 0 atau None
                    sekolah_stats.append({
                        'sekolah': sekolah.nama_sekolah,
                        'bangun_pagi': 0,
                        'beribadah': 0,
                        'berolahraga': 0,
                        'sehat_dan_lemar': 0,
                        'belajar': 0,
                        'bermasyarakat': 0,
                        'tidur_cepat': 0,
                        'rata_rata': 0
                    })
            else:
                # Tidak ada data
                sekolah_stats.append({
                    'sekolah': sekolah.nama_sekolah,
                    'bangun_pagi': 0,
                    'beribadah': 0,
                    'berolahraga': 0,
                    'sehat_dan_lemar': 0,
                    'belajar': 0,
                    'bermasyarakat': 0,
                    'tidur_cepat': 0,
                    'rata_rata': 0
                })
                
        except Exception as e:
            # Jika error, tambahkan dengan nilai default
            sekolah_stats.append({
                'sekolah': sekolah.nama_sekolah,
                'bangun_pagi': 0,
                'beribadah': 0,
                'berolahraga': 0,
                'sehat_dan_lemar': 0,
                'belajar': 0,
                'bermasyarakat': 0,
                'tidur_cepat': 0,
                'rata_rata': 0
            })
    
    # Urutkan sekolah berdasarkan rata-rata
    sekolah_stats_sorted = sorted(sekolah_stats, key=lambda x: x['rata_rata'], reverse=True)
    
    # Hitung overall performance
    try:
        total_performance = db.session.query(
            func.avg(Kebiasaan.bangun_pagi),
            func.avg(Kebiasaan.beribadah),
            func.avg(Kebiasaan.berolahraga),
            func.avg(Kebiasaan.sehat_dan_lemar),
            func.avg(Kebiasaan.belajar),
            func.avg(Kebiasaan.bermasyarakat),
            func.avg(Kebiasaan.tidur_cepat)
        ).first()
        
        overall_avg = sum([val or 0 for val in total_performance]) / 7
    except:
        overall_avg = 0
    
    response_data = {
        'tahun_ajaran': tahun_ajaran_text,
        'total_users': total_users,
        'total_pegawai': total_pegawai,
        'total_sekolah': total_sekolah_aktif,
        'overall_performance': round(overall_avg, 1),
        'habits_data': habits_data,
        'trend_data': trend_data,
        'sekolah_stats': sekolah_stats_sorted
    }
    
    return jsonify(response_data)
@superadmin_bp.route("/api/users")
@login_required
def api_users():
    # Pastikan hanya superadmin yang bisa akses
    if current_user.role != 'superadmin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Ambil semua user dengan data pegawai dan sekolah
        users = User.query.all()
        
        users_data = []
        for user in users:
            # Cek apakah user punya data pegawai
            pegawai = Pegawai.query.filter_by(user_id=user.id).first()
            sekolah_nama = pegawai.sekolah.nama_sekolah if pegawai and pegawai.sekolah else ""
            
            users_data.append({
                'id': user.id,
                'username': user.username,
                'nama_lengkap': user.nama_lengkap or '',
                'email': user.email or '',
                'role': user.role,
                'sekolah': sekolah_nama,
                'nip': pegawai.nip if pegawai else ''
            })
        
        return jsonify({'users': users_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== API CHANGE USER PASSWORD =====
@superadmin_bp.route("/api/change_user_password", methods=["POST"])
@login_required
def api_change_user_password():
    # Pastikan hanya superadmin yang bisa akses
    if current_user.role != 'superadmin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        new_password = data.get('new_password')
        
        if not user_id or not new_password:
            return jsonify({'success': False, 'message': 'User ID dan password baru harus diisi'})
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'message': 'Password minimal 6 karakter'})
        
        # Cari user berdasarkan ID
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User tidak ditemukan'})
        
        # ✅ GUNAKAN BCRYPT YANG SAMA DENGAN LUPA PASSWORD
        user.password = bcrypt.hash(new_password)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Password untuk user {user.username} berhasil diubah'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

# ===== API CHANGE USER NIP =====
@superadmin_bp.route("/api/change_user_nip", methods=["POST"])
@login_required
def api_change_user_nip():
    # Pastikan hanya superadmin yang bisa akses
    if current_user.role != 'superadmin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        new_nip = data.get('new_nip')
        
        if not user_id or not new_nip:
            return jsonify({'success': False, 'message': 'User ID dan NIP baru harus diisi'})
        
        # Cari user dan data pegawainya
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User tidak ditemukan'})
        
        pegawai = Pegawai.query.filter_by(user_id=user_id).first()
        if not pegawai:
            return jsonify({'success': False, 'message': 'Data pegawai tidak ditemukan'})
        
        # Validasi NIP unik (kecuali untuk user yang sama)
        existing_pegawai = Pegawai.query.filter(
            Pegawai.nip == new_nip,
            Pegawai.user_id != user_id
        ).first()
        
        if existing_pegawai:
            existing_user = User.query.get(existing_pegawai.user_id)
            nama_pegawai = existing_user.nama_lengkap if existing_user else "Unknown"
            return jsonify({
                'success': False, 
                'message': f'NIP {new_nip} sudah digunakan oleh {nama_pegawai}. Silakan gunakan NIP yang berbeda.'
            })
        
        # Update NIP
        pegawai.nip = new_nip
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'NIP untuk user {user.username} berhasil diubah menjadi {new_nip}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    


# ===== UPLOAD DATA WILAYAH & SEKOLAH (EXCEL) =====
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@superadmin_bp.route("/upload-wilayah", methods=["GET", "POST"])
@login_required
def upload_wilayah():
    if not current_user.is_superadmin:
        flash("Akses ditolak!", "danger")
        return redirect(url_for("tahun_ajaran.dashboard"))
    
    if request.method == "POST":
        if 'file' not in request.files:
            flash("Tidak ada file yang dipilih", "danger")
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash("File belum dipilih", "danger")
            return redirect(request.url)
        if not allowed_file(file.filename):
            flash("Format file harus .xlsx atau .xls", "danger")
            return redirect(request.url)
        
        filename = secure_filename(file.filename)
        # Simpan sementara di folder instance/tmp atau /tmp
        filepath = os.path.join('/tmp', filename)
        file.save(filepath)
        
        try:
            hasil = import_data_sekolah_from_excel(filepath)
            flash(
                f"✅ Import selesai! Provinsi baru: {hasil['provinsi_baru']}, "
                f"Kabupaten baru: {hasil['kabupaten_baru']}, "
                f"Kecamatan baru: {hasil['kecamatan_baru']}, "
                f"Sekolah baru: {hasil['sekolah_baru']}, "
                f"Data duplikat dilewati: {hasil['duplikat']}",
                "success"
            )
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Terjadi kesalahan: {str(e)}", "danger")
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
        
        return redirect(url_for("superadmin.upload_wilayah"))
    
    return render_template("superadmin/upload_wilayah.html")

# ========== API PAGINATION & FILTER UNTUK SEKOLAH (PULUHAN RIBU DATA) ==========
@superadmin_bp.route("/api/sekolah_stats")
@login_required
def api_sekolah_stats_paginated():
    """API untuk data sekolah dengan pagination dan filter kabupaten (server-side)"""
    if not current_user.is_superadmin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 25, type=int)
        kabupaten_nama = request.args.get('kabupaten', 'all', type=str)
        search = request.args.get('search', '', type=str)
        
        if limit > 100:
            limit = 100
        if page < 1:
            page = 1
        
        # Query sekolah dasar
        sekolah_query = db.session.query(
            Sekolah.id,
            Sekolah.nama_sekolah,
            Kabupaten.id.label('kabupaten_id'),
            Kabupaten.nama.label('kabupaten_nama')
        ).join(Kecamatan, Sekolah.kecamatan_id == Kecamatan.id)\
         .join(Kabupaten, Kecamatan.kabupaten_id == Kabupaten.id)
        
        if kabupaten_nama != 'all':
            sekolah_query = sekolah_query.filter(Kabupaten.nama == kabupaten_nama)
        if search:
            sekolah_query = sekolah_query.filter(Sekolah.nama_sekolah.ilike(f'%{search}%'))
        
        semua_sekolah = sekolah_query.all()
        
        # Hitung rata-rata per sekolah
        sekolah_dengan_rata = []
        for sekolah in semua_sekolah:
            avg_query = db.session.query(
                func.coalesce(func.avg(Kebiasaan.bangun_pagi), 0).label('bangun_pagi'),
                func.coalesce(func.avg(Kebiasaan.beribadah), 0).label('beribadah'),
                func.coalesce(func.avg(Kebiasaan.berolahraga), 0).label('berolahraga'),
                func.coalesce(func.avg(Kebiasaan.sehat_dan_lemar), 0).label('sehat_dan_lemar'),
                func.coalesce(func.avg(Kebiasaan.belajar), 0).label('belajar'),
                func.coalesce(func.avg(Kebiasaan.bermasyarakat), 0).label('bermasyarakat'),
                func.coalesce(func.avg(Kebiasaan.tidur_cepat), 0).label('tidur_cepat')
            ).join(Kelas, Kelas.id == Kebiasaan.kelas_id)\
             .filter(Kelas.sekolah_id == sekolah.id)
            
            nilai = avg_query.first()
            
            nilai_list = [
                float(nilai.bangun_pagi or 0),
                float(nilai.beribadah or 0),
                float(nilai.berolahraga or 0),
                float(nilai.sehat_dan_lemar or 0),
                float(nilai.belajar or 0),
                float(nilai.bermasyarakat or 0),
                float(nilai.tidur_cepat or 0)
            ]
            rata_rata = sum(nilai_list) / 7
            
            sekolah_dengan_rata.append({
                'sekolah_id': sekolah.id,
                'sekolah': sekolah.nama_sekolah,
                'kabupaten_id': sekolah.kabupaten_id,
                'kabupaten': sekolah.kabupaten_nama,
                'bangun_pagi': nilai_list[0],
                'beribadah': nilai_list[1],
                'berolahraga': nilai_list[2],
                'sehat_dan_lemar': nilai_list[3],
                'belajar': nilai_list[4],
                'bermasyarakat': nilai_list[5],
                'tidur_cepat': nilai_list[6],
                'rata_rata': rata_rata
            })
        
        # 🔥 URUTKAN BERDASARKAN RATA-RATA TERTINGGI
        sekolah_dengan_rata.sort(key=lambda x: x['rata_rata'], reverse=True)
        
        total_data = len(sekolah_dengan_rata)
        offset = (page - 1) * limit
        data_paginated = sekolah_dengan_rata[offset:offset + limit]
        
        data = []
        for item in data_paginated:
            data.append({
                'sekolah_id': item['sekolah_id'],
                'sekolah': item['sekolah'],
                'kabupaten_id': item['kabupaten_id'],
                'kabupaten': item['kabupaten'],
                'bangun_pagi': round(item['bangun_pagi'], 2),
                'beribadah': round(item['beribadah'], 2),
                'berolahraga': round(item['berolahraga'], 2),
                'sehat_dan_lemar': round(item['sehat_dan_lemar'], 2),
                'belajar': round(item['belajar'], 2),
                'bermasyarakat': round(item['bermasyarakat'], 2),
                'tidur_cepat': round(item['tidur_cepat'], 2),
                'rata_rata': round(item['rata_rata'], 2)
            })
        
        total_pages = (total_data + limit - 1) // limit if limit > 0 else 0
        
        return jsonify({
            'success': True,
            'data': data,
            'total': total_data,
            'page': page,
            'limit': limit,
            'total_pages': total_pages
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
@superadmin_bp.route("/api/sekolah_stats_by_bulan")
@login_required
def api_sekolah_stats_by_bulan():
    """API untuk data sekolah per bulan tertentu"""
    if not current_user.is_superadmin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 25, type=int)
        kabupaten_nama = request.args.get('kabupaten', 'all', type=str)
        bulan = request.args.get('bulan', '', type=str)
        search = request.args.get('search', '', type=str)
        
        if limit > 100:
            limit = 100
        if page < 1:
            page = 1
        
        # Query sekolah dasar
        sekolah_query = db.session.query(
            Sekolah.id,
            Sekolah.nama_sekolah,
            Kabupaten.id.label('kabupaten_id'),
            Kabupaten.nama.label('kabupaten_nama')
        ).join(Kecamatan, Sekolah.kecamatan_id == Kecamatan.id)\
         .join(Kabupaten, Kecamatan.kabupaten_id == Kabupaten.id)
        
        if kabupaten_nama != 'all':
            sekolah_query = sekolah_query.filter(Kabupaten.nama == kabupaten_nama)
        if search:
            sekolah_query = sekolah_query.filter(Sekolah.nama_sekolah.ilike(f'%{search}%'))
        
        semua_sekolah = sekolah_query.all()
        
        sekolah_dengan_data = []
        for sekolah in semua_sekolah:
            if bulan:
                # Ambil nilai untuk bulan tertentu
                nilai = db.session.query(
                    Kebiasaan.bangun_pagi,
                    Kebiasaan.beribadah,
                    Kebiasaan.berolahraga,
                    Kebiasaan.sehat_dan_lemar,
                    Kebiasaan.belajar,
                    Kebiasaan.bermasyarakat,
                    Kebiasaan.tidur_cepat
                ).join(Kelas, Kelas.id == Kebiasaan.kelas_id)\
                 .filter(Kelas.sekolah_id == sekolah.id, Kebiasaan.bulan == bulan)\
                 .first()
                
                if nilai:
                    bangun_pagi = float(nilai.bangun_pagi or 0)
                    beribadah = float(nilai.beribadah or 0)
                    berolahraga = float(nilai.berolahraga or 0)
                    sehat_dan_lemar = float(nilai.sehat_dan_lemar or 0)
                    belajar = float(nilai.belajar or 0)
                    bermasyarakat = float(nilai.bermasyarakat or 0)
                    tidur_cepat = float(nilai.tidur_cepat or 0)
                else:
                    bangun_pagi = beribadah = berolahraga = sehat_dan_lemar = belajar = bermasyarakat = tidur_cepat = 0
            else:
                # Ambil rata-rata semua bulan
                avg_query = db.session.query(
                    func.avg(Kebiasaan.bangun_pagi).label('bangun_pagi'),
                    func.avg(Kebiasaan.beribadah).label('beribadah'),
                    func.avg(Kebiasaan.berolahraga).label('berolahraga'),
                    func.avg(Kebiasaan.sehat_dan_lemar).label('sehat_dan_lemar'),
                    func.avg(Kebiasaan.belajar).label('belajar'),
                    func.avg(Kebiasaan.bermasyarakat).label('bermasyarakat'),
                    func.avg(Kebiasaan.tidur_cepat).label('tidur_cepat')
                ).join(Kelas, Kelas.id == Kebiasaan.kelas_id)\
                 .filter(Kelas.sekolah_id == sekolah.id)
                
                avg_result = avg_query.first()
                bangun_pagi = float(avg_result.bangun_pagi or 0)
                beribadah = float(avg_result.beribadah or 0)
                berolahraga = float(avg_result.berolahraga or 0)
                sehat_dan_lemar = float(avg_result.sehat_dan_lemar or 0)
                belajar = float(avg_result.belajar or 0)
                bermasyarakat = float(avg_result.bermasyarakat or 0)
                tidur_cepat = float(avg_result.tidur_cepat or 0)
            
            nilai_list = [bangun_pagi, beribadah, berolahraga, sehat_dan_lemar, belajar, bermasyarakat, tidur_cepat]
            rata_rata = sum(nilai_list) / 7
            
            sekolah_dengan_data.append({
                'sekolah_id': sekolah.id,
                'sekolah': sekolah.nama_sekolah,
                'kabupaten_id': sekolah.kabupaten_id,
                'kabupaten': sekolah.kabupaten_nama,
                'bangun_pagi': bangun_pagi,
                'beribadah': beribadah,
                'berolahraga': berolahraga,
                'sehat_dan_lemar': sehat_dan_lemar,
                'belajar': belajar,
                'bermasyarakat': bermasyarakat,
                'tidur_cepat': tidur_cepat,
                'rata_rata': rata_rata
            })
        
        # Urutkan berdasarkan rata-rata tertinggi
        sekolah_dengan_data.sort(key=lambda x: x['rata_rata'], reverse=True)
        
        total_data = len(sekolah_dengan_data)
        offset = (page - 1) * limit
        data_paginated = sekolah_dengan_data[offset:offset + limit]
        
        data = []
        for item in data_paginated:
            data.append({
                'sekolah_id': item['sekolah_id'],
                'sekolah': item['sekolah'],
                'kabupaten_id': item['kabupaten_id'],
                'kabupaten': item['kabupaten'],
                'bangun_pagi': round(item['bangun_pagi'], 2),
                'beribadah': round(item['beribadah'], 2),
                'berolahraga': round(item['berolahraga'], 2),
                'sehat_dan_lemar': round(item['sehat_dan_lemar'], 2),
                'belajar': round(item['belajar'], 2),
                'bermasyarakat': round(item['bermasyarakat'], 2),
                'tidur_cepat': round(item['tidur_cepat'], 2),
                'rata_rata': round(item['rata_rata'], 2)
            })
        
        total_pages = (total_data + limit - 1) // limit if limit > 0 else 0
        
        return jsonify({
            'success': True,
            'data': data,
            'total': total_data,
            'page': page,
            'limit': limit,
            'total_pages': total_pages,
            'bulan': bulan if bulan else 'all'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== API DAFTAR KABUPATEN UNTUK DROPDOWN FILTER ==========
@superadmin_bp.route("/api/kabupaten_list")
@login_required
def api_kabupaten_list():
    """API untuk mengambil daftar semua kabupaten yang memiliki sekolah"""
    if not current_user.is_superadmin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    try:
        kabupaten_data = db.session.query(
            Kabupaten.id,
            Kabupaten.nama
        ).join(Kecamatan, Kabupaten.id == Kecamatan.kabupaten_id)\
         .join(Sekolah, Kecamatan.id == Sekolah.kecamatan_id)\
         .filter(Sekolah.id.isnot(None))\
         .distinct()\
         .order_by(Kabupaten.nama.asc())\
         .all()
        
        kabupaten_list = [{'id': k.id, 'nama': k.nama} for k in kabupaten_data]
        
        return jsonify({
            'success': True,
            'kabupaten_list': kabupaten_list
        }), 200
        
    except Exception as e:
        print(f"Error in api_kabupaten_list: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========== API STATISTIK RINGKASAN (TANPA DATA SEKOLAH DETAIL) ==========
@superadmin_bp.route("/api/statistik_summary")
@login_required
def api_statistik_summary():
    """API untuk data statistik ringkasan (total users, pegawai, sekolah, overall performance)"""
    if not current_user.is_superadmin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    try:
        total_users = User.query.count()
        total_pegawai = Pegawai.query.count()
        total_sekolah = Sekolah.query.count()
        
        tahun_ajaran_terakhir = TahunAjaran.query.order_by(TahunAjaran.id.desc()).first()
        tahun_ajaran_text = tahun_ajaran_terakhir.tahun_ajaran if tahun_ajaran_terakhir else "2025/2026"
        
        try:
            total_performance = db.session.query(
                func.avg(Kebiasaan.bangun_pagi),
                func.avg(Kebiasaan.beribadah),
                func.avg(Kebiasaan.berolahraga),
                func.avg(Kebiasaan.sehat_dan_lemar),
                func.avg(Kebiasaan.belajar),
                func.avg(Kebiasaan.bermasyarakat),
                func.avg(Kebiasaan.tidur_cepat)
            ).first()
            
            nilai_valid = [val or 0 for val in total_performance if val is not None]
            overall_avg = sum(nilai_valid) / len(nilai_valid) if nilai_valid else 0
        except:
            overall_avg = 0
        
        return jsonify({
            'success': True,
            'tahun_ajaran': tahun_ajaran_text,
            'overall_performance': round(overall_avg, 1),
            'total_users': total_users,
            'total_pegawai': total_pegawai,
            'total_sekolah': total_sekolah
        }), 200
        
    except Exception as e:
        print(f"Error in api_statistik_summary: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    
# ========== API GRAFIK PER KABUPATEN ==========
@superadmin_bp.route("/api/statistik_by_kabupaten")
@login_required
def api_statistik_by_kabupaten():
    """API untuk data grafik berdasarkan filter kabupaten"""
    if not current_user.is_superadmin:
        return jsonify({"error": "Unauthorized"}), 403
    
    kabupaten_nama = request.args.get('kabupaten', 'all', type=str)
    
    try:
        # Query untuk sekolah dengan filter kabupaten
        sekolah_query = Sekolah.query.join(Kecamatan).join(Kabupaten)
        
        if kabupaten_nama != 'all':
            sekolah_query = sekolah_query.filter(Kabupaten.nama == kabupaten_nama)
        
        sekolah_ids = [s.id for s in sekolah_query.all()]
        
        if not sekolah_ids:
            return jsonify({
                'habits_data': {},
                'trend_data': {'labels': [], 'datasets': []},
                'tahun_ajaran': 'Tidak ada data'
            }), 200
        
        # Data untuk 7 grafik kebiasaan (hanya sekolah yang punya data)
        kebiasaan_fields = ['bangun_pagi', 'beribadah', 'berolahraga', 'sehat_dan_lemar', 'belajar', 'bermasyarakat', 'tidur_cepat']
        kebiasaan_labels = ['Bangun Pagi', 'Beribadah', 'Berolahraga', 'Sehat & Bergizi', 'Belajar', 'Bermasyarakat', 'Tidur Cepat']
        
        habits_data = {}
        
        for i, field_name in enumerate(kebiasaan_fields):
            field_label = kebiasaan_labels[i]
            
            # Query rata-rata per sekolah (hanya yang punya data Kebiasaan)
            results = db.session.query(
                Sekolah.nama_sekolah,
                func.avg(getattr(Kebiasaan, field_name)).label('rata_rata')
            ).join(Kelas, Kelas.id == Kebiasaan.kelas_id
            ).join(Sekolah, Sekolah.id == Kelas.sekolah_id
            ).join(Kecamatan, Sekolah.kecamatan_id == Kecamatan.id
            ).join(Kabupaten, Kecamatan.kabupaten_id == Kabupaten.id
            ).filter(getattr(Kebiasaan, field_name).isnot(None))
            
            if kabupaten_nama != 'all':
                results = results.filter(Kabupaten.nama == kabupaten_nama)
            
            results = results.group_by(Sekolah.id, Sekolah.nama_sekolah).all()
            
            sekolah_dengan_data = [(row.nama_sekolah, float(row.rata_rata or 0)) for row in results if row.rata_rata and row.rata_rata > 0]
            sekolah_dengan_data.sort(key=lambda x: x[1], reverse=True)
            
            if len(sekolah_dengan_data) > 10:
                sekolah_dengan_data = sekolah_dengan_data[:10]
            
            habits_data[field_label] = {
                'labels': [item[0] for item in sekolah_dengan_data],
                'data': [item[1] for item in sekolah_dengan_data]
            }
        
        # Data untuk trend chart
        urutan_bulan_tahun_ajaran = [
            '2025-07', '2025-08', '2025-09', '2025-10', '2025-11', '2025-12',
            '2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06'
        ]
        
        nama_bulan_tampilan = {
            '2025-07': 'Jul 2025', '2025-08': 'Agust 2025', '2025-09': 'Sept 2025', 
            '2025-10': 'Okt 2025', '2025-11': 'Nop 2025', '2025-12': 'Des 2025',
            '2026-01': 'Jan 2026', '2026-02': 'Feb 2026', '2026-03': 'Mar 2026', 
            '2026-04': 'Apr 2026', '2026-05': 'Mei 2026', '2026-06': 'Jun 2026'
        }
        
        # Query trend data dengan filter kabupaten
        trend_query = db.session.query(
            Kebiasaan.bulan,
            func.avg(Kebiasaan.bangun_pagi).label('bangun_pagi'),
            func.avg(Kebiasaan.beribadah).label('beribadah'),
            func.avg(Kebiasaan.berolahraga).label('berolahraga'),
            func.avg(Kebiasaan.sehat_dan_lemar).label('sehat_dan_lemar'),
            func.avg(Kebiasaan.belajar).label('belajar'),
            func.avg(Kebiasaan.bermasyarakat).label('bermasyarakat'),
            func.avg(Kebiasaan.tidur_cepat).label('tidur_cepat')
        ).join(Kelas, Kelas.id == Kebiasaan.kelas_id
        ).join(Sekolah, Sekolah.id == Kelas.sekolah_id
        ).join(Kecamatan, Sekolah.kecamatan_id == Kecamatan.id
        ).join(Kabupaten, Kecamatan.kabupaten_id == Kabupaten.id
        ).filter(Kebiasaan.bulan.isnot(None))
        
        if kabupaten_nama != 'all':
            trend_query = trend_query.filter(Kabupaten.nama == kabupaten_nama)
        
        bulan_stats = trend_query.group_by(Kebiasaan.bulan).all()
        
        bulan_data = {b.bulan: b for b in bulan_stats}
        
        trend_datasets = []
        for i, field in enumerate(kebiasaan_fields):
            data_per_bulan = []
            for bulan in urutan_bulan_tahun_ajaran:
                if bulan in bulan_data:
                    val = getattr(bulan_data[bulan], field)
                    data_per_bulan.append(float(val) if val else None)
                else:
                    data_per_bulan.append(None)
            
            trend_datasets.append({
                'label': kebiasaan_labels[i],
                'data': data_per_bulan,
                'borderColor': ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#2E8B57'][i],
                'tension': 0.3,
                'spanGaps': True
            })
        
        trend_data = {
            'labels': [nama_bulan_tampilan[b] for b in urutan_bulan_tahun_ajaran if b in nama_bulan_tampilan],
            'datasets': trend_datasets
        }
        
        tahun_ajaran_terakhir = TahunAjaran.query.order_by(TahunAjaran.id.desc()).first()
        tahun_ajaran_text = tahun_ajaran_terakhir.tahun_ajaran if tahun_ajaran_terakhir else "2025/2026"
        
        return jsonify({
            'habits_data': habits_data,
            'trend_data': trend_data,
            'tahun_ajaran': tahun_ajaran_text
        }), 200
        
    except Exception as e:
        print(f"Error in api_statistik_by_kabupaten: {str(e)}")
        return jsonify({
            'habits_data': {},
            'trend_data': {'labels': [], 'datasets': []},
            'tahun_ajaran': 'Error'
        }), 200
    
@superadmin_bp.route("/api/bulan_list")
@login_required
def api_bulan_list():
    """API untuk daftar bulan yang memiliki data"""
    if not current_user.is_superadmin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    try:
        bulan_data = db.session.query(
            Kebiasaan.bulan,
            func.count(Kebiasaan.id).label('jumlah')
        ).filter(Kebiasaan.bulan.isnot(None))\
         .group_by(Kebiasaan.bulan)\
         .order_by(Kebiasaan.bulan.desc())\
         .all()
        
        bulan_list = []
        for b in bulan_data:
            if b.bulan:
                tahun, bulan = b.bulan.split('-')
                nama_bulan = {
                    '01': 'Januari', '02': 'Februari', '03': 'Maret', '04': 'April',
                    '05': 'Mei', '06': 'Juni', '07': 'Juli', '08': 'Agustus',
                    '09': 'September', '10': 'Oktober', '11': 'November', '12': 'Desember'
                }.get(bulan, bulan)
                bulan_list.append({
                    'value': b.bulan,
                    'display': f"{nama_bulan} {tahun}",
                    'jumlah': b.jumlah
                })
        
        return jsonify({'success': True, 'bulan_list': bulan_list}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'bulan_list': []}), 500
    
@superadmin_bp.route("/api/statistik_summary_by_kabupaten")
@login_required
def api_statistik_summary_by_kabupaten():
    """API statistik berdasarkan kabupaten"""
    if not current_user.is_superadmin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    kabupaten_nama = request.args.get('kabupaten', 'all', type=str)
    
    try:
        # Total sekolah
        sekolah_query = Sekolah.query.join(Kecamatan).join(Kabupaten)
        if kabupaten_nama != 'all':
            sekolah_query = sekolah_query.filter(Kabupaten.nama == kabupaten_nama)
        total_sekolah = sekolah_query.count()
        
        # Total pegawai
        pegawai_query = Pegawai.query.join(Sekolah, Pegawai.sekolah_id == Sekolah.id)\
                                     .join(Kecamatan, Sekolah.kecamatan_id == Kecamatan.id)\
                                     .join(Kabupaten, Kecamatan.kabupaten_id == Kabupaten.id)
        if kabupaten_nama != 'all':
            pegawai_query = pegawai_query.filter(Kabupaten.nama == kabupaten_nama)
        total_pegawai = pegawai_query.count()
        
        # Total user
        user_ids = [p.user_id for p in pegawai_query.all() if p.user_id]
        total_users = len(set(user_ids))
        
        # Overall performance
        perf_query = db.session.query(
            func.avg(Kebiasaan.bangun_pagi).label('bangun_pagi'),
            func.avg(Kebiasaan.beribadah).label('beribadah'),
            func.avg(Kebiasaan.berolahraga).label('berolahraga'),
            func.avg(Kebiasaan.sehat_dan_lemar).label('sehat_dan_lemar'),
            func.avg(Kebiasaan.belajar).label('belajar'),
            func.avg(Kebiasaan.bermasyarakat).label('bermasyarakat'),
            func.avg(Kebiasaan.tidur_cepat).label('tidur_cepat')
        ).join(Kelas, Kebiasaan.kelas_id == Kelas.id)\
         .join(Sekolah, Kelas.sekolah_id == Sekolah.id)\
         .join(Kecamatan, Sekolah.kecamatan_id == Kecamatan.id)\
         .join(Kabupaten, Kecamatan.kabupaten_id == Kabupaten.id)
        
        if kabupaten_nama != 'all':
            perf_query = perf_query.filter(Kabupaten.nama == kabupaten_nama)
        
        perf_result = perf_query.first()
        if perf_result:
            nilai_list = [perf_result.bangun_pagi or 0, perf_result.beribadah or 0,
                          perf_result.berolahraga or 0, perf_result.sehat_dan_lemar or 0,
                          perf_result.belajar or 0, perf_result.bermasyarakat or 0,
                          perf_result.tidur_cepat or 0]
            overall_performance = sum(nilai_list) / 7
        else:
            overall_performance = 0
        
        tahun_ajaran = TahunAjaran.query.order_by(TahunAjaran.id.desc()).first()
        tahun_ajaran_text = tahun_ajaran.tahun_ajaran if tahun_ajaran else "2025/2026"
        
        return jsonify({
            'success': True,
            'tahun_ajaran': tahun_ajaran_text,
            'overall_performance': round(overall_performance, 1),
            'total_users': total_users,
            'total_pegawai': total_pegawai,
            'total_sekolah': total_sekolah
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== API UPDATE USER ROLE ==========
@superadmin_bp.route("/api/update_user_role", methods=["POST"])
@login_required
def api_update_user_role():
    """API untuk superadmin mengubah role user"""
    if not current_user.is_superadmin:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        new_role = data.get('role')
        
        if not user_id or not new_role:
            return jsonify({"success": False, "message": "Data tidak lengkap"})
        
        # Validasi role yang diperbolehkan
        allowed_roles = ['user', 'superadmin', 'kepala_dinas']
        if new_role not in allowed_roles:
            return jsonify({"success": False, "message": f"Role '{new_role}' tidak valid"})
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({"success": False, "message": "User tidak ditemukan"})
        
        # Jangan biarkan superadmin mengubah role sendiri menjadi non-superadmin
        if user.id == current_user.id and new_role != 'superadmin':
            return jsonify({"success": False, "message": "Anda tidak dapat mengubah role sendiri!"})
        
        user.role = new_role
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Role user '{user.username}' berhasil diubah menjadi {new_role}"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500