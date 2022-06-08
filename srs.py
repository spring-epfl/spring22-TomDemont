from app import app, db
from app.models import Attack, Defence, Match, Team, User
from app.tasks_attack import treat_uploaded_attack
from app.tasks_defence import treat_uploaded_defence
from app.tasks_control import send_mail
from db_scripts import populate_test_users


@app.shell_context_processor
def make_shell_context():
    return {
        "db": db,
        "User": User,
        "Team": Team,
        "Defence": Defence,
        "Match": Match,
        "Attack": Attack,
        "treat_uploaded_defence": treat_uploaded_defence,
        "treat_uploaded_attack": treat_uploaded_attack,
        "send_mail": send_mail,
        "populate_test_users": populate_test_users,
    }
