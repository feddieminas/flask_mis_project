import os
if os.path.exists('env.py'):
    import env


class Config:
    MONGO_DBNAME = 'COE'
    MONGO_URI = os.environ.get("MONGO_URI")
    SECRET_KEY = os.environ.get("SECRET_KEY")
