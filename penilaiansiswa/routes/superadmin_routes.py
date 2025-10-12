from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from penilaiansiswa import db
from penilaiansiswa.models.users import User, Pegawai
from penilaiansiswa.models.sekolah import Sekolah
from penilaiansiswa.models import Kebiasaan, Kelas, Siswa, TahunAjaran
from sqlalchemy import func, extract
from datetime import datetime
from passlib.hash import bcrypt

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