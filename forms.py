from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, FloatField
from wtforms import SubmitField
from wtforms.validators import DataRequired, InputRequired, ValidationError

""" LOGIN """


class LoginForm(FlaskForm):
    """Login form to access writing and settings pages"""

    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


class PercentField(FloatField):
    def process_formdata(self, value):
        if value is None:
            self.data = value.strip('%').replace(',', '.')
        else:
            self.data = 0
        super(PercentField).process_formdata(self.data)


class WACCForm(FlaskForm):
    weights = SelectField('Risk Free Weighting', choices=[], default='100US')
    country = SelectField('Country', choices=[], default='Greece')
    beta = SelectField('Beta', choices=[], default='No Industry | 1')
    mvalue_equity = FloatField('Mkt Value Equity', default=0.000)
    yield_on_debt = PercentField('Yield On Debt', default=0.000)
    tax = FloatField('Tax', [InputRequired()], default=0.00)
    mvalue_debt = FloatField('Mkt Value Debt', default=0.000)
    submit = SubmitField('SUBMIT')

    def validate_beta(form, field):
        if field.data < 0:
            raise ValidationError("Negative beta not applied")
