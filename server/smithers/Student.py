import collections
import copy
import datetime
from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import mail

import config
from util import DFC
import Logging as log
from flask import redirect, url_for, request, render_template, Blueprint
from util import next_url, localize_time
from Report import Report, Attachment
from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, TextAreaField, SubmitField, BooleanField, SelectField, DateField, Label
from wtforms_components import read_only
from wtforms.validators import InputRequired, Email, AnyOf
import wtforms
from SmartModel import SmartModel, FieldAnnotation
from collections import deque
import pytz
from htmltreediff import diff
import flask
import CKEditorSupport
from Exceptions import UnauthorizedException

def flash(message, category):
    log.info("Flashed {}: {}".format(category, message))
    flask.flash(message, category)

student_ops = Blueprint("student_ops", __name__)
student_parent_key=ndb.Key("Student", "students")


class WhiteList(SmartModel):
    authorized_users = ndb.TextProperty()

    @classmethod
    def field_annotations(cls):
        return dict(
            authorized_users=FieldAnnotation(
                description='One address per line',
            ))

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

#request.
days_of_the_week = ["Sunday",
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday"]
_day_before = deque(days_of_the_week)
_day_before.rotate(1)
day_before = {a: b for (a, b) in zip(days_of_the_week, _day_before)}

_day_after = deque(days_of_the_week)
_day_after.rotate(-1)
day_after = {a: b for (a, b) in zip(days_of_the_week, _day_after)}

day_to_int = {a: b for (a,b) in zip(days_of_the_week, range(0,len(days_of_the_week)))}

class Student(SmartModel):
    """A main model for representing users."""
    username = ndb.StringProperty()
    email = ndb.StringProperty()
    full_name = ndb.StringProperty()
    userid = ndb.StringProperty()

    last_signed_expectations_agreement = ndb.DateTimeProperty()
    last_entered_availability = ndb.DateTimeProperty()
    last_read_report_guidelines = ndb.DateTimeProperty()

    meeting_day_of_week = ndb.StringProperty()

    is_test_account = ndb.BooleanProperty()

    submits_reports = ndb.BooleanProperty()

    def get_submits_reports(self):
        return self.submits_reports is None or self.submits_reports

    @classmethod
    def field_annotations(cls):
        return dict(
            full_name=FieldAnnotation(
                label='Full name',
                description='Your name',
            ),
            email=FieldAnnotation(
                validators=[Email()]
            ),
            meeting_day_of_week=FieldAnnotation(
                validators=[AnyOf(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])]
            ),
            userid = FieldAnnotation(
                read_only=True
            )
        )

    @classmethod
    def formatted_members(cls):
        return [
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

    def get_display_name(self):
        return self.full_name or self.email
    
    def get_admin_path(self):
        return url_for("student_ops.display_one_student", key=self.key.urlsafe())

    def delete_student(self):
        self.key.delete()

    def nickname(self):
        return self.email


    def get_draft_report(self):
        r = Report.query(ancestor=self.key).order(-Report.created).get()
        if r and r.is_draft():
            return r
        else:
            print "couldn't find draft report"
            return None

    def compute_next_due_date(self, ignore_latest=False):

        now = pytz.UTC.localize(datetime.datetime.utcnow())

        local_now = localize_time(now)
        log.info("local_now = {}".format(local_now))
        log.info("now = {}".format(now))

        today = now.date()
        log.info("today = {}".format(today))

        this_day = local_now.strftime("%A")

        if self.meeting_day_of_week in [None, ""]:
            meeting_day_of_week = this_day
        else:
            meeting_day_of_week = self.meeting_day_of_week

        if this_day == meeting_day_of_week:
            time_due_today = datetime.datetime.combine(today, config.report_due_time)
            log.info("time_due_today = {}".format(time_due_today))
            time_due_today = config.local_time_zone.localize(time_due_today)
            log.info("time_due_today = {}".format(time_due_today))

            if now > time_due_today:
                raw_next_due_date = time_due_today + datetime.timedelta(days=7)
                log.info("raw_next_due_date [1] = {}".format(raw_next_due_date))
            else:
                raw_next_due_date = time_due_today
                log.info("raw_next_due_date [2] = {}".format(raw_next_due_date))
        else:
            due_day = local_now.date()
            while due_day.strftime("%A") != meeting_day_of_week:
                due_day = due_day + datetime.timedelta(days=1)
                log.info("due_day [1] = {}".format(due_day))
            raw_next_due_date = config.local_time_zone.localize(datetime.datetime.combine(due_day, config.report_due_time))
            log.info("raw_next_due_date [3] = {}".format(raw_next_due_date))

        log.info("raw_next_due_date final = {}".format(raw_next_due_date))

        submission_period_start = raw_next_due_date - config.report_submit_period

        if now > submission_period_start and now < raw_next_due_date:
            log.info("In submission window")
            latest_report = self.get_latest_report()
            if not latest_report or ignore_latest:
                log.info("return raw_next_due_date = {}".format(raw_next_due_date))
                return raw_next_due_date
            else:
                last_report_time = self.get_latest_report().local_created_time()
                log.info("last_report_time = {}".format(last_report_time))

            if last_report_time > submission_period_start and last_report_time < raw_next_due_date:
                r = raw_next_due_date + datetime.timedelta(days=7)
                log.info("return {}".format(r))
                return r
            else:
                log.info("return {}".format(raw_next_due_date))
                return raw_next_due_date
        else:
            log.info("return {}".format(raw_next_due_date))
            return raw_next_due_date


    def compute_next_submission_time(self):
        return self.compute_next_due_date() - config.report_submit_period

    def get_latest_report(self):
        return Report.query(Report.is_draft_computed == False, ancestor=self.key).order(-Report.created).get()

    def is_report_overdue(self):
        if self.is_report_due():
            return False

        latest_submitted_report = self.get_latest_report()

        if latest_submitted_report is None:
            return False

        next_due_time = self.compute_next_due_date(ignore_latest=True)
        now = pytz.UTC.localize(datetime.datetime.utcnow())

        if now < next_due_time and now > next_due_time - config.report_submit_period:
            last_report_submission_period_stop = next_due_time
        else:
            last_report_submission_period_stop = next_due_time - datetime.timedelta(days=7)

        last_report_submission_period_start = last_report_submission_period_stop - config.report_submit_period

        log.info(self.full_name)
        log.info("last_report_submission_period_start: {}".format(last_report_submission_period_start))
        log.info("last_report_submission_period_stop : {}".format(last_report_submission_period_stop))

        if not (latest_submitted_report.local_created_time() > last_report_submission_period_start
                and latest_submitted_report.local_created_time() < last_report_submission_period_stop):
            return True
        else:
            return False


    def is_report_due(self):
        if self.is_test_account:
            return True

        next_due = self.compute_next_due_date()

        log.info("next_due={}".format(next_due))
        now = pytz.UTC.localize(datetime.datetime.utcnow())
        now = localize_time(now)
        log.info("now={}".format(now))
        if next_due is None:
            log.info("return false 1 -- not due")
            return False

        log.info("next_due -now = {}".format(next_due-now))
        log.info("config.report_submit_period = {}".format(config.report_submit_period))
        if next_due - now > config.report_submit_period:
            log.info ("return false 2 -- too early.")
            return False

        latest_report = self.get_latest_report()
        log.info ("latest_report= {}".format(latest_report))
        if latest_report is None:
            log.info ("return true 1 -- no report, not too early, so it's due")
            return True

        log.info ("latest_report.local_created_time() = {}".format(latest_report.local_created_time()))
        log.info ("next_due - config.report_submit_period = {}".format(next_due - config.report_submit_period))
        if latest_report.local_created_time() < next_due - config.report_submit_period:
            log.info ("return True -- There is a report, it's not too early, and the last report is before the submission window")
            return True
        log.info ("fall off, return false")
        return False

    @classmethod
    def get_student(self, id):
        r = None
        try:
            r = ndb.Key(urlsafe=id).get()
        except:
            pass

        if r is None:
            try:
                r = Student.query(Student.username == id or
                                  Student.email == id).get()
            except:
                pass

        if r is None:
            raise Exception("Missing user: {}".format(id))

        return r

    @classmethod
    def lookup(cls, id):
        return cls.get_student(id)

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
                                  username=user.email().split("@")[0],
                                  is_test_account=False,
                                  meeting_day_of_week="",
                                  submits_reports=True)
                student.put()
            else:
                raise UnauthorizedException("Unauthorized email address")
        return student



class UpdateUserForm(FlaskForm):
    full_name = StringField("Full Name", validators=[InputRequired()])
    meeting_day_of_week = SelectField("Meeting day",
                                      choices=[("", ""),
                                               ("Monday"   , "Monday"),
                                               ("Tuesday"  , "Tuesday"),
                                               ("Wednesday", "Wednesday"),
                                               ("Thursday" , "Thursday"),
                                               ("Friday"   , "Friday")],
                                      validators=[AnyOf(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])])
    email = StringField("Email")
    last_signed_expectations_agreement = DateField()
    submit = SubmitField("Submit")

    def __init__(self, *args, **kwargs):
        super(UpdateUserForm, self).__init__(*args, **kwargs)
        read_only(self.email)
        read_only(self.last_signed_expectations_agreement)

def get_student_perm_check(user_key):
    if user_key is None:
        return Student.get_current_student()
    else:
        user = ndb.Key(urlsafe=user_key).get()
        if user != Student.get_current_student() and not users.is_current_user_admin():
            return None
        else:
            return user

@student_ops.route("/user/<user_key>/update/", methods=['GET', 'POST'])
@student_ops.route("/user/update/", methods=['GET', 'POST'])
def update_user(user_key=None):
    student = get_student_perm_check(user_key)
    if not student:
        return "Access denied", 403

    form = UpdateUserForm(request.form)
    log.info("updating student {}: {}".format(student.email, request.form))

    if request.method == "POST":
        if form.validate():
            log.info("update user: {}".format(student.email))
            form.populate_obj(student)
            student.put()
            flash("Account updated", category='success')
            return redirect(next_url(url_for(".index")))
        else:
            return render_template("update_user.jinja.html",
                                   form=form,
                                   student=student
                                   )
    else:
        form.full_name.data = student.full_name
        form.email.data = student.email
        form.meeting_day_of_week.data = student.meeting_day_of_week
        form.last_signed_expectations_agreement.data = student.last_signed_expectations_agreement
        return render_template("update_user.jinja.html",
                               form=form,
                               student=student
                               )


@student_ops.route("/user/<user_key>", methods=['GET'])
@student_ops.route("/user/", methods=["GET"])
def view_user(user_key=None):
    user = get_student_perm_check(user_key)
    if not user:
        return "Access denied", 403

    all_reports = Report.query(Report.is_draft_computed == False, ancestor=user.key).order(-Report.created).fetch()

    return render_template("view_student.jinja.html",
                           reports=all_reports,
                           student=user)


@student_ops.route("/user/list_all", methods=["GET"])
def list_all_users():

    Student.get_current_student().is_report_overdue()
    students = copy.copy(flask.g.student_list)

    now = pytz.UTC.localize(datetime.datetime.utcnow())
    local_now = localize_time(now)
    today = int(local_now.strftime("%w"))

    def day_order(a): # sort so people due soon are at the top.
        d = a[0].meeting_day_of_week
        if not a[0].get_submits_reports():
            return 100000
        if not d:
            d = "Monday"
        return (day_to_int[d] - today) % len(days_of_the_week)

    return render_template("view_all_students.jinja.html",
                           students=sorted(students, key=day_order))


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

class ReadingRequirement(Requirement):

    def __init__(self,
                 submission_start_date,
                 get_last_completion,
                 redirect_method):
        super(ReadingRequirement, self).__init__()
        
        self.submission_start_date = submission_start_date
        self.get_last_completion = get_last_completion
        self.redirect_method = redirect_method
        
    def is_satisfied(self, student):
        return self.get_last_completion(student) and self.get_last_completion(student) > self.submission_start_date 

    def redirect_url(self, student):
        return self.url_for(self.redirect_method)

    
class UpdateUser(Requirement):
    def is_satisfied(self, student):
        return student.full_name is not None and student.meeting_day_of_week is not None

    def redirect_url(self, student):
        return self.url_for(".update_user")

    
class ReadReportGuidelines(ReadingRequirement):

    def __init__(self):
        super(ReadReportGuidelines, self).__init__(submission_start_date=datetime.datetime(2017, 9, 14),
                                                   get_last_completion=lambda x: x.last_read_report_guidelines,
                                                   redirect_method=".read_report_guidelines")
                                                  

class ReportGuidelinesForm(FlaskForm):
    #name = StringField("Name", validators=[InputRequired()])
    agree = BooleanField("I have read the report guideline.", validators=[InputRequired()])
    submit = SubmitField("Submit")


# lines with ### are the ones that differ between this and the form for entering schedule info.  We should really be able to merge them.
@student_ops.route("/report_guidelines", methods=["POST", "GET"])
def read_report_guidelines():
    student = Student.get_current_student()
    form = ReportGuidelinesForm(request.form) ###
    target_week = "October 2nd" # this is the week they should enter there information for. ###
    if request.method == "POST":
        if form.validate():
            try:
                student.last_read_report_guidelines = datetime.datetime.now() ###
                student.put()
            except Exception as e:
                flash(str(e), category='error')
                return redirect(url_for(".read_report_guidelines")) ###
            else:
                flash("Response recorded", category='success')
                return redirect(next_url(url_for(".submit_report")))
        else:
            [ flash(e, category='error') for e in form.agree.errors ]
            return render_template("html/ProgressReports.jinja.html",
                                   form=form,
                                   target_week=target_week,
                                   last_signed=student.last_read_report_guidelines and localize_time(student.last_read_report_guidelines), ###
                                   student=student
                                   )

    else:
        return render_template("html/ProgressReports.jinja.html", ###
                               form=form,
                               target_week=target_week,
                               last_signed=student.last_read_report_guidelines and localize_time(student.last_read_report_guidelines),  ###
                               student=student
                             )

    
class EnterMeetingAvailability(Requirement):
    
    def is_satisfied(self, student):
        submission_start_date = datetime.datetime(2017, 9, 15)
        return student.last_entered_availability and student.last_entered_availability > submission_start_date

    def redirect_url(self, student):
        return self.url_for(".enter_meeting_schedule_info")

class MeetingAvailabiltyForm(FlaskForm):
    #name = StringField("Name", validators=[InputRequired()])
    agree = BooleanField("I have entered my non-availability information.", validators=[InputRequired()])
    submit = SubmitField("Submit")

@student_ops.route("/meeting_times", methods=["POST", "GET"])
def enter_meeting_schedule_info():
    student = Student.get_current_student()
    form = MeetingAvailabiltyForm(request.form)
    target_week = "October 2nd" # this is the week they should enter there information for.
    if request.method == "POST":
        if form.validate():
            try:
                student.last_entered_availability = datetime.datetime.now()
                student.put()
            except Exception as e:
                flash(str(e), category='error')
                return redirect(url_for(".enter_meeting_schedule_info"))
            else:
                flash("Response recorded", category='success')
                return redirect(next_url(url_for(".submit_report")))
        else:
            [ flash(e, category='error') for e in form.agree.errors ]
            return render_template("html/meetings.jinja.html",
                                   form=form,
                                   target_week=target_week,
                                   last_signed=student.last_signed_expectations_agreement and localize_time(student.last_signed_expectations_agreement),
                                   student=student
                                   )

    else:
        return render_template("html/meetings.jinja.html",
                               form=form,
                               target_week=target_week,
                               #how_long=datetime.datetime.now() - student.last_signed_expectations_agreement,
                               last_signed=student.last_signed_expectations_agreement and localize_time(student.last_signed_expectations_agreement),
                               student=student
                             )

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
    if request.method == "POST":
        if form.validate():
            try:
                student.last_signed_expectations_agreement = datetime.datetime.now()
                student.put()
            except Exception as e:
                flash(str(e), category='error')
                return redirect(url_for(".sign_expectation_agreement"))
            else:
                flash("Expectation agreement signed", category='success')
                return redirect(next_url(url_for(".submit_report")))
        else:
            [ flash(e, category='error') for e in form.agree.errors ]
            return render_template("expectations.jinja.html",
                                   form=form,
                                   last_signed=student.last_signed_expectations_agreement and localize_time(student.last_signed_expectations_agreement),
                                   student=student
                                   )

    else:
       return render_template("expectations.jinja.html",
                               form=form,
                               #how_long=datetime.datetime.now() - student.last_signed_expectations_agreement,
                               last_signed=student.last_signed_expectations_agreement and localize_time(student.last_signed_expectations_agreement),
                               student=student
                             )

requirements = [UpdateUser(),
                SignExpectationsAgreement(),
                EnterMeetingAvailability(),
                ReadReportGuidelines()
                ]

class BaseReportForm(FlaskForm):
    long_term_goal = TextAreaField('Long Term Goal', validators=[InputRequired()])
    disp_previous_weekly_goals = TextAreaField("Previous Weekly Goals")
    previous_weekly_goals = HiddenField()
    report_for_date = HiddenField()
    report_id=HiddenField()
    progress_made = TextAreaField('Weekly Progress', validators=[InputRequired()])
    problems_encountered = TextAreaField('Problems Encountered & Blocking Questions', validators=[InputRequired()])
    next_weekly_goals = TextAreaField('Next Weekly Goals', validators=[InputRequired()])
    other_issues = TextAreaField('Other (Non-Research-related) Issues')

    advisor_comments = TextAreaField('Advisor Notes')

    def __init__(self, *args, **kwargs):
        super(BaseReportForm, self).__init__(*args, **kwargs)
        read_only(self.disp_previous_weekly_goals)

    def read_only(self):
        read_only(self.long_term_goal)
        read_only(self.disp_previous_weekly_goals)
        read_only(self.progress_made)
        read_only(self.problems_encountered)
        read_only(self.next_weekly_goals)
        read_only(self.other_issues)

    def load_from_report(self, report):
        self.disp_previous_weekly_goals.data = report.previous_weekly_goals
        self.long_term_goal.data = report.long_term_goal
        self.disp_previous_weekly_goals.data = report.previous_weekly_goals
        self.previous_weekly_goals.data = report.previous_weekly_goals
        self.progress_made.data = report.progress_made
        self.problems_encountered.data = report.problems_encountered
        self.next_weekly_goals.data = report.next_weekly_goals
        self.other_issues.data = report.other_issues
        self.report_id.data = report.key.urlsafe()
        self.report_for_date.data = report.report_for_date
        self.advisor_comments.data = report.advisor_comments

    def update_to_report(self, report):
        if self.long_term_goal.data:
            report.long_term_goal = self.long_term_goal.data
        if self.previous_weekly_goals.data:
            report.previous_weekly_goals = self.previous_weekly_goals.data
        if self.progress_made.data:
            report.progress_made = self.progress_made.data
        if self.problems_encountered.data:
            report.problems_encountered = self.problems_encountered.data
        if self.next_weekly_goals.data:
            report.next_weekly_goals = self.next_weekly_goals.data
        if self.other_issues.data:
            report.other_issues = self.other_issues.data
        if self.advisor_comments.data:
            report.advisor_comments = self.advisor_comments.data

class NewReportForm(BaseReportForm):
    #save = SubmitField("Save")
    attachments = wtforms.FileField("File to Attach")#, multiple=True)#, validators=[FileRequired()])
    submit = SubmitField("Submit")
    save = SubmitField("Save")


class ViewReportForm(BaseReportForm):
    save = SubmitField("Submit")

class UpdateReportForm(BaseReportForm):
    submit = SubmitField("Submit Update")
    attachments = wtforms.FileField("File to Attach")#, multiple=True)#, validators=[FileRequired()])
    #cancel = SubmitField("Cancel")

class CommentOnReport(FlaskForm):
    body = TextAreaField("Report")
    submit = SubmitField("Submit")

@student_ops.route("/weekly/<report_key>/comment", methods=["GET", "POST"])
def comment_on_report(report_key):
    report = lookup_report(report_key)
    form = CommentOnReport(request.form)

    if request.method == "POST":
        if form.validate():
            print form.body.data
    else:
        t = render_report_for_email(report, "", report.key.parent().get())
        print t
        form.body.data = t
        return render_template("comment_on_report.jinja.html",
                               form=form)

@student_ops.route("/weekly/<report_key>/", methods=['GET'])
@student_ops.route("/weekly/", methods=['GET'])
def view_report(report_key=None):
    if report_key is None:
        student = Student.get_current_student()
        report = student.get_latest_report()
    else:
        report = lookup_report(report_key)
        student = report.key.parent().get()

    if report is None:
        return "Missing report", 404

    form = ViewReportForm()
    form.read_only()

    r = render_view_report_page(form, report, student)
    return r

def render_view_report_page(form, report, student):
    form.load_from_report(report)
    prev_report = Report.query(Report.created < report.created, Report.is_draft_computed == False, ancestor=student.key).order(-Report.created).get()
    next_report = Report.query(Report.created > report.created, Report.is_draft_computed == False, ancestor=student.key).order(Report.created).get()

    all_reports = Report.query(Report.is_draft_computed == False, ancestor=student.key).order(-Report.created).fetch()

    body = render_report_for_email(report, "foo", student)

    r = render_template("view_report.jinja.html",
                        form=form,
                        display_user=student,
                        current_user=Student.get_current_student(),
                        next_report=url_for(".view_report",
                                            report_key=next_report.key.urlsafe()) if next_report else None,
                        prev_report=url_for(".view_report",
                                            report_key=prev_report.key.urlsafe()) if prev_report else None,
                        the_report=report,
                        all_reports=all_reports,
                        update_url=url_for('.update_report', report_key=report.key.urlsafe()),
                        allow_edit=all_reports[0] == report,
                        body=body,
                        is_advisor=users.is_current_user_admin(),
                        attachments=Attachment.query(ancestor=report.key).fetch()
                        )
    return r


@student_ops.route('/weekly/new_report', methods=["POST", 'GET'])
def submit_report():

    try:
        student = Student.get_current_student()
    except UnauthorizedException:
        flash("Couldn't retrieve current user", category='error')
        return redirect(url_for(".logout"))
    
    for r in requirements:
        if not r.is_satisfied(student):
            return r.do_redirect(student)

    if student.full_name is None:
        return redirect(url_for(".update_user", next=url_for(".submit_report")))

    return new_report(student)


def new_report(student):
    form = NewReportForm(request.form)

    if request.method == "POST":
        if form.validate():
            try:
                report = student.get_draft_report()

                save_attachment(report)

                form.report_for_date.data = datetime.datetime.strptime(form.report_for_date.data, "%Y-%m-%d").date()

                if "submit" in request.form:
                    report.is_draft_report = False
                elif "save" in request.form:
                    pass

                form.populate_obj(report)
                report.put()

            except Exception as e:
                flash("Couldn't save/submit report: {}".format(e),category='error')
                return render_new_report_page(form, student)

            if "submit" in request.form:
                flash("Report Submitted.", category="success")
                try:
                    send_update_email(student, report)
                except Exception as e:
                    flash("Couldn't send notification email: {}".format(e), category="warning")
                return redirect(url_for(".view_report"))
            else:
                flash("Report saved but not submitted.", category="success")
                return redirect(url_for(".submit_report"))

        else:
            flash("Correct the errors below", category="error")
            return render_new_report_page(form, student)
    else:
        draft_report = student.get_draft_report()

        if draft_report is not None:
            form.load_from_report(draft_report)
        else:
            if student.is_report_due():
                latest_report = student.get_latest_report()
                draft = new_draft_report(student, latest_report)
                form.load_from_report(draft)


        return render_new_report_page(form, student)

def new_draft_report(student, latest_report):

    report = Report(parent=student.key)
    if latest_report:
        report.advisor_comments = latest_report.advisor_comments
        report.previous_weekly_goals = latest_report.next_weekly_goals
        report.progress_made = latest_report.next_weekly_goals
        # report.next_weekly_goals = latest_report.next_weekly_goals
        report.long_term_goal = latest_report.long_term_goal
    report.is_draft_report = True
    report.student = student.nickname()

    report.put()
    return report


@student_ops.route('/weekly/<report_key>/update', methods=["POST", 'GET'])
def update_report(report_key):
    student = Student.get_current_student()
    return do_update_report(student, report_key)


def do_update_report(student, report_key):
    form = UpdateReportForm(request.form)

    form.progress_made.validators = []
    form.problems_encountered.validators = []

    if not users.is_current_user_admin():
        read_only(form.previous_weekly_goals)
        read_only(form.progress_made)
        read_only(form.problems_encountered)
        # read_only(form.other_issues)

        most_recent_report = Report.query(Report.is_draft_computed == False, ancestor=student.key).order(-Report.created).get()
        if most_recent_report.key.urlsafe() != report_key:
            flash("You can only edit your most recent report.", category="error")
            return redirect(url_for(".view_report", report_key=report_key))

    if request.method == "POST":
        if form.validate():
            try:
                report = ndb.Key(urlsafe=form.report_id.data).get()
                old_report = copy.copy(report)
                form.report_for_date.data = datetime.datetime.strptime(form.report_for_date.data, "%Y-%m-%d").date()
                # print "FORM = {}".format(request.form)
                form.update_to_report(report)

                save_attachment(report)

                report.put()
            except Exception as e:
                flash("Couldn't update report: {}".format(e), category='error')
                return render_update_report_page(form, student, report_key)
            else:
                flash("Report Updated.", category="success")

            try:
                send_update_email(student, report, old_report)
            except Exception as e:
                flash("Couldn't send notification email: {}".format(e), category="warning")

            return redirect(url_for(".view_report", report_key=report_key))
        else:
            flash("Correct the errors below", category="error")
            return render_update_report_page(form, student, report_key)
    else:
        return render_update_report_page(form, student, report_key)


def save_attachment(report):
    fileobj = request.files['attachments']
    print "FILE = {}".format(fileobj.filename)
    if fileobj.filename:
        error, attachment_url = CKEditorSupport.save_blob(fileobj)
        attachment = Attachment(parent=report.key)
        attachment.url = attachment_url
        attachment.file_name = fileobj.filename
        attachment.put()


@student_ops.route('/weekly/<report_key>/advisor_update', methods=["POST", 'GET'])
def update_advisor_comments(report_key):
    student = Student.get_current_student()
    report = ndb.Key(urlsafe=report_key).get()

    form = ViewReportForm(request.form)


    if request.method == "POST":
        if True or form.validate():
            try:
                report.advisor_comments = form.advisor_comments.data
                report.put()
            except Exception as e:
                flash("Couldn't update report: {}".format(e),category='error')
                return render_view_report_page(form, report, student)

            flash("Advisor comments saved.", category="success")

            return redirect(url_for(".view_report", report_key=report_key))
        else:
            flash("Correct the errors below", category="error")
            return render_view_report_page(form, report, student)
    else:
        return render_view_report_page(form, report, student)


def render_update_report_page(form, student, report_key):

    display_report = lookup_report(report_key, student)

    form.load_from_report(display_report)

    r = render_template("update_report.jinja.html",
                        form=form,
                        display_user=student,
                        report_is_due=student.is_report_due(),
                        the_report=display_report,
                        is_advisor=users.is_current_user_admin(),
                        attachments=Attachment.query(ancestor=display_report.key).fetch()
                        )
    return r


def render_new_report_page(form, student):


    t = student.compute_next_due_date()
    if t:
        form.report_for_date.data = t.date()

    if not student.is_report_due():
        form.read_only()
        form.submit.disabled=True

    draft = student.get_draft_report()
    r = render_template("new_report.jinja.html",
                        form=form,
                        display_user=student,
                        report_is_due=student.is_report_due(),
                        attachments=Attachment.query(ancestor=draft.key).fetch() if draft else []
                        )
    return r


def lookup_report(report_key, student = None):
    if report_key == "current":
        if student == None:
            return None
        report_query = Report.query(Report.is_draft_computed == False, ancestor=student.key).order(Report.created)
        report_count = report_query.count()
        reports = report_query.fetch()
        if len(reports) == 0:
            return None
        display_report = reports[report_count - 1]
    else:
        try:
            display_report = ndb.Key(urlsafe=report_key).get()
        except:
            return None
    return display_report


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


def send_update_email(user, report, old_report=None):

    report_url="{}{}".format(request.host_url[0:-1],
                             url_for(".view_report", report_key=report.key.urlsafe()))

    html_message = render_report_for_email(report, report_url, user)
    if old_report:
        old_html_message = render_report_for_email(old_report, report_url, user)
        html_message = diff(old_html_message, html_message,pretty=True)
        subject = "Updated Progress Report for {} ({})".format(user.full_name,
                                                                           report.local_created_time().strftime("%b %d, %Y"))
    else:
        subject = "Progress Report for {} ({})".format(user.full_name,
                                                                           report.local_created_time().strftime("%b %d, %Y"))
    email = mail.EmailMessage(sender=config.admin_email,
                              to=config.admin_email,
                              subject=subject,
                              #body=message,
                              reply_to=user.email,
                              html=html_message
                              )
    email.send()

    log.info("sent message to {}: \n{}".format(config.admin_email, html_message))

    email.to=user.email
    del email.reply_to
    email.send()


def render_report_for_email(report, report_url, user):
    form = BaseReportForm()
    form.load_from_report(report)
    html_message = render_template("update_email.jinja.html",
                                   display_user=user,
                                   form=form,
                                   the_report=report,
                                   report_url=report_url)
    return html_message


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
            flash(str(e), category='error')
            return redirect(url_for(".update_whitelist"))
        else:
            flash("Successfuly added", category="success")
            return redirect(url_for(".update_whitelist"))
    else:
        return render_template("update_whitelist.jinja.html",
                               white_list=WhiteList.get_list().authorized_users.split("\n"),
                               form=form,
                               white_list_entity=WhiteList.get_list()
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
        return redirect(url_for(".list_all_users"))

@student_ops.route("/resource/<file>")
def render_resource(file):
    return render_template("html/{}".format(file.replace(".html",".jinja.html")))



@student_ops.route("/send_reminder_emails")
def send_reminder_emails():

    students = Student.query(ancestor=student_parent_key).fetch()
    now = localize_time(datetime.datetime.now())
    today = now.strftime("%A")

    for s in students:
        if not s.get_submits_reports():
            continue
        if s.meeting_day_of_week:
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
            else:
                log.info("Report for {} not due until {}".format(s.email, day_before[s.meeting_day_of_week]))
        else:
            log.info("No meeting day for {}".format(s.email))
    return "success", 200



@student_ops.route("/<student_key>/latest_report")
def latest_report(student_key):
    try:
        student = ndb.Key(urlsafe=student_key).get()
    except:
        students = Student.query(Student.username == student_key).fetch()
        if len(students) == 0:
            student = None
        else:
            student = students[0]
            
    if student is None:
        flash("Couldn't find user '{}'".format(student_key))
        return redirect(url_for(".index"))
            
    latest_report = student.get_latest_report()
    if not latest_report:
        flash("{} has not submitted any reports.".format(student.full_name))
        return redirect(url_for(".index"))

    return view_report(report_key=latest_report.key.urlsafe())


@student_ops.route("/send_summary_emails")
def send_summary_emails():
    students = Student.query(ancestor=student_parent_key).fetch()
    now = localize_time(datetime.datetime.now())
    today = now.strftime("%A")

    if len(students) == 0:
        return "success", 200

    ontime  = []
    overdue = []
    all_students = []
    for s in students:
        if s.get_submits_reports():
            all_students.append(s)
        else:
            continue
        if s.meeting_day_of_week:
            if today == s.meeting_day_of_week:
                if s.is_report_overdue():
                    overdue.append(s)
                else:
                    ontime.append(s)

    if len(all_students) > 0 and len(overdue) + len(ontime) > 1: # > 1 because if there's only one student, we don't need to send mail.
        message = render_template("submitted_reports_email.jinja.txt",
                                  ontime=ontime,
                                  overdue=overdue,
                                  recipient=s.full_name)

        email = mail.EmailMessage(sender=config.admin_email,
                                  to=[s.email for s in all_students],
                                  bcc=config.admin_email,
                                  subject="Today's progress reports",
                                  body=message)

        email.send()
        log.info("Sent summary email to {}".format(", ".join([s.email for s in all_students])))
        log.info("Message: ".format(message))

            
    return "success", 200
                
    

@student_ops.route("/list_summary_emails")
def list_summary_emails():
    students = Student.query(ancestor=student_parent_key).fetch()
    now = localize_time(datetime.datetime.now())
    today = now.strftime("%A")

    ontime  = []
    overdue = []
    for s in students:
        if not s.get_submits_reports():
            continue
        if s.meeting_day_of_week:
            if today == s.meeting_day_of_week:
                if s.is_report_overdue():
                    overdue.append(s)
                else:
                    ontime.append(s)

    all_students = ontime + overdue

    log.info("all_students={}".format(all_students))
    log.info("ontime={}".format(ontime))
    log.info("overdue={}".format(overdue))

    return "success", 200


@student_ops.route("/attachment/<key>", methods=["delete"])
def delete_attachment(key):
    try:
        ndb.Key(urlsafe=key).delete()
        return "success", 200
    except:
        return "Unknown attachment", 404
