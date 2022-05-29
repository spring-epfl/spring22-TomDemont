import os
from zipfile import ZipFile

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import (
    BooleanField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    NumberRange,
    ValidationError,
)

from app import app
from app.models import Team, User


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=64)])
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
    team_select = SelectField(
        "Team selection", validators=[DataRequired()], default="New team"
    )
    new_team_name = StringField(
        "New team name",
        render_kw={"placeholder": "Fill only if you want to create a new team"},
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

    def validate_team_select(self, team_select):
        team = Team.query.filter_by(team_name=team_select.data).first()
        if team_select.data != "New team" and team is not None and team.is_full():
            raise ValidationError("The team you try to join is already full")

    def validate_new_team_name(self, new_team_name):
        if new_team_name == "New team":
            raise ValidationError("You cannot give this name to your team")

        if self.team_select.data != "New team" and new_team_name.data != "":
            raise ValidationError("Fill only if you want to create a new team")

        if (
            (self.team_select.data == "New team" and new_team_name.data == "")
            or not new_team_name.data.isascii()
            or new_team_name.data.isspace()
        ):
            raise ValidationError(
                "You need to provide a non-empty, ascii characters only team name"
            )
        team = Team.query.filter_by(team_name=new_team_name.data).first()
        if team is not None:
            raise ValidationError(
                "The team you try to join is already exists, select it it the field"
            )


def validate_uploaded_dataset(file):
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
        if file_ext[1:] not in app.config["DATASET_EXTENSIONS"]:
            raise ValidationError(
                "Your upload should contain a dataset in the right file format"
            )
    file.data.stream.seek(0)


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
    submit = SubmitField("Upload")

    def validate_file(self, file):
        validate_uploaded_dataset(file)


class AttackUpload(FlaskForm):
    file = FileField(
        "CSV Attack Classification",
        validators=[
            FileRequired(),
            FileAllowed(
                app.config["UPLOAD_EXTENSIONS"],
                message="Please, see upload file format instructions",
            ),
        ],
    )
    submit = SubmitField("Upload")

    def validate_file(self, file):
        validate_uploaded_dataset(file)
