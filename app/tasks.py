from hashlib import sha256
import os
import sys
from tkinter import ROUND
from zipfile import ZipFile

import pandas as pd
from flask_mail import Message
from pandas import DataFrame

from app import app, celery, db, mail
from app.models import Attack, Defence, User, Utility
import secrets


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


def split_train_test_set(df: DataFrame) -> tuple[DataFrame, DataFrame, DataFrame]:
    rnd = secrets.randbits(128)
    # we recreate rep indexes to avoid identification of the repetitions that are missing in the trainset and therefore are in the test set, making classification way easier.
    df["rep"] = [
        int.from_bytes(
            sha256("{}{}{}".format(rnd, cell_id, rep).encode()).digest()[:3],
            byteorder=sys.byteorder,
        )
        for cell_id, rep in zip(df["rep"], df["cell_id"])
    ]

    test_set_cellid_rep = (
        df[["cell_id", "rep"]]
        .drop_duplicates()
        .sample(app.config["NB_TRACES_TO_CLASSIFY"])
    )
    test_set_rows = df.merge(test_set_cellid_rep)

    cellid_rep_to_rnd_index = (
        test_set_rows[["cell_id", "rep"]]
        .drop_duplicates()
        .sample(frac=1)
        .reset_index(drop=True)
        .reset_index()
    )
    m = {(x[1], x[2]): x[0] for x in cellid_rep_to_rnd_index.values}

    test_set_capture_index = test_set_rows.assign(
        capture_id=test_set_rows[["cell_id", "rep"]].apply(tuple, axis=1).map(m)
    )

    test_set = test_set_capture_index[
        ["capture_id", "direction_size", "timestamp"]
    ].sort_values(by=["capture_id", "timestamp"])
    verification_set = test_set_capture_index[["capture_id", "cell_id"]].sort_values(
        by=["capture_id", "cell_id"]
    )
    train_set = df.drop(index=test_set_rows.index).sort_values(by=["cell_id", "rep"])

    return test_set, verification_set, train_set


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
    with ZipFile(filepath, "r") as zip:
        with zip.open(zip.filelist[0], "r") as data_set:
            df = pd.read_csv(data_set)
            if set(df.columns) != set(app.config["DATASET_COLUMNS"]):
                error_msg = "Your dataset does not have the correct columns.\nPlease follow the upload instructions.\n"
            else:
                ok_df, error_msg = verify_dataframe(df)
                if ok_df:
                    utility = evaluate_utility(df)
                    defence = Defence(
                        defender_team_id=team.id,
                        utility=utility,
                        round=app.config["ROUND"],
                    )
                    test_set, verification_set, train_set = split_train_test_set(df)
                    test_set_filname = os.path.join(
                        app.root_path,
                        app.config["UPLOAD_FOLDER"],
                        app.config["TEST_FILENAME_FORMAT"].format(team.id),
                    )
                    test_set.to_csv(test_set_filname, index=False)

                    verif_set_filname = os.path.join(
                        app.root_path,
                        app.config["UPLOAD_FOLDER"],
                        app.config["VERIF_FILENAME_FORMAT"].format(team.id),
                    )
                    verification_set.to_csv(verif_set_filname, index=False)

                    train_set_filname = os.path.join(
                        app.root_path,
                        app.config["UPLOAD_FOLDER"],
                        app.config["TRAIN_FILENAME_FORMAT"].format(team.id),
                    )
                    train_set.to_csv(train_set_filname, index=False)

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


def verify_attack(df: DataFrame, user: User) -> tuple[bool, str]:
    if (
        df.count()
        != app.config["NB_TRACES_TO_CLASSIFY"] * app.config["MATCHES_PER_TEAM"]
    ):
        return (
            False,
            "Your file does not contain classification for every trace you should attack",
        )
    if not set(df["team_id"].drop_duplicates()) == set(
        user.team_id_to_attack_in_round(app.config["ROUND"])
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


def evaluate_attack_perf(df: DataFrame, user: User) -> Attack:
    for attacked_id in user.team_id_to_attack(app.config["ROUND"]):
        pass


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
            if set(df.columns) != set(app.config["ATTACK_COLUMNS"]):
                error_msg = "Your attack does not have the correct columns.\nPlease follow the upload instructions.\n"
            else:
                ok_df, error_msg = verify_dataframe(df)
                if ok_df:
                    accuracy = evaluate_attack_perf(df)
                    # TODO
    if error_msg != "":
        send_mail.delay(
            "Your upload for Secret Race Strolling failed",
            [member1.email, member2.email],
            "Hey Team {:s},\nYour upload {:s} failed.\n{:s}\n".format(
                team.team_name, filename[:-4], error_msg
            ),
        )
    os.remove(filepath)
