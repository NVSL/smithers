from flask import Blueprint
from google.appengine.ext import ndb

from smithers.util import localize_time

report_ops = Blueprint("report_ops", __name__)
report_parent_key = ndb.Key("Report", "reports")

class Report(ndb.Model):
    """A main model for representing users."""
    created = ndb.DateTimeProperty(auto_now_add=True)

    long_term_goal = ndb.TextProperty()
    previous_weekly_goals = ndb.TextProperty()
    progress_made  = ndb.TextProperty()
    problems_encountered = ndb.TextProperty()
    next_weekly_goals = ndb.TextProperty()
    report_for_date = ndb.DateProperty()
    student = ndb.StringProperty()

    def delete(self):
        self.key.delete()

    def local_created_time(self):

        return localize_time(self.created)