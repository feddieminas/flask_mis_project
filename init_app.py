from flask import Flask
from flask_login import LoginManager
from flask_pymongo import PyMongo
from config import Config
from flask_wtf.csrf import CSRFProtect


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    return app


app = create_app()
csrf = CSRFProtect(app)
mongo = PyMongo(app)
login = LoginManager(app)
