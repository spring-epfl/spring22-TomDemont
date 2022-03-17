from app import login
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from flask_login import UserMixin


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(96), index=True, unique=True)
    password_hash = db.Column(db.String(102))
    attacks = db.relationship(
        "MatchResult",
        backref="attacker",
        foreign_keys="MatchResult.attacker_id",
        lazy="dynamic",
    )
    defenses = db.relationship(
        "MatchResult",
        backref="defender",
        foreign_keys="MatchResult.defender_id",
        lazy="dynamic",
    )

    def set_password(self, password):
        # basically hashes with random salt using PBKDF2, see https://werkzeug.palletsprojects.com/en/2.0.x/utils/#module-werkzeug.security
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return "<User {} (id: {})>".format(self.username, self.id)


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class MatchResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    attacker_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    defender_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    attacker_score = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return "<Match on {} (id: {}) - {} attacked {}>".format(
            self.timestamp, self.id, self.attacker, self.defender
        )
