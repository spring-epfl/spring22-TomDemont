"""
Initialization of the app package. Regular Flask app variable creation with its modules.
"""

import logging
import os
from logging.handlers import RotatingFileHandler, SMTPHandler

from celery import Celery
from config import Config
from flask import Flask
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

"""Initialize all components used by the app"""
app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login = LoginManager(app)
login.login_view = "login"  # function name for login
bootstrap = Bootstrap(app)
mail = Mail(app)
celery = Celery(
    app.name,
    broker=app.config["CELERY_BROKER_URL"],
    backend=app.config["RESULT_BACKEND"],
)
celery.conf.update(app.config)

"""Handles logging by mail and on files if we are not in debug mode"""
if not app.debug:
    if app.config["MAIL_SERVER"] and not app.config["MAIL_USE_SSL"]:
        # we cannot yet have mail logs with a SMTP over SSL connection
        # https://docs.python.org/3/library/logging.handlers.html#logging.handlers.SMTPHandler
        # There exists code to circumvent this https://github.com/dycw/ssl-smtp-handler but not widely adopted
        auth = None
        if app.config["MAIL_USERNAME"] or app.config["MAIL_PASSWORD"]:
            auth = (app.config["MAIL_USERNAME"], app.config["MAIL_PASSWORD"])
        secure = None
        if app.config["MAIL_USE_TLS"]:
            secure = ()
        mail_handler = SMTPHandler(
            mailhost=(app.config["MAIL_SERVER"], app.config["MAIL_PORT"]),
            fromaddr="no-reply@" + app.config["MAIL_SERVER"],
            toaddrs=app.config["ADMINS"],
            subject="Secret Race Strolling Failure",
            credentials=auth,
            secure=secure,
        )
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)

    if not os.path.exists("logs"):
        os.mkdir("logs")
    file_handler = RotatingFileHandler("logs/srs.log", maxBytes=10240, backupCount=10)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        )
    )
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)

    app.logger.setLevel(logging.INFO)
    app.logger.info("Secret Race Strolling startup")

# import in the bottom to avoid circular dependencies
from app import errors, models, routes, tasks_attack, tasks_control, tasks_defence
