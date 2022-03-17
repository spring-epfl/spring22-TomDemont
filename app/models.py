from datetime import datetime
from app import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(96), index=True, unique=True)
    password_hash = db.Column(db.String(64))
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

    def __repr__(self):
        return "<User {} (id: {})>".format(self.username, self.id)


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
