from flask import Blueprint, jsonify, request, render_template, abort
from flask_login import login_required, current_user
from penilaiansiswa.models import TahunAjaran, Kelas, Kebiasaan, Siswa, Pegawai, Sekolah, Provinsi, Kabupaten, Kecamatan
from penilaiansiswa.routes.tahun_ajaran_routes import extract_years_from_ta, get_kelas_for_current_user, generate_bulan_list_for_semester
from penilaiansiswa import db
from datetime import datetime
import traceback
from penilaiansiswa.utils.kebiasaan_labels import get_field_labels

laporan_bp = Blueprint("laporan", __name__, url_prefix="/laporan")

@laporan_bp.route("/data_filter")
@login_required
def data_filter():
    try:
        if not hasattr(current_user, 'pegawai') or not current_user.pegawai:
            return jsonify({"success": False, "message": "User tidak terkait pegawai"}), 403

        sekolah = getattr(current_user.pegawai, "sekolah", None)
        if not sekolah:
            return jsonify({"success": False, "message": "Pegawai tidak terkait sekolah"}), 403

        semua_tahun = TahunAjaran.query.filter_by(sekolah_id=sekolah.id).order_by(TahunAjaran.id.desc()).all()

        semua_tahun_ajaran = []
        kelas_dict = {}
        bulan_dict = {}

        for ta in semua_tahun:
            start_year, end_year = extract_years_from_ta(ta)
            semester = getattr(ta, "semester", "ganjil").capitalize()
            ta_name = f"{start_year}/{end_year} ({semester})"
            semua_tahun_ajaran.append({"id": ta.id, "name": ta_name})

            kelas_list = get_kelas_for_current_user(sekolah, ta)
            kelas_dict[ta.id] = [{"id": k.id, "nama": k.nama_kelas} for k in kelas_list]
            bulan_list = generate_bulan_list_for_semester(ta)
            bulan_dict[ta.id] = bulan_list

        return jsonify({
            "success": True,
            "tahun": semua_tahun_ajaran,
            "kelas": kelas_dict,
            "bulan": bulan_dict
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@laporan_bp.route("/rchk/<int:kelas_id>/<string:bulan>")
@login_required
def laporan_rchk(kelas_id, bulan):
    try:
        kelas = Kelas.query.get_or_404(kelas_id)
        if not hasattr(current_user, 'pegawai') or kelas.wali_kelas_id != current_user.pegawai.id:
            abort(403, description="Anda bukan wali kelas dari kelas ini")

        tahun_ajaran = TahunAjaran.query.get(kelas.tahun_ajaran_id)
        sekolah = Sekolah.query.get(kelas.sekolah_id)
        kepala_sekolah = Pegawai.query.get(tahun_ajaran.kepala_sekolah_id) if tahun_ajaran else None
        wali_kelas = Pegawai.query.get(kelas.wali_kelas_id)

        kecamatan = Kecamatan.query.get(sekolah.kecamatan_id) if sekolah else None
        kabupaten = Kabupaten.query.get(kecamatan.kabupaten_id) if kecamatan else None
        provinsi = Provinsi.query.get(kabupaten.provinsi_id) if kabupaten else None

        siswa_list = Siswa.query.filter_by(kelas_id=kelas.id).order_by(Siswa.nama_siswa).all()

        kebiasaan_fields = [
            'bangun_pagi', 'beribadah', 'berolahraga',
            'sehat_dan_lemar', 'belajar', 'bermasyarakat', 'tidur_cepat'
        ]
        field_labels = get_field_labels()

        jml_perempuan = sum(1 for s in siswa_list if s.jenis_kelamin == 'P')
        jml_laki = sum(1 for s in siswa_list if s.jenis_kelamin == 'L')

        terbiasa_perempuan = 0
        terbiasa_laki = 0

        rekap_umum = {field: {'terbiasa': 0, 'belum': 0} for field in kebiasaan_fields}
        rekap_jk = {
            'P': {field: {'terbiasa': 0, 'belum': 0} for field in kebiasaan_fields},
            'L': {field: {'terbiasa': 0, 'belum': 0} for field in kebiasaan_fields}
        }

        for siswa in siswa_list:
            kebiasaan = Kebiasaan.query.filter_by(
                siswa_id=siswa.id,
                kelas_id=kelas.id,
                bulan=bulan
            ).first()

            nilai_kebiasaan = []
            for field in kebiasaan_fields:
                nilai = getattr(kebiasaan, field, 0) if kebiasaan else 0
                nilai_kebiasaan.append(nilai)

                if nilai >= 20:
                    rekap_umum[field]['terbiasa'] += 1
                    rekap_jk[siswa.jenis_kelamin][field]['terbiasa'] += 1
                else:
                    rekap_umum[field]['belum'] += 1
                    rekap_jk[siswa.jenis_kelamin][field]['belum'] += 1

            # LOGIKA TERBIASA: semua 7 nilai >= 20
            if all(nilai >= 20 for nilai in nilai_kebiasaan):
                if siswa.jenis_kelamin == 'P':
                    terbiasa_perempuan += 1
                elif siswa.jenis_kelamin == 'L':
                    terbiasa_laki += 1

        total_siswa = len(siswa_list)
        total_terbiasa = terbiasa_perempuan + terbiasa_laki

        # Tambahkan prosentase ke rekap umum
        for field in kebiasaan_fields:
            total_field = rekap_umum[field]['terbiasa'] + rekap_umum[field]['belum']
            if total_field > 0:
                rekap_umum[field]['terbiasa_pct'] = round((rekap_umum[field]['terbiasa'] / total_field) * 100, 2)
                rekap_umum[field]['belum_pct'] = round((rekap_umum[field]['belum'] / total_field) * 100, 2)
            else:
                rekap_umum[field]['terbiasa_pct'] = 0.0
                rekap_umum[field]['belum_pct'] = 0.0

        # Tambahkan prosentase ke rekap per jenis kelamin
        for jk in ['P', 'L']:
            for field in kebiasaan_fields:
                total_field = rekap_jk[jk][field]['terbiasa'] + rekap_jk[jk][field]['belum']
                if total_field > 0:
                    rekap_jk[jk][field]['terbiasa_pct'] = round((rekap_jk[jk][field]['terbiasa'] / total_field) * 100, 2)
                    rekap_jk[jk][field]['belum_pct'] = round((rekap_jk[jk][field]['belum'] / total_field) * 100, 2)
                else:
                    rekap_jk[jk][field]['terbiasa_pct'] = 0.0
                    rekap_jk[jk][field]['belum_pct'] = 0.0

        data = {
            'tahun_ajaran': tahun_ajaran.tahun_ajaran if tahun_ajaran else '',
            'sekolah': {
                'nama': sekolah.nama_sekolah if sekolah else '',
                'npsn': sekolah.npsn if sekolah else '',
                'kecamatan': kecamatan.nama if kecamatan else '',
                'kabupaten': kabupaten.nama if kabupaten else '',
                'provinsi': provinsi.nama if provinsi else ''
            },
            'kepala_sekolah': {
                'nama': kepala_sekolah.nama if kepala_sekolah else '',
                'nip': kepala_sekolah.nip if kepala_sekolah else ''
            } if kepala_sekolah else {'nama': '', 'nip': ''},
            'wali_kelas': {
                'nama': wali_kelas.nama if wali_kelas else '',
                'nip': wali_kelas.nip if wali_kelas else ''
            } if wali_kelas else {'nama': '', 'nip': ''},
            'rekap_siswa': {
                'perempuan': {'total': jml_perempuan, 'terbiasa': terbiasa_perempuan, 'belum': jml_perempuan - terbiasa_perempuan},
                'laki': {'total': jml_laki, 'terbiasa': terbiasa_laki, 'belum': jml_laki - terbiasa_laki},
                'total': {'total': total_siswa, 'terbiasa': total_terbiasa, 'belum': total_siswa - total_terbiasa}
            },
            'rekap_umum': rekap_umum,
            'rekap_jk': rekap_jk,
            'bulan': bulan,
            'nama_kelas': kelas.nama_kelas,
            'kelas_id': kelas_id,
            'field_labels': field_labels
        }

        return render_template("laporan/rchk.html", data=data, now=datetime.now())

    except Exception as e:
        print(f"ERROR REPORT RCHK: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"Error generating report: {str(e)}"
        }), 500
@laporan_bp.route("/semester/<int:kelas_id>/<int:tahun_ajaran_id>")
@login_required
def laporan_semester(kelas_id, tahun_ajaran_id):
    try:
        kelas = Kelas.query.get_or_404(kelas_id)
        if not hasattr(current_user, "pegawai") or kelas.wali_kelas_id != current_user.pegawai.id:
            abort(403, description="Anda bukan wali kelas dari kelas ini")

        tahun_ajaran = TahunAjaran.query.get_or_404(tahun_ajaran_id)
        sekolah = Sekolah.query.get(kelas.sekolah_id)
        kepala_sekolah = Pegawai.query.get(tahun_ajaran.kepala_sekolah_id) if tahun_ajaran else None
        wali_kelas = Pegawai.query.get(kelas.wali_kelas_id)

        kecamatan = Kecamatan.query.get(sekolah.kecamatan_id) if sekolah else None
        kabupaten = Kabupaten.query.get(kecamatan.kabupaten_id) if kecamatan else None
        provinsi = Provinsi.query.get(kabupaten.provinsi_id) if kabupaten else None

        # Label field kebiasaan
        kebiasaan_fields = [
            "bangun_pagi", "beribadah", "berolahraga",
            "sehat_dan_lemar", "belajar", "bermasyarakat", "tidur_cepat"
        ]
        field_labels = get_field_labels()

        # Tentukan semester - konversi format tampilan
        if tahun_ajaran.semester.lower() == "ganjil":
            semester = "I"
        elif tahun_ajaran.semester.lower() == "genap":
            semester = "II"
        else:
            semester = tahun_ajaran.semester  # fallback

        # Ambil bulan list (normalize ke string)
        bulan_raw = generate_bulan_list_for_semester(tahun_ajaran)
        bulan_list = [b["value"] if isinstance(b, dict) else b for b in bulan_raw]

        # Daftar siswa
        siswa_list = Siswa.query.filter_by(kelas_id=kelas.id).order_by(Siswa.nama_siswa).all()

        jml_perempuan = sum(1 for s in siswa_list if s.jenis_kelamin == "P")
        jml_laki = sum(1 for s in siswa_list if s.jenis_kelamin == "L")
        terbiasa_perempuan = 0
        terbiasa_laki = 0

        rekap_umum = {field: {"terbiasa": 0, "belum": 0} for field in kebiasaan_fields}
        rekap_jk = {
            "P": {field: {"terbiasa": 0, "belum": 0} for field in kebiasaan_fields},
            "L": {field: {"terbiasa": 0, "belum": 0} for field in kebiasaan_fields},
        }

        for siswa in siswa_list:
            semua_field_terbiasa = True
            for field in kebiasaan_fields:
                field_terbiasa = True
                for bulan in bulan_list:
                    kebiasaan = Kebiasaan.query.filter_by(
                        siswa_id=siswa.id,
                        kelas_id=kelas.id,
                        bulan=bulan
                    ).first()
                    nilai = getattr(kebiasaan, field, 0) if kebiasaan else 0
                    if nilai < 20:  # ambang batas
                        field_terbiasa = False
                        break

                if field_terbiasa:
                    rekap_umum[field]["terbiasa"] += 1
                    rekap_jk[siswa.jenis_kelamin][field]["terbiasa"] += 1
                else:
                    rekap_umum[field]["belum"] += 1
                    rekap_jk[siswa.jenis_kelamin][field]["belum"] += 1
                    semua_field_terbiasa = False

            if semua_field_terbiasa:
                if siswa.jenis_kelamin == "P":
                    terbiasa_perempuan += 1
                elif siswa.jenis_kelamin == "L":
                    terbiasa_laki += 1

        total_siswa = len(siswa_list)
        total_terbiasa = terbiasa_perempuan + terbiasa_laki

        # Hitung prosentase rekap umum
        for field in kebiasaan_fields:
            total_field = rekap_umum[field]["terbiasa"] + rekap_umum[field]["belum"]
            if total_field > 0:
                rekap_umum[field]["terbiasa_pct"] = round((rekap_umum[field]["terbiasa"] / total_field) * 100, 2)
                rekap_umum[field]["belum_pct"] = round((rekap_umum[field]["belum"] / total_field) * 100, 2)
            else:
                rekap_umum[field]["terbiasa_pct"] = 0.0
                rekap_umum[field]["belum_pct"] = 0.0

        # Hitung prosentase per jenis kelamin
        for jk in ["P", "L"]:
            for field in kebiasaan_fields:
                total_field = rekap_jk[jk][field]["terbiasa"] + rekap_jk[jk][field]["belum"]
                if total_field > 0:
                    rekap_jk[jk][field]["terbiasa_pct"] = round((rekap_jk[jk][field]["terbiasa"] / total_field) * 100, 2)
                    rekap_jk[jk][field]["belum_pct"] = round((rekap_jk[jk][field]["belum"] / total_field) * 100, 2)
                else:
                    rekap_jk[jk][field]["terbiasa_pct"] = 0.0
                    rekap_jk[jk][field]["belum_pct"] = 0.0

        data = {
            "tahun_ajaran": tahun_ajaran.tahun_ajaran if tahun_ajaran else "",
            "semester": semester,
            "sekolah": {
                "nama": sekolah.nama_sekolah if sekolah else "",
                "npsn": sekolah.npsn if sekolah else "",
                "kecamatan": kecamatan.nama if kecamatan else "",
                "kabupaten": kabupaten.nama if kabupaten else "",
                "provinsi": provinsi.nama if provinsi else ""
            },
            "kepala_sekolah": {
                "nama": kepala_sekolah.nama if kepala_sekolah else "",
                "nip": kepala_sekolah.nip if kepala_sekolah else ""
            } if kepala_sekolah else {"nama": "", "nip": ""},
            "wali_kelas": {
                "nama": wali_kelas.nama if wali_kelas else "",
                "nip": wali_kelas.nip if wali_kelas else ""
            } if wali_kelas else {"nama": "", "nip": ""},
            "rekap_siswa": {
                "perempuan": {"total": jml_perempuan, "terbiasa": terbiasa_perempuan, "belum": jml_perempuan - terbiasa_perempuan},
                "laki": {"total": jml_laki, "terbiasa": terbiasa_laki, "belum": jml_laki - terbiasa_laki},
                "total": {"total": total_siswa, "terbiasa": total_terbiasa, "belum": total_siswa - total_terbiasa}
            },
            "rekap_umum_semester": rekap_umum,
            "rekap_jk_semester": rekap_jk,
            "nama_kelas": kelas.nama_kelas,
            "kelas_id": kelas_id,
            "field_labels": field_labels
        }

        return render_template("laporan/laporan_semester.html", data=data, now=datetime.now())

    except Exception as e:
        print("ERROR REPORT SEMESTER:", e)
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Error generating semester report: {str(e)}"}), 500


@laporan_bp.route("/test")
@login_required
def test_laporan():
    return jsonify({
        "success": True,
        "message": "Laporan endpoint bekerja dengan baik",
        "endpoints": {
            "data_filter": "/laporan/data_filter",
            "rchk": "/laporan/rchk/<kelas_id>/<bulan>"
        }
    })

@laporan_bp.app_template_filter('format_bulan')
def format_bulan_filter(bulan_str):
    """Filter Jinja2 untuk format bulan YYYY-MM ke Bahasa Indonesia"""
    try:
        if bulan_str and '-' in bulan_str:
            tahun, bulan = bulan_str.split('-')
            bulan = int(bulan)
            bulan_names = [
                'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
            ]
            return f"{bulan_names[bulan - 1]} {tahun}"
        return bulan_str
    except (ValueError, IndexError):
        return bulan_str
    
#LAPAORAN PENILAIAN DETAIL#
@laporan_bp.route("/penilaian/<int:kelas_id>/<string:bulan>")
@login_required
def laporan_penilaian(kelas_id, bulan):
    try:
        kelas = Kelas.query.get_or_404(kelas_id)
        if not hasattr(current_user, 'pegawai') or kelas.wali_kelas_id != current_user.pegawai.id:
            abort(403, description="Anda bukan wali kelas dari kelas ini")

        # Parse bulan untuk mendapatkan label
        try:
            tahun, bulan_num = bulan.split('-')
            bulan_num = int(bulan_num)
            bulan_names = [
                'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
            ]
            bulan_label = f"{bulan_names[bulan_num - 1]} {tahun}"
        except:
            bulan_label = bulan

        # Data sekolah dan tahun ajaran
        tahun_ajaran = TahunAjaran.query.get(kelas.tahun_ajaran_id)
        sekolah = Sekolah.query.get(kelas.sekolah_id)
        wali_kelas = Pegawai.query.get(kelas.wali_kelas_id)
        kepala_sekolah = Pegawai.query.get(tahun_ajaran.kepala_sekolah_id) if tahun_ajaran else None

        # Data kecamatan, kabupaten, provinsi
        kecamatan = Kecamatan.query.get(sekolah.kecamatan_id) if sekolah else None
        kabupaten = Kabupaten.query.get(kecamatan.kabupaten_id) if kecamatan else None
        provinsi = Provinsi.query.get(kabupaten.provinsi_id) if kabupaten else None

        # Data siswa dengan nilai
        siswa_list = Siswa.query.filter_by(kelas_id=kelas.id).order_by(Siswa.nama_siswa).all()
        
        siswa_with_nilai = []
        for siswa in siswa_list:
            kebiasaan = Kebiasaan.query.filter_by(
                siswa_id=siswa.id,
                kelas_id=kelas.id,
                bulan=bulan
            ).first()
            
            # Konversi jenis kelamin ke format yang lebih readable
            jk_map = {'L': 'Laki-laki', 'P': 'Perempuan'}
            jenis_kelamin = jk_map.get(siswa.jenis_kelamin, siswa.jenis_kelamin)
            
            siswa_data = {
                'id': siswa.id,
                'nama_siswa': siswa.nama_siswa,
                'jenis_kelamin': jenis_kelamin,
                'nilai': {
                    'bangun_pagi': getattr(kebiasaan, 'bangun_pagi', None),
                    'beribadah': getattr(kebiasaan, 'beribadah', None),
                    'berolahraga': getattr(kebiasaan, 'berolahraga', None),
                    'sehat_dan_lemar': getattr(kebiasaan, 'sehat_dan_lemar', None),
                    'belajar': getattr(kebiasaan, 'belajar', None),
                    'bermasyarakat': getattr(kebiasaan, 'bermasyarakat', None),
                    'tidur_cepat': getattr(kebiasaan, 'tidur_cepat', None),
                    'catatan': getattr(kebiasaan, 'catatan', '')
                } if kebiasaan else {}
            }
            siswa_with_nilai.append(siswa_data)

        data = {
            'kelas': {
                'id': kelas.id,
                'nama_kelas': kelas.nama_kelas
            },
            'tahun_ajaran': {
                'tahun_ajaran': tahun_ajaran.tahun_ajaran if tahun_ajaran else '',
                'semester': tahun_ajaran.semester if tahun_ajaran else ''
            },
            'sekolah': {
                'nama_sekolah': sekolah.nama_sekolah if sekolah else '',
                'npsn': sekolah.npsn if sekolah else '',
                'kecamatan': kecamatan.nama if kecamatan else '',
                'kabupaten': kabupaten.nama if kabupaten else '',
                'provinsi': provinsi.nama if provinsi else ''
            },
            'kepala_sekolah': {
                'nama': kepala_sekolah.nama if kepala_sekolah else '',
                'nip': kepala_sekolah.nip if kepala_sekolah else ''
            } if kepala_sekolah else {'nama': '', 'nip': ''},
            'wali_kelas': {
                'nama': wali_kelas.nama if wali_kelas else '',
                'nip': wali_kelas.nip if wali_kelas else ''
            },
            'siswa_list': siswa_with_nilai,
            'bulan': bulan,
            'bulan_label': bulan_label,
            'tanggal_cetak': datetime.now().strftime('%d %B %Y %H:%M')
        }

        return render_template("laporan/laporan_penilaian.html", data=data)

    except Exception as e:
        print(f"ERROR LAPORAN PENILAIAN: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"Error generating penilaian report: {str(e)}"
        }), 500
    

@laporan_bp.route("/tahunan/<int:kelas_id>/<int:tahun_ajaran_id>")
@login_required
def laporan_tahunan(kelas_id, tahun_ajaran_id):
    try:
        kelas = Kelas.query.get_or_404(kelas_id)
        if not hasattr(current_user, "pegawai") or kelas.wali_kelas_id != current_user.pegawai.id:
            abort(403, description="Anda bukan wali kelas dari kelas ini")

        tahun_ajaran = TahunAjaran.query.get_or_404(tahun_ajaran_id)
        sekolah = Sekolah.query.get(kelas.sekolah_id)
        kepala_sekolah = Pegawai.query.get(tahun_ajaran.kepala_sekolah_id) if tahun_ajaran else None
        wali_kelas = Pegawai.query.get(kelas.wali_kelas_id)

        kecamatan = Kecamatan.query.get(sekolah.kecamatan_id) if sekolah else None
        kabupaten = Kabupaten.query.get(kecamatan.kabupaten_id) if kecamatan else None
        provinsi = Provinsi.query.get(kabupaten.provinsi_id) if kabupaten else None

        # Label field kebiasaan
        kebiasaan_fields = [
            "bangun_pagi", "beribadah", "berolahraga",
            "sehat_dan_lemar", "belajar", "bermasyarakat", "tidur_cepat"
        ]
        field_labels = get_field_labels()

        # Generate bulan list untuk seluruh tahun ajaran (ganjil + genap)
        bulan_list_ganjil = generate_bulan_list_for_semester(tahun_ajaran, "ganjil")
        bulan_list_genap = generate_bulan_list_for_semester(tahun_ajaran, "genap")
        semua_bulan = bulan_list_ganjil + bulan_list_genap
        bulan_labels = [b['label'] for b in semua_bulan]

        # Daftar siswa
        siswa_list = Siswa.query.filter_by(kelas_id=kelas.id).order_by(Siswa.nama_siswa).all()

        jml_perempuan = sum(1 for s in siswa_list if s.jenis_kelamin == "P")
        jml_laki = sum(1 for s in siswa_list if s.jenis_kelamin == "L")
        terbiasa_perempuan = 0
        terbiasa_laki = 0

        rekap_umum = {field: {"terbiasa": 0, "belum": 0} for field in kebiasaan_fields}
        rekap_jk = {
            "P": {field: {"terbiasa": 0, "belum": 0} for field in kebiasaan_fields},
            "L": {field: {"terbiasa": 0, "belum": 0} for field in kebiasaan_fields},
        }

        for siswa in siswa_list:
            semua_field_terbiasa = True
            for field in kebiasaan_fields:
                field_terbiasa = True
                for bulan_data in semua_bulan:
                    bulan = bulan_data['value']
                    kebiasaan = Kebiasaan.query.filter_by(
                        siswa_id=siswa.id,
                        kelas_id=kelas.id,
                        bulan=bulan
                    ).first()
                    nilai = getattr(kebiasaan, field, 0) if kebiasaan else 0
                    # Jika ada satu bulan saja yang nilainya < 20, dianggap belum terbiasa
                    if nilai < 20:
                        field_terbiasa = False
                        break  # Langsung break, tidak perlu cek bulan lainnya

                if field_terbiasa:
                    rekap_umum[field]["terbiasa"] += 1
                    rekap_jk[siswa.jenis_kelamin][field]["terbiasa"] += 1
                else:
                    rekap_umum[field]["belum"] += 1
                    rekap_jk[siswa.jenis_kelamin][field]["belum"] += 1
                    semua_field_terbiasa = False

            if semua_field_terbiasa:
                if siswa.jenis_kelamin == "P":
                    terbiasa_perempuan += 1
                elif siswa.jenis_kelamin == "L":
                    terbiasa_laki += 1

        total_siswa = len(siswa_list)
        total_terbiasa = terbiasa_perempuan + terbiasa_laki

        # Hitung prosentase rekap umum
        for field in kebiasaan_fields:
            total_field = rekap_umum[field]["terbiasa"] + rekap_umum[field]["belum"]
            if total_field > 0:
                rekap_umum[field]["terbiasa_pct"] = round((rekap_umum[field]["terbiasa"] / total_field) * 100, 2)
                rekap_umum[field]["belum_pct"] = round((rekap_umum[field]["belum"] / total_field) * 100, 2)
            else:
                rekap_umum[field]["terbiasa_pct"] = 0.0
                rekap_umum[field]["belum_pct"] = 0.0

        # Hitung prosentase per jenis kelamin
        for jk in ["P", "L"]:
            for field in kebiasaan_fields:
                total_field = rekap_jk[jk][field]["terbiasa"] + rekap_jk[jk][field]["belum"]
                if total_field > 0:
                    rekap_jk[jk][field]["terbiasa_pct"] = round((rekap_jk[jk][field]["terbiasa"] / total_field) * 100, 2)
                    rekap_jk[jk][field]["belum_pct"] = round((rekap_jk[jk][field]["belum"] / total_field) * 100, 2)
                else:
                    rekap_jk[jk][field]["terbiasa_pct"] = 0.0
                    rekap_jk[jk][field]["belum_pct"] = 0.0

        data = {
            "tahun_ajaran": {
                "tahun_ajaran": tahun_ajaran.tahun_ajaran if tahun_ajaran else "",
                "semester": tahun_ajaran.semester if tahun_ajaran else ""
            },
            "sekolah": {
                "nama": sekolah.nama_sekolah if sekolah else "",
                "npsn": sekolah.npsn if sekolah else "",
                "kecamatan": kecamatan.nama if kecamatan else "",
                "kabupaten": kabupaten.nama if kabupaten else "",
                "provinsi": provinsi.nama if provinsi else ""
            },
            "kepala_sekolah": {
                "nama": kepala_sekolah.nama if kepala_sekolah else "",
                "nip": kepala_sekolah.nip if kepala_sekolah else ""
            } if kepala_sekolah else {"nama": "", "nip": ""},
            "wali_kelas": {
                "nama": wali_kelas.nama if wali_kelas else "",
                "nip": wali_kelas.nip if wali_kelas else ""
            } if wali_kelas else {"nama": "", "nip": ""},
            "kelas": {  # PERUBAHAN: Ditambahkan object kelas
                "id": kelas.id,
                "nama_kelas": kelas.nama_kelas
            },
            "rekap_siswa": {
                "perempuan": {"total": jml_perempuan, "terbiasa": terbiasa_perempuan, "belum": jml_perempuan - terbiasa_perempuan},
                "laki": {"total": jml_laki, "terbiasa": terbiasa_laki, "belum": jml_laki - terbiasa_laki},
                "total": {"total": total_siswa, "terbiasa": total_terbiasa, "belum": total_siswa - total_terbiasa}
            },
            "rekap_umum": rekap_umum,
            "rekap_jk": rekap_jk,
            "nama_kelas": kelas.nama_kelas,  # Tetap dipertahankan untuk backward compatibility
            "kelas_id": kelas_id,
            "field_labels": field_labels,
            "bulan_list": bulan_labels,
            "tanggal_cetak": datetime.now().strftime('%d %B %Y %H:%M')
        }

        return render_template("laporan/laporan_tahunan.html", data=data)

    except Exception as e:
        print("ERROR REPORT TAHUNAN:", e)
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Error generating tahunan report: {str(e)}"}), 500

@laporan_bp.route("/api/tahun-ajaran")
@login_required
def api_tahun_ajaran():
    try:
        tahun_ajaran_list = TahunAjaran.query.order_by(TahunAjaran.tahun_ajaran.desc()).all()
        
        data = {
            "tahun_ajaran": [
                {
                    "id": ta.id,
                    "tahun_ajaran": ta.tahun_ajaran,
                    "semester": ta.semester,
                    "status": ta.status
                }
                for ta in tahun_ajaran_list
            ]
        }
        
        return jsonify(data)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@laporan_bp.route("/api/kelas-by-tahun-ajaran/<int:tahun_ajaran_id>")
@login_required
def api_kelas_by_tahun_ajaran(tahun_ajaran_id):
    try:
        kelas_list = Kelas.query.filter_by(tahun_ajaran_id=tahun_ajaran_id).order_by(Kelas.nama_kelas).all()
        
        data = {
            "kelas": [
                {
                    "id": kelas.id,
                    "nama_kelas": kelas.nama_kelas,
                    "wali_kelas_id": kelas.wali_kelas_id
                }
                for kelas in kelas_list
            ]
        }
        
        return jsonify(data)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@laporan_bp.route("/api/siswa-by-kelas/<int:kelas_id>")
@login_required
def api_siswa_by_kelas(kelas_id):
    try:
        print(f"DEBUG: Mengambil siswa untuk kelas_id: {kelas_id}")
        
        # Cek apakah kelas exists
        kelas = Kelas.query.get(kelas_id)
        if not kelas:
            return jsonify({"success": False, "message": "Kelas tidak ditemukan"}), 404
        
        # Cek authorization - hanya wali kelas yang bisa mengakses
        if not hasattr(current_user, 'pegawai') or kelas.wali_kelas_id != current_user.pegawai.id:
            return jsonify({"success": False, "message": "Anda bukan wali kelas dari kelas ini"}), 403

        # Ambil data siswa dari database - sesuai dengan model Siswa
        siswa_list = Siswa.query.filter_by(kelas_id=kelas_id).order_by(Siswa.nama_siswa).all()
        print(f"DEBUG: Ditemukan {len(siswa_list)} siswa di kelas {kelas.nama_kelas}")
        
        # Format data sesuai model Siswa
        data_siswa = []
        for siswa in siswa_list:
            data_siswa.append({
                "id": siswa.id,
                "nama_siswa": siswa.nama_siswa,
                "jenis_kelamin": siswa.jenis_kelamin,
                "kelas_id": siswa.kelas_id,
                "status": siswa.status
            })
        
        response_data = {
            "success": True,
            "kelas": {
                "id": kelas.id,
                "nama_kelas": kelas.nama_kelas
            },
            "siswa": data_siswa,
            "total": len(data_siswa)
        }
        
        return jsonify(response_data)
    
    except Exception as e:
        print(f"ERROR API SISWA BY KELAS: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

# Route utama untuk laporan penilaian siswa

@laporan_bp.route("/penilaian-siswa/<int:siswa_id>")
@login_required
def laporan_penilaian_siswa(siswa_id):
    try:
        # Dapatkan parameter dari query string
        tahun_ajaran_id = request.args.get('tahun_ajaran_id')
        semester_param = request.args.get('semester', '').lower()
        
        print(f"DEBUG: Membuat laporan untuk siswa_id: {siswa_id}, semester: {semester_param}")
        
        # Cari siswa
        siswa = Siswa.query.get(siswa_id)
        if not siswa:
            return render_template("error.html", 
                                message=f"Siswa dengan ID {siswa_id} tidak ditemukan di database."), 404
        
        kelas = Kelas.query.get_or_404(siswa.kelas_id)
        
        # Authorization check
        if not hasattr(current_user, 'pegawai') or kelas.wali_kelas_id != current_user.pegawai.id:
            abort(403, description="Anda bukan wali kelas dari kelas ini")

        # Jika tahun_ajaran_id tidak ditentukan, gunakan tahun ajaran dari kelas siswa
        if tahun_ajaran_id:
            tahun_ajaran = TahunAjaran.query.get(tahun_ajaran_id)
        else:
            tahun_ajaran = TahunAjaran.query.get(kelas.tahun_ajaran_id)

        if not tahun_ajaran:
            abort(404, description="Tahun ajaran tidak ditemukan")

        # Extract tahun dari tahun ajaran (format: "2023/2024")
        tahun_parts = tahun_ajaran.tahun_ajaran.split('/')
        if len(tahun_parts) == 2:
            tahun_awal = int(tahun_parts[0])  # 2023
            tahun_akhir = int(tahun_parts[1]) # 2024
        else:
            tahun_awal = int(tahun_parts[0])
            tahun_akhir = tahun_awal + 1

        # Tentukan bulan yang akan ditampilkan berdasarkan semester
        # Tahun Ajaran: Juli tahun_awal - Juni tahun_akhir
        bulan_data = []
        
        if semester_param == 'ganjil':
            # Semester Ganjil: Juli - Desember tahun_awal
            for bulan_num in range(7, 13):
                tahun = tahun_awal
                bulan_key = f"{tahun}-{bulan_num:02d}"
                bulan_data.append((bulan_num, tahun, bulan_key))
            semester_label = "Semester Ganjil"
        elif semester_param == 'genap':
            # Semester Genap: Januari - Juni tahun_akhir  
            for bulan_num in range(1, 7):
                tahun = tahun_akhir
                bulan_key = f"{tahun}-{bulan_num:02d}"
                bulan_data.append((bulan_num, tahun, bulan_key))
            semester_label = "Semester Genap"
        else:
            # Satu Tahun Penuh: Juli tahun_awal - Juni tahun_akhir
            # Juli-Desember tahun_awal
            for bulan_num in range(7, 13):
                tahun = tahun_awal
                bulan_key = f"{tahun}-{bulan_num:02d}"
                bulan_data.append((bulan_num, tahun, bulan_key))
            # Januari-Juni tahun_akhir
            for bulan_num in range(1, 7):
                tahun = tahun_akhir
                bulan_key = f"{tahun}-{bulan_num:02d}"
                bulan_data.append((bulan_num, tahun, bulan_key))
            semester_label = "Tahun Penuh"

        # Data sekolah dan tahun ajaran
        sekolah = Sekolah.query.get(kelas.sekolah_id)
        wali_kelas = Pegawai.query.get(kelas.wali_kelas_id)
        kepala_sekolah = Pegawai.query.get(tahun_ajaran.kepala_sekolah_id) if tahun_ajaran else None

        # Data kecamatan, kabupaten, provinsi
        kecamatan = Kecamatan.query.get(sekolah.kecamatan_id) if sekolah else None
        kabupaten = Kabupaten.query.get(kecamatan.kabupaten_id) if kecamatan else None
        provinsi = Provinsi.query.get(kabupaten.provinsi_id) if kabupaten else None

        # Daftar bulan yang akan ditampilkan
        bulan_list = []
        bulan_names = [
            'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
            'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
        ]
        
        # Track status kebiasaan (apakah ada yang kurang dari 20)
        status_kebiasaan = {
            'bangun_pagi': True,
            'beribadah': True, 
            'berolahraga': True,
            'sehat_dan_lemar': True,
            'belajar': True,
            'bermasyarakat': True,
            'tidur_cepat': True
        }

        for bulan_num, tahun, bulan_key in bulan_data:
            bulan_label = f"{bulan_names[bulan_num - 1]} {tahun}"
            
            # Cari data kebiasaan untuk bulan ini
            kebiasaan = Kebiasaan.query.filter_by(
                siswa_id=siswa.id,
                kelas_id=kelas.id,
                bulan=bulan_key
            ).first()
            
            nilai_data = {}
            if kebiasaan:
                # Hitung nilai jika ada data
                nilai_fields = ['bangun_pagi', 'beribadah', 'berolahraga', 
                               'sehat_dan_lemar', 'belajar', 'bermasyarakat', 'tidur_cepat']
                
                for field in nilai_fields:
                    nilai = getattr(kebiasaan, field, None)
                    nilai_data[field] = nilai
                    
                    # Cek jika ada nilai yang kurang dari 20
                    if nilai is not None and nilai < 20:
                        status_kebiasaan[field] = False
            else:
                # Jika tidak ada data, set semua nilai menjadi None
                nilai_fields = ['bangun_pagi', 'beribadah', 'berolahraga', 
                               'sehat_dan_lemar', 'belajar', 'bermasyarakat', 'tidur_cepat']
                for field in nilai_fields:
                    nilai_data[field] = None
                    # Jika tidak ada data, anggap belum terbiasa
                    status_kebiasaan[field] = False

            bulan_data_item = {
                'nama_bulan': bulan_label,
                'bulan_key': bulan_key,
                'nilai': nilai_data,
                'catatan': getattr(kebiasaan, 'catatan', '') if kebiasaan else ''
            }
            bulan_list.append(bulan_data_item)

        # Tentukan keterangan untuk setiap kebiasaan
        keterangan_kebiasaan = {}
        for field in status_kebiasaan:
            if status_kebiasaan[field]:
                keterangan_kebiasaan[field] = "Terbiasa"
            else:
                keterangan_kebiasaan[field] = "Belum Terbiasa"

        data = {
            'siswa': {
                'id': siswa.id,
                'nama_siswa': siswa.nama_siswa,
                'jenis_kelamin': 'Laki-laki' if siswa.jenis_kelamin == 'L' else 'Perempuan'
            },
            'kelas': {
                'id': kelas.id,
                'nama_kelas': kelas.nama_kelas
            },
            'tahun_ajaran': {
                'id': tahun_ajaran.id,
                'tahun_ajaran': tahun_ajaran.tahun_ajaran,
                'semester': tahun_ajaran.semester
            },
            'sekolah': {
                'nama_sekolah': sekolah.nama_sekolah if sekolah else '',
                'npsn': sekolah.npsn if sekolah else '',
                'kecamatan': kecamatan.nama if kecamatan else '',
                'kabupaten': kabupaten.nama if kabupaten else '',
                'provinsi': provinsi.nama if provinsi else ''
            },
            'kepala_sekolah': {
                'nama': kepala_sekolah.nama if kepala_sekolah else '',
                'nip': kepala_sekolah.nip if kepala_sekolah else ''
            } if kepala_sekolah else {'nama': '', 'nip': ''},
            'wali_kelas': {
                'nama': wali_kelas.nama if wali_kelas else '',
                'nip': wali_kelas.nip if wali_kelas else ''
            },
            'bulan_list': bulan_list,
            'status_kebiasaan': status_kebiasaan,
            'keterangan_kebiasaan': keterangan_kebiasaan,
            'semester': semester_label,
            'tanggal_cetak': datetime.now().strftime('%d %B %Y %H:%M')
        }

        return render_template("laporan/laporan_penilaian_siswa.html", data=data)

    except Exception as e:
        print(f"ERROR LAPORAN PENILAIAN SISWA: {e}")
        traceback.print_exc()
        return render_template("error.html", 
                            message=f"Error generating penilaian siswa report: {str(e)}"), 500