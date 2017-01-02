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
from wtforms.validators import InputRequired, Email


student_ops = Blueprint("student_ops", __name__)
student_parent_key=ndb.Key("Student", "students")

class WhiteList(ndb.Model):
    authorized_users = ndb.TextProperty()

    @classmethod
    def get_list(cls):
        white_list = ndb.Key(WhiteList, "whitelist").get()

        if white_list is None:
            white_list = WhiteList(id="whitelist")
            white_list.authorized_users=config.admin_email
            white_list.put()

        return white_list

    def is_whitelisted(self, email):
        return email.upper() in map(lambda x: x.strip().upper(),
                                    self.authorized_users.split("\n"))


    def remove_from_whitelist(self, email, put=True):
        emails = self.authorized_users.split("\n")
        emails = [e for e in emails if e != email]
        self.authorized_users = "\n".join(emails)
        if put:
            self.put()


    def add_to_whitelist(self, email, put=True):
        self.remove_from_whitelist(email,put=False)
        emails = self.authorized_users.split("\n") + [email]
        self.authorized_users = "\n".join(emails)
        if put:
            self.put()

class Student(ndb.Model):
    """A main model for representing users."""
    username = ndb.StringProperty()
    email = ndb.StringProperty()
    full_name = ndb.StringProperty()
    userid = ndb.StringProperty()

    last_signed_expectations_agreement = ndb.DateTimeProperty()

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

    def nickname(self):
        return self.email

    @classmethod
    def get_student(self,id):
        try:
            return ndb.Key(urlsafe=id).get()
        except:# ProtocolBufferDecodeError:
            return Student.query(Student.username == id or
                                 Student.email == id).get()

    @classmethod
    def get_current_student(cls):
        user = users.GetCurrentUser()

        student = ndb.Key("Student", "students",
                          Student, user.user_id()).get()

        if student is None:
            if users.is_current_user_admin() or WhiteList.get_list().is_whitelisted(user.email()):
                WhiteList.get_list().remove_from_whitelist(user.email())
                log.info("Creating student entity for user: {}".format(user))
                student = Student(parent=student_parent_key,
                                  id=user.user_id(),
                                  email=user.email(),
                                  userid=user.user_id(),
                                  username=user.email().split("@")[0])
                student.put()
            else:
                raise Exception("Unauthorized email address")
        return student


class DisplayReportForm(FlaskForm):
    long_term_goal = TextAreaField('Current Goal', validators=[InputRequired()])
    disp_previous_weekly_goals = TextAreaField("Previous Weekly Goals")
    previous_weekly_goals = HiddenField()
    progress_made = TextAreaField('Weekly Progress', validators=[InputRequired()])
    problems_encountered = TextAreaField('Probems Encountered', validators=[InputRequired()])
    next_weekly_goals = TextAreaField('Next Weekly Goals', validators=[InputRequired()])
    submit = SubmitField("Submit")

    def __init__(self, *args, **kwargs):
        super(DisplayReportForm, self).__init__(*args, **kwargs)
        read_only(self.disp_previous_weekly_goals)

    def read_only(self):
        read_only(self.long_term_goal)
        read_only(self.disp_previous_weekly_goals)
        read_only(self.progress_made)
        read_only(self.problems_encountered)
        read_only(self.next_weekly_goals)
        del self.submit


class UpdateUserForm(FlaskForm):
    full_name = StringField("Full Name", validators=[InputRequired()])
    email = StringField("Email")
    submit = SubmitField("Submit")

    def __init__(self, *args, **kwargs):
        super(UpdateUserForm, self).__init__(*args, **kwargs)
        read_only(self.email)


@student_ops.route("/user/update/", methods=['GET', 'POST'])
def update_user():
    student = Student.get_current_student()
    form = UpdateUserForm(request.form)
    log.info("updating student {}: {}".format(student.email, request.form))

    if request.method == "POST" and form.validate():
        log.info("update user: {}".format(student.email))
        form.populate_obj(student)
        student.put()
        return redirect(next_url(url_for(".submit_report")))
    else:
        form.full_name.data = student.full_name
        form.email.data = student.email
        return render_template("update_user.jinja.html",
                               form=form)


@student_ops.route("/student/<student>")
def browse_report(student):
    s = Student.get_student(student)
    return view_or_enter_reports(s, default_to_submission=False)

class Requirement(object):

    def __init__(self):
        super(Requirement, self).__init__()
        self.next_url = None

    def do_redirect(self, student, next_url=None):
        if next_url is None:
            next_url = request.full_path
        self.next_url = next_url
        return redirect(self.redirect_url(student))

    def url_for(self, *args, **kwargs):
        return url_for(*args, next=self.next_url, **kwargs)

class UpdateUser(Requirement):
    def is_satisfied(self, student):
        return student.full_name is not None

    def redirect_url(self, student):
        return self.url_for(".update_user")

class SignExpectationsAgreement(Requirement):
    def is_satisfied(self, student):
        if student.last_signed_expectations_agreement is None:
            return False

        how_long = datetime.datetime.now() - student.last_signed_expectations_agreement
        if how_long > config.expectation_agreement_period:
            return False
        else:
            return True

    def redirect_url(self, student):
        return self.url_for(".sign_expectation_agreement")

class ExpectationAgreementForm(FlaskForm):
    #name = StringField("Name", validators=[InputRequired()])
    agree = BooleanField("I have read and understood the document above.", validators=[InputRequired()])
    submit = SubmitField("Agree")

@student_ops.route("/expectations", methods=["POST", "GET"])
def sign_expectation_agreement():
    student = Student.get_current_student()
    form = ExpectationAgreementForm(request.form)
    if request.method == "POST" and form.validate():
        try:
            student.last_signed_expectations_agreement = datetime.datetime.now()
            student.put()
        except Exception as e:
            return redirect(url_for(".sign_expectation_agreement", error=str("Error: {}".format(e))))
        else:
            return redirect(next_url(url_for(".submit_report")))
    else:
       return render_template("expectations.jinja.html",
                               form=form,
                               #how_long=datetime.datetime.now() - student.last_signed_expectations_agreement,
                               last_signed=student.last_signed_expectations_agreement and localize_time(student.last_signed_expectations_agreement),
                               student=student
                             )

requirements = [UpdateUser(),
                SignExpectationsAgreement()]

@student_ops.route('/report', methods=["POST",'GET'])
def submit_report():
    student = Student.get_current_student()
    for r in requirements:
        if not r.is_satisfied(student):
            return r.do_redirect(student)

    if student.full_name is None:
        return redirect(url_for(".update_user", next=url_for(".submit_report")))
    return view_or_enter_reports(student)


def view_or_enter_reports(student, default_to_submission=True):
    form = DisplayReportForm(request.form)
    report_query = Report.query(ancestor=student.key).order(Report.created)
    report_count = report_query.count()
    if request.method == "POST" and form.validate():
        try:
            report = Report(parent=student.key)
            form.populate_obj(report)
            report.previous_weekly_goals = form.previous_weekly_goals.data
            report.student = student.nickname()
            #raise Exception("hello")
            report.put()
        except Exception as e:
            return redirect(url_for(".submit_report", index=report_count, error=str("Error: {}".format(e))))
        else:
            send_update_email(student, report)
            return redirect(url_for(".submit_report", index=report_count, notification="Report Saved"))
    else:
        error = None

        if report_count > 0:
            reports = report_query.fetch()
            latest_report = reports[report_count - 1]
        else:
            latest_report = None

        if default_to_submission:
            index = int(request.args.get("index", report_count))
        else:
            if report_count == 0:
                index = int(request.args.get("index", report_count))
                error = "{} has not submitted any reports".format(student.full_name or student.email)
            else:
                index = int(request.args.get("index", report_count - 1))

        if index == report_count:
            if latest_report is not None:
                form.previous_weekly_goals.data = latest_report.next_weekly_goals
                form.disp_previous_weekly_goals.data = latest_report.next_weekly_goals
                form.next_weekly_goals.data = latest_report.next_weekly_goals
                form.long_term_goal.data = latest_report.long_term_goal
            is_new_report = True
            display_report = None
        elif index > report_count or index < 0:
            log.info("redirecting {} {}".format(index, report_count))
            return redirect(url_for(".submit_report"))
        else:
            display_report = reports[index]
            form.disp_previous_weekly_goals.data = display_report.previous_weekly_goals
            form.long_term_goal.data = display_report.long_term_goal
            form.disp_previous_weekly_goals.data = display_report.previous_weekly_goals
            form.previous_weekly_goals.data = display_report.previous_weekly_goals
            form.progress_made.data = display_report.progress_made
            form.problems_encountered.data = display_report.problems_encountered
            form.next_weekly_goals.data = display_report.next_weekly_goals
            form.read_only()
            is_new_report = False

        if index >= report_count:
            next_report = None
        else:
            next_report = url_for(request.endpoint,
                                  student=student.key.urlsafe(),
                                  index=index + 1)

        if index <= 0:
            prev_report = None
        else:
            prev_report = url_for(request.endpoint,
                                  student=student.key.urlsafe(),
                                  index=index - 1)

        return render_template("new_report.jinja.html",
                               form=form,
                               is_new_report=is_new_report,
                               display_user=student,
                               current_user=Student.get_current_student(),
                               next_report=next_report,
                               prev_report=prev_report,
                               the_report=display_report,
                               error=error or request.args.get("error") or request.form.get("error"),
                               notification=request.args.get("notification") or request.form.get("notification")
                               )


class UpdateWhiteListForm(FlaskForm):
    email = StringField("Email Address", validators=[InputRequired(),Email()])
    custom_message = TextAreaField("Custom Message")
    submit = SubmitField("Add")


def send_welcome_email(email, custom_message=None):
    if custom_message is not None and custom_message.strip() == "":
        custom_message = None

    message = render_template("welcome_email.jinja.txt",
                              email=email,
                              url=request.host_url[0:-1],
                              custom_message=custom_message)

    email = mail.EmailMessage(sender=config.admin_email,
                              to=email,
                              bcc=config.admin_email,
                              subject="NVSL Progress Reporting",
                              body=message)
    email.send()
    log.info("sent message to {}: \n{}".format(email, message))


def send_update_email(user, report):

    message = render_template("update_email.jinja.txt",
                              user=user,
                              report=report,
                              report_url="{}{}".format(request.host_url[0:-1],
                                                       url_for(".browse_report", student=user.key.urlsafe())))

    email = mail.EmailMessage(sender=config.admin_email,
                              to=config.admin_email,
                              subject="Progress Report for {} ({})".format(user.full_name, report.local_created_time().strftime("%b %d, %Y")),
                              body=message)
    email.send()
    log.info("sent message to {}: \n{}".format(config.admin_email, message))


@student_ops.route("/whitelist", methods=['POST', 'GET'])
def update_whitelist():

    form = UpdateWhiteListForm()

    if form.validate_on_submit():
        try:
            if Student.query(Student.email == form.email.data).count() > 0:
                raise Exception("User with email '{}' already exists".format(form.email.data))

            list = WhiteList.get_list()
            list.add_to_whitelist(form.email.data)
            send_welcome_email(form.email.data, custom_message=form.custom_message.data)
        except Exception as e:
            return redirect(url_for(".update_whitelist", error="Error: {}".format(e)))
        else:

            return redirect(url_for(".update_whitelist", notification="Successfully added"))
    else:
        return render_template("update_whitelist.jinja.html",
                               white_list=WhiteList.get_list().authorized_users.split("\n"),
                               form=form,
                               error=request.args.get("error") or request.form.get("error"),
                               notification=request.args.get("notification") or request.form.get("notification"),
                               )


@student_ops.route('/logout', methods=['POST', 'GET'])
def logout():
    return redirect(request.form.get('continue', users.CreateLogoutURL(url_for(".submit_report"))))


class NewStudentForm(FlaskForm):
    email = StringField('E-mail', validators=[InputRequired()])
    full_name=StringField('Name', validators=[InputRequired()])
#
# @student_ops.route("/student/")
# @role_required(config.admin_role)
# def display_all_students():
#
#     # DFC("start vm",
#     members = [m for m in Student.formatted_members]
#
#     table = build_table_spec("students",
#                              Student.query().fetch(),
#                              members,
#                              "username",
#                              default_sort_reversed=True)
#     return render_template("admin_student_list.jinja.html",
#         userlist=table
#     )
#
# @student_ops.route("/student/<key>")
# @role_required(config.admin_role)
# def display_one_student(key):
#     student = ndb.Key(urlsafe=key).get()
#
#     build_spec = build_list_spec("student",
#                                  student,
#                                  Student.formatted_members)
#
#     return render_template("admin_student.jinja.html",
#         user_attrs = build_spec,
#         user = student
#     )


@student_ops.route("/")
def index():
    if not users.is_current_user_admin():
        return redirect(url_for(".submit_report"))
    else:
        return render_template("smithers_page.jinja.html")

@student_ops.route("/resource/<file>")
def render_resource(file):
    return render_template("html/{}".format(file.replace(".html",".jinja.html")))