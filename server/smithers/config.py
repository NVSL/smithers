import pytz
import datetime

webapp2_config = dict()
webapp2_config['webapp2_extras.sessions'] = {
    'secret_key': 'my_secret_keyateth52ao059[2',
}

project_name="nvslsmithers"

admin_role = "admin"
admin_country = "usa"
admin_fullname="Steven Swanson"
admin_username="swanson"
admin_email_sender= "swanson@eng.ucsd.edu"
admin_email_recipients= ["swawnson@eng.ucsd.edu", "jzhao@eng.ucsd.edu" ]

comments_url="https://github.com/NVSL/smithers/issues"

local_time_zone = pytz.timezone("US/Pacific")

expectation_agreement_period = datetime.timedelta(weeks=26)

report_due_time = datetime.time(hour=2)
report_submit_period = datetime.timedelta(days=1)