from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, FloatField
from wtforms.validators import DataRequired, Optional, InputRequired
from wtforms.widgets import html5
from init_app import mongo

""" LOGIN """


class LoginForm(FlaskForm):
    """Login form to access writing and settings pages"""

    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


""" WACC """


def countries():
    myctrs = sorted(mongo.db.countries_i.distinct("COUNTRY",
                    {"COUNTRY": {"$nin": ["", "null", "Null", None]}}))
    return [(c, c) for c in myctrs]


def weights():
    mywts = mongo.db.weights_i.find({}, {"_id": 0, "WT": 1}).sort([("ID", 1)])
    return [(str(i+1), w['WT']) for i, w in enumerate(mywts)]


def betas():
    mybts = list(mongo.db.betas_i.aggregate([
        {"$project":
            {"INDUSTRY_ULBETA":
                {"$concat":
                    ["$INDUSTRY",
                     {"$cond": [{"$eq": ["$INDUSTRY", "Manual"]}, "", " | "]},
                     {"$cond": [{"$eq": ["$INDUSTRY", "Manual"]}, "",
                                {"$toString": "$UNLEVERED_BETA"}]}
                     ]
                 },
                "_id": 0,
                "ID": {"$toInt": "$ID"},
                "UNLEVERED_BETA": 1
             }
         }
    ]))
    return sorted([(b['ID'], b['INDUSTRY_ULBETA']) for b in mybts],
                  key=lambda x: x[0])


class PassSelectField(SelectField):
    def pre_validate(self, form):
        pass


class FlexiFloatField(FloatField):
    def process_formdata(self, valuelist):
        if valuelist:
            valuelist[0] = valuelist[0].replace(",", ".")
        return super(FlexiFloatField, self).process_formdata(valuelist)


class WACCForm(FlaskForm):
    weights = PassSelectField('Risk Free Weighting', choices=weights(),
                              default='1', coerce=str)
    country = SelectField('Country', choices=countries(), default=u'Greece',
                          coerce=str)
    beta = PassSelectField('Beta', choices=betas(), default='1', coerce=str)
    beta_manual = FlexiFloatField('Beta Manual', validators=[Optional()],
                                  default=None, render_kw={'disabled': ''},
                                  widget=html5.NumberInput(step=0.01))
    yield_on_debt = FlexiFloatField('Yield On Debt %',
                                    validators=[InputRequired()],
                                    default=0.0,
                                    render_kw={"placeholder": "%"},
                                    widget=html5.NumberInput(step=0.01))
    tax = FlexiFloatField('Tax %', validators=[InputRequired()],
                          default=0.0, render_kw={"placeholder": "%"},
                          widget=html5.NumberInput(min=0, max=100, step=0.1))
    mvalue_debt = FlexiFloatField('Mkt Value Debt',
                                  validators=[InputRequired()], default=0.0,
                                  widget=html5.NumberInput(step=0.001))
    mvalue_equity = FlexiFloatField('Mkt Value Equity',
                                    validators=[InputRequired()],
                                    default=0.0,
                                    widget=html5.NumberInput(step=0.001))
