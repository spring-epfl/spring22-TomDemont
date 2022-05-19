import os
from datetime import datetime
from random import shuffle
from zipfile import ZipFile

from flask import (
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
    send_file,
)
from flask_login import (
    current_user,
    fresh_login_required,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.urls import url_parse

from app import app, db
from app.forms import AttackUpload, DefenceUpload, LoginForm, RegistrationForm
from app.models import Attack, Defence, Match, Team, User
from app.tasks import send_mail, treat_uploaded_defence, treat_uploaded_attack
import tempfile


@app.route("/")
@app.route("/index", methods=["GET"])
@login_required
def index():
    page = request.args.get("page", 1, type=int)
    pagination, matches_items = Match.paginate_and_itemize_match_query(
        db.session.query(Match).order_by(Match.round.desc()),
        page,
        app.config["MATCHES_PER_PAGE"],
        current_user.team(),
    )
    next_url = (
        url_for("index", page=pagination.next_num) if pagination.has_next else None
    )
    prev_url = (
        url_for("index", page=pagination.prev_num) if pagination.has_prev else None
    )

    return render_template(
        "index.html",
        title="Home",
        matches=matches_items,
        next_url=next_url,
        prev_url=prev_url,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = RegistrationForm()
    form.team_select.choices = ["New team"] + [
        team.team_name for team in Team.query.all() if not team.is_full()
    ]
    if form.validate_on_submit():
        print("validated")
        user = User(username=form.username.data, email=form.email.data, is_admin=False)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        if form.team_select.data != "New team":
            team = Team.query.filter_by(team_name=form.team_select.data).first()
            team.member2_id = user.id
            db.session.commit()
        else:
            team = Team(team_name=form.new_team_name.data, member1_id=user.id)
            db.session.add(team)
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


@app.route("/generate_matches/", methods=["GET"])
@fresh_login_required
def generate_matches():
    if not current_user.is_admin:
        # Only the admins should be able to generate the matches
        abort(403)
    else:
        round = request.args.get("round", 0, type=int)
        if round == 0:
            # those special cases are treated as query for the "usages" of the function
            return render_template("generate_matches.html")
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
            flash("You have not generated the matches for round {}".format(round - 1))
            abort(400)
        # we only keep teams of participants non-admin
        all_teams = list(filter(lambda x: not x.has_admin(), Team.query.all()))
        nb_teams = len(all_teams)
        # we make sure not to have more than nb_teams-1 matches per team to avoid self-matching
        matches_per_team = min([app.config["MATCHES_PER_TEAM"], nb_teams - 1])
        # we shuffle the whole teams list to have random matches
        shuffle(all_teams)
        for team_index in range(nb_teams):
            for match_index in range(1, matches_per_team + 1):
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
        app.config["ROUND"] = round
        return redirect(url_for("index"))


@app.route("/user/<username>", methods=["GET"])
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    team = user.team()
    return render_template("user.html", user=user, team=team)


@app.route("/join_team/", methods=["GET"])
@fresh_login_required
def join_team():
    if current_user.has_team():
        flash("You already have a team")
        abort(400)
    team_name = request.args.get("team_name", None, type=str)
    team = Team.query.filter_by(team_name=team_name).first_or_404()
    if team.is_full():
        flash("This team is already full")
        abort(400)
    if team.has_admin() and not current_user.is_admin():
        abort(403)
    if team.member1_id is None:
        team.member1_id = current_user.id
    else:
        team.member2_id = current_user.id
    db.session.commit()
    flash("Congrats, you joined {}".format(team.team_name))
    return redirect(url_for("team", team_name=team.team_name))


@app.route("/attack/", methods=["GET", "POST"])
@login_required
def attack():
    if not app.config["ATTACK_PHASE"]:
        flash("You cannot attack others now")
        abort(503)
    if not current_user.has_team():
        flash("You cannot make attacks if you have no team")
        abort(503)
    download = request.args.get("download", False, type=bool)
    if download:
        nb_def_matches_in_round = (
            current_user.team()
            .defence_matches_in_round(round=app.config["ROUND"])
            .count()
        )
        if nb_def_matches_in_round < 1:
            flash("You have no match yet for this round")
            abort(404)

        team_id_to_attack = current_user.team().team_id_to_attack_in_round(
            round=app.config["ROUND"]
        )
        files_to_send = [
            app.config["TEST_FILENAME_FORMAT"].format(team_id)
            for team_id in team_id_to_attack
        ] + [
            app.config["TRAIN_FILENAME_FORMAT"].format(team_id)
            for team_id in team_id_to_attack
        ]

        _, temp_file = tempfile.mkstemp(".zip")
        with ZipFile(temp_file, "w") as zip:
            for file in files_to_send:
                try:
                    zip.write(
                        os.path.join(app.root_path, app.config["UPLOAD_FOLDER"], file),
                        arcname=os.path.split(file)[1],
                    )
                except FileNotFoundError:
                    print("File not found: {:s}".format(file))
        file_to_send_name = "user_{:d}_round_{:d}_uploads.zip".format(
            current_user.id, app.config["ROUND"]
        )
        return send_file(temp_file, download_name=file_to_send_name)

    form = AttackUpload()
    if form.validate_on_submit():
        uploaded_file = request.files["file"]
        filename = "team_{:d}_{:s}_attack.zip".format(
            current_user.team().id, datetime.utcnow().strftime("%m_%d_%Y_%H:%M:%S")
        )
        save_path = os.path.join(
            app.root_path, app.config["TEMPORARY_UPLOAD_FOLDER"], filename
        )
        uploaded_file.save(save_path)
        treat_uploaded_attack.delay(filename, current_user.id)
        flash(
            "Attack received! Evaluation in process, you will receive results by email shortly"
        )
        return redirect(url_for("team", team_name=current_user.team().team_name))
    return render_template("attack.html", form=form)


@app.route("/defence/", methods=["GET", "POST"])
@login_required
def defence():
    if not app.config["DEFENCE_PHASE"]:
        flash("You cannot upload your defence trace now")
        abort(503)
    if not current_user.has_team():
        flash("You cannot upload a defence while you have no team")
        abort(503)
    form = DefenceUpload()
    if form.validate_on_submit():
        uploaded_file = request.files["file"]
        filename = "team_{:d}_{:s}_defence.zip".format(
            current_user.team().id, datetime.utcnow().strftime("%m_%d_%Y_%H:%M:%S")
        )
        save_path = os.path.join(
            app.root_path, app.config["TEMPORARY_UPLOAD_FOLDER"], filename
        )
        uploaded_file.save(save_path)
        treat_uploaded_defence.delay(filename, current_user.id)
        flash(
            "Defence received! Evaluation in process, you will receive results by email shortly"
        )
        return redirect(url_for("team", team_name=current_user.team().team_name))

    return render_template("upload_def.html", form=form)


@app.route("/team/<team_name>", methods=["GET"])
@login_required
def team(team_name):
    team = Team.query.filter_by(team_name=team_name).first_or_404()
    member1, member2 = team.members()
    page_match = request.args.get("page_match", 1, type=int)
    page_attack = request.args.get("page_attack", 1, type=int)
    pagination, matches_items = Match.paginate_and_itemize_match_query(
        team.attack_matches.order_by(Match.round.desc()),
        page_match,
        app.config["MATCHES_PER_TEAM"],
        current_user.team(),
    )
    match_next_url = (
        url_for(
            "team",
            team_name=team.team_name,
            page_match=pagination.next_num,
            page_attack=page_attack,  # we must not forget to propagate the attack page
        )
        if pagination.has_next
        else None
    )
    match_prev_url = (
        url_for(
            "team",
            team_name=team.team_name,
            page_match=pagination.prev_num,
            page_attack=page_attack,  # we must not forget to propagate the attack page
        )
        if pagination.has_prev
        else None
    )

    defence = team.defences.order_by(Defence.timestamp.desc()).first()

    attacks = (
        team.attacks()
        .order_by(Attack.timestamp.desc())
        .paginate(page_attack, app.config["MATCHES_PER_TEAM"], False)
    )
    attack_next_url = (
        url_for(
            "team",
            team_name=team.team_name,
            page_match=page_match,  # we must not forget to propagate the match page
            page_attack=attacks.next_num,
        )
        if attacks.has_next
        else None
    )
    attack_prev_url = (
        url_for(
            "team",
            team_name=team.team_name,
            page_match=page_match,  # we must not forget to propagate the match page
            page_attack=attacks.prev_num,
        )
        if attacks.has_prev
        else None
    )
    attacks_items = attacks.items

    return render_template(
        "team.html",
        team=team,
        member1=member1,
        member2=member2,
        matches=matches_items,
        attacks=attacks_items,
        defence=defence,
        match_next_url=match_next_url,
        match_prev_url=match_prev_url,
        attack_next_url=attack_next_url,
        attack_prev_url=attack_prev_url,
    )
