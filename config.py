import os

basedir = os.path.abspath(os.path.dirname(__file__))


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
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    ADMINS = ["tom.demont@epfl.ch"]
    MATCHES_PER_PAGE = os.environ.get("MATCHES_PER_PAGE") or 40
    MATCHES_PER_TEAM = os.environ.get("MATCHES_PER_TEAM") or 3
    DEFENCE_PHASE = True
    ATTACK_PHASE = True
    ROUND = 1
    UPLOAD_EXTENSIONS = ["zip"]
    DATASET_EXTENSIONS = [".csv"]
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024
    UPLOAD_FOLDER = "uploads"
    TEMPORARY_UPLOAD_FOLDER = "temp_uploads"
    DATASET_COLUMNS = ["cell_id", "rep", "direction_size", "timestamp"]
    CELERY_BROKER_URL = 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

