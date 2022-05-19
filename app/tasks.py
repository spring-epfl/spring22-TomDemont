import os
import secrets
import sys
from hashlib import sha256
from zipfile import ZipFile

import pandas as pd
from flask_mail import Message
from pandas import DataFrame
from sklearn.metrics import accuracy_score, roc_auc_score

from app import app, celery, db, mail
from app.models import Attack, AttackResult, Defence, Team, User, Utility, Match


@celery.task
def send_mail(subject, recipients, text_body, sender=None, attachments=None) -> None:
    with app.app_context():
        msg = Message(subject, sender=sender, recipients=recipients)
        msg.body = text_body + "\nKind regards,\nSecret Race Strolling Team"
        if attachments:
            for attachment in attachments:
                msg.attach(*attachment)
        mail.send(msg)


def verify_dataframe(df: DataFrame) -> tuple[bool, str]:
    if set(df.columns) != set(app.config["DATASET_COLUMNS"]):
        return (
            False,
            "Your dataset does not have the correct columns.\nPlease follow the upload instructions.\n",
        )
    if df["cell_id"].drop_duplicates().count() != 100:
        return (
            False,
            "Your dataset does not contain captures for every cell_id",
        )
    rep_per_cell_id = (
        df[["cell_id", "rep"]].drop_duplicates().groupby("cell_id").count()
    )
    if not (abs(rep_per_cell_id - 37) < 5).all().bool():
        return (
            False,
            "Your dataset does not contain between 32 and 42 query traces per cell_id",
        )
    packets_per_query = df.groupby(["cell_id", "rep"]).count()
    if not (packets_per_query > 1).all().all():
        return False, "Some of your traces contain less that 2 packets for a query"
    return True, ""


def evaluate_utility(df: DataFrame) -> Utility:
    in_volume_grouped_by = (
        df[df["direction_size"] < 0].groupby(["cell_id", "rep"])["direction_size"].sum()
    )
    out_volume_grouped_by = (
        df[df["direction_size"] > 0].groupby(["cell_id", "rep"])["direction_size"].sum()
    )
    comm_time_grouped_by = df.groupby(["cell_id", "rep"])["timestamp"].max()
    return Utility(
        in_volume_grouped_by.max(),
        in_volume_grouped_by.mean(),
        in_volume_grouped_by.median(),
        out_volume_grouped_by.max(),
        out_volume_grouped_by.mean(),
        out_volume_grouped_by.median(),
        comm_time_grouped_by.max(),
        comm_time_grouped_by.mean(),
        comm_time_grouped_by.median(),
    )


def randomize_rep_index(df: DataFrame) -> list[int]:
    rnd = secrets.randbits(128)
    cell_id_rep_to_rnd = {
        (cell_id, rep): int.from_bytes(
            sha256("{}{}{}".format(rnd, cell_id, rep).encode()).digest()[:3],
            byteorder=sys.byteorder,
        )
        for cell_id, rep in df[["cell_id", "rep"]].drop_duplicates().values
    }
    return [
        cell_id_rep_to_rnd[(cell_id, rep)]
        for cell_id, rep in df[["cell_id", "rep"]].values
    ]


def split_train_test_set(df: DataFrame) -> tuple[DataFrame, DataFrame, DataFrame]:
    # we recreate rep indexes to avoid identification of the repetitions that are missing in the trainset and therefore are in the test set, making classification way easier.
    df["rep"] = randomize_rep_index(df)

    sub_test_set_all_cell_id = (
        df[["cell_id", "rep"]].groupby("cell_id").first().reset_index()
    )

    indexes_to_drop = df[["cell_id", "rep"]].merge(sub_test_set_all_cell_id).index

    test_set_cellid_rep = pd.concat(
        [
            df[["cell_id", "rep"]]
            .drop(index=indexes_to_drop)
            .drop_duplicates()
            .sample(300 - df["cell_id"].nunique()),
            sub_test_set_all_cell_id,
        ]
    )

    test_set_rows = df.merge(test_set_cellid_rep)

    test_set_rows["capture_id"] = randomize_rep_index(test_set_rows)

    test_set = test_set_rows[["capture_id", "direction_size", "timestamp"]].sort_values(
        by=["capture_id", "timestamp"]
    )

    verification_set = (
        test_set_rows[["capture_id", "cell_id"]]
        .drop_duplicates()
        .sort_values(by=["capture_id"])
    )

    train_set = df.drop(index=test_set_rows.index).sort_values(by=["cell_id", "rep"])

    return [test_set, verification_set, train_set]


@celery.task
def treat_uploaded_defence(filename: str, user_id: int) -> None:
    # The task is called only is the user had a team
    user = User.query.get(user_id)
    team = user.team()
    member1, member2 = team.members()
    filepath = os.path.join(
        app.root_path, app.config["TEMPORARY_UPLOAD_FOLDER"], filename
    )
    error_msg = ""
    with ZipFile(filepath, "r") as zipfile:
        with zipfile.open(zipfile.filelist[0], "r") as data_set:
            df = pd.read_csv(data_set)
            ok_df, error_msg = verify_dataframe(df)
            if ok_df:
                utility = evaluate_utility(df)
                defence = Defence(
                    defender_team_id=team.id,
                    utility=utility,
                    round=app.config["ROUND"],
                )
                datasets = split_train_test_set(df)
                for fname_format, dataframe in zip(
                    [
                        "TEST_FILENAME_FORMAT",
                        "VERIF_FILENAME_FORMAT",
                        "TRAIN_FILENAME_FORMAT",
                    ],
                    datasets,
                ):
                    dataset_filename = os.path.join(
                        app.root_path,
                        app.config["UPLOAD_FOLDER"],
                        app.config[fname_format].format(team.id),
                    )
                    dataframe.to_csv(dataset_filename, index=False)

                db.session.add(defence)
                db.session.commit()
                send_mail.delay(
                    "Your upload for Secret Race Strolling succeeded",
                    [member1.email, member2.email],
                    "Hey Team {:s}\nYour upload {:s} succeded. Here are your utility results:\n {}\n".format(
                        team.team_name, filename[:-4], utility
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
