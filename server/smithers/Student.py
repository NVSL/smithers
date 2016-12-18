from google.appengine.ext import ndb
from google.appengine.api import users
from smithers.util import build_list_spec, build_table_spec
import config
from util import DFC, Time
import Logging as log
from flask import redirect, url_for, request, flash, render_template, abort, Blueprint
from util import role_required, next_url
from Report import Report

from flask_wtf import FlaskForm

#import flask_login
from wtforms import StringField, PasswordField, HiddenField, TextAreaField, SubmitField
from wtforms_components import read_only
from wtforms.validators import DataRequired

student_ops = Blueprint("student_ops", __name__)
student_parent_key=ndb.Key("Student", "students")

class Student(ndb.Model):#, flask_login.UserMixin):
    """A main model for representing users."""
    username=ndb.StringProperty()
    email=ndb.StringProperty()
    full_name=ndb.StringProperty()
    userid= ndb.StringProperty()

    formatted_members = [
        DFC("urlsafe",
            display=lambda u: u.key.urlsafe(),
            show=False),
        DFC("full_name",
            display=lambda u: u.get_fullname(),
            ex_display="ANON",
            link=lambda u: u.get_admin_path()),
        DFC("username",
            display=lambda u: u.get_username(),
            ex_display="ANON",
            link=lambda u: u.get_admin_path()),
        DFC("email",
            link=lambda u: "mailto:{}".format(u.get_email())),
    ]

    def get_fullname(self):
        return self.full_name

    def get_admin_path(self):
        return url_for("student_ops.display_one_student", key=self.key.urlsafe())

    def delete_student(self):
        self.key.delete()

    @classmethod
    def get_student(self,id):
        r = None
        try:
            return ndb.Key(urlsafe=id).get()
        except:# ProtocolBufferDecodeError:
            return Student.query(Student.username == id or
                                 Student.email == id).get()


class DisplayReportForm(FlaskForm):
    long_term_goal = TextAreaField('Current Goal', validators=[DataRequired()])
    previous_weekly_goals = TextAreaField("Previous Weekly Goals")
    progress_made = TextAreaField('Weekly Progress', validators=[DataRequired()])
    problems_encountered = TextAreaField('Probems Encountered', validators=[DataRequired()])
    next_weekly_goals = TextAreaField('Next Weekly Goals', validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        super(DisplayReportForm, self).__init__(*args, **kwargs)
        read_only(self.previous_weekly_goals)

    def read_only(self):
        read_only(self.long_term_goal)
        read_only(self.previous_weekly_goals)
        read_only(self.progress_made)
        read_only(self.problems_encountered)
        read_only(self.next_weekly_goals)


class SubmitReportForm(DisplayReportForm):
    submit = SubmitField("Submit")


@student_ops.route('/report', methods=["POST",'GET'])
def submit_report():
    user = users.GetCurrentUser()

    form = SubmitReportForm()

    report_query = Report.query(Report.student == user.nickname()).order(Report.created)
    report_count = report_query.count()

    if form.validate_on_submit():
        report = Report()
        form.populate_obj(report)
        report.student = user.nickname()
        report.put()

        return redirect(url_for(".submit_report", index=report_count))
    else:
        if report_count > 0:
            reports = report_query.fetch()
            latest_report = reports[report_count - 1]
        else:
            latest_report = None
        print request.args

        index = int(request.args.get("index", report_count))
        log.info("{} {} {}".format(index, report_count, latest_report))

        if index == report_count:
            form = SubmitReportForm()
            if latest_report is not None:
                form.previous_weekly_goals.data = latest_report.next_weekly_goals
                form.next_weekly_goals.data = latest_report.next_weekly_goals
                form.long_term_goal.data = latest_report.long_term_goal
            is_new_report = True
            display_report = None
        elif index > report_count or index < 0:
            print "redirecting {} {}".format(index, report_count)
            return redirect(url_for(".submit_report"))
        else:
            display_report = reports[index]
            form = DisplayReportForm(obj=display_report)
            form.read_only()
            is_new_report = False


        if index >= report_count:
            next_report = None
        else:
            next_report = url_for(".submit_report", index=index + 1)

        if index <= 0:
            prev_report = None
        else:
            prev_report = url_for(".submit_report", index=index - 1)


        return render_template("new_report.html.jinja",
                               form=form,
                               is_new_report=is_new_report,
                               current_user=user,
                               next_report=next_report,
                               prev_report=prev_report,
                               the_report=display_report,
                               logout_trampoline=url_for(".logout"),
                               logout_url=users.CreateLogoutURL(url_for(".submit_report")))


@student_ops.route('/logout', methods=['POST'])
def logout():
    print
    return redirect(request.form['continue'])


class NewStudentForm(FlaskForm):
    email = StringField('E-mail', validators=[DataRequired()])
    full_name=StringField('Name', validators=[DataRequired()])

@student_ops.route("/student/op/create", methods=['POST', 'GET'])
def create():

    form = NewStudentForm()
    
    if form.validate_on_submit():
        existing = Student.query(
            Student.email == form['email'].data).get()
        if existing is not None:
            return "Student already exists a {}".format(str(existing))

        #username = form['username'].data
        email = form['email'].data
        full_name = form['full_name'].data

        student = Student(email=email, full_name=full_name)

        log.info("Creating student {}".format(student.email))
        student.put()
        return redirect(url_for("student_ops.display_all_students"))
    else:
        return render_template("new_student.html.jinja", form=form)

@student_ops.route("/student/")
@role_required(config.admin_role)
def display_all_students():

    # DFC("start vm",
    members = [m for m in Student.formatted_members]

    table = build_table_spec("students",
                             Student.query().fetch(),
                             members,
                             "username",
                             default_sort_reversed=True)
    return render_template("admin_student_list.html.jinja",
        userlist=table
    )

@student_ops.route("/student/<key>")
@role_required(config.admin_role)
def display_one_student(key):
    student = ndb.Key(urlsafe=key).get()

    build_spec = build_list_spec("student",
                                 student,
                                 Student.formatted_members)

    return render_template("admin_student.html.jinja",
        user_attrs = build_spec,
        user = student
    )
