from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange

class RequestResetForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Kirim Link Reset")

class ResetPasswordForm(FlaskForm):
    password = PasswordField("Password Baru", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField("Ulangi Password", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Ubah Password")

# ========== FORM UNTUK AKTIVASI SEKOLAH ==========
class AktivasiSekolahForm(FlaskForm):
    """Form untuk aktivasi dan perpanjangan masa aktif sekolah"""
    masa_berlaku = SelectField(
        'Masa Berlaku',
        choices=[
            (365, '1 Tahun'),
            (730, '2 Tahun'),
            (180, '6 Bulan'),
            (90, '3 Bulan')
        ],
        default=365,
        coerce=int,
        validators=[DataRequired()]
    )
    submit = SubmitField('Aktivasi Sekolah')