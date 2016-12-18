from google.appengine.ext import ndb
from google.appengine.api import users
from smithers.util import build_list_spec, build_table_spec
import config
from util import DFC, Time
import Logging as log
from flask import redirect, url_for, render_template,Blueprint
from util import role_required, next_url

from flask_wtf import FlaskForm

# import flask_login
from wtforms import StringField, PasswordField, HiddenField, TextAreaField, SubmitField
from wtforms.validators import DataRequired

report_ops = Blueprint("report_ops", __name__)
report_parent_key = ndb.Key("Report", "reports")

class Report(ndb.Model):
    """A main model for representing users."""
    created = ndb.DateTimeProperty(auto_now_add=True)

    long_term_goal = ndb.TextProperty()
    previous_weekly_goals = ndb.TextProperty()
    progress_made  = ndb.TextProperty()
    problems_encountered = ndb.TextProperty()
    next_weekly_goals = ndb.TextProperty()

    student = ndb.StringProperty()

    formatted_members = [
        Time("created"),
        DFC("current_goal"),
        DFC("progress_made"),
        DFC("problems_encountered"),
        DFC("next_tasks")
    ]

    def delete(self):
        self.key.delete()


class ReportForm(FlaskForm):
    long_term_goal = TextAreaField('Current Goal', validators=[DataRequired()])
    previous_weekly_goals = TextAreaField("Previous Weekly Goals", validators=[DataRequired()])
    progress_made = TextAreaField('Weekly Progress', validators=[DataRequired()])
    problems_encountered = TextAreaField('Probems Encountered', validators=[DataRequired()])
    next_weekly_goals = TextAreaField('Next Weerly Goals', validators=[DataRequired()])
    submit = SubmitField("Submit")

@report_ops.route("/report/op/create", methods=['POST', 'GET'])
def create():
    form = ReportForm()

    if form.validate_on_submit():
        report = Report()
        form.populate_obj(report)
        report.put()

        return redirect(url_for("report_ops.display_all_reports"))
    else:
        return render_template("new_report.html.jinja", form=form)


@report_ops.route("/report/")
@role_required(config.admin_role)
def display_all_reports():
    # DFC("start vm",
    members = [m for m in Report.formatted_members]

    table = build_table_spec("reports",
                             Report.query().fetch(),
                             members,
                             "username",
                             default_sort_reversed=True)
    return render_template("admin_report_list.html.jinja",
                           userlist=table
                           )


@report_ops.route("/report/<key>")
@role_required(config.admin_role)
def display_one_report(key):
    report = ndb.Key(urlsafe=key).get()

    build_spec = build_list_spec("report",
                                 report,
                                 Report.formatted_members)

    return render_template("admin_report.html.jinja",
                           user_attrs=build_spec,
                           user=report
                           )
