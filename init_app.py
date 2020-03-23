from flask import Flask
from flask_login import LoginManager
from flask_talisman import Talisman
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

csp = {
    'default-src': [
        '\'unsafe-inline\' \'self\'',
        '*.cloudflare.com',
        '*.bootstrapcdn.com',
        '*.googleapis.com',
        '*.gstatic.com'
    ],
    'style-src': [
        '\'unsafe-inline\' \'self\'',
        '*.cloudflare.com',
        '*.bootstrapcdn.com',
        '*.googleapis.com',
        '*.gstatic.com'
    ],
    'script-src': [
        '\'unsafe-inline\' \'self\'',
        '*.jquery.com',
        '*.cloudflare.com',
        '*.bootstrapcdn.com',
        '*.googleapis.com'
    ]
}

Talisman(app, content_security_policy=csp)
