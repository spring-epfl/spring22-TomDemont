from datetime import datetime
from typing import Any

from flask_login import UserMixin
from sqlalchemy import func, or_
from sqlalchemy.orm import Query
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(96), index=True, unique=True)
    password_hash = db.Column(db.String(102))
    sciper = db.Column(db.Integer, unique=True)

    def team(self) -> Any:
        return (
            db.session.query(Team)
            .filter(or_(Team.member1_id == self.id, Team.member2_id == self.id))
            .first()
        )

    def set_password(self, password: str) -> None:
        # basically hashes with random salt using PBKDF2, see https://werkzeug.palletsprojects.com/en/2.0.x/utils/#module-werkzeug.security
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return "<User {} (id: {})>".format(self.username, self.id)


@login.user_loader
def load_user(id: int) -> User:
    return User.query.get(int(id))


class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_name = db.Column(db.String(64), index=True, unique=True)
    member1_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True)
    member2_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True)

    defences = db.relationship(
        "Defence",
        backref="defender_team",
        foreign_keys="Defence.defender_team_id",
        lazy="dynamic",
    )

    defence_matchs = db.relationship(
        "Match",
        backref="defender_team",
        foreign_keys="Match.defender_team_id",
        lazy="dynamic",
    )

    attack_matchs = db.relationship(
        "Match",
        backref="attacker_team",
        foreign_keys="Match.attacker_team_id",
        lazy="dynamic",
    )

    def members(self) -> tuple[Any, Any]:
        return (
            db.session.query(User).filter(User.id == self.member1_id).first(),
            db.session.query(User).filter(User.id == self.member2_id).first(),
        )

    def attacks(self) -> Query:
        self_attacks = (
            db.session.query(Match.id)
            .filter(Match.attacker_team_id == self.id)
            .subquery()
        )
        return db.session.query(Attack).join(
            self_attacks, self_attacks.c.id == Attack.match_id
        )

    def __repr__(self) -> str:
        return "<Team {} (id: {})>".format(self.team_name, self.id)


class Utility:
    """Stores the utility metrics kept to evaluate a defence"""

    def __init__(self, data_volume: int, time: float) -> None:
        self.data_volume = data_volume
        self.time = time

    def __repr__(self):
        return "<Utility - volume: {}, time: {}>".format(self.data_volume, self.time)


class Defence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    defender_team_id = db.Column(db.Integer, db.ForeignKey("team.id"))
    utility = db.Column(db.PickleType)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    round = db.Column(db.Integer, index=True)

    def __repr__(self) -> str:
        return "<Defence of {} (id: {})>".format(self.defender_team, self.id)


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    defender_team_id = db.Column(db.Integer, db.ForeignKey("team.id"))
    attacker_team_id = db.Column(db.Integer, db.ForeignKey("team.id"))
    round = db.Column(db.Integer, index=True)
    __table_args__ = (
        db.UniqueConstraint(
            "defender_team_id",
            "attacker_team_id",
            "round",
            name="_match_pair_once_per_round",
        ),
    )

    attacks = db.relationship(
        "Attack",
        backref="match",
        foreign_keys="Attack.match_id",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return "<Match {} defends against {} (id: {})>".format(
            self.defender_team, self.attacker_team, self.id
        )


class AttackResult:
    def __init__(self, accuracy, false_positive) -> None:
        self.accuracy = accuracy
        self.false_positive = false_positive

    def __repr__(self) -> str:
        return "<AttackResult - accuracy: {}, flase_positive: {}>".format(
            self.accuracy, self.false_positive
        )


class Attack(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("match.id"))
    results = db.Column(db.PickleType)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    def __repr__(self) -> str:
        return "<Attack - for match {} (id: {})".format(self.match, self.id)
