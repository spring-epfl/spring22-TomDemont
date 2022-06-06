import numpy as np
import pandas as pd
import random as rd
from sklearn.ensemble import RandomForestClassifier

import sys


def classify(train_features, train_labels, test_features, test_labels):
    # Initialize a random forest classifier. We prefer to use all the jobs our processor can handle, we are people in a hurry
    clf = RandomForestClassifier(n_jobs=-1, n_estimators=260)
    # Train the classifier using the training features and labels.
    clf.fit(train_features, train_labels)
    # Use the classifier to make predictions on the test features.
    predictions = clf.predict(test_features)
    # Use the classifier to give the list of predictions probabilities on each test feature
    predictions_proba = clf.predict_proba(test_features)

    return predictions, predictions_proba


def load_data(attacked_team_id: str):
    features_test = np.array(
        pd.read_csv(f"team_{attacked_team_id}_test.csv.zip")
        .groupby(["capture_id"])["direction_size"]
        .apply(np.array)
        .reset_index()["direction_size"]
    )

    features_train = np.array(
        pd.read_csv(f"team_{attacked_team_id}_train.csv.zip")
        .groupby(["cell_id", "rep"])["direction_size"]
        .apply(np.array)
        .reset_index()["direction_size"]
    )
    labels_train = (
        pd.read_csv(f"team_{attacked_team_id}_train.csv.zip")[["cell_id", "rep"]]
        .drop_duplicates()["cell_id"]
        .to_numpy()
    )

    max_len = max([len(a) for a in features_train] + [len(b) for b in features_test])
    Z_train = np.zeros((len(features_train), max_len))
    for enu, row in enumerate(features_train):
        Z_train[enu, : len(row)] = row

    Z_test = np.zeros((len(features_test), max_len))
    for enu, row in enumerate(features_test):
        Z_test[enu, : len(row)] = row

    return Z_test, Z_train, labels_train


def main(team_id: str):
    Z_test, Z_train, labels_train = load_data(team_id)
    _, predictions_proba = classify(Z_train, labels_train, Z_test, None)

    # for row in predictions_proba:
    #     rd.shuffle(row)
    
    df = pd.DataFrame(
        predictions_proba,
        index=None,
        columns=["proba_class_{}".format(i) for i in range(1, 101)],
    )
    capture_id_indexes = (
        pd.read_csv(f"team_{team_id}_test.csv.zip")["capture_id"]
        .drop_duplicates()
        .to_list()
    )
    df.insert(loc=0, column="capture_id", value=capture_id_indexes)
    df.insert(
        loc=0,
        column="team_id",
        value=[team_id for _ in range(len(predictions_proba))],
    )

    return df


if __name__ == "__main__":
    try:
        all_dfs = []
        for attacked_team_id in sys.argv[1:]:
            all_dfs.append(main(attacked_team_id))
        df = pd.concat(all_dfs)
        df.to_csv("my_classification.csv.zip", index=False)
    except KeyboardInterrupt:
        sys.exit(0)
