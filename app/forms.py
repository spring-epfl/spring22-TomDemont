import os
from zipfile import ZipFile

import pandas as pd
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import BooleanField, IntegerField, PasswordField, StringField, SubmitField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    NumberRange,
    ValidationError,
)

from app import app
from app.models import User


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Sign In")


class RegistrationForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    password2 = PasswordField(
        "Repeat Password", validators=[DataRequired(), EqualTo("password")]
    )
    sciper = IntegerField(
        "Sciper",
        validators=[
            DataRequired(),
            NumberRange(100000, 999999, "Please enter a valid Sciper"),
        ],
    )
    submit = SubmitField("Register")

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError("Please use a different username.")
        if not username.data.isascii():
            raise ValidationError(
                "Please use a username containing only ASCII characters."
            )

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError("Please use a different email address.")


class DefenceUpload(FlaskForm):
    file = FileField(
        "CSV Defence Trace",
        validators=[
            FileRequired(),
            FileAllowed(
                app.config["UPLOAD_EXTENSIONS"],
                message="Please, see upload file format instructions",
            ),
        ],
    )
    submit = SubmitField("Register")

    def validate_file(self, file):
        filename = file.data.filename
        if filename == "":
            raise ValidationError("No file uploaded")
        with ZipFile(file.data.stream, "r") as zip:
            name_list = zip.namelist()
            if len(name_list) != 1:
                print(name_list)
                raise ValidationError(
                    "Your upload does not contain the correct files. Check your hidden files"
                )
            file_ext = os.path.splitext(name_list[0])[1]
            if file_ext not in app.config["DATASET_EXTENSIONS"]:
                raise ValidationError(
                    "Your upload should contain a dataset in the right file format"
                )
        file.data.stream.seek(0)
