from flask import Flask
from flask_bootstrap import Bootstrap


# import flask_login
from google.appengine.ext import ndb
import logging as log

# login_manager = flask_login.LoginManager()
app = Flask(__name__)
Bootstrap(app)

app.secret_key = 'A0Zr9aoeu8j/3yXaoeuaoeuaoeujmN]LWX/,?RT'
# login_manager.init_app(app)
# login_manager.login_view = "student_ops.login"
# login_manager.login_message = "Please log in to do that"

import traceback

from smithers.Student import student_ops
from smithers.Report import report_ops
app.register_blueprint(student_ops)
app.register_blueprint(report_ops)
# app.register_blueprint(app_ops)

# from locutor.User import ensure_admin
# ensure_admin()

# traceback.print_stack()
# print app.url_map
