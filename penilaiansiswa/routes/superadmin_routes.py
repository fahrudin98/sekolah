from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from penilaiansiswa import db
from penilaiansiswa.models.users import User, Pegawai
from penilaiansiswa.models.sekolah import Sekolah
from penilaiansiswa.models import Kebiasaan, Kelas, Siswa, TahunAjaran
from sqlalchemy import func, extract
from datetime import datetime

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
    
    # Parse tahun dari tahun ajaran
    try:
        tahun_awal = int(tahun_ajaran_text.split('/')[0])  # 2025
        tahun_akhir = int(tahun_ajaran_text.split('/')[1])  # 2026
    except:
        tahun_awal = 2025
        tahun_akhir = 2026
    
    # Total Performance (rata-rata semua kebiasaan)
    total_performance = db.session.query(
        func.avg(Kebiasaan.bangun_pagi),
        func.avg(Kebiasaan.beribadah),
        func.avg(Kebiasaan.berolahraga),
        func.avg(Kebiasaan.sehat_dan_lemar),
        func.avg(Kebiasaan.belajar),
        func.avg(Kebiasaan.bermasyarakat),
        func.avg(Kebiasaan.tidur_cepat)
    ).first()
    
    # Hitung overall average
    overall_avg = sum([val or 0 for val in total_performance]) / 7
    
    # Data untuk 7 grafik kebiasaan (top 10 sekolah per kebiasaan)
    kebiasaan_fields = ['bangun_pagi', 'beribadah', 'berolahraga', 'sehat_dan_lemar', 'belajar', 'bermasyarakat', 'tidur_cepat']
    kebiasaan_labels = ['Bangun Pagi', 'Beribadah', 'Berolahraga', 'Sehat & Bergizi', 'Belajar', 'Bermasyarakat', 'Tidur Cepat']
    
    habits_data = {}
    for i, field in enumerate(kebiasaan_fields):
        # Filter berdasarkan tahun ajaran terakhir
        query = db.session.query(
            Sekolah.nama_sekolah,
            func.avg(getattr(Kebiasaan, field)).label('rata_rata')
        ).join(Kelas, Kelas.sekolah_id == Sekolah.id
        ).join(Kebiasaan, Kebiasaan.kelas_id == Kelas.id
        ).filter(getattr(Kebiasaan, field).isnot(None))
        
        # Filter berdasarkan tahun ajaran terakhir
        if tahun_ajaran_terakhir:
            query = query.filter(Kelas.tahun_ajaran_id == tahun_ajaran_terakhir.id)
        
        top_sekolah = query.group_by(Sekolah.id, Sekolah.nama_sekolah
        ).order_by(func.avg(getattr(Kebiasaan, field)).desc()
        ).limit(10).all()
        
        habits_data[kebiasaan_labels[i]] = {
            'labels': [s.nama_sekolah for s in top_sekolah],
            'data': [float(s.rata_rata or 0) for s in top_sekolah]
        }
    
    # Data untuk line chart - sesuaikan dengan format bulan di database "YYYY-MM"
    # Urutan bulan sesuai tahun ajaran 2025/2026
    urutan_bulan_tahun_ajaran = [
        '2025-07', '2025-08', '2025-09', '2025-10', '2025-11', '2025-12',
        '2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06'
    ]
    
    # Mapping nama bulan untuk tampilan
    nama_bulan_tampilan = {
        '2025-07': 'Jul 2025', '2025-08': 'Agust 2025', '2025-09': 'Sept 2025', 
        '2025-10': 'Okt 2025', '2025-11': 'Nop 2025', '2025-12': 'Des 2025',
        '2026-01': 'Jan 2026', '2026-02': 'Feb 2026', '2026-03': 'Mar 2026', 
        '2026-04': 'Apr 2026', '2026-05': 'Mei 2026', '2026-06': 'Jun 2026'
    }
    
    # Query data yang ada (filter berdasarkan tahun ajaran terakhir)
    query = db.session.query(
        Kebiasaan.bulan,
        func.avg(Kebiasaan.bangun_pagi).label('bangun_pagi'),
        func.avg(Kebiasaan.beribadah).label('beribadah'),
        func.avg(Kebiasaan.berolahraga).label('berolahraga'),
        func.avg(Kebiasaan.sehat_dan_lemar).label('sehat_dan_lemar'),
        func.avg(Kebiasaan.belajar).label('belajar'),
        func.avg(Kebiasaan.bermasyarakat).label('bermasyarakat'),
        func.avg(Kebiasaan.tidur_cepat).label('tidur_cepat')
    ).filter(
        Kebiasaan.bangun_pagi.isnot(None)
    )
    
    # Filter berdasarkan tahun ajaran terakhir
    if tahun_ajaran_terakhir:
        query = query.join(Kelas, Kelas.id == Kebiasaan.kelas_id
                  ).filter(Kelas.tahun_ajaran_id == tahun_ajaran_terakhir.id)
    
    bulan_stats = query.group_by(Kebiasaan.bulan).all()
    
    # Buat mapping data per bulan (sekarang string "YYYY-MM")
    bulan_data = {b.bulan: b for b in bulan_stats}
    
    # Siapkan data untuk semua bulan dalam urutan tahun ajaran
    trend_datasets = []
    for i, field in enumerate(kebiasaan_fields):
        data_per_bulan = []
        for bulan in urutan_bulan_tahun_ajaran:
            if bulan in bulan_data:
                # Ada data untuk bulan ini
                data_per_bulan.append(float(getattr(bulan_data[bulan], field) or 0))
            else:
                # Tidak ada data, set null untuk tidak ditampilkan
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
    
    # Rata-rata semua sekolah untuk tabel
    semua_sekolah = Sekolah.query.all()
    sekolah_stats = []
    
    for sekolah in semua_sekolah:
        # Filter berdasarkan tahun ajaran terakhir
        query_stats = db.session.query(
            func.avg(Kebiasaan.bangun_pagi).label('bangun_pagi'),
            func.avg(Kebiasaan.beribadah).label('beribadah'),
            func.avg(Kebiasaan.berolahraga).label('berolahraga'),
            func.avg(Kebiasaan.sehat_dan_lemar).label('sehat_dan_lemar'),
            func.avg(Kebiasaan.belajar).label('belajar'),
            func.avg(Kebiasaan.bermasyarakat).label('bermasyarakat'),
            func.avg(Kebiasaan.tidur_cepat).label('tidur_cepat')
        ).join(Kelas, Kelas.id == Kebiasaan.kelas_id
        ).filter(Kelas.sekolah_id == sekolah.id)
        
        # Filter berdasarkan tahun ajaran terakhir
        if tahun_ajaran_terakhir:
            query_stats = query_stats.filter(Kelas.tahun_ajaran_id == tahun_ajaran_terakhir.id)
        
        stats = query_stats.first()
        
        if stats and any([getattr(stats, field) for field in kebiasaan_fields]):
            # Hitung rata-rata hanya jika ada data
            nilai_nilai = [
                float(stats.bangun_pagi or 0),
                float(stats.beribadah or 0),
                float(stats.berolahraga or 0),
                float(stats.sehat_dan_lemar or 0),
                float(stats.belajar or 0),
                float(stats.bermasyarakat or 0),
                float(stats.tidur_cepat or 0)
            ]
            
            # Filter nilai yang > 0 (ada data)
            nilai_valid = [nilai for nilai in nilai_nilai if nilai > 0]
            
            if nilai_valid:  # Hanya tambah jika ada data valid
                sekolah_stats.append({
                    'sekolah': sekolah.nama_sekolah,
                    'bangun_pagi': float(stats.bangun_pagi or 0),
                    'beribadah': float(stats.beribadah or 0),
                    'berolahraga': float(stats.berolahraga or 0),
                    'sehat_dan_lemar': float(stats.sehat_dan_lemar or 0),
                    'belajar': float(stats.belajar or 0),
                    'bermasyarakat': float(stats.bermasyarakat or 0),
                    'tidur_cepat': float(stats.tidur_cepat or 0),
                    'rata_rata': sum(nilai_valid) / len(nilai_valid)
                })
    
    return jsonify({
        'tahun_ajaran': tahun_ajaran_text,
        'total_users': total_users,
        'total_pegawai': total_pegawai,
        'total_sekolah': total_sekolah_aktif,
        'overall_performance': round(overall_avg, 1),
        'habits_data': habits_data,
        'trend_data': trend_data,
        'sekolah_stats': sorted(sekolah_stats, key=lambda x: x['rata_rata'], reverse=True)
    })

@superadmin_bp.route("/api/users")
@login_required
def api_users():
    if not current_user.is_superadmin:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Ambil semua user dengan data pegawai dan sekolah
    users = db.session.query(
        User, Pegawai, Sekolah
    ).outerjoin(Pegawai, Pegawai.user_id == User.id
    ).outerjoin(Sekolah, Sekolah.id == Pegawai.sekolah_id
    ).all()
    
    users_data = []
    for user, pegawai, sekolah in users:
        users_data.append({
            'id': user.id,
            'username': user.username,
            'nama_lengkap': user.nama_lengkap,
            'email': user.email,
            'role': user.role,
            'sekolah': sekolah.nama_sekolah if sekolah else '-',
            'nip': pegawai.nip if pegawai else '-',
            'pegawai_id': pegawai.id if pegawai else None
        })
    
    return jsonify({'users': users_data})

@superadmin_bp.route("/api/change_user_password", methods=["POST"])
@login_required
def api_change_user_password():
    if not current_user.is_superadmin:
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.get_json()
    user_id = data.get('user_id')
    new_password = data.get('new_password')
    
    if not user_id or not new_password:
        return jsonify({"success": False, "message": "Data tidak lengkap"})
    
    try:
        from werkzeug.security import generate_password_hash
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({"success": False, "message": "User tidak ditemukan"})
        
        # Update password
        user.password = generate_password_hash(new_password)
        db.session.commit()
        
        return jsonify({"success": True, "message": f"Password untuk {user.username} berhasil diubah"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"})