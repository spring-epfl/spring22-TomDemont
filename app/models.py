"""Defines data model with SQLAlchemy ORM"""


from datetime import datetime
from math import log10
from typing import Optional, Union

from flask_login import UserMixin
from flask_sqlalchemy import Pagination
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Query
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login


class User(UserMixin, db.Model):
    """User of the application. Used for defining access control with UserMixin class. This user is expected to be mapped to one student."""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(96), index=True, unique=True)
    password_hash = db.Column(db.String(102))
    sciper = db.Column(db.Integer, unique=True)
    is_admin = db.Column(db.Boolean, default=False)

    def team(self) -> Optional["Team"]:
        """Gives the Team object this user is member of or None if they're in no team."""
        return (
            db.session.query(Team)
            .filter(or_(Team.member1_id == self.id, Team.member2_id == self.id))
            .first()
        )

    def has_team(self) -> bool:
        """Returns whether this user is member of a team"""
        return self.team() is not None

    def set_password(self, password: str) -> None:
        """Sets the password for this user by storing its salted hash. Does not push to db !"""
        # basically hashes with random salt using PBKDF2, see https://werkzeug.palletsprojects.com/en/2.0.x/utils/#module-werkzeug.security
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Check if password matches this user stored password salted hash"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return "<User {} (id: {})>".format(self.username, self.id)


# Required by flask-login module
@login.user_loader
def load_user(id: int) -> User:
    return User.query.get(int(id))


class Team(db.Model):
    """Team composed of 2 users. Basis for Attack/Defence system. Most of the application is working around these actors."""

    id = db.Column(db.Integer, primary_key=True)
    team_name = db.Column(db.String(64), index=True, unique=True)
    member1_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True)
    member2_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True)

    # reference to the defences published by this team
    defences = db.relationship(
        "Defence",
        backref="defender_team",
        foreign_keys="Defence.defender_team_id",
        lazy="dynamic",
    )

    # reference to the matches in which this team has a defence role
    defence_matches = db.relationship(
        "Match",
        backref="defender_team",
        foreign_keys="Match.defender_team_id",
        lazy="dynamic",
    )

    # reference to the matches in which this team has an attacker role
    attack_matches = db.relationship(
        "Match",
        backref="attacker_team",
        foreign_keys="Match.attacker_team_id",
        lazy="dynamic",
    )

    def members(self) -> tuple[Optional[User], Optional[User]]:
        """Returns the tuple containing the users this team is composed of (potentially None tuple members if the team is not full)."""
        return (
            db.session.query(User).filter(User.id == self.member1_id).first(),
            db.session.query(User).filter(User.id == self.member2_id).first(),
        )

    def has_admin(self) -> bool:
        """Returns whether this team has an admin member"""
        mem1, mem2 = self.members()
        return (mem1 and mem1.is_admin) or (mem2 and mem2.is_admin)

    def is_full(self) -> bool:
        """Returns whether this team has all its members"""
        return self.member1_id and self.member2_id

    def attacks(self) -> Query:
        """Returns a query for all the attacks this team's ever made."""
        self_attacks = (
            db.session.query(Match.id)
            .filter(Match.attacker_team_id == self.id)
            .subquery()
        )
        return db.session.query(Attack).join(
            self_attacks, self_attacks.c.id == Attack.match_id
        )

    def teams_to_attack_in_round(self, round: int) -> Query:
        """Returns a query for all the teams this team should attack during the round"""
        attack_matches_sub = self.attack_matches.filter(Match.round == round).subquery()
        return (
            db.session.query(Team)
            .join(attack_matches_sub, attack_matches_sub.c.defender_team_id == Team.id)
            .distinct()
        )

    def team_id_to_attack_in_round(self, round: int) -> list[int]:
        """Returns the list of team_id this team should attack during the round"""
        teams_to_attack_subq = self.teams_to_attack_in_round(round=round).subquery()
        tuple_team_id_to_attack = db.session.query(teams_to_attack_subq.c.id).all()
        # we must unpack the returned columns to have only a list[int]
        return [t[0] for t in tuple_team_id_to_attack]

    def defence_matches_in_round(self, round) -> Query:
        """Returns a query for this team's matches in which this team is defender in the round"""
        return self.defence_matches.filter(Match.round == round)

    def get_match_against(self, round, other_team_id) -> Query:
        """Returns a query for the matches in which this team attacks the team with id other_team_id during the round"""
        return self.attack_matches.filter(
            and_(Match.round == round, Match.defender_team_id == other_team_id)
        )

    def utility_score(self, round) -> Union[float, str]:
        """Returns either the utility score of this team for Defence in the round, or the error message to be displayed. The considered defence is the most recent one of this round. The highest the score, the least utility consuming the defence is."""
        defence = (
            self.defences.filter(Defence.round == round)
            .order_by(Defence.timestamp.desc())
            .first()
        )
        return (
            defence.utility.aggregated_score() if defence else "No defence uploaded yet"
        )

    def attack_performance(self, round) -> Union[float, str]:
        """Returns either the attack performance score of this team for Attack in the round, or the error message to be displayed. For each match in the round, only the latest attack is considered for the computation. The returned result is the average of attack performance if all assigned attacks have been performed, the error message string is returned otherwise. The highest score, the better the attack."""
        atk_matches_in_round = self.attack_matches.filter(
            Match.round == round
        ).subquery()
        # query holding the attacks performed during this rounds
        self_atk_subq = (
            self.attacks()
            .join(atk_matches_in_round, Attack.match_id == atk_matches_in_round.c.id)
            .subquery()
        )
        # query holding the most recent attack for each match along with the timestamp
        self_most_recent_atks_rows = (
            db.session.query(self_atk_subq, func.max(self_atk_subq.c.timestamp))
            .group_by(self_atk_subq.c.match_id)
            .subquery()
        )
        # all the Attack objects of the most recent attack for each performed match in this round
        self_most_recent_atks = (
            db.session.query(Attack)
            .join(
                self_most_recent_atks_rows, Attack.id == self_most_recent_atks_rows.c.id
            )
            .all()
        )
        return (
            sum(
                [attack.results.aggregated_result() for attack in self_most_recent_atks]
            )
            / len(self_most_recent_atks)
            if len(self_most_recent_atks) == Match.nb_matches_in_round(round, self.id)
            else "Some attacks remain to do"
        )

    def total_score(self, round) -> Union[float, str]:
        """Returns either the aggregated performance score of this team in the round, or the error message to be displayed. The total score is the product of the utility and attack performance metrics. We can see it as (accuracy*roc_auc_score)/(time_consumption*bandwidth_consumption). If not all attacks are done, the attack perf score is set to 1.0 (this should be less than a random classifier's performance with the current settings and for secretstroll application)"""
        atk_perf = self.attack_performance(round)
        util_score = self.utility_score(round)
        if isinstance(util_score, float):
            return (atk_perf if isinstance(atk_perf, float) else 1.0) * util_score
        else:
            return "Cannot compute full score yet"

    def __repr__(self) -> str:
        return "<Team {} (id: {})>".format(self.team_name, self.id)


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
        return "<Utility: \nmed_in_volume: {:.0f} bytes,\nmed_out_volume: {:.0f} bytes,\nmed_time: {:.3f} seconds>".format(
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

    def aggregated_score(self) -> float:
        """Returns an aggregated value for the utility metric. Magic numbers 8*8 for having nice score values. We take care of taking absolute value as the in_volume is represented by a negative number of bytes"""
        return (8 * 8) / (
            log10(abs(self.med_in_volume * self.med_out_volume * self.med_time))
        )


class Defence(db.Model):
    """Representation a team's defence."""

    id = db.Column(db.Integer, primary_key=True)
    defender_team_id = db.Column(db.Integer, db.ForeignKey("team.id"))
    utility = db.Column(db.PickleType)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    round = db.Column(db.Integer, index=True)

    def __repr__(self) -> str:
        return "<Defence of {} (id: {})>".format(self.defender_team, self.id)


class Match(db.Model):
    """Representation of a a match between two teams. This Match can conceptually be repeated many times (the attacker can attack many times) and there should be unique triplet (defender_team, attacker_team, round)."""

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

    # reference to the attacks performed for this match
    attacks = db.relationship(
        "Attack",
        backref="match",
        foreign_keys="Attack.match_id",
        lazy="dynamic",
    )

    @staticmethod
    def nb_matches_in_round(round: int, attacker_team_id: int) -> int:
        """Gives the number of matches attributed during this round to a team with the attacker role."""
        return (
            db.session.query(Match)
            .filter(
                and_(Match.round == round, Match.attacker_team_id == attacker_team_id)
            )
            .count()
        )

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

    def match_done(self) -> bool:
        """Returns whether the attacker already made an attack or not for this match"""
        return db.session.query(Attack).filter(Attack.match_id == self.id).count() > 0

    def __repr__(self) -> str:
        return "<Match {} defends against {} (id: {})>".format(
            self.defender_team, self.attacker_team, self.id
        )


class AttackResult:
    """Stores the attack performance metrics kept to evaluate an attack"""

    def __init__(self, accuracy, roc_auc_score) -> None:
        self.accuracy = accuracy
        self.roc_auc_score = roc_auc_score

    def __repr__(self) -> str:
        return "<AttackResult - accuracy: {:.4f}, roc_auc_score: {:.5f}>".format(
            self.accuracy, self.roc_auc_score
        )

    def to_dict(self) -> dict:
        return {"accuracy": self.accuracy, "roc_auc_score": self.roc_auc_score}

    def aggregated_result(self) -> float:
        """Returns an aggregated value for the attack performance metric. Magic number 1000 for displaying nice score values in the context of Secret Race Strolling"""
        return 1000 * self.roc_auc_score * self.accuracy


class Attack(db.Model):
    """Representation of an attack made for a match by an attacker"""

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("match.id"))
    results = db.Column(db.PickleType)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    def __repr__(self) -> str:
        return "<Attack - for match against {}, scored: {}".format(
            self.match.defender_team, self.results
        )
