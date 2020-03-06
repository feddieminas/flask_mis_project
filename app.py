import os
import pandas as pd
import math
if os.path.exists('env.py'):
    import env
from flask import Flask, render_template, redirect, request, url_for, session, flash, jsonify
from werkzeug.urls import url_parse
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from forms import LoginForm, WACCForm, betas
from bson.son import SON
from bson.json_util import dumps
from user import User
from init_app import app, csrf, mongo


""" forms """

login = LoginManager(app)
login.login_view = 'login'


""" custom template filters
@app.template_filter('conv_percents')
def percents(val):
    return "{0:.3f}%".format(val*100)
cr['ERP']|conv_percents
"""


""" custom functions no pipeline """


def regions():
    return sorted(mongo.db.countries_i.distinct("REGION",
                  {"COUNTRY": {"$nin": ["", "null", "Null", None]}}))


""" custom functions yes pipeline """


def db_erp_data():
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
                "from": "methods_i",
                "localField": "METHOD_ID",
                "foreignField": "ID",
                "as": "Methods"
            }
        },
        {"$unwind": "$Weights"},
        {"$unwind": "$Methods"},
        {
            "$project": {
                "WT": "$Weights.WT",
                "METHOD": "$Methods.METHOD",
                "CATEGORY": "$Methods.CATEGORY",
                "TYPE": "$Methods.TYPE",
                "ERP_PRICE": 1,
                "_id": 0
            }
        }
    ]

    data = list(mongo.db.erp_o.aggregate(pipeline))
    return data


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


def _p2f_or_na(val):
    return "NA" if val == "NA" else float(str(val).strip('%'))


def _conv_percent_or_na(val):
    return "NA" if math.isnan(val) else u"{0:.2f}%".format(val*100)


class wacc_settings:
    headers = {"DM_CDS_OFFICIAL": "td1", "DM_CDS_CUSTOM": "td2",
               "DP_YIELD_OFFICIAL": "td3", "DM_RATING_OFFICIAL": "td4",
               "DM_RATING_CUSTOM": "td5", "DP_RATING_OFFICIAL": "td6"}
    total_rows = 17


def _wacc_calc_data(inputData, tax=None):
    """
    if the input data is a list of dictionaries, it comes from the
    default loaded index() country Greece. If we have a list of tuples,
    it comes from the updated wacc_nums().
    """
    if isinstance(inputData[0], tuple):
        wts = db_weights_data()
    else:
        # insert the defaults for Greece (list of tuples) as inputData
        # variable.
        wts = inputData[:]
        inputData = [('weights', '100US'), ('country', 'Greece'),
                     ('beta', 'No Industry | 1'), ('beta_manual', None),
                     ('yield_on_debt', 1.0), ('tax', tax),
                     ('mvalue_debt', 1.0), ('mvalue_equity', 1.0)]
    filt_wts = list(filter(lambda c: c['WT'].upper() == inputData[0][1], wts))
    wacc_data = []
    for i in range(wacc_settings.total_rows):
        wacc_data.append({"td1": None, "td2": None, "td3": None,
                          "td4": None, "td5": None, "td6": None})
    """ Weight RF Rate (A) """
    for w in filt_wts:
        wacc_data[0][wacc_settings.headers[str(w["METHOD"].upper()
                     + "_" + w["CATEGORY"].upper()
                     + "_" + w["TYPE"].upper())]] = _conv_percent_or_na(
                         w["WT_PRICE"])
    """ Unlevered Industry Beta """
    beta = float(inputData[3][1]) if inputData[2][1] == "Manual" else float(
        inputData[2][1].split("|")[1].strip())
    wacc_data[1] = {key: beta for key in wacc_data[1]}
    """ Levered Beta (B), calc at the end """
    wacc_data[2] = {key: 1 for key in wacc_data[2]}
    """ ERP (C) """
    filt_erps = list(filter(lambda e: e['WT'].upper() == inputData[0][1]
                            or e['METHOD'].upper() == 'DM', db_erp_data()))
    for e in filt_erps:
        wacc_data[3][wacc_settings.headers[str(e["METHOD"].upper()
                     + "_" + e["CATEGORY"].upper()
                     + "_" + e["TYPE"].upper())]] = _conv_percent_or_na(
                         e["ERP_PRICE"])
    wacc_data[3]["td4"], wacc_data[3]["td5"] = wacc_data[3]["td1"], wacc_data[3]["td2"]
    """ BASE COE (A + B * C), calc at the end """
    wacc_data[4] = {key: 1 for key in wacc_data[4]}
    """ CRP (D) """
    filt_crps = list(filter(lambda e:
                     e['COUNTRY'].upper() == inputData[1][1].upper(),
                            db_data()))
    for e in filt_crps:
        wacc_data[5][wacc_settings.headers[str(e["METHOD"].upper()
                     + "_" + e["CATEGORY"].upper()
                     + "_" + e["TYPE"].upper())]] = _conv_percent_or_na(
                         e["CRP_PRICE"])
    """ Int. COE (A + B * C) + (D), calc at the end """
    """ Mkt Equity Val (CUR, MM) """
    wacc_data[7] = {key: inputData[7][1] for key in wacc_data[7]}
    """ Enterprise Val (%), calc at the end """
    wacc_data[8] = {key: 1 for key in wacc_data[8]}
    """ Pre Tax Cost of Debt (%) """
    wacc_data[9] = {key: _conv_percent_or_na(float(inputData[4][1])/100)
                    for key in wacc_data[9]}
    """ After Tax Cost of Debt (%) """
    wacc_data[10] = {key: _conv_percent_or_na(((inputData[4][1])
                     * (1-(float(inputData[5][1])/100)))/100)
                     for key in wacc_data[10]}
    """ Mkt Val of Debt (CUR, MM) """
    wacc_data[11] = {key: inputData[6][1] for key in wacc_data[11]}
    """ Enterprise Val (%), calc at the end """
    wacc_data[12] = {key: 1 for key in wacc_data[12]}
    """ Enterprise Val (CUR, MM) """
    wacc_data[13] = {key: float(wacc_data[7][key] + wacc_data[11][key])
                     for key in wacc_data[13]}
    """ Enterprise Val (%) """
    wacc_data[14] = {key: 1 for key in wacc_data[14]}
    for i in range(len(wacc_data[14])):
        a = _p2f_or_na(wacc_data[13]["td" + str(i+1)])
        if isinstance(a, str):
            wacc_data[14]["td" + str(i+1)] = "NA"
        else:
            wacc_data[14]["td" + str(i+1)] = _conv_percent_or_na(
                    a/wacc_data[14]["td" + str(i+1)]
                    if a == 0 else a/a)  # zero-division-error issue
    """ Debt to Equity Ratio (%) """
    wacc_data[15] = {key: 1 for key in wacc_data[15]}
    wacc_data[15] = {key: _conv_percent_or_na(
        float(wacc_data[11][key] / wacc_data[15][key] if
              wacc_data[7][key] == 0 else
              wacc_data[11][key] / wacc_data[7][key]))
              for key in wacc_data[15]}  # zero-division-error issue
    """ Remained Calcs from above """
    for i in range(len(wacc_data[2])):  # Levered Beta (B)
        a = _p2f_or_na(wacc_data[15]["td" + str(i+1)])/100
        wacc_data[2]["td" + str(i+1)] = round(wacc_data[1]["td" + str(i+1)] * (
            1+(1-float(inputData[5][1])/100) * a), 2)
    for i in range(len(wacc_data[4])):  # BASE COE (A + B * C)
        a, b = _p2f_or_na(wacc_data[0]["td" + str(i+1)])/100, _p2f_or_na(
            wacc_data[3]["td" + str(i+1)])/100
        wacc_data[4]["td" + str(i+1)] = _conv_percent_or_na(a + (
            wacc_data[2]["td" + str(i+1)] * b))
    for i in range(len(wacc_data[6])):  # Int. COE (A + B * C) + (D)
        a, b = _p2f_or_na(wacc_data[4]["td" + str(i+1)]), _p2f_or_na(
            wacc_data[5]["td" + str(i+1)])
        if any([isinstance(a, str), isinstance(b, str)]):
            wacc_data[6]["td" + str(i+1)] = "NA"
        else:
            wacc_data[6]["td" + str(i+1)] = _conv_percent_or_na((a + b)/100)
    for i in range(len(wacc_data[8])):  # Enterprise Val (%)
        a, b = wacc_data[7]["td" + str(i+1)], wacc_data[13]["td" + str(i+1)]
        if any([isinstance(a, str), isinstance(b, str)]):
            wacc_data[8]["td" + str(i+1)] = "NA"
        else:
            wacc_data[8]["td" + str(i+1)] = _conv_percent_or_na(
                a/wacc_data[8]["td" + str(i+1)] if b == 0 else a / b)
    for i in range(len(wacc_data[12])):  # Enterprise Val (%)
        a, b = wacc_data[11]["td" + str(i+1)], wacc_data[13]["td" + str(i+1)]
        if any([isinstance(a, str), isinstance(b, str)]):
            wacc_data[12]["td" + str(i+1)] = "NA"
        else:
            wacc_data[12]["td" + str(i+1)] = _conv_percent_or_na(
              a/wacc_data[12]["td" + str(i+1)] if b == 0 else a / b)
    """ WACC """
    for i in range(len(wacc_data[16])):
        a, b, c, d = _p2f_or_na(wacc_data[6]["td" + str(i+1)])/100, _p2f_or_na(
            wacc_data[8]["td" + str(i+1)])/100, _p2f_or_na(
                wacc_data[10]["td" + str(i+1)])/100, _p2f_or_na(
                    wacc_data[12]["td" + str(i+1)])/100
        if any([isinstance(a, str), isinstance(b, str),
                isinstance(c, str), isinstance(d, str)]):
            wacc_data[16]["td" + str(i+1)] = "NA"
        else:
            wacc_data[16]["td" + str(i+1)] = _conv_percent_or_na(
                (a * b) + (c * d))
    return wacc_data  # want to make it list of dicts


""" INDEX.HTML """


@app.route('/', methods=['GET'])
def index():
    form = WACCForm()
    taxJSf = db_tax_data()  # mylistOfDict
    default_tax = "{0:.1f}".format(
                   float(list(filter(lambda c: c['COUNTRY'].upper()
                              in 'GREECE', taxJSf))[0]['TAX'] * 100))
    wts = db_weights_data()
    dts = {}  # my dates to insert at the headers
    sources = set({'DM_OFFICIAL', 'DM_CUSTOM', 'DP_OFFICIAL'})
    for w in wts:
        if w['METHOD'] + "_" + w['TYPE'].upper() in sources:
            dts.update({w['METHOD'] + "_" + w['TYPE'].upper():
                        _my_period_set(w['TYPE'], w['DYEAR'],
                        w['DMONTH'], w['DDAY'])})
            sources.remove(w['METHOD'] + "_" + w['TYPE'].upper())
    """
    wacc function retrieve data for Greece of No Industry | 1
    and weight 100US
    """
    wacc_data = _wacc_calc_data(wts, default_tax)
    return render_template('index.html', form=form, taxJSonCl=taxJSf,
                           dts=dts, default_tax=default_tax,
                           wacc_data=wacc_data)


""" WACC.JSON """


@app.route('/_wacc_nums', methods=['POST'])
def wacc_nums():
    form = WACCForm(item=request.get_json())
    mylistOfTup = []
    if form.validate_on_submit():
        for key, value in form.data.items():
            if any(k == key for k in ["weights", "country", "beta"]):
                mylistOfTup.append((key, str(value)))
            elif (key == 'csrf_token'):
                continue
            else:
                if key == "beta_manual":
                    value = 0 if str(form.beta.data) == "Manual" and value in ['', None] else value
                else:
                    value = 0 if value in ['', None] else value
                mylistOfTup.append((key, None if value is None
                                    else float(value)))
        """
        wacc function retrieve data for selected country
        of tuples
        """
        wacc_data = _wacc_calc_data(mylistOfTup)
        return jsonify(wacc_data=wacc_data)
    else:
        return jsonify(wacc_data=None)


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
                           regions=regions(), betas=betas()[1:],
                           filtered=filtered)


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

Upload a csv file (or multiple) with a specific name (as method arg)
and an extension of _ and eight value secret key, which
you define on env vars. We reset the collection and insert
the new ones. Two approaches were shown below, insert_one and
insert_many. Equally all approaches can go to different methods. 

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
            mongo.db.countries_i.delete_many({"ID": {"$gte": 0}})
            for i in range(0, self.dfdLen):
                mongo.db.countries_i.insert_one(self.dfd[i])
            return True
        except Exception:
            return False

    """ methods_i.csv """
    def method_methods_i(self):
        try:
            mongo.db.methods_i.delete_many({"ID": {"$gte": 0}})
            for i in range(0, self.dfdLen):
                mongo.db.methods_i.insert_one(self.dfd[i])
            return True
        except Exception:
            return False

    """ yearqm_i.csv """
    def method_yearqm_i(self):
        try:
            mongo.db.yearqm_i.delete_many({"ID": {"$gte": 0}})
            for i in range(0, self.dfdLen):
                mongo.db.yearqm_i.insert_one(self.dfd[i])
            return True
        except Exception:
            return False

    """ betas_i.csv """
    def method_betas_i(self):
        try:
            mongo.db.betas_i.delete_many({"ID": {"$gte": 0}})
            for i in range(0, self.dfdLen):
                mongo.db.betas_i.insert_one(self.dfd[i])
            return True
        except Exception:
            return False

    """ weights_i.csv """
    def method_weights_i(self):
        try:
            mongo.db.weights_i.delete_many({"ID": {"$gte": 0}})
            for i in range(0, self.dfdLen):
                mongo.db.weights_i.insert_one(self.dfd[i])
            return True
        except Exception:
            return False

    """ taxes_o.csv """
    def method_taxes_o(self):
        try:
            mongo.db.taxes_o.delete_many({"COUNTRY_ID": {"$gte": 0}})
            mongo.db.taxes_o.insert_many(self.dfd)
            return True
        except Exception:
            return False

    """ weights_o.csv """
    def method_weights_o(self):
        try:
            mongo.db.weights_o.delete_many({"WT_ID": {"$gte": 0}})
            mongo.db.weights_o.insert_many(self.dfd)
            return True
        except Exception:
            return False

    """ erp_o.csv """
    def method_erp_o(self):
        try:
            mongo.db.erp_o.delete_many({"WT_ID": {"$gte": 0}})
            mongo.db.erp_o.insert_many(self.dfd)
            return True
        except Exception:
            return False

    """ riskfree_o.csv """
    def method_riskfree_o(self):
        try:
            mongo.db.riskfree_o.delete_many({"COUNTRY_ID": {"$gte": 0}})
            mongo.db.riskfree_o.insert_many(self.dfd)
            return True
        except Exception:
            return False

    """ crp_o.csv """
    def method_crp_o(self):
        try:
            mongo.db.crp_o.delete_many({"COUNTRY_ID": {"$gte": 0}})
            mongo.db.crp_o.insert_many(self.dfd)
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
                df = pd.read_csv(f, sep=';')
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
