# penilaiansiswa/routes/sekolah_routes.py
from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from penilaiansiswa import db
from penilaiansiswa.models.sekolah import Sekolah
from penilaiansiswa.forms import AktivasiSekolahForm

sekolah_bp = Blueprint('sekolah', __name__, url_prefix='/sekolah')


@sekolah_bp.route('/<int:sekolah_id>/aktivasi', methods=['GET', 'POST'])
@login_required
def aktivasi_sekolah(sekolah_id):
    """Form untuk mengaktifkan sekolah - hanya superadmin"""
    if  current_user.role != 'superadmin':
        flash('Anda tidak memiliki akses ke halaman ini.', 'danger')
        return redirect(url_for('tahun_ajaran.dashboard'))
    
    sekolah = Sekolah.query.get_or_404(sekolah_id)
    
    if sekolah.status_aktif:
        flash(f'Sekolah {sekolah.nama_sekolah} sudah aktif.', 'warning')
        return redirect(url_for('tahun_ajaran.dashboard'))
    
    form = AktivasiSekolahForm()
    
    if form.validate_on_submit():
        sekolah.aktivasi(masa_berlaku_hari=form.masa_berlaku.data)
        db.session.commit()
        
        flash(
            f'Sekolah {sekolah.nama_sekolah} berhasil diaktifkan. '
            f'Masa berlaku sampai {sekolah.tanggal_kadaluarsa.strftime("%d-%m-%Y")}',
            'success'
        )
        return redirect(url_for('tahun_ajaran.dashboard'))
    
    return render_template('aktivasi_sekolah.html', form=form, sekolah=sekolah)


@sekolah_bp.route('/<int:sekolah_id>/perpanjang', methods=['GET', 'POST'])
@login_required
def perpanjang_sekolah(sekolah_id):
    """Form untuk memperpanjang masa aktif sekolah"""
    sekolah = Sekolah.query.get_or_404(sekolah_id)
    
    # Cek akses
    is_kepala_sekolah = False
    if hasattr(current_user, 'pegawai') and current_user.pegawai:
        from penilaiansiswa.models.sekolah import TahunAjaran
        ta_aktif = TahunAjaran.query.filter_by(
            sekolah_id=sekolah_id,
            kepala_sekolah_id=current_user.pegawai.id,
            aktif=True
        ).first()
        is_kepala_sekolah = ta_aktif is not None
    
    if  current_user.role != 'superadmin' and not is_kepala_sekolah:
        flash('Anda tidak memiliki akses ke halaman ini.', 'danger')
        return redirect(url_for('tahun_ajaran.dashboard'))
    
    if not sekolah.status_aktif:
        flash('Sekolah tidak aktif. Silakan aktivasi terlebih dahulu.', 'warning')
        return redirect(url_for('sekolah.aktivasi_sekolah', sekolah_id=sekolah_id))
    
    form = AktivasiSekolahForm()
    
    if form.validate_on_submit():
        sekolah.perpanjang(tambahan_hari=form.masa_berlaku.data)
        db.session.commit()
        
        flash(
            f'Masa aktif sekolah {sekolah.nama_sekolah} berhasil diperpanjang. '
            f'Masa berlaku baru sampai {sekolah.tanggal_kadaluarsa.strftime("%d-%m-%Y")}',
            'success'
        )
        return redirect(url_for('tahun_ajaran.dashboard'))
    
    sisa_hari = sekolah.sisa_hari if sekolah.sisa_hari else 0
    
    return render_template(
        'perpanjang_sekolah.html',
        form=form,
        sekolah=sekolah,
        sisa_hari=sisa_hari
    )

@sekolah_bp.route('/manage')
@login_required
def manage_sekolah():
    """Halaman manajemen sekolah untuk superadmin dengan pagination"""
    if current_user.role != 'superadmin':
        flash('Akses ditolak. Hanya untuk superadmin.', 'danger')
        return redirect(url_for('tahun_ajaran.dashboard'))
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)  # default 50 per halaman
    
    # Ambil data dengan pagination
    pagination = Sekolah.query.order_by(Sekolah.nama_sekolah).paginate(
        page=page, 
        per_page=per_page,
        error_out=False
    )
    
    sekolah_list = pagination.items
    total_sekolah = pagination.total
    aktif_count = Sekolah.query.filter_by(status_aktif=True).count()
    nonaktif_count = total_sekolah - aktif_count
    
    return render_template(
        'manage_sekolah.html',
        sekolah_list=sekolah_list,
        total_sekolah=total_sekolah,
        aktif_count=aktif_count,
        nonaktif_count=nonaktif_count,
        pagination=pagination,
        page=page,
        per_page=per_page
    )