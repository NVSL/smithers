import datetime
from google.appengine.ext import ndb
import Student
import random

from flask import Blueprint, render_template, abort, url_for, redirect, Response, request, flash
from flask_login import login_required, current_user
from google.appengine.api import mail
import VMInstance
import logging as log
import util
import config

STATE_NOT_STARTED = "NOT_STARTED"
OLD_STATE_NOT_STARTED= "NOT STARTED"
STATE_TEST_STARTED = "TEST_STARTED"
STATE_TEST_FINISHED = "TEST_FINISHED"

app_ops=Blueprint("app_ops", __name__)

matrices_zip = "/static/src/matrices.zip"

task2_cartoons=[
    ("http://i.imgur.com/4JoPs.jpg", "" ),
    ("https://imgs.xkcd.com/comics/log_scale_2x.png", "https://xkcd.com/1162/"),
    ("https://imgs.xkcd.com/comics/escalators.png", "https://xkcd.com/252/"),
    ("https://imgs.xkcd.com/comics/good_code.png", "https://xkcd.com/844/"),
]

task1_cartoons=[
    ("https://imgs.xkcd.com/comics/sandwich.png", "https://xkcd.com/149/"),
    ("https://imgs.xkcd.com/comics/wisdom_of_the_ancients.png", "https://xkcd.com/979/"),
    #"https://imgs.xkcd.com/comics/server_attention_span.png",
]

end_task_cartoons= [
]

welcome_cartoons=[
    ("https://imgs.xkcd.com/comics/11th_grade.png", "https://xkcd.com/519/"),
    ("https://imgs.xkcd.com/comics/the_difference.png", "https://xkcd.com/242/"),
    ("https://imgs.xkcd.com/comics/computer_problems.png", "https://xkcd.com/722/"),
]
complete_cartoons= [
    ("https://imgs.xkcd.com/comics/tasks_2x.png", "https://xkcd.com/1425/"),
    ("https://imgs.xkcd.com/comics/thesis_defense_2x.png", "https://xkcd.com/1403/"),
    ("https://imgs.xkcd.com/comics/dependencies.png", "https://xkcd.com/754/")
]


def format_duration(delta):
    ts = delta.total_seconds()
    return "{} hours".format(ts/(60*60))

@app_ops.route("/")
@app_ops.route("/app/")
@login_required
def application_status(user=None, test_state=None,skills=None):
    if user is None:
        user = current_user
        test_state = current_user.test_state
        skills =current_user.get_skills()
    else:
        skills=skills.split(",")
        assert test_state is not None;



    error = request.args.get("error")
    notification = request.args.get("notification")

    time_to_work = format_duration(user.get_time_allowed())

    if test_state == STATE_NOT_STARTED or test_state == OLD_STATE_NOT_STARTED:
        template = "application/welcome.html.jinja"
        return render_template(template,
                               url=url_for("app_ops.do_start_task"),
                               error=error,
                               notification=notification,
                               contact_email=config.admin_email,
                               cartoon=random.choice(welcome_cartoons),
                               time_to_work=time_to_work
                               )
    elif test_state == STATE_TEST_STARTED:
        template = "application/test_started.html.jinja"
        now = datetime.datetime.now()
        if user.test_expires_time is None or now > user.test_expires_time:
            now = "0:00:00 (Your machine will be turned of at any moment)"
        else:
            now = (user.test_expires_time-datetime.datetime.now())
            now = "{}:{}:{}".format(max(0,now.days*24), max(0,int(round(now.seconds/3600))), max(0,now.seconds%60))
        unknown_languages = list(set(["Java", "Python", "Javascript", "C"]) - set(skills))
        #known_languages = skills
        return render_template(template, url=url_for("app_ops.do_complete_task"),
                               script_url=url_for("app_ops.generate_script"),
                               private_key_url=url_for("app_ops.private_key"),
                               ip_address=user.get_instance().get_ipaddr(),
                               username=user.get_username(),
                               now=datetime.datetime.now().strftime("%x %X %Z"),
                               time_remaining=now,
                               error=error,
                               notification=notification,
                               contact_email=config.admin_email,
                               user_url="{}{}".format(request.host_url[0:-1], user.get_admin_path()),
                               cartoon1=random.choice(task1_cartoons),
                               cartoon2=random.choice(task2_cartoons),
                               skills=skills,
                               zip_file=matrices_zip,
                               unknown_languages=unknown_languages
                               #cartoon=random.choice(end_task_cartoons)
                               )
    elif test_state == STATE_TEST_FINISHED:
        template = "application/test_finished.html.jinja"
        return render_template(template,
                               comment_url=url_for("app_ops.save_comment"),
                               comment=user.get_comment(),
                               error=error,
                               notification=notification,
                               contact_email=config.admin_email,
                               user_url="{}{}".format(request.host_url[0:-1], user.get_admin_path()),
                               cartoon=random.choice(complete_cartoons)
                               )
    else:
        log.info("Unknown state {} for user {}".format(test_state, user.get_username()))
        return abort(400)


def compute_zone(country):
    return config.default_zone

def _do_complete_task(user):
    log.info("Student {} task is complete".format(user.get_username()))
    try:
        user.get_instance().disconnect_net()
        #user.get_instance().remove_pub_key(user.get_ssh_name())
        time_spent = request.form['timespent']
    except Exception as e:
        log.info("Error trying to complete task for {} {}".format(user.get_username(), e))
        return redirect(url_for("app_ops.application_status", error="Error: {}".format(e)))
    else:
        send_completion_email(user)
        user.test_ended_time = datetime.datetime.now()
        user.time_spent = time_spent
        user.set_test_state(STATE_TEST_FINISHED)

@app_ops.route("/app/finish_task",methods=['POST','GET'])
@login_required
def do_complete_task(user=None):

    if user is None:
        user = current_user
        if request.form['username'] != user.get_username():
            redirect(url_for("app_ops.application_status", error="Please enter your username."))

    if user.test_state == STATE_TEST_STARTED:
        r = _do_complete_task(user)
        if r is not None:
            return r

    return redirect(url_for("app_ops.application_status"))


@app_ops.route("/app/start_task",methods=['POST','GET'])
@login_required
def do_start_task():

    if request.form['username'] != current_user.get_username():
        return redirect(url_for("app_ops.application_status", error="Please enter your username."))

    if current_user.test_state == STATE_NOT_STARTED or current_user.test_state == OLD_STATE_NOT_STARTED:
        try:
            instance = VMInstance.VMInstance.create(current_user.get_username().replace("@","-").replace(".","-"),
                                                    compute_zone(current_user.get_country()),
                                                    config.machine_type,
                                                    ssh_name=current_user.get_ssh_name())
        except Exception as e:
            return redirect(url_for("app_ops.application_status", error="Error: {}".format(e)))
        else:
            current_user.test_started_time = datetime.datetime.now()
            current_user.test_expires_time = datetime.datetime.now() + current_user.get_time_allowed()
            current_user.set_instance(instance.key)
            current_user.set_skills(list(set(request.form.keys()) - set(["username"])))
            current_user.set_test_state(STATE_TEST_STARTED)

    return redirect(url_for("app_ops.application_status"))

def respond_with_script(target_user, file_name, ip_addr=None):

    if current_user.has_role(config.admin_role):
        private_key = current_user.private_key
        login_name = current_user.get_ssh_name()
    else:
        private_key = target_user.get_instance().private_key
        login_name = target_user.get_ssh_name()

    if ip_addr is None:
        ip_addr = target_user.get_instance().get_ipaddr()

    r = Response(render_template("connect.sh.jinja",
                                 username=login_name,
                                 private_key=private_key,
                                 ip_address=ip_addr),
                 mimetype="application/octet-stream")
    r.headers['Content-Disposition'] = 'attachment; filename={}'.format(file_name)
    return r

@app_ops.route("/app/connect.sh")
@login_required
def generate_script():
    return respond_with_script(current_user, "connect.sh")

@app_ops.route("/app/user/<user>/connect.sh")
@login_required
@util.role_required(config.admin_role)
def generate_script_for_user(user):
    user = Student.Student.get_user(user)
    return respond_with_script(user, "connect_{}.sh".format(user.get_username()))

@app_ops.route("/app/user/<user>/master_connect.sh")
@login_required
@util.role_required(config.admin_role)
def generate_master_script_for_user(user):
    user = Student.Student.get_user(user)
    return respond_with_script(user, "connect_{}.sh".format(user.get_username()))

@app_ops.route("/app/private_key")
@login_required
def private_key():
    r = Response(current_user.get_instance().private_key,
                 mimetype="application/octet-stream")
    r.headers['Content-Disposition'] = 'attachment; filename={}'.format(current_user.get_username())
    return r

@app_ops.route("/app/comment", methods=['POST'])
@login_required
def save_comment():
    current_user.set_comment(request.form['comment'])
    return redirect(url_for("app_ops.application_status", notification="Comment Saved"))

def send_welcome_email(user, custom_message=None):
    if custom_message is not None and custom_message.strip() == "":
        custom_message = None

    message = render_template("application/welcome_email.txt.jinja",
                              user=user,
                              login_url="{}{}".format(request.host_url[0:-1], url_for("user_ops.login")),
                              custom_message=custom_message)

    email = mail.EmailMessage(sender=config.admin_email,
                              to=user.get_email(),
                              bcc=config.admin_email,
                              subject="Your application to UCSD CSE",
                              body=message)
    email.send()
    log.info("sent message to {}: \n{}".format(user.get_email(), message))

def send_completion_email(user):

    message = render_template("application/completion_email.txt.jinja",
                              user_url="{}{}".format(request.host_url[0:-1], user.get_admin_path()),
                              user=user)

    email = mail.EmailMessage(sender=config.admin_email,
                              to=config.admin_email,
                              subject="{} has completed the task".format(user.get_fullname()),
                              body=message)
    email.send()
    log.info("sent message to {}: \n{}".format(config.admin_email, message))

@app_ops.route("/app/enforce_deadlines")
def enforce_deadlines():
    for u in Student.Student.query().fetch():
        if u.test_expires_time is not None and \
                        u.test_expires_time < datetime.datetime.now() and \
                        u.test_state != STATE_TEST_FINISHED:
            _do_complete_task(u)
            log.info("{} is out of time.  Stopping... {}".format(u.get_username(), u.test_expires_time))
    return redirect("/", code=200)

@app_ops.route("/app/user/<user>/connect-and-visit")
@login_required
@util.role_required(config.admin_role)
def connect_and_visit(user):
    user = Student.Student.get_user(user)
    user.get_instance().connect_net()
    return redirect("http://{}".format(user.get_instance().get_ipaddr()))

@app_ops.route("/app/user/<user>/preview")
@login_required
@util.role_required(config.admin_role)
def preview(user):
    user = Student.Student.get_user(user)
    return application_status(user=user,
                              test_state=request.args['state'],
                              skills=request.args.get('skills'))
#request.r