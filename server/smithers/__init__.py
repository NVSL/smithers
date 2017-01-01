from flask import Flask, url_for
from google.appengine.api import users
import config
from flask_bootstrap import Bootstrap

# import flask_login
from google.appengine.ext import ndb
import logging as log
from flask_nav import Nav
from flask_nav.elements import Navbar, View, Subgroup

# login_manager = flask_login.LoginManager()
app = Flask(__name__)
Bootstrap(app)

app.secret_key = 'A0Zr9aoeu8j/3yXaoeuaoeuaoeujmN]LWX/,?RT'

nav = Nav()

def resource(file, name):
    return View(name, "student_ops.render_resource", file=file)

@nav.navigation()
def mynavbar():
    return Navbar(
        'NVSL',
        View('Reporting', 'student_ops.submit_report'),
        Subgroup('Resources',
                 resource("travel.html", "Travel"),
                 resource("internships.html", "Internships"),
                 resource("meetings.html", "Scheduling Meetings"),
                 resource("GivingTalks.html", "Giving Talks"),
                 resource("WritingPapers.html", "Writing Papers"),
                 resource("Misc.html", "Misc")),
        View('Logout', 'student_ops.logout')
    )


nav.init_app(app)

# login_manager.init_app(app)
# login_manager.login_view = "student_ops.login"
# login_manager.login_message = "Please log in to do that"

import traceback

from smithers.Student import student_ops, Student
from smithers.Report import report_ops
app.register_blueprint(student_ops)
app.register_blueprint(report_ops)


class smithers_globals(app.app_ctx_globals_class):
    def __init__(self, *args, **kwargs):
        super(smithers_globals,self).__init__(*args, **kwargs)
        self.current_user=Student.get_current_student()
        self.student_list=[(s, s.key.urlsafe()) for s in Student.query().fetch()]
        self.admin_view = users.is_current_user_admin()
        self.config = config

    def CreateLogoutURL(self, next):
        return users.CreateLogoutURL(next)

app.app_ctx_globals_class = smithers_globals

# app.register_blueprint(app_ops)

# from locutor.User import ensure_admin
# ensure_admin()

# traceback.print_stack()
# print app.url_map
