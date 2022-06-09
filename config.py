import os

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
# loads environment variables from '.env' file
load_dotenv(os.path.join(basedir, ".env"))


class Config(object):
    """
    ###################
    TECHNICAL
    ###################
    """

    SECRET_KEY = (
        os.environ.get("SECRET_KEY") or "you-will-never-guess"
    )  # should not keep default value
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "sqlite:///" + os.path.join(basedir, "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CELERY_BROKER_URL = (
        os.environ.get("CELERY_BROKER_URL") or "redis://localhost:6379/0"
    )
    RESULT_BACKEND = os.environ.get("RESULT_BACKEND") or "redis://localhost:6379/0"
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER") or "uploads"
    TEMPORARY_UPLOAD_FOLDER = (
        os.environ.get("TEMPORARY_UPLOAD_FOLDER") or "temp_uploads"
    )

    """
    ###################
    MAIL SUPPORT
    ###################
    """

    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT") or 25)
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS") is not None
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL") is not None
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    ADMIN = os.environ.get("ADMIN")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")
    MAIL_TEST_RECEIVER_FORMAT = os.environ.get(
        "MAIL_TEST_RECEIVER_FORMAT"
    )  # for testing and generating fake user database, should not be kept on deployment

    """
    ###################
    APPEARANCE
    ###################
    """

    MATCHES_PER_PAGE = int(os.environ.get("MATCHES_PER_PAGE") or 40 * 3)

    """
    ###################
    COMPETITION DESIGN
    ###################
    """

    MATCHES_PER_TEAM = int(os.environ.get("MATCHES_PER_TEAM") or 3)
    DEFENCE_PHASE = True  # for development, should be set to False at startup. Expected to be modifiable at runtime
    ATTACK_PHASE = True  # Expected to be modifiable at runtime
    ROUND = 1  # Expected to be modifiable at runtime
    NB_CLASSES = int(os.environ.get("NB_CLASSES") or 100)
    NB_TRACES_TO_CLASSIFY = int(os.environ.get("NB_TRACES_TO_CLASSIFY") or 300)

    """
    ###################
    TRACE VERIFICATION
    ###################
    """

    MAX_CONTENT_LENGTH = (
        int(os.environ.get("MAX_CONTENT_LENGTH") or 32) * 1024 * 1024
    )  # in Megabytes, max size of uploaded (compressed) file
    MEAN_NB_REP_PER_CLASS = int(os.environ.get("MEAN_NB_REP_PER_CLASS") or 32)
    DEVIATION_NB_REP_PER_CLASS = int(os.environ.get("DEVIATION_NB_REP_PER_CLASS") or 7)
    ROWS_PER_CAPTURE = int(os.environ.get("ROWS_PER_CAPTURE") or 5)

    """
    ###################
    LEADERBOARD
    ###################
    """

    LEADERBOARD_CACHE_TIME = int(
        os.environ.get("LEADERBOARD_CACHE_TIME") or 5
    )  # in seconds

    """
    ###################
    FILENAME & FORMATS
    ###################
    """

    UPLOAD_EXTENSIONS = [
        "zip"
    ]  # WTF verificator needs no dot. Accepted extension for the uploaded file, we want it all compressed to reduce traffic size
    DEFENCE_FILE_EXTENSIONS = [
        "csv"
    ]  # Accepted extension of the zipped file for the defence upload
    ATTACK_FILE_EXTENSIONS = [
        "csv"
    ]  # Accepted extension of the zipped file for the defence upload
    DEFENCE_COLUMNS = [
        col.strip()
        for col in (
            os.environ.get("DEFENCE_COLUMNS") or "cell_id,rep,direction_size,timestamp"
        ).split(",")
        if col != ""
    ]  # Column names for the uploaded defence dataframe, comma separated. First elem should represent the class, second the repetition id for this class
    PROBA_CLASS_PREFIX = "proba_class_"  # weirdly, Python does not recognize this as defined for the below array generation. Should make sure this is equal to the below prefix
    ATTACK_COLUMNS = (
        [
            col.strip()
            for col in (os.environ.get("ATTACK_COLUMNS") or "team_id,capture_id").split(
                ","
            )
            if col != ""
        ]
    ) + [
        "proba_class_" + "{}".format(i) for i in range(1, NB_CLASSES + 1)
    ]  # Column names for the uploaded attack dataframe, comma separated. Automatically appends the proba_cell_id_{} columns, required for performance evaluation. First elem should represent the team_id attacked, second the id of the attacked feature
    TEST_FILENAME_FORMAT = "team_{}_test.csv.zip"
    TRAIN_FILENAME_FORMAT = "team_{}_train.csv.zip"
    VERIF_FILENAME_FORMAT = "team_{}_verif.csv.zip"
