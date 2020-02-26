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
from flask_wtf.csrf import CSRFProtect


app = Flask(__name__)
csrf = CSRFProtect(app)

app.config["MONGO_DBNAME"] = 'COE'
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.config["SECRET_KEY"] = os.urandom(16)

mongo = PyMongo(app)


""" forms """

login = LoginManager(app)
login.login_view = 'login'


""" custom functions no pipeline """


def weights():
    return sorted(mongo.db.weights_i.distinct("WT"))


def countries():
    return sorted(mongo.db.countries_i.distinct("COUNTRY"))


def regions():
    return sorted(mongo.db.countries_i.distinct("REGION"))


""" custom functions yes pipeline """


def betas():
    return list(mongo.db.betas_i.aggregate([
        {"$project": {"INDUSTRY_ULBETA": {"$concat":
         ["$INDUSTRY", " | ", {"$toString": "$UNLEVERED_BETA"}]},
         "_id": 0, "INDUSTRY": 1, "UNLEVERED_BETA": 1}}
    ]))


def db_weights_data():
    pipeline = [
        {
            "$lookup": {
                "from": "weights_i",
                "localField": "WT_ID",
                "foreignField": "ID",
                "as": "Weights"
            }
        },
        {
            "$lookup": {
                "from": "yearqm_i",
                "localField": "YEARQM_ID",
                "foreignField": "ID",
                "as": "YearQM"
            }
        },
        {
            "$lookup": {
                "from": "methods_i",
                "localField": "METHOD_ID",
                "foreignField": "ID",
                "as": "Methods"
            }
        },
        {"$unwind": "$Weights"},
        {"$unwind": "$YearQM"},
        {"$unwind": "$Methods"},
        {
            "$project": {
                "DYEAR": "$YearQM.DYEAR",
                "DMONTH": "$YearQM.DMONTH",
                "DDAY": 1,
                "WT": "$Weights.WT",
                "METHOD": "$Methods.METHOD",
                "CATEGORY": "$Methods.CATEGORY",
                "TYPE": "$Methods.TYPE",
                "WT_PRICE": 1,
                "_id": 0
            }
        }
    ]

    data = list(mongo.db.weights_o.aggregate(pipeline))
    return data


def db_tax_data():
    pipeline = [
        {
            "$lookup": {
                "from": "countries_i",
                "localField": "COUNTRY_ID",
                "foreignField": "ID",
                "as": "Country"
            }
        },
        {"$unwind": "$Country"},
        {
            "$project": {
                "COUNTRY": "$Country.COUNTRY",
                "TAX": 1,
                "_id": 0
            }
        },
        {"$sort": SON([("COUNTRY", 1)])}
    ]

    data = list(mongo.db.taxes_o.aggregate(pipeline))
    return data


def db_data(filtering=None):
    pipeline = [
        {
            "$lookup": {
                "from": "countries_i",
                "localField": "COUNTRY_ID",
                "foreignField": "ID",
                "as": "Country"
            }
        },
        {
            "$lookup": {
                "from": "yearqm_i",
                "localField": "YEARQM_ID",
                "foreignField": "ID",
                "as": "YearQM"
            }
        },
        {
            "$lookup": {
                "from": "methods_i",
                "localField": "METHOD_ID",
                "foreignField": "ID",
                "as": "Methods"
            }
        },
        {"$unwind": "$Country"},
        {"$unwind": "$YearQM"},
        {"$unwind": "$Methods"},
        {
            "$project": {
                "DYEAR": "$YearQM.DYEAR",
                "DMONTH": "$YearQM.DMONTH",
                "DDAY": 1,
                "COUNTRY": "$Country.COUNTRY",
                "REGION": "$Country.REGION",
                "METHOD": "$Methods.METHOD",
                "CATEGORY": "$Methods.CATEGORY",
                "TYPE": "$Methods.TYPE",
                "CRP_PRICE": 1,
                "_id": 0
            }
        },
        {"$sort": SON([("COUNTRY", 1), ("METHOD", 1), ("CATEGORY", 1)])}
    ]

    data = list(mongo.db.crp_o.aggregate(pipeline))
    if bool(filtering):
        theRegions = regions()
        filtering = {theRegions[int(f)-1] for f in filtering if f.isdigit()}
        data = [x for x in _filterbyvalue(data, filtering)]
    return data


def _filterbyvalue(seq, values):
    for el in seq:
        for v in values:
            if any([bool(el["COUNTRY"] == v), bool(el["REGION"] == v),
                    bool(el["METHOD"] == v)]):
                yield el


def _my_period_set(cr_type, y_val, m_val, d_val):
    mdict = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
                5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
                9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
    if cr_type == "Official":
        return "{} {}".format(mdict[int(m_val)], str(y_val)[2:])
    else:
        return "{} {} {}".format(d_val, mdict[int(m_val)], str(y_val)[2:])
    return


def _conv_percent_or_na(val):
    return "NA" if math.isnan(val) else u"{0:.3f}%".format(val*100)


def _wacc_calc_data(inputData):
    """
    if the input data is a list of dictionaries, it comes from the
    default loaded index() country Greece. If we have a list of tuples,
    it comes from the updated wacc_nums().
    """
    test = False
    if isinstance(inputData[0], tuple):
        wts = db_weights_data()
        test = True
    return test


""" INDEX.HTML """


@app.route('/', methods=['GET'])
def index():
    form = WACCForm()
    form.weights.choices = [(w, w) for w in weights()]
    form.country.choices = [(c, c) for c in countries()]
    form.beta.choices = [(b['INDUSTRY'],
                          b['INDUSTRY_ULBETA']) for b in betas()]
    taxJSf = db_tax_data()  # mylistOfDict
    wts = db_weights_data()
    print(isinstance(wts[0], dict), type(wts[0]))
    dts = {}  # my dates to insert at the headers
    sources = set({'DM_OFFICIAL', 'DM_CUSTOM', 'DP_OFFICIAL'})
    for w in wts:
        if w['METHOD'] + "_" + w['TYPE'].upper() in sources:
            dts.update({w['METHOD'] + "_" + w['TYPE'].upper():
                        _my_period_set(w['TYPE'], w['DYEAR'],
                        w['DMONTH'], w['DDAY'])})
            sources.remove(w['METHOD'] + "_" + w['TYPE'].upper())
    """
    # wacc function retrieve data for Greece of No Industry | 1
    # and weight 100US
    print(_wacc_calc_data(wts))  # will return to False
    """
    return render_template('index.html', form=form, taxJSonCl=taxJSf,
                           dts=dts)


""" WACC.JSON """


@app.route('/_wacc_nums', methods=['POST'])
def wacc_nums():
    weight = ("weight", request.form.get('weight', None, type=str))
    country = ("country", request.form.get('country', None, type=str))
    beta = ("beta", request.form.get('beta', 'No Industry | 1', type=str))
    yield_on_debt = ("yield_on_debt", request.form.get('yield_on_debt', 0,
                     type=float))
    tax = ("tax", request.form.get('tax', 0, type=float))
    mvalue_debt = ("mvalue_debt", request.form.get('mvalue_debt', 0,
                   type=float))
    mvalue_equity = ("mvalue_equity", request.form.get('mvalue_equity', 0,
                     type=float))
    mylistOfTup = list([weight, country, beta,
                        yield_on_debt, tax, mvalue_debt, mvalue_equity])
    print(isinstance(mylistOfTup[0], tuple), type(mylistOfTup[0]))
    """
    # wacc function retrieve data for selected country
    # of tuples [('weight', '100US'), ('country', 'Greece'),
    # ('beta', 'No Industry'), ('yield_on_debt', 0.0),
    # ('tax', 0.0), ('mvalue_debt', 0.0), ('mvalue_equity', 0.0)]
    print(_wacc_calc_data(mylistOfTup))  # will return to True
    """
    all_data = [{"name": item[0], "value": item[1]} for item in mylistOfTup]
    print(type(all_data), type(all_data[0]))  # class list, class dict
    return jsonify(result=all_data)


""" PANEL.HTML """


@app.route('/panel', methods=['GET'])
def panel():
    if 'f' not in session:
        session['f'] = None

    filtered = True if session['f'] is not None else False

    crpJSf = db_data(session['f'])

    for cr in crpJSf:
        cr['PERIOD'] = _my_period_set(cr['TYPE'], cr['DYEAR'],
                                      cr['DMONTH'], cr['DDAY'])
        cr['CRP_PRICE'] = _conv_percent_or_na(cr['CRP_PRICE'])

    page_limit = 25
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


""" FILE_INSERT.HTML

Approach as been that when the first column of each parsed CSV
has distinct numbers, I use the replace_one with upsert true, as
it auto replace and inserts updated values. When I do not have the
first column with distinct values, but rather a group of columns,
I reset the collection and insert the many documents, my updated ones.
Should I have had lots of rows, my approach would have been different rather
than the mentioned one.
The second a approach (remove and insert) could also be used instead of replace_one.
Another approach would have been to use the deprecated
update function to all (instead of replace_one function and same args), where
its functionality covers both of the above two methods.

"""


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

    """ countries_i.csv """
    def method_countries_i(self):
        try:
            for i in range(0, self.dfdLen):
                mongo.db.countries_i.replace_one({self.dfFstCol:
                                                 self.dfd[i][self.dfFstCol]},
                                                 self.dfd[i], True)
            return True
        except Exception:
            return False

    """ methods_i.csv """
    def method_methods_i(self):
        try:
            for i in range(0, self.dfdLen):
                mongo.db.methods_i.replace_one({self.dfFstCol:
                                               self.dfd[i][self.dfFstCol]},
                                               self.dfd[i], True)
            return True
        except Exception:
            return False

    """ yearqm_i.csv """
    def method_yearqm_i(self):
        try:
            for i in range(0, self.dfdLen):
                mongo.db.yearqm_i.replace_one({self.dfFstCol:
                                              self.dfd[i][self.dfFstCol]},
                                              self.dfd[i], True)
            return True
        except Exception:
            return False

    """ betas_i.csv """
    def method_betas_i(self):
        try:
            for i in range(0, self.dfdLen):
                mongo.db.betas_i.replace_one({self.dfFstCol:
                                             self.dfd[i][self.dfFstCol]},
                                             self.dfd[i], True)
            return True
        except Exception:
            return False

    """ weights_i.csv """
    def method_weights_i(self):
        try:
            for i in range(0, self.dfdLen):
                mongo.db.weights_i.replace_one({self.dfFstCol:
                                               self.dfd[i][self.dfFstCol]},
                                               self.dfd[i], True)
            return True
        except Exception:
            return False

    """ taxes_o.csv """
    def method_taxes_o(self):
        try:
            for i in range(0, self.dfdLen):
                mongo.db.taxes_o.replace_one({self.dfFstCol:
                                             self.dfd[i][self.dfFstCol]},
                                             self.dfd[i], True)
            return True
        except Exception:
            return False

    """ weights_o.csv """
    def method_weights_o(self):
        try:
            mongo.db.weights_o.remove({})
            for i in range(0, self.dfdLen):
                mongo.db.weights_o.insert_one(self.dfd[i])
            return True
        except Exception:
            return False

    """ erp_o.csv """
    def method_erp_o(self):
        try:
            mongo.db.erp_o.remove({})
            for i in range(0, self.dfdLen):
                mongo.db.erp_o.insert_one(self.dfd[i])
            return True
        except Exception:
            return False

    """ riskfree_o.csv """
    def method_riskfree_o(self):
        try:
            mongo.db.riskfree_o.remove({})
            for i in range(0, self.dfdLen):
                mongo.db.riskfree_o.insert_one(self.dfd[i])
            return True
        except Exception:
            return False

    """ crp_o.csv """
    def method_crp_o(self):
        try:
            mongo.db.crp_o.remove({})
            for i in range(0, self.dfdLen):
                mongo.db.crp_o.insert_one(self.dfd[i])
            return True
        except Exception:
            return False


@app.route('/admin/db_upload', methods=['POST'])
@login_required
def db_upload():
    files = request.files.getlist('db_file')
    if not files or not any(f for f in files):
        flash(" No File Chosen", "warning")
    else:
        f_secret = str(os.environ.get("file_secret"))
        for f in files:
            myFileYesExt = f.filename
            if myFileYesExt.endswith('csv') and f_secret in myFileYesExt:
                df = pd.read_csv(f)
                dfFstCol = str(df.columns[0])
                dfd = df.to_dict(orient='records')
                MDBUpload = Switcher(dfd, dfFstCol)
                myFileYesExt = myFileYesExt[:myFileYesExt.index("_" +
                                            f_secret)].lower()
                occured = MDBUpload.strs_to_methods(myFileYesExt)
                if occured:
                    flash(myFileYesExt + " Yes Inserted", "success")
                else:
                    flash(myFileYesExt + " Not Inserted", "danger")
            else:
                flash(myFileYesExt + " No Actions Taken", "warning")
    return redirect(url_for('file_insert'))


if __name__ == '__main__':
    app.run(host=os.environ.get('IP'), port=os.environ.get('PORT'), debug=True)
