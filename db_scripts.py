from app import db, app
from app.models import Attack, Defence, Match, Team, User


def flush_matches():
    for a in Attack.query.all():
        db.session.delete(a)
    db.session.commit()
    for m in Match.query.all():
        db.session.delete(m)
    db.session.commit()
    app.config["ROUND"] = 1


def flush_whole_db():
    flush_matches()
    for d in Defence.query.all():
        db.session.delete(d)
    db.session.commit()
    for t in Team.query.all():
        db.session.delete(t)
    db.session.commit()
    for u in User.query.all():
        db.session.delete(u)
    db.session.commit()


def populate_test_users():
    flush_whole_db()
    for i, u_name in enumerate(
        [
            "alice",
            "bob",
            "charlie",
            "dimitri",
            "eugene",
            "francois",
            "gerald",
            "hector",
            "ignatus",
            "john",
        ]
    ):
        u = User(
            username=u_name,
            email=app.config["MAIL_TEST_RECEIVER_FORMAT"].format(u_name),
            sciper=1001 + i,
        )
        db.session.add(u)
        db.session.commit()
        u.set_password("admin")

    admin = User(
        username="admin",
        email=app.config["MAIL_TEST_RECEIVER_FORMAT"].format("admin"),
        sciper=1000,
        is_admin=True,
    )
    db.session.add(admin)
    db.session.commit()
    admin.set_password("admin")

    for i, t_name in enumerate(["al-bo", "cha-di", "eu-fra", "ger-hec", "ign-joh"]):
        db.session.add(
            Team(team_name=t_name, member1_id=2 * i + 1, member2_id=2 * i + 2)
        )
    db.session.commit()
