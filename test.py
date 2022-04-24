import unittest

from app import app, db
from app.models import *


class UserModelCase(unittest.TestCase):
    def setUp(self):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_password_hashing(self):
        u = User(username="robb", sciper=123456)
        u.set_password("hoho")
        self.assertFalse(u.check_password("beep"))
        self.assertTrue(u.check_password("hoho"))

    def test_matches(self):
        # Setup users
        u1 = User(username="john", email="john@example.com")
        u2 = User(username="susan", email="susan@example.com")
        u3 = User(username="paul", email="paul@example.com")
        u4 = User(username="emilie", email="emilie@example.com")
        db.session.add_all([u1, u2, u3, u4])
        db.session.commit()

        # Setup teams
        t1 = Team(team_name="beepboop", member1_id=u1.id, member2_id=u2.id)
        t2 = Team(team_name="diffie", member1_id=u3.id, member2_id=u4.id)
        db.session.add_all([t1, t2])
        db.session.commit()

        self.assertEqual(u1.team(), t1)
        self.assertEqual(t2.members(), (u3, u4))

        # Setup defences
        d1 = Defence(defender_team_id=t1.id)
        d2 = Defence(defender_team_id=t2.id)

        db.session.add_all([d1, d2])
        db.session.commit()

        self.assertEqual(d1.defender_team, t1)
        self.assertEqual(t2.defences.all(), [d2])

        # Create matches
        m1 = Match(defender_team_id=t1.id, attacker_team_id=t2.id)
        m2 = Match(defender_team_id=t2.id, attacker_team_id=t1.id)

        db.session.add_all([m1, m2])
        db.session.commit()

        self.assertEqual(t1.defence_matches.all(), [m1])
        self.assertEqual(t2.attack_matches.all(), [m1])

        # Create attacks
        a1 = Attack(match_id=m1.id)
        a2 = Attack(match_id=m2.id)

        db.session.add_all([a1, a2])
        db.session.commit()

        self.assertEqual(m1.attacks.all(), [a1])
        self.assertEqual(t1.attacks().all(), [a2])


if __name__ == "__main__":
    unittest.main(verbosity=2)
