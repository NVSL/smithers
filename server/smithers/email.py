import datetime
from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import mail

import config
from util import DFC
import Logging as log
from flask import redirect, url_for, request, render_template, Blueprint
from util import next_url, localize_time
from Report import Report
from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, TextAreaField, SubmitField, BooleanField
from wtforms_components import read_only
from wtforms.validators import InputRequired, Email, Optional

email_ops = Blueprint("email", __name__)

class EmailForm(FlaskForm):
    to_field = StringField("To", validators=[Email(),InputRequired()])
    bcc_field = StringField("Bcc", validators=[Optional(), Email()])
    cc_field =  StringField("CC", validators=[Optional(), Email()])
    subject =   StringField("Subject", validators=[InputRequired()])
    message = TextAreaField("Message")
    submit = SubmitField()

@email_ops.route("/email/", methods=['GET', 'POST'])
def email():
    form = EmailForm(request.form)

    if request.method == "POST" and form.validate():

        def emtpty_is_none(s, default=None):
            if s.strip() == "":
                return default
            else:
                return s

        t = dict(sender=config.admin_email_sender,
                 to=form.to_field.data,
                 cc=emtpty_is_none(form.cc_field.data),
                 bcc=emtpty_is_none(form.bcc_field.data),
                 subject=form.subject.data,
                 body=form.message.data)

        t = {k:v for (k,v) in t.items() if v is not None}

        email = mail.EmailMessage(**t)
        email.send()
        return redirect(url_for(".email"))
    else:
        return render_template("send_email.jinja.html",
                               form=form)
