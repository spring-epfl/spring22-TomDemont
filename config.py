import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    # for development, will be changed asap
    SECRET_KEY = os.environ.get("SECRET_KEY") or "you-will-never-guess"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "sqlite:///" + os.path.join(basedir, "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = ['tom.demont@epfl.ch']
    MATCHES_PER_PAGE = os.environ.get('MATCHES_PER_PAGE') or 4
    MATCHES_PER_TEAM = os.environ.get('MATCHES_PER_TEAM') or 3
