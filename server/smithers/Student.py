from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import mail

import config
from util import DFC
import Logging as log
from flask import redirect, url_for, request, render_template, Blueprint
from util import next_url
from Report import Report
from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, TextAreaField, SubmitField
from wtforms_components import read_only
from wtforms.validators import DataRequired

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

    def is_white_listed(self, email):
        return email.upper() in map(lambda x: x.strip().upper(),
                                    self.authorized_users.split("\n"))


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
            if users.is_current_user_admin() or WhiteList.get_list().is_white_listed(user.email()):
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
    long_term_goal = TextAreaField('Current Goal', validators=[DataRequired()])
    disp_previous_weekly_goals = TextAreaField("Previous Weekly Goals")
    previous_weekly_goals = HiddenField()
    progress_made = TextAreaField('Weekly Progress', validators=[DataRequired()])
    problems_encountered = TextAreaField('Probems Encountered', validators=[DataRequired()])
    next_weekly_goals = TextAreaField('Next Weekly Goals', validators=[DataRequired()])
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
    full_name = StringField("Full Name", validators=[DataRequired()])
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
        return render_template("update_user.html.jinja",
                               form=form)


@student_ops.route("/student/<student>")
def browse_report(student):
    s = Student.get_student(student)
    return view_or_enter_reports(s, default_to_submission=False)


@student_ops.route('/report', methods=["POST",'GET'])
def submit_report():
    student = Student.get_current_student()
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
            # raise Exception()
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

        return render_template("new_report.html.jinja",
                               form=form,
                               is_new_report=is_new_report,
                               display_user=student,
                               next_report=next_report,
                               prev_report=prev_report,
                               the_report=display_report,
                               error=error or request.args.get("error") or request.form.get("error"),
                               notification=request.args.get("notification") or request.form.get("notification")
                               )


class UpdateWhiteListForm(FlaskForm):
    email = StringField("Email Address", validators=[DataRequired()])
    custom_message = TextAreaField("Custom Message")
    submit = SubmitField("Add")


def send_welcome_email(email, custom_message=None):
    if custom_message is not None and custom_message.strip() == "":
        custom_message = None

    message = render_template("welcome_email.txt.jinja",
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

    message = render_template("update_email.txt.jinja",
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
            list = WhiteList.get_list()
            s = list.authorized_users.strip().split("\n")
            s.append(form.email.data)
            send_welcome_email(form.email.data, custom_message=form.custom_message.data)
            list.authorized_users = "\n".join(s)
            list.put()
        except Exception as e:
            return redirect(url_for(".update_whitelist", error="Error: {}".format(e)))
        else:

            return redirect(url_for(".update_whitelist", notification="Successfully added"))
    else:
        return render_template("update_whitelist.html.jinja",
                               white_list=WhiteList.get_list().authorized_users.split("\n"),
                               form=form,
                               error=request.args.get("error") or request.form.get("error"),
                               notification=request.args.get("notification") or request.form.get("notification"),
                               )


@student_ops.route('/logout', methods=['POST', 'GET'])
def logout():
    return redirect(request.form.get('continue', users.CreateLogoutURL(url_for(".submit_report"))))


class NewStudentForm(FlaskForm):
    email = StringField('E-mail', validators=[DataRequired()])
    full_name=StringField('Name', validators=[DataRequired()])
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
#     return render_template("admin_student_list.html.jinja",
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
#     return render_template("admin_student.html.jinja",
#         user_attrs = build_spec,
#         user = student
#     )


@student_ops.route("/")
def index():
    if not users.is_current_user_admin():
        return redirect(url_for(".submit_report"))
    else:
        return render_template("smithers_page.html.jinja")