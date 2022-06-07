"""Defines the tasks and jobs triggered when a user uploads a defence dataset. Handles from the upload to saving the train, test and verification sets to files and saving utility results to the database."""

import os
import secrets
import sys
from hashlib import sha256

import pandas as pd
from pandas import DataFrame

from app import app, celery, db
from app.models import Defence, User, Utility
from app.tasks_control import send_mail

# convenient as called multiple times in this code. Those should not be changed during runtime in any case
CLASS_NAME = app.config["DEFENCE_COLUMNS"][0]
REP_NAME = app.config["DEFENCE_COLUMNS"][1]
MEAN_NB_REP_PER_CLASS = app.config["MEAN_NB_REP_PER_CLASS"]
DEVIATION_NB_REP_PER_CLASS = app.config["DEVIATION_NB_REP_PER_CLASS"]
ROWS_PER_CAPTURE = app.config["ROWS_PER_CAPTURE"]
NB_CLASSES = app.config["NB_CLASSES"]
CAPTURE_NAME = app.config["ATTACK_COLUMNS"][1]


def verify_dataframe(df: DataFrame) -> tuple[bool, str]:
    """Verifies if the uploaded dataset corresponds to expectations and can be evaluated correctly.

    Args:
        df: the dataframe containing the data uploaded by the users

    Returns:
        verified: whether the verification succeeded or not
        error_msg: a string error message to eventually include in a mail feedback"""
    # sets remove dependency on the order
    if set(df.columns) != set(app.config["DEFENCE_COLUMNS"]):
        return (
            False,
            "Your dataset does not have the correct columns.\nPlease follow the upload instructions.\n",
        )
    if df[CLASS_NAME].drop_duplicates().count() != NB_CLASSES:
        return (
            False,
            "Your dataset does not contain captures for every cell_id",
        )
    rep_per_class = (
        df[[CLASS_NAME, REP_NAME]].drop_duplicates().groupby(CLASS_NAME).count()
    )
    if (
        not (abs(rep_per_class - MEAN_NB_REP_PER_CLASS) < DEVIATION_NB_REP_PER_CLASS)
        .all()
        .bool()
    ):
        return (
            False,
            f"Your dataset does not contain between {MEAN_NB_REP_PER_CLASS-DEVIATION_NB_REP_PER_CLASS} and {MEAN_NB_REP_PER_CLASS+DEVIATION_NB_REP_PER_CLASS} repetition per class",
        )
    rows_per_capture = df.groupby([CLASS_NAME, REP_NAME]).count()
    if not (rows_per_capture > ROWS_PER_CAPTURE).all().all():
        return (
            False,
            f"Some of your traces contain less that {ROWS_PER_CAPTURE} packets for a query",
        )
    return True, ""


def evaluate_utility(df: DataFrame) -> Utility:
    """Evaluates the utility metric of the trace uploaded by the user. This evaluation depends on the application and here is only valid in the context of network fingerprinting.

    Args:
        df: the dataframe containing the data uploaded by the users. Expected to have columns 'direction_size' and 'timestamp'

    Returns:
        utility: the Utility object holding the results
    """
    in_volume_grouped_by = (
        df[df["direction_size"] < 0]
        .groupby([CLASS_NAME, REP_NAME])["direction_size"]
        .sum()
    )
    out_volume_grouped_by = (
        df[df["direction_size"] > 0]
        .groupby([CLASS_NAME, REP_NAME])["direction_size"]
        .sum()
    )
    comm_time_grouped_by = df.groupby([CLASS_NAME, REP_NAME])["timestamp"].max()
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
    """Utility method that aims at giving new labels to the repetition column of the uploaded dataset to break relationship between train and test sets repetition labels while preserving the relation between rows belonging to a same capture. This allows to safely give train and test set while not leaking information on test set's labels from the repetition index.

    Args:
        df: the dataframe containing the data uploaded by the users

    Returns:
        rep_to_rnd: the list of new indexes to replace the previous repetition column
    """
    # random 'salt', unique for a run but changes between runs
    rnd = secrets.randbits(128)
    # precomputes the mapping from class_id, rep to its new random label
    # for efficiency as we expect a lot of redundancy
    # random is only 3 bytes number, there should be way less than 2^12 pairs which reduces collision proba
    class_rep_pair_to_rnd = {
        (class_id, rep): int.from_bytes(
            sha256("{}{}{}".format(rnd, class_id, rep).encode()).digest()[:3],
            byteorder=sys.byteorder,
        )
        for class_id, rep in df[[CLASS_NAME, REP_NAME]].drop_duplicates().values
    }
    return [
        class_rep_pair_to_rnd[(cell_id, rep)]
        for cell_id, rep in df[[CLASS_NAME, REP_NAME]].values
    ]


def split_train_test_set(df: DataFrame) -> tuple[DataFrame, DataFrame, DataFrame]:
    """Splits between test and train set from the user uploaded data. Takes care of including at least capture one of each class in the test set (required for the roc_auc_score computation). This splitting depends on the application and here is only valid in the context of network fingerprinting.

    Args:
        df: the dataframe containing the data uploaded by the users. Expected to have columns 'direction_size' and 'timestamp'

    Returns:
        test_set: dataframe containing repetition id and features of captures to classify
        verification_set: dataframe containing the true label for each repetition id of the test set
        train_set: the features and corresponding labels to train a model on
    """
    # we recreate rep indexes to avoid identification of the repetitions that are missing in the trainset and therefore are in the test set, making classification way easier.
    df[REP_NAME] = randomize_rep_index(df)

    # takes class name and rep name pair making sure each class_name is included once
    sub_test_set_all_cell_id = (
        df[[CLASS_NAME, REP_NAME]].groupby(CLASS_NAME).first().reset_index()
    )
    # identifies the already selected class, rep pair's indexes in the original dataframe
    indexes_to_drop = df[[CLASS_NAME, REP_NAME]].merge(sub_test_set_all_cell_id).index
    # selects the remaining class, rep pairs of the test set by sampling NB_TRACES_TO_CLASSIFY - NB_CLASSES captures randomly. The full test set is the concatenation of both
    test_set_cellid_rep = pd.concat(
        [
            df[[CLASS_NAME, REP_NAME]]
            .drop(index=indexes_to_drop)
            .drop_duplicates()
            .sample(app.config["NB_TRACES_TO_CLASSIFY"] - df[CLASS_NAME].nunique()),
            sub_test_set_all_cell_id,
        ]
    )
    # selects the rows from original dataframe by their class, rep pair
    test_set_rows = df.merge(test_set_cellid_rep)
    # creates the capture_id column by randomizing again the repetition's
    test_set_rows[CAPTURE_NAME] = randomize_rep_index(test_set_rows)

    test_set = test_set_rows[[CAPTURE_NAME, "direction_size", "timestamp"]].sort_values(
        by=[CAPTURE_NAME, "timestamp"]
    )

    verification_set = (
        test_set_rows[[CAPTURE_NAME, CLASS_NAME]]
        .drop_duplicates()
        .sort_values(by=[CAPTURE_NAME])
    )

    train_set = df.drop(index=test_set_rows.index).sort_values(by=["cell_id", "rep"])

    return [test_set, verification_set, train_set]


@celery.task
def treat_uploaded_defence(filename: str, user_id: int) -> None:
    """Deals with a file uploaded for defence from its verification to the creation of associated test, train and verification sets. Made to be triggered asynchronously and handled by a celery worker. Once done, the 3 sets are saved in separate compressed files and the Defence resulting is pushed in the database. Depends on the application and here is only valid in the context of network fingerprinting.

    Args:
        filename: the filename of the file uploaded by user and saved in the temporary upload folder
        user_id: the id of the user we are evaluating the defence of (passing user_id is easier to pass than User object as the arguments are serialized and sent to the celery workers)

    """
    # The task is called only if the user had a team
    user = User.query.get(user_id)
    team = user.team()
    member1, member2 = team.members()
    if not team.is_full():
        # we consider a team of twice the same member for ease of computation
        member2 = member1
    filepath = os.path.join(
        app.root_path, app.config["TEMPORARY_UPLOAD_FOLDER"], filename
    )
    error_msg = ""
    try:
        df = pd.read_csv(filepath)
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
                # we must take care of removing the indexes in case this could reveal the split
                dataframe.to_csv(dataset_filename, index=False)

            db.session.add(defence)
            db.session.commit()
            send_mail.delay(
                "Your upload for Secret Race Strolling succeeded",
                [member1.email, member2.email],
                "Hey Team {:s}\nYour upload {:s} succeeded. Here are your utility results:\n {}\n".format(
                    team.team_name, filename[:-4], utility
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
