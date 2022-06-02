"""Defines the tasks and jobs triggered when a user uploads an attack file. Handles from the upload to performance results to the database."""


import os

import pandas as pd
from pandas import DataFrame
from sklearn.metrics import accuracy_score, roc_auc_score

from app import app, celery, db
from app.models import Attack, AttackResult, Match, Team, User
from app.tasks_control import send_mail

CLASS_NAME = app.config["DEFENCE_COLUMNS"][0]
NB_TRACES_TO_CLASSIFY = app.config["NB_TRACES_TO_CLASSIFY"]
TEAM_ID_NAME = app.config["ATTACK_COLUMNS"][0]
CAPTURE_NAME = app.config["ATTACK_COLUMNS"][1]
PROBA_CLASS_REGEX = app.config["PROBA_CLASS_PREFIX"] + "\d+"


def verify_attack(df: DataFrame, team: Team) -> tuple[bool, str]:
    """Verifies if the uploaded file corresponds to expectations and can be evaluated correctly.

    Args:
        df: the dataframe containing the data uploaded by the users

    Returns:
        verified: whether the verification succeeded or not
        error_msg: a string error message to eventually include in a mail feedback"""
    if set(df.columns) != set(app.config["ATTACK_COLUMNS"]):
        return (
            False,
            "Your file does not have the correct columns.\nPlease follow the upload instructions.\n",
        )
    if len(df.index) != NB_TRACES_TO_CLASSIFY * Match.nb_matches_in_round(
        app.config["ROUND"], team.id
    ):
        return (
            False,
            "Your file does not contain classification for every trace you should attack: expected: {:d}, have: {:d}".format(
                NB_TRACES_TO_CLASSIFY
                * Match.nb_matches_in_round(app.config["ROUND"], team.id),
                len(df.index),
            ),
        )
    if set(df[TEAM_ID_NAME].drop_duplicates()) != set(
        team.team_id_to_attack_in_round(app.config["ROUND"])
    ):
        return (
            False,
            "Your file contains attacks against teams you should not attack or does not attack all teams you should attack",
        )
    for attacked_id in team.team_id_to_attack_in_round(app.config["ROUND"]):
        # we verify if we have some bad or missing capture id classifed
        verif_file_path = os.path.join(
            app.root_path,
            app.config["UPLOAD_FOLDER"],
            app.config["VERIF_FILENAME_FORMAT"].format(attacked_id),
        )
        verif_df_capture_id = set(
            pd.read_csv(verif_file_path)[CAPTURE_NAME].drop_duplicates()
        )
        if (
            set(df[df[TEAM_ID_NAME] == attacked_id][CAPTURE_NAME].drop_duplicates())
            != verif_df_capture_id
        ):
            return (
                False,
                f"Your file contains invalid capture_id indexes.",
            )
    if (
        not (abs(df.filter(regex=PROBA_CLASS_REGEX) - 0.5) <= 0.5).all().all()
        or not (
            abs(df.filter(regex=PROBA_CLASS_REGEX).sum(axis=1) - 1.0) <= 10 ** (-10)
        ).all()
    ):
        # we must take care of the floating point precision in the sum to verify if our probabilities sum to 1
        return (
            False,
            f"Your output probabilities are not a valid distribution: {df.filter(regex=PROBA_CLASS_REGEX)}",
        )
    return True, ""


def evaluate_attack_perf(df: DataFrame, team: Team) -> list[Attack]:
    """Evaluates the attack metrics scored by the uploaded attack classification.

    Args:
        df: the dataframe containing the data uploaded by the users

    Returns:
        performed_attacks: the list of Attack objects holding the result of every attack to be pushed to db"""
    performed_attacks = []
    for attacked_id in team.team_id_to_attack_in_round(app.config["ROUND"]):
        verif_file_path = os.path.join(
            app.root_path,
            app.config["UPLOAD_FOLDER"],
            app.config["VERIF_FILENAME_FORMAT"].format(attacked_id),
        )

        true_labels = pd.read_csv(verif_file_path)[CLASS_NAME].to_numpy()
        # we take the full proba classification against the attacked team
        proba_classif = (
            df[df[TEAM_ID_NAME] == attacked_id]
            .filter(regex=PROBA_CLASS_REGEX)
            .to_numpy()
        )
        # we get the hard classification to have accuracy
        classif = (
            df[df[TEAM_ID_NAME] == attacked_id]
            .filter(regex=PROBA_CLASS_REGEX)
            .idxmax(axis=1)  # we take column of the label classified with highest prob
            .apply(
                lambda x: int(x.split("_")[-1])
            )  # we use the fact that the class id is present in the column's name
            .to_numpy()
        )
        results = AttackResult(
            accuracy=accuracy_score(true_labels, classif),
            roc_auc_score=roc_auc_score(true_labels, proba_classif, multi_class="ovr"),
        )
        # from the previous queries we already know this match should exist
        evaluated_match = team.get_match_against(
            app.config["ROUND"], attacked_id
        ).first()

        performed_attacks.append(Attack(match_id=evaluated_match.id, results=results))
    return performed_attacks


@celery.task
def treat_uploaded_attack(filename: str, user_id: int) -> None:
    """Deals with a file uploaded for attack from its verification to the evaluation of its performance. Made to be triggered asychronously and handled by a celery worker. Once done, all the attacks for this user in the current round are pushed to the database. Depends on the application and here is only valid in the context of network fingerprinting.

    Args:
        filename: the filename of the file uploaded by user and saved in the temporary upload folder
        user_id: the id of the user we are evaluating the defence of (passing user_id is easier to pass than User object as the arguments are serialized and sent to the celery workers)

    """
    # The task is called only is the user had a team
    user = User.query.get(user_id)
    team = user.team()
    member1, member2 = team.members()
    filepath = os.path.join(
        app.root_path, app.config["TEMPORARY_UPLOAD_FOLDER"], filename
    )
    error_msg = ""
    try:
        df = pd.read_csv(filepath)
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
        else:
            send_mail.delay(
                "Your upload for Secret Race Strolling failed",
                [member1.email, member2.email],
                "Hey Team {:s},\nYour upload {:s} failed.\n{:s}\n".format(
                    team.team_name, filename[:-4], error_msg
                ),
            )
    finally:
        # in any case, we don't want to keep the temporary uploaded file in the server
        os.remove(filepath)
