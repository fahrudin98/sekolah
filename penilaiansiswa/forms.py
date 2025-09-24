from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length

class RequestResetForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Kirim Link Reset")

class ResetPasswordForm(FlaskForm):
    password = PasswordField("Password Baru", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField("Ulangi Password", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Ubah Password")