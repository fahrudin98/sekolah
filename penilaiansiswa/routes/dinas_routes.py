from flask import Blueprint, render_template, jsonify, request, session
from flask_login import login_required, current_user
from penilaiansiswa import db
from penilaiansiswa.models.sekolah import Sekolah, Kabupaten, Kecamatan, TahunAjaran, Kelas, Kebiasaan
from penilaiansiswa.models.users import Pegawai, User
from sqlalchemy import func

dinas_bp = Blueprint("dinas", __name__, url_prefix="/kepala_dinas")

# ========== HELPER ==========
def get_kabupaten_id_user():
    """Mengambil kabupaten_id dari user yang login sebagai kepala dinas"""
    pegawai = Pegawai.query.filter_by(user_id=current_user.id).first()
    if pegawai and pegawai.sekolah and pegawai.sekolah.kecamatan:
        return pegawai.sekolah.kecamatan.kabupaten_id
    return None

def get_kabupaten_nama():
    kab_id = get_kabupaten_id_user()
    if kab_id:
        kab = Kabupaten.query.get(kab_id)
        return kab.nama if kab else None
    return None

# ========== HALAMAN UTAMA ==========
@dinas_bp.route("/dashboard")
@login_required
def dashboard():
    """Halaman utama dashboard kepala dinas"""
    # Pastikan user adalah kepala dinas
    if not current_user.is_kepala_dinas:
        from flask import flash, redirect, url_for
        flash("Akses ditolak! Halaman ini hanya untuk Kepala Dinas.", "danger")
        return redirect(url_for("tahun_ajaran.dashboard"))
    
    kabupaten_nama = get_kabupaten_nama()
    tahun_ajaran_list = TahunAjaran.query.order_by(TahunAjaran.id.desc()).all()
    
    return render_template(
        "kepala_dinas/dashboard.html",
        user=current_user,
        kabupaten_nama=kabupaten_nama or "Kabupaten",
        tahun_ajaran_list=tahun_ajaran_list
    )

# ========== API STATISTIK UTAMA ==========
@dinas_bp.route("/api/statistik")
@login_required
def api_statistik():
    """API untuk data dashboard kepala dinas (1 kabupaten)"""
    if not current_user.is_kepala_dinas:
        return jsonify({"error": "Unauthorized"}), 403
    
    kabupaten_id = get_kabupaten_id_user()
    if not kabupaten_id:
        return jsonify({"error": "Kabupaten tidak ditemukan untuk user ini"}), 404
    
    # Ambil parameter
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 25, type=int)
    bulan = request.args.get('bulan', '', type=str)
    tahun_ajaran_id = request.args.get('tahun_ajaran_id', '', type=str)
    search = request.args.get('search', '', type=str)
    
    if limit > 100:
        limit = 100
    if page < 1:
        page = 1
    
    # ========== 1. DATA STATISTIK RINGKASAN ==========
    # Total sekolah di kabupaten
    total_sekolah = Sekolah.query.join(Kecamatan).filter(Kecamatan.kabupaten_id == kabupaten_id).count()
    
    # Total pegawai di kabupaten
    total_pegawai = Pegawai.query.join(Sekolah).join(Kecamatan).filter(Kecamatan.kabupaten_id == kabupaten_id).count()
    
    # Total user (unique)
    pegawai_ids = Pegawai.query.join(Sekolah).join(Kecamatan).filter(Kecamatan.kabupaten_id == kabupaten_id).all()
    user_ids = set([p.user_id for p in pegawai_ids if p.user_id])
    total_users = len(user_ids)
    
    # Total siswa di kabupaten
    total_siswa = db.session.query(Kelas).join(Sekolah).join(Kecamatan).filter(Kecamatan.kabupaten_id == kabupaten_id).count()
    # Estimasi siswa (1 kelas = 30 siswa rata-rata)
    total_siswa = total_siswa * 30
    
    # Rata-rata keseluruhan kabupaten
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
     .filter(Kecamatan.kabupaten_id == kabupaten_id)
    
    if tahun_ajaran_id:
        perf_query = perf_query.filter(Kelas.tahun_ajaran_id == tahun_ajaran_id)
    if bulan:
        perf_query = perf_query.filter(Kebiasaan.bulan == bulan)
    
    perf_result = perf_query.first()
    if perf_result:
        nilai_list = [
            perf_result.bangun_pagi or 0, perf_result.beribadah or 0,
            perf_result.berolahraga or 0, perf_result.sehat_dan_lemar or 0,
            perf_result.belajar or 0, perf_result.bermasyarakat or 0,
            perf_result.tidur_cepat or 0
        ]
        overall_performance = sum(nilai_list) / 7
    else:
        overall_performance = 0
    
    # ========== 2. DATA SEKOLAH UNTUK TABEL ==========
    sekolah_query = Sekolah.query.join(Kecamatan).filter(Kecamatan.kabupaten_id == kabupaten_id)
    
    if search:
        sekolah_query = sekolah_query.filter(Sekolah.nama_sekolah.ilike(f'%{search}%'))
    
    semua_sekolah = sekolah_query.all()
    
    sekolah_dengan_data = []
    for sekolah in semua_sekolah:
        nilai_query = db.session.query(
            func.avg(Kebiasaan.bangun_pagi).label('bangun_pagi'),
            func.avg(Kebiasaan.beribadah).label('beribadah'),
            func.avg(Kebiasaan.berolahraga).label('berolahraga'),
            func.avg(Kebiasaan.sehat_dan_lemar).label('sehat_dan_lemar'),
            func.avg(Kebiasaan.belajar).label('belajar'),
            func.avg(Kebiasaan.bermasyarakat).label('bermasyarakat'),
            func.avg(Kebiasaan.tidur_cepat).label('tidur_cepat')
        ).join(Kelas, Kebiasaan.kelas_id == Kelas.id)\
         .filter(Kelas.sekolah_id == sekolah.id)
        
        if tahun_ajaran_id:
            nilai_query = nilai_query.filter(Kelas.tahun_ajaran_id == tahun_ajaran_id)
        if bulan:
            nilai_query = nilai_query.filter(Kebiasaan.bulan == bulan)
        
        nilai = nilai_query.first()
        
        nilai_list = [
            float(nilai.bangun_pagi or 0), float(nilai.beribadah or 0),
            float(nilai.berolahraga or 0), float(nilai.sehat_dan_lemar or 0),
            float(nilai.belajar or 0), float(nilai.bermasyarakat or 0),
            float(nilai.tidur_cepat or 0)
        ]
        rata_rata = sum(nilai_list) / 7
        
        sekolah_dengan_data.append({
            'sekolah': sekolah.nama_sekolah,
            'bangun_pagi': round(nilai_list[0], 2),
            'beribadah': round(nilai_list[1], 2),
            'berolahraga': round(nilai_list[2], 2),
            'sehat_dan_lemar': round(nilai_list[3], 2),
            'belajar': round(nilai_list[4], 2),
            'bermasyarakat': round(nilai_list[5], 2),
            'tidur_cepat': round(nilai_list[6], 2),
            'rata_rata': round(rata_rata, 2)
        })
    
    # Urutkan berdasarkan rata-rata tertinggi
    sekolah_dengan_data.sort(key=lambda x: x['rata_rata'], reverse=True)
    
    total_data = len(sekolah_dengan_data)
    offset = (page - 1) * limit
    data_paginated = sekolah_dengan_data[offset:offset + limit]
    total_pages = (total_data + limit - 1) // limit if limit > 0 else 0
    
    # ========== 3. DATA GRAFIK KEBIASAAN (10 SEKOLAH TERBAIK) ==========
    kebiasaan_fields = ['bangun_pagi', 'beribadah', 'berolahraga', 'sehat_dan_lemar', 'belajar', 'bermasyarakat', 'tidur_cepat']
    kebiasaan_labels = ['Bangun Pagi', 'Beribadah', 'Berolahraga', 'Makan Sehat', 'Belajar', 'Bermasyarakat', 'Tidur Cepat']
    
    habits_data = {}
    
    for i, field_name in enumerate(kebiasaan_fields):
        field_label = kebiasaan_labels[i]
        sekolah_nilai = []
        
        for sekolah in semua_sekolah:
            val_query = db.session.query(
                func.avg(getattr(Kebiasaan, field_name)).label('nilai')
            ).join(Kelas, Kebiasaan.kelas_id == Kelas.id)\
             .filter(Kelas.sekolah_id == sekolah.id)
            
            if tahun_ajaran_id:
                val_query = val_query.filter(Kelas.tahun_ajaran_id == tahun_ajaran_id)
            if bulan:
                val_query = val_query.filter(Kebiasaan.bulan == bulan)
            
            nilai = val_query.first()
            val = float(nilai.nilai or 0)
            
            if val > 0:
                sekolah_nilai.append((sekolah.nama_sekolah, val))
        
        sekolah_nilai.sort(key=lambda x: x[1], reverse=True)
        sekolah_nilai = sekolah_nilai[:10]
        
        habits_data[field_label] = {
            'labels': [item[0] for item in sekolah_nilai],
            'data': [item[1] for item in sekolah_nilai]
        }
    
    # ========== 4. DATA TREND CHART ==========
    urutan_bulan = ['2025-07', '2025-08', '2025-09', '2025-10', '2025-11', '2025-12',
                    '2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06']
    
    nama_bulan = {
        '2025-07': 'Jul 2025', '2025-08': 'Agust 2025', '2025-09': 'Sept 2025',
        '2025-10': 'Okt 2025', '2025-11': 'Nop 2025', '2025-12': 'Des 2025',
        '2026-01': 'Jan 2026', '2026-02': 'Feb 2026', '2026-03': 'Mar 2026',
        '2026-04': 'Apr 2026', '2026-05': 'Mei 2026', '2026-06': 'Jun 2026'
    }
    
    trend_query = db.session.query(
        Kebiasaan.bulan,
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
     .filter(Kecamatan.kabupaten_id == kabupaten_id)
    
    if tahun_ajaran_id:
        trend_query = trend_query.filter(Kelas.tahun_ajaran_id == tahun_ajaran_id)
    
    trend_query = trend_query.filter(Kebiasaan.bulan.isnot(None)).group_by(Kebiasaan.bulan)
    bulan_stats = trend_query.all()
    bulan_dict = {b.bulan: b for b in bulan_stats}
    
    colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#2E8B57']
    trend_datasets = []
    
    for i, field in enumerate(kebiasaan_fields):
        data_per_bulan = []
        for bln in urutan_bulan:
            if bln in bulan_dict:
                val = getattr(bulan_dict[bln], field)
                data_per_bulan.append(float(val) if val else None)
            else:
                data_per_bulan.append(None)
        
        trend_datasets.append({
            'label': kebiasaan_labels[i],
            'data': data_per_bulan,
            'borderColor': colors[i],
            'tension': 0.3,
            'spanGaps': True
        })
    
    trend_data = {
        'labels': [nama_bulan[b] for b in urutan_bulan],
        'datasets': trend_datasets
    }
    
    tahun_ajaran_obj = TahunAjaran.query.get(tahun_ajaran_id) if tahun_ajaran_id else TahunAjaran.query.filter_by(aktif=True).first()
    tahun_ajaran_text = tahun_ajaran_obj.tahun_ajaran if tahun_ajaran_obj else "Semua"
    
    return jsonify({
        'success': True,
        'kabupaten_nama': get_kabupaten_nama(),
        'tahun_ajaran': tahun_ajaran_text,
        'overall_performance': round(overall_performance, 1),
        'total_sekolah': total_sekolah,
        'total_pegawai': total_pegawai,
        'total_siswa': total_siswa,
        'total_users': total_users,
        'data_sekolah': data_paginated,
        'total_data': total_data,
        'page': page,
        'limit': limit,
        'total_pages': total_pages,
        'habits_data': habits_data,
        'trend_data': trend_data
    })


# ========== API DAFTAR BULAN ==========
@dinas_bp.route("/api/bulan_list")
@login_required
def api_bulan_list():
    """API untuk mengambil daftar bulan yang memiliki data"""
    if not current_user.is_kepala_dinas:
        return jsonify({'success': False, 'bulan_list': []}), 403
    
    kabupaten_id = get_kabupaten_id_user()
    if not kabupaten_id:
        return jsonify({'success': False, 'bulan_list': []})
    
    tahun_ajaran_id = request.args.get('tahun_ajaran_id', '', type=str)
    
    query = db.session.query(
        Kebiasaan.bulan,
        func.count(Kebiasaan.id).label('jumlah')
    ).join(Kelas, Kebiasaan.kelas_id == Kelas.id)\
     .join(Sekolah, Kelas.sekolah_id == Sekolah.id)\
     .join(Kecamatan, Sekolah.kecamatan_id == Kecamatan.id)\
     .filter(Kecamatan.kabupaten_id == kabupaten_id)
    
    if tahun_ajaran_id:
        query = query.filter(Kelas.tahun_ajaran_id == tahun_ajaran_id)
    
    bulan_data = query.filter(Kebiasaan.bulan.isnot(None)).group_by(Kebiasaan.bulan).order_by(Kebiasaan.bulan.desc()).all()
    
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
    
    return jsonify({'success': True, 'bulan_list': bulan_list})