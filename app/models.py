from datetime import datetime
from typing import Any, Optional

from flask import url_for
from flask_login import UserMixin
from flask_sqlalchemy import Pagination
from sqlalchemy import func, or_
from sqlalchemy.orm import Query
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login


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

    defence_matches = db.relationship(
        "Match",
        backref="defender_team",
        foreign_keys="Match.defender_team_id",
        lazy="dynamic",
    )

    attack_matches = db.relationship(
        "Match",
        backref="attacker_team",
        foreign_keys="Match.attacker_team_id",
        lazy="dynamic",
    )

    def members(self) -> tuple[Optional[Any], Optional[Any]]:
        return (
            db.session.query(User).filter(User.id == self.member1_id).first(),
            db.session.query(User).filter(User.id == self.member2_id).first(),
        )

    def has_admin(self) -> bool:
        mem1, mem2 = self.members()
        return (mem1 is not None and mem1.is_admin) or (
            mem2 is not None and mem2.is_admin
        )

    def is_full(self) -> bool:
        return self.member1_id is not None and self.member2_id is not None

    def attacks(self) -> Query:
        self_attacks = (
            db.session.query(Match.id)
            .filter(Match.attacker_team_id == self.id)
            .subquery()
        )
        return db.session.query(Attack).join(
            self_attacks, self_attacks.c.id == Attack.match_id
        )

    def teams_to_attack_in_round(self, round: int) -> Query:
        attack_matches_sub = self.attack_matches.filter(Match.round == round).subquery()
        return (
            db.session.query(Team)
            .join(attack_matches_sub, attack_matches_sub.c.defender_team_id == Team.id)
            .distinct()
        )

    def team_id_to_attack_in_round(self, round: int) -> list[int]:
        teams_to_attack_subq = self.teams_to_attack_in_round(round=round).subquery()
        tuple_team_id_to_attack = db.session.query(teams_to_attack_subq.c.id).all()
        return [t[0] for t in tuple_team_id_to_attack]

    def defence_matches_in_round(self, round) -> Query:
        return self.defence_matches.filter(Match.round == round)

    def __repr__(self) -> str:
        return "<Team {} (id: {})>".format(self.team_name, self.id)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(96), index=True, unique=True)
    password_hash = db.Column(db.String(102))
    sciper = db.Column(db.Integer, unique=True)
    is_admin = db.Column(db.Boolean, default=False)

    def team(self) -> Optional[Team]:
        return (
            db.session.query(Team)
            .filter(or_(Team.member1_id == self.id, Team.member2_id == self.id))
            .first()
        )

    def has_team(self) -> bool:
        return self.team() is not None

    def has_match(self) -> bool:
        team = self.team()
        return (
            self.has_team()
            and team.defence_matches.count() > 0
            and team.defence_matches.count() > 0
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


class Utility:
    """Stores the utility metrics kept to evaluate a defence"""

    def __init__(
        self,
        max_in_volume: int,
        mean_in_volume: float,
        med_in_volume: float,
        max_out_volume: int,
        mean_out_volume: float,
        med_out_volume: float,
        max_time: float,
        mean_time: float,
        med_time: float,
    ) -> None:
        self.max_in_volume = max_in_volume
        self.mean_in_volume = mean_in_volume
        self.med_in_volume = med_in_volume
        self.max_out_volume = max_out_volume
        self.mean_out_volume = mean_out_volume
        self.med_out_volume = med_out_volume
        self.max_time = max_time
        self.mean_time = mean_time
        self.med_time = med_time

    def __repr__(self):
        return "<Utility: \nmed_in_volume: {:.1f} bytes\nmed_out_volume: {:.1f} bytes\nmed_time: {:.3f} seconds>".format(
            abs(self.med_in_volume), self.med_out_volume, self.med_time
        )

    def to_dict(self) -> dict:
        return {
            "max_in_volume": self.max_in_volume,
            "mean_in_volume": self.mean_in_volume,
            "med_in_volume": self.med_in_volume,
            "max_out_volume": self.max_out_volume,
            "mean_out_volume": self.mean_out_volume,
            "med_out_volume": self.med_out_volume,
            "max_time": self.max_time,
            "mean_time": self.mean_time,
            "med_time": self.med_time,
        }


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

    def match_done(self) -> bool:
        """Returns whether the attacker already made an attack or not for this match"""
        return db.session.query(Attack).filter(Attack.match_id == self.id).count() > 0

    @staticmethod
    def paginate_and_itemize_match_query(
        matches: Query, page: int, matches_per_page: int, current_user_team: Team
    ) -> tuple[Pagination, list[dict]]:
        """Produces a pagination and matches items to prepare input for a _match.html template
        Args:
            - matches: a query object on the Match table (holds the matches that will be displayed)
            - page: the page index for the pagination object
            - matches_per_page: the number matches to display in the pagination
            - current_user_team: the user we want to make the display adapted for
        Returns:
            Pagination object and the list of itemized Match objects for the displaying on _match.html template"""
        matches_sub = matches.subquery()
        # we keep all the indexes of the matches that were already attacked at least once
        attacks_done = (
            db.session.query(matches_sub.c.id)
            .join(Attack, Attack.match_id == matches_sub.c.id)
            .all()
        )
        # we flatten the returned object
        attacks_done = [attack_done[0] for attack_done in attacks_done]

        paginated = matches.paginate(page, matches_per_page)
        matches_items = paginated.items
        for m in matches_items:
            # takes the paginated items and appends other useful data for displaying
            m.match_done = m.id in attacks_done
        return paginated, matches_items

    def __repr__(self) -> str:
        return "<Match {} defends against {} (id: {})>".format(
            self.defender_team, self.attacker_team, self.id
        )


class AttackResult:
    def __init__(self, accuracy, false_positive) -> None:
        self.accuracy = accuracy
        self.false_positive = false_positive

    def __repr__(self) -> str:
        return "<AttackResult - accuracy: {}, false_positive: {}>".format(
            self.accuracy, self.false_positive
        )

    def to_dict(self) -> dict:
        return {"accuracy": self.accuracy, "false_positive": self.false_positive}


class Attack(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("match.id"))
    results = db.Column(db.PickleType)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    def __repr__(self) -> str:
        return "<Attack - for match {} (id: {})".format(self.match, self.id)
