from app import app, db
from app.models import Attack, Defence, Match, Team, User
from app.tasks import (
    send_mail,
    split_train_test_set,
    treat_uploaded_defence,
    verify_dataframe,
)


@app.shell_context_processor
def make_shell_context():
    return {
        "db": db,
        "User": User,
        "Team": Team,
        "Defence": Defence,
        "Match": Match,
        "Attack": Attack,
        "verify_dataframe": verify_dataframe,
        "treat_uploaded_defence": treat_uploaded_defence,
        "send_mail": send_mail,
        "split_train_test_set": split_train_test_set,
    }
