import os
import pandas as pd
import math
if os.path.exists('env.py'):
    import env
from flask import Flask, render_template, redirect, request, url_for, session, flash, jsonify
from flask_pymongo import PyMongo
from werkzeug.urls import url_parse
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from forms import LoginForm, WACCForm
from bson.son import SON
from bson.json_util import dumps
from user import User


app = Flask(__name__)

app.config["MONGO_DBNAME"] = 'COE'
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.config["SECRET_KEY"] = os.urandom(16)

mongo = PyMongo(app)


""" forms """

login = LoginManager(app)
login.login_view = 'login'


""" custom template filters """


@app.template_filter('conv_percents')
def percents(val):
    return "{0:.3f}%".format(val*100)


""" custom functions """


def regions():
    return sorted(mongo.db.countries.distinct("REGION"))


def db_data(filtering=None):
    pipeline = [
        {
            "$lookup": {
                "from": "countries",
                "localField": "COUNTRY_ID",
                "foreignField": "ID",
                "as": "Country"
            }
        },
        {
            "$lookup": {
                "from": "methods",
                "localField": "METHOD_ID",
                "foreignField": "ID",
                "as": "Method"
            }
        },
        {
            "$lookup": {
                "from": "yearsqs",
                "localField": "YEAR_Q_ID",
                "foreignField": "ID",
                "as": "YearQ"
            }
        },
        {"$unwind": "$Country"},
        {"$unwind": "$Method"},
        {"$unwind": "$YearQ"},
        {
            "$project": {
                "YEAR": "$YearQ.YEAR",
                "QUARTER": "$YearQ.QUARTER",
                "COUNTRY": "$Country.COUNTRY",
                "REGION": "$Country.REGION",
                "METHOD": "$Method.Method",
                "RATING_SPREAD": 1,
                "ERP": 1,
                "CRP": 1,
                "_id": 0
            }
        },
        {"$sort": SON([("YEAR", -1), ("QUARTER", -1), ("METHOD", 1)])}
    ]

    data = list(mongo.db.erpcrp.aggregate(pipeline))
    if bool(filtering):
        theRegions = regions()
        filtering = {theRegions[int(f)-1] for f in filtering if f.isdigit()}
        data = [x for x in filterbyvalue(data, filtering)]

    return data


def filterbyvalue(seq, values):
    for el in seq:
        for v in values:
            if any([bool(el["COUNTRY"] == v), bool(el["REGION"] == v),
                    bool(el["METHOD"] == v)]):
                yield el


""" INDEX.HTML """


@app.route('/', methods=['GET'])
def index():
    form = WACCForm()
    form.country.choices = [(r, r) for r in regions()]
    return render_template('index.html', form=form)


""" WACC.JSON """


@app.route('/_wacc_nums', methods=['POST'])
def wacc_nums():
    beta = ("beta", request.form.get('beta', 0, type=float))
    mvalue_equity = ("mvalue_equity", request.form.get('mvalue_equity', 0,
                     type=float))
    weights = ("weights", request.form.get('weights', None, type=str))
    mylist = list([beta, mvalue_equity, weights])
    all_data = [{"name": item[0], "value": item[1]} for item in mylist]
    return jsonify(result=all_data)


""" PANEL.HTML """


@app.route('/panel', methods=['GET'])
def panel():
    if 'f' not in session:
        session['f'] = None

    filtered = True if session['f'] is not None else False

    crpJSf = db_data(session['f'])

    page_limit = 2
    current_page = int(request.args.get('current_page', 1))
    total = len(crpJSf)
    pages = range(1, int(math.ceil(total / page_limit)) + 1)

    crpJS = crpJSf[(current_page - 1)*page_limit:
                   ((current_page - 1)*page_limit) + page_limit]

    return render_template('panel.html', crpJS=crpJS,
                           crpJSonCl=crpJSf,
                           current_page=current_page, pages=pages,
                           regions=regions(), filtered=filtered)


""" FILTER.POST """


@app.route('/panel/filtering', methods=['POST'])
def filtering():
    session['f'] = None
    theOptions = request.form.getlist('region_options')
    if len(theOptions):
        session['f'] = dumps(theOptions)
    return redirect(url_for('panel'))


""" ADMIN.HTML """


@login.user_loader
def load_user(username):
    u = mongo.db.users.find_one({"user": username})
    if not u:
        return None
    return User(username=u['user'])


@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        user = mongo.db.users.find_one({"user": form.username.data})
        if user and User.check_password(user['pass'], form.password.data):
            user_obj = User(username=user['user'])
            login_user(user_obj)
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('file_insert')
                flash("You have succesfully logged in", "success")
            return redirect(next_page)
        else:
            flash("Invalid username or password", "danger")
    return render_template('admin.html', form=form)


@app.route('/admin/logout')
@login_required
def logout():
    logout_user()
    flash("You have succesfully logged out", "success")
    return redirect(url_for('index'))


""" FILE_INSERT.HTML """


@app.route('/admin/file_insert')
@login_required
def file_insert():
    return render_template('file_insert.html')


class Switcher(object):
    def __init__(self, dfd, dfFstCol):
        self.dfd = dfd
        self.dfdLen = len(dfd)
        self.dfFstCol = dfFstCol

    def strs_to_methods(self, argument):
        """Dispatch method"""
        method_name = 'method_' + str(argument)
        method = getattr(self, method_name, lambda: False)
        return method()

    """ Countries.csv """
    def method_countries(self):
        try:
            for i in range(0, self.dfdLen):
                mongo.db.countries.update({self.dfFstCol:
                                           self.dfd[i][self.dfFstCol]}, self.dfd[i], True)
            return True
        except Exception:
            return False

    """ Methods.csv """
    def method_methods(self):
        try:
            for i in range(0, self.dfdLen):
                mongo.db.methods.update({self.dfFstCol:
                                         self.dfd[i][self.dfFstCol]}, self.dfd[i], True)
            return True
        except Exception:
            return False

    """ years_qs.csv """
    def method_years_qs(self):
        try:
            for i in range(0, self.dfdLen):
                mongo.db.yearsqs.update({self.dfFstCol:
                                         self.dfd[i][self.dfFstCol]}, self.dfd[i], True)
            return True
        except Exception:
            return False

    """ erp_crp.csv """
    def method_erp_crp(self):
        try:
            for i in range(0, self.dfdLen):
                mongo.db.erpcrp.update({self.dfFstCol:
                                        self.dfd[i][self.dfFstCol]}, self.dfd[i], True)
            return True
        except Exception:
            return False

    """ remained methods country taxes, betas, risk free rates, weights """


@app.route('/admin/db_upload', methods=['POST'])
@login_required
def db_upload():
    files = request.files.getlist('db_file')
    if not files or not any(f for f in files):
        flash(" No File Chosen", "warning")
    else:
        for f in files:
            myFileYesExt = f.filename
            if myFileYesExt.endswith('csv'):
                df = pd.read_csv(f)
                dfFstCol = str(df.columns[0])
                dfd = df.to_dict(orient='records')
                MDBUpload = Switcher(dfd, dfFstCol)
                occured = MDBUpload.strs_to_methods(
                    myFileYesExt[:myFileYesExt.index('.csv')].lower())
                if occured:
                    flash(myFileYesExt + " Yes Inserted", "success")
                else:
                    flash(myFileYesExt + " Not Inserted", "danger")
            else:
                flash(myFileYesExt + " No Actions Taken", "warning")
    return redirect(url_for('file_insert'))


if __name__ == '__main__':
    app.run(host=os.environ.get('IP'), port=os.environ.get('PORT'), debug=True)
