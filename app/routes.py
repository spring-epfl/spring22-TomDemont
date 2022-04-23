from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import (
    current_user,
    fresh_login_required,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.urls import url_parse

from app import app, db
from app.forms import LoginForm, RegistrationForm
from app.models import Match, Team, User

from random import shuffle


@app.route("/")
@app.route("/index")
@login_required
def index():
    page = request.args.get("page", 1, type=int)
    matches = (
        db.session.query(Match)
        .order_by(Match.round.desc())
        .paginate(page, app.config["MATCHS_PER_PAGE"], False)
    )
    next_url = url_for("index", page=matches.next_num) if matches.has_next else None
    prev_url = url_for("index", page=matches.prev_num) if matches.has_prev else None
    return render_template(
        "index.html",
        title="Home",
        matches=matches.items,
        next_url=next_url,
        prev_url=prev_url,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, is_admin=False)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Congratulations, you are now a registered user!")
        return redirect(url_for("login"))
    return render_template("register.html", title="Register", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password")
            return redirect(url_for("login"))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get("next")
        # check if no next page specified or next page is out of domain
        if not next_page or url_parse(next_page).netloc != "":
            next_page = url_for("index")
        return redirect(next_page)
    return render_template("login.html", title="Sign In", form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/generate_matchs/<round>")
@fresh_login_required
def generate_matchs(round):
    if not current_user.is_admin:
        # Only the admins should be able to generate the matchs
        abort(403)
    else:
        if round == "usage" or int(round) == 0:
            # those special cases are treated as query for the "usages" of the function
            return render_template("generate_matchs.html")
        round = int(round)
        if round < 0:
            flash("Cannot have a negative round number")
            abort(400)
        if db.session.query(Match.round).filter(Match.round == round).count() > 0:
            flash("Already generated this round")
            abort(400)
        if (
            round > 1
            and db.session.query(Match.round).filter(Match.round == round - 1).count()
            == 0
        ):
            flash("You have not generated the matchs for round {}".format(round - 1))
            abort(400)
        # we only keep teams of participants non-admin
        all_teams = list(filter(lambda x: not x.has_admin(), Team.query.all()))
        nb_teams = len(all_teams)
        # we make sure not to have more than nb_teams-1 matchs per team to avoid self-matching
        matchs_per_team = min([app.config["MATCHS_PER_TEAM"], nb_teams - 1])
        # we shuffle the whole teams list to have random matchs
        shuffle(all_teams, k=nb_teams)
        for team_index in range(nb_teams):
            for match_index in range(1, matchs_per_team + 1):
                # we circle through the shuffled participants list
                # every team is matched to adversaries in indexes after theirs
                # it makes sure they have random adversaries that are not themselves
                m = Match(
                    attacker_team_id=all_teams[team_index].id,
                    defender_team_id=all_teams[
                        (team_index + match_index) % nb_teams
                    ].id,
                    round=round,
                )
                db.session.add(m)
        db.session.commit()
        return redirect(url_for("index"))


@app.route("/user/<username>")
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get("page", 1, type=int)
    if True or not user.has_team() or not user.has_match():
        return render_template(
            "user.html",
            user=user,
        )
    matches = user.team().attacks().paginate(page, app.config["MATCHS_PER_PAGE"], False)
    next_url = (
        url_for("user", username=current_user.username, page=matches.next_num)
        if matches.has_next
        else None
    )
    prev_url = (
        url_for("user", username=current_user.username, page=matches.prev_num)
        if matches.has_prev
        else None
    )
    return render_template(
        "user.html",
        user=user,
        matches=matches.items,
        next_url=next_url,
        prev_url=prev_url,
    )
