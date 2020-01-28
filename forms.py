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
    weights = SelectField(
        'Risk Free Weighting',
        choices=[('100US', '100w US'),
                 ('40US60GE', '40w US - 60w GE'),
                 ("10US90GE", '10w US - 90w GE')]
    )
    country = SelectField('Country', choices=[])
    beta = FloatField('Beta', [InputRequired()], default=1.0)
    mvalue_equity = FloatField('Mkt Value Equity', default=0.0)
    yield_on_debt = PercentField('Yield On Debt', default=0.0)
    tax = FloatField('Tax', [InputRequired()], default=0.0)
    mvalue_debt = FloatField('Mkt Value Debt', default=0.0)
    submit = SubmitField('SUBMIT')

    def validate_beta(form, field):
        if field.data < 0:
            raise ValidationError("Negative beta not applied")
