import unittest
from app import app, db
from app.models import User, MatchResult


class UserModelCase(unittest.TestCase):
    def setUp(self):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_password_hashing(self):
        u = User(username="robb")
        u.set_password("hoho")
        self.assertFalse(u.check_password("beep"))
        self.assertTrue(u.check_password("hoho"))

    def test_match(self):
        # sets up 2 users
        u1 = User(username="john", email="john@example.com")
        u2 = User(username="susan", email="susan@example.com")
        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()
        self.assertEqual(u1.attacks.all(), [])
        self.assertEqual(u1.defenses.all(), [])

        # creates a match with the object init
        m = MatchResult(attacker_id=u1.id, defender_id=u2.id, attacker_score=5.32890)
        db.session.add(m)
        db.session.commit()
        self.assertEqual(u1.attacks.count(), 1)
        self.assertEqual(u1.attacks.first().defender.username, "susan")
        self.assertEqual(u2.defenses.count(), 1)
        self.assertEqual(u2.defenses.first().attacker.username, "john")

        db.session.delete(m)
        db.session.commit()

        # creates another match with the attacked function
        u2.attacked(u1, 9.567)
        self.assertEqual(u2.attacks.count(), 1)
        self.assertEqual(u2.attacks.first().defender.username, "john")
        self.assertEqual(u1.defenses.count(), 1)
        self.assertEqual(u1.defenses.first().attacker.username, "susan")

    def test_best_matches(self):
        self.maxDiff = None
        # creates 4 users
        u1 = User(username="john", email="john@example.com")
        u2 = User(username="susan", email="susan@example.com")
        u3 = User(username="boby", email="boby@example.com")
        u4 = User(username="tomy", email="tomy@example.com")
        db.session.add_all([u1, u2, u3, u4])
        db.session.commit()

        # creates the attacks
        m1 = u1.attacked(u2, 1.2)
        m2 = u1.attacked(u2, 3.4)
        m3 = u2.attacked(u1, 1.6)
        m4 = u3.attacked(u4, 0.6)
        m5 = u3.attacked(u4, 10.2)
        m6 = u3.attacked(u4, 1.5)

        true_bests = [m5, m3, m2]
        bests_from_func = MatchResult.get_best_matches().all()
        self.assertEqual(bests_from_func, true_bests)
        self.assertEqual(u1.get_best_attacks().all(), [m2])
        self.assertEqual(u3.get_best_attacks().all(), [m5])


if __name__ == "__main__":
    unittest.main(verbosity=2)
