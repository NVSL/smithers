import datetime
from flask import Blueprint
from google.appengine.ext import ndb
from SmartModel import SmartModel, FieldAnnotation
from wtforms.validators import  Email
from smithers.util import localize_time

report_ops = Blueprint("report_ops", __name__)
report_parent_key = ndb.Key("Report", "reports")

class Report(SmartModel):
    """A main model for representing users."""
    created = ndb.DateTimeProperty(auto_now_add=True)

    long_term_goal = ndb.TextProperty()
    previous_weekly_goals = ndb.TextProperty()
    progress_made  = ndb.TextProperty()
    problems_encountered = ndb.TextProperty()
    next_weekly_goals = ndb.TextProperty()
    other_issues = ndb.TextProperty()
    report_for_date = ndb.DateProperty()
    student = ndb.StringProperty()

    advisor_comments = ndb.TextProperty()

    is_draft_report = ndb.BooleanProperty()
    is_semiannual_report = ndb.BooleanProperty(default=False)

    def get_advisor_comments(self):
        if self.advisor_comments:
            return self.advisor_comments
        else:
            return ""

    def is_stale(self):
         return localize_time(datetime.datetime.now()) - self.local_created_time() > datetime.timedelta(days=2)

    def delete(self):
        self.key.delete()

    def local_created_time(self):
        return localize_time(self.created)

    def is_draft(self):
        return self.is_draft_report

    @classmethod
    def field_annotations(cls):
        return dict(student = FieldAnnotation(validators =[Email()]))

    @classmethod
    def lookup(cls, id):
        r = ndb.Key(urlsafe=id).get()
        if r is None:
            raise Exception("Missing report: {}".format(id))
        return r

    def get_attachments(self):
        return Attachment.query(ancestor=self.key).order(Attachment.created).fetch()

class Attachment(SmartModel):
    created = ndb.DateTimeProperty(auto_now_add=True)
    url = ndb.TextProperty()
    file_name = ndb.TextProperty()
    size = ndb.IntegerProperty()

