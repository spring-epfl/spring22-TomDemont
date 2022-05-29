import os

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


class Config(object):
    # for development, will be changed asap
    SECRET_KEY = os.environ.get("SECRET_KEY") or "you-will-never-guess"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "sqlite:///" + os.path.join(basedir, "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT") or 25)
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS") is not None
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL") is not None
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    ADMINS = os.environ.get("ADMINS")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")
    MAIL_TEST_RECEIVER_FORMAT = "tom.demont+{}@epfl.ch"
    MATCHES_PER_TEAM = os.environ.get("MATCHES_PER_TEAM") or 3
    MATCHES_PER_PAGE = os.environ.get("MATCHES_PER_TEAM") or 40 * MATCHES_PER_TEAM
    DEFENCE_PHASE = True
    ATTACK_PHASE = True
    ROUND = 1
    UPLOAD_EXTENSIONS = ["zip"]  # WTF verificator need no dot
    DATASET_EXTENSIONS = ["csv"]
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32MB
    UPLOAD_FOLDER = "uploads"
    TEMPORARY_UPLOAD_FOLDER = "temp_uploads"
    DATASET_COLUMNS = ["cell_id", "rep", "direction_size", "timestamp"]
    ATTACK_COLUMNS = ["team_id", "capture_id"] + [
        "proba_cell_id_{}".format(i) for i in range(1, 101)
    ]
    CELERY_BROKER_URL = "redis://localhost:6379/0"
    RESULT_BACKEND = "redis://localhost:6379/0"
    TEST_FILENAME_FORMAT = "team_{}_test.csv.zip"
    TRAIN_FILENAME_FORMAT = "team_{}_train.csv.zip"
    VERIF_FILENAME_FORMAT = "team_{}_verif.csv.zip"
    NB_TRACES_TO_CLASSIFY = os.environ.get("NB_TRACES_TO_CLASSIFY") or 300
