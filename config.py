import os


class Config(object):
    # for development, will be changed asap 
    SECRET_KEY = os.environ.get("SECRET_KEY") or "you-will-never-guess"
