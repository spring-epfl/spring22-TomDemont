from app import login
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from flask_login import UserMixin
from sqlalchemy import func


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

    def get_best_attacks(self):
        """Returns only the best match of matchings with this user as attacker. Namely, it discards tuples that have the same attacker (being self) and defender but have a lower scores than the others"""
        best_match_and_score_for_self = (
            db.session.query(
                MatchResult.id,
                func.max(MatchResult.attacker_score),
            )
            .filter(MatchResult.attacker_id == self.id)
            .group_by(MatchResult.attacker_id, MatchResult.defender_id)
            .order_by(MatchResult.timestamp.desc())
            .subquery()
        )
        # we remove the second column that was used for aggregation
        return db.session.query(MatchResult).join(
            best_match_and_score_for_self,
            MatchResult.id == best_match_and_score_for_self.c.id,
        )

    # we don't create the "defended" method as we in any case have both users in scope
    def attacked(self, other_user, score=0.0):
        """Records the attack of self on another user and self's score for this attack. Returns the attack object added to database"""
        if isinstance(other_user, User) and other_user.id != self.id:
            # we ensure users cannot attack themselves
            m = MatchResult(
                attacker_id=self.id, defender_id=other_user.id, attacker_score=score
            )
            db.session.add(m)
            db.session.commit()
            return m
        else:
            raise TypeError("Users can only attack other users")

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

    @staticmethod
    def get_best_matches():
        """Returns only the best match of every matching. Namely, it discards tuples that have the same attacker and defender but have a lower scores than the others"""
        best_match_and_score = (
            db.session.query(
                MatchResult.id,
                func.max(MatchResult.attacker_score),
            )
            .group_by(MatchResult.attacker_id, MatchResult.defender_id)
            .order_by(MatchResult.timestamp.desc())
            .subquery()
        )
        # we remove the second column that was used for aggregation
        return db.session.query(MatchResult).join(
            best_match_and_score,
            MatchResult.id == best_match_and_score.c.id,
        )

    def __repr__(self):
        return "<Match on {} (id: {}) - {} attacked {} and scored {}>".format(
            self.timestamp, self.id, self.attacker, self.defender, self.attacker_score
        )
