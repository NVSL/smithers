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
from wtforms import StringField, HiddenField, TextAreaField, SubmitField, BooleanField, SelectField, DateField
from wtforms_components import read_only
from wtforms.validators import InputRequired, Email

from collections import deque


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


days_of_the_week = ["Sunday",
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday"]
_day_before = deque(days_of_the_week)
_day_before.rotate(1)
day_before = {a: b for (a, b) in zip(days_of_the_week, _day_before)}

_day_after = deque(days_of_the_week)
_day_after.rotate(-1)
day_after = {a: b for (a, b) in zip(days_of_the_week, _day_after)}

class Student(ndb.Model):
    """A main model for representing users."""
    username = ndb.StringProperty()
    email = ndb.StringProperty()
    full_name = ndb.StringProperty()
    userid = ndb.StringProperty()

    last_signed_expectations_agreement = ndb.DateTimeProperty()

    meeting_day_of_week = ndb.StringProperty()

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

    def compute_next_due_date(self):
        if self.meeting_day_of_week is None:
            return None

        now = localize_time(datetime.datetime.now())
        today = now.date()

        due_date = now.date()
        this_day = now.strftime("%A")

        if this_day == self.meeting_day_of_week:
            time_due_today = datetime.datetime.combine(today, config.report_due_time)
            if now > time_due_today:
                raw_next_due_date = time_due_today + datetime.timedelta(days=7)
            else:
                raw_next_due_date = time_due_today
        else:
            while due_date.strftime("%A") != self.meeting_day_of_week:
                due_date = due_date + datetime.timedelta(days=1)

            raw_next_due_date = datetime.datetime.combine(due_date, config.report_due_time)

        submission_period_start = raw_next_due_date - config.report_submit_period

        if now > submission_period_start and now < raw_next_due_date:
            latest_report = self.get_latest_report()
            if latest_report is not None:
                last_report_time = self.get_latest_report().local_created_time()
            else:
                return raw_next_due_date

            if last_report_time > submission_period_start and last_report_time < raw_next_due_date:
                return raw_next_due_date + datetime.timedelta(days=7)
            else:
                return raw_next_due_date
        else:
            return raw_next_due_date


    def compute_next_submission_time(self):
        return self.compute_next_due_date() - config.report_submit_period

    def get_latest_report(self):
        return Report.query(ancestor=self.key).order(Report.created).get()

    def is_report_due(self):
        next_due = self.compute_next_due_date()
        now = localize_time(datetime.datetime.now())

        if next_due is None:
            return False

        if next_due - now > config.report_submit_period:
            return False

        latest_report = self.get_latest_report()

        if latest_report is None:
            return True

        if latest_report.local_created_time() < next_due - config.report_submit_period:
            return False

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



class UpdateUserForm(FlaskForm):
    full_name = StringField("Full Name", validators=[InputRequired()])
    meeting_day_of_week = SelectField("Meeting day",
                                      choices=[("Monday"   , "Monday"),
                                               ("Tuesday"  , "Tuesday"),
                                               ("Wednesday", "Wednesday"),
                                               ("Thursday" , "Thursday"),
                                               ("Friday"   , "Friday")])
    email = StringField("Email")
    last_signed_expectations_agreement = DateField()
    submit = SubmitField("Submit")

    def __init__(self, *args, **kwargs):
        super(UpdateUserForm, self).__init__(*args, **kwargs)
        read_only(self.email)
        read_only(self.last_signed_expectations_agreement)


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
        form.meeting_day_of_week.data = student.meeting_day_of_week
        form.last_signed_expectations_agreement.data = student.last_signed_expectations_agreement
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
        return student.full_name is not None and student.meeting_day_of_week is not None

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

@student_ops.route("/report_alt", methods=["GET"])
def report_alt():
    student = Student.get_current_student()
    report_query = Report.query(ancestor=student.key).order(Report.created)
    report = report_query.get()
    form = DisplayReportForm()

    form.disp_previous_weekly_goals.data = report.previous_weekly_goals
    form.long_term_goal.data = report.long_term_goal
    form.disp_previous_weekly_goals.data = report.previous_weekly_goals
    form.previous_weekly_goals.data = report.previous_weekly_goals
    form.progress_made.data = report.progress_made
    form.problems_encountered.data = report.problems_encountered
    form.next_weekly_goals.data = report.next_weekly_goals

    return render_template("report_alt.jinja.html",
                           display_user=student,
                           the_report=report,
                           form=form)
@student_ops.route('/report', methods=["POST",'GET'])
def submit_report():
    student = Student.get_current_student()
    for r in requirements:
        if not r.is_satisfied(student):
            return r.do_redirect(student)

    if student.full_name is None:
        return redirect(url_for(".update_user", next=url_for(".submit_report")))
    return view_or_enter_reports(student)


class DisplayReportForm(FlaskForm):
    long_term_goal = TextAreaField('Current Goal', validators=[InputRequired()])
    disp_previous_weekly_goals = TextAreaField("Previous Weekly Goals")
    previous_weekly_goals = HiddenField()
    report_for_date = HiddenField()
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


def view_or_enter_reports(student, default_to_submission=True):
    form = DisplayReportForm(request.form)
    report_query = Report.query(ancestor=student.key).order(Report.created)
    report_count = report_query.count()
    if request.method == "POST" and form.validate():
        try:
            report = Report(parent=student.key)
            form.report_for_date.data = datetime.datetime.strptime(form.report_for_date.data, "%Y-%m-%d" ).date()
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
            t = student.compute_next_due_date()
            if t:
                form.report_for_date.data = t.date()

            if not student.is_report_due():
                form.read_only()
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


@student_ops.route("/")
def index():
    if not users.is_current_user_admin():
        return redirect(url_for(".submit_report"))
    else:
        return render_template("smithers_page.jinja.html")

@student_ops.route("/resource/<file>")
def render_resource(file):
    return render_template("html/{}".format(file.replace(".html",".jinja.html")))



@student_ops.route("/send_reminder_emails")
def send_reminder_emails():

    students = Student.query(ancestor=student_parent_key).fetch()
    now = localize_time(datetime.datetime.now())
    today = now.strftime("%A")

    for s in students:
        if s.meeting_day_of_week is not None:
            if today == day_before[s.meeting_day_of_week] and s.is_report_due():
                due_time = s.compute_next_due_date()
                time_left = datetime.datetime(year=2016, month=1, day=1) + (due_time - now)
                time_left_str = time_left.strftime(" %H hours, %M minutes").replace(" 0"," ")

                message = render_template("report_reminder_email.jinja.txt",
                                          student=s,
                                          time_left=time_left_str,
                                          due_time=due_time,
                                          due_hour=datetime.time(hour=2),
                                          url=request.host_url[0:-1])

                email = mail.EmailMessage(sender=config.admin_email,
                                          to=s.email,
                                          bcc=config.admin_email,
                                          subject="Your progress report is due in {}".format(time_left_str),
                                          body=message)
                email.send()
                log.info("sent reminder message to {}: \n{}".format(email, message))

    return "success", 200