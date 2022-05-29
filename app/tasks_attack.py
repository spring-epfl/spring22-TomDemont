import os
from zipfile import ZipFile

import pandas as pd
from pandas import DataFrame
from sklearn.metrics import accuracy_score, roc_auc_score

from app import app, celery, db
from app.models import Attack, AttackResult, Match, Team, User
from app.tasks_control import send_mail


def verify_attack(df: DataFrame, team: Team) -> tuple[bool, str]:
    if set(df.columns) != set(app.config["ATTACK_COLUMNS"]):
        return (
            False,
            "Your file does not have the correct columns.\nPlease follow the upload instructions.\n",
        )
    if len(df.index) != app.config["NB_TRACES_TO_CLASSIFY"] * Match.nb_matches_in_round(
        app.config["ROUND"], team.id
    ):
        return (
            False,
            "Your file does not contain classification for every trace you should attack: expected: {}, have: {}".format(
                app.config["NB_TRACES_TO_CLASSIFY"]
                * Match.nb_matches_in_round(app.config["ROUND"], team.id),
                len(df.index),
            ),
        )
    if not set(df["team_id"].drop_duplicates()) == set(
        team.team_id_to_attack_in_round(app.config["ROUND"])
    ):
        return (
            False,
            "Your file contains attacks against teams you should not attack or does not attack all teams you should attack",
        )
    if not set(df["capture_id"].drop_duplicates()) == set(
        [i for i in range(app.config["NB_TRACES_TO_CLASSIFY"])]
    ):
        return (
            False,
            "Your file contains invalid capture_id indexes",
        )
    if (
        not (abs(df.filter(regex="proba_cell_id_\d+") - 0.5) <= 0.5).all().all()
        or not (
            abs(df.filter(regex="proba_cell_id_\d+").sum(axis=1) - 1.0) <= 10 ** (-10)
        ).all()
    ):
        return (
            False,
            "Your output probabilities are not a valid distribution",
        )
    return True, ""


def evaluate_attack_perf(df: DataFrame, team: Team) -> list[Attack]:
    performed_attacks = []
    for attacked_id in team.team_id_to_attack_in_round(app.config["ROUND"]):
        verif_file_path = os.path.join(
            app.root_path,
            app.config["UPLOAD_FOLDER"],
            app.config["VERIF_FILENAME_FORMAT"].format(attacked_id),
        )

        true_labels = pd.read_csv(verif_file_path)["cell_id"].to_numpy()
        proba_classif = (
            df[df["team_id"] == attacked_id]
            .filter(regex="proba_cell_id_\d+")
            .to_numpy()
        )
        classif = (
            df[df["team_id"] == attacked_id]
            .filter(regex="proba_cell_id_\d+")
            .idxmax(axis=1)
            .apply(lambda x: int(x.split("_")[-1]))
            .to_numpy()
        )
        results = AttackResult(
            accuracy=accuracy_score(true_labels, classif),
            auc_roc_score=roc_auc_score(true_labels, proba_classif, multi_class="ovr"),
        )

        evaluated_match = team.get_match_against(
            app.config["ROUND"], attacked_id
        ).first()

        performed_attacks.append(Attack(match_id=evaluated_match.id, results=results))
    return performed_attacks


@celery.task
def treat_uploaded_attack(filename: str, user_id: int) -> None:
    # The task is called only is the user had a team
    user = User.query.get(user_id)
    team = user.team()
    member1, member2 = team.members()
    filepath = os.path.join(
        app.root_path, app.config["TEMPORARY_UPLOAD_FOLDER"], filename
    )
    error_msg = ""
    with ZipFile(filepath, "r") as zip:
        with zip.open(zip.filelist[0], "r") as data_set:
            df = pd.read_csv(data_set)
            ok_df, error_msg = verify_attack(df, team)
            if ok_df:
                performed_attacks = evaluate_attack_perf(df, team)
                db.session.add_all(performed_attacks)
                db.session.commit()

                attacks_repr = ""
                for a in performed_attacks:
                    attacks_repr += a.__repr__()
                send_mail.delay(
                    "Your upload for Secret Race Strolling succeeded",
                    [member1.email, member2.email],
                    "Hey Team {:s}\nYour upload {:s} succeded. Here are your utility results:\n {}\n".format(
                        team.team_name, filename[:-4], attacks_repr
                    ),
                )
    if error_msg != "":
        send_mail.delay(
            "Your upload for Secret Race Strolling failed",
            [member1.email, member2.email],
            "Hey Team {:s},\nYour upload {:s} failed.\n{:s}\n".format(
                team.team_name, filename[:-4], error_msg
            ),
        )
    os.remove(filepath)
