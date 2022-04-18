from app import app, db
from app.models import User, Team, Defence, Match, Attack


@app.shell_context_processor
def make_shell_context():
    return {
        "db": db,
        "User": User,
        "Team": Team,
        "Defence": Defence,
        "Match": Match,
        "Attack": Attack,
    }
