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

    is_draft_computed = ndb.ComputedProperty(lambda self: True if self.is_draft_report else False)

    def get_advisor_comments(self):
        if self.advisor_comments:
            return self.advisor_comments
        else:
            return ""

    def delete(self):
        self.key.delete()

    def local_created_time(self):
        return localize_time(self.created)

    def is_draft(self):
        return self.is_draft_computed

    @classmethod
    def field_annotations(cls):
        return dict(student = FieldAnnotation(validators =[Email()]))

    @classmethod
    def lookup(cls, id):
        r = ndb.Key(urlsafe=id).get()
        if r is None:
            raise Exception("Missing report: {}".format(id))
        return r


class Attachment(SmartModel):
    created = ndb.DateTimeProperty(auto_now_add=True)
    url = ndb.TextProperty()
    file_name = ndb.TextProperty()
