import os
import secrets
import sys
from hashlib import sha256
from zipfile import ZipFile

import pandas as pd
from pandas import DataFrame

from app import app, celery, db
from app.models import Defence, User, Utility
from app.tasks_control import send_mail


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
