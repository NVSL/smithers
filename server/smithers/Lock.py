import datetime
from google.appengine.ext import ndb
from SmartModel import SmartModel, FieldAnnotation
from flask import request, Blueprint, Response
import re
import functools
import json
import requests
import requests_toolbelt.adapters.appengine
requests_toolbelt.adapters.appengine.monkeypatch()
import os

if os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine/'):
    # deployment
    bot_token = "xoxb-387044746918-450535067811-YKOGCOiuQkwlMwmxeozobeyv"
else:
    # testing
    bot_token = "xoxb-387044746918-450796593989-XxfFDDFm3sHSWS4Hi7iQUZjz"

lock_ops = Blueprint("lock_ops", __name__)
resource_parent_key = ndb.Key("Lock", "lock")

class Resource(SmartModel):
    name = ndb.StringProperty()
    created = ndb.DateProperty(auto_now_add=True)
    lock_holder = ndb.StringProperty()

    def lock(self, user):
        self.lock_holder = user
        self.put()

    def unlock(self):
        self.lock_holder = None
        self.put()

    def is_locked(self):
        return self.lock_holder

    def lock_holder_at(self):
        return "<@{}>".format(self.lock_holder) if self.lock_holder else "no one"

class ResourceGroup(SmartModel):
    channel_name = ndb.StringProperty()
    channel_id = ndb.StringProperty()

    @classmethod
    def get_by_id(cls, id):
        r = ResourceGroup.query(ResourceGroup.channel_id == id, ancestor=resource_parent_key).get()
        if r:
            return r
        else:
            new = ResourceGroup(channel_id=request.values['channel_id'],
                                channel_name=request.values['channel_name'],
                                parent=resource_parent_key)
            new.put()
            return new

    def get_resources(self):
        return Resource.query(ancestor=self.key).fetch()

    def get_resource_by_name(self, name):
        return Resource.query(Resource.name == name, ancestor=self.key).get()

def success(text, list=None):
    if list:
        text = (text and (text + "\n")) + "\n".join(filter(lambda x:x, list))
    t = dict(text=text)
    r = json.dumps(t)
    print r
    return Response(r, mimetype='application/json')

def invoke(f):
    @functools.wraps(f)
    def wrapper():
        group = ResourceGroup.get_by_id(request.values['channel_id'])
        return f(group, re.split("\s+", request.values['text']))
    return wrapper


def list_resources(group, args):
    resources = group.get_resources()

    return success("Channel resources:\n".format(len(resources)),
                   list=map(lambda x: "*{}* {}".format(x.name, ":lock: {}".format(x.lock_holder_at()) if x.is_locked() else ""), sorted(resources, key=lambda x: x.name)))


def create_resource(group, args):
    created = []
    preexisting = []
    for name in args:
        if group.get_resource_by_name(name):
            preexisting.append(name)
        else:
            new = Resource(parent=group.key,
                           name=name)
            new.put()
            created.append(name)

    if created:
        notify_channel("<@{}> created {}.".format(request.values['user_id'], ", ".join(map(lambda x: "*{}*".format(x), created))))

    if preexisting:
        return success("",
                       [
                           preexisting and "Already existing: {}".format(", ".join(map(lambda x: "*{}*".format(x), preexisting)))
                       ])
    else:
        return ""

#    return success("Created *{}*".format(name))

#    return success("Resource *{}* already exists.".format(name))


def delete_resource(group, args):
    existed = []
    missing = []
    for name in args:
        r = group.get_resource_by_name(name)
        if not group.get_resource_by_name(name):
            missing.append(name)
        else:
            r.key.delete()
            existed.append(name)

    if existed:
        notify_channel("<@{}> deleted {}.".format(request.values['user_id'], ", ".join(map(lambda x: "*{}*".format(x), existed))))

    if missing:
        return success("",
                   [
                       missing and "Does not exist: {}".format(", ".join(map(lambda x: "*{}*".format(x), missing)))
                   ])
    else:
        return ""

def grab_resource(group, args):
    name = args[0]

    r = group.get_resource_by_name(name)
    if not r:
        return success("*{}* not found.".format(name))
    if r.is_locked():
        return success("*{}* is locked by {}.".format(r.name, r.lock_holder_at()))

    r.lock(request.values['user_id'])
    notify_channel("<@{}> locked *{}*.".format(request.values['user_id'], name))
    return ""


def notify_channel(text):
    payload = dict(text=text,
                   channel=request.values['channel_id'],
                   token=bot_token)
    requests.post("https://slack.com/api/chat.postMessage",
                  data=payload)


def release_resource(group, args):
    name = args[0]

    r = group.get_resource_by_name(name)
    if not r:
        return success("*{}* not found.".format(name))
    if not r.is_locked():
        return success("*{}* is not locked.".format(r.name, r.lock_holder_at()))
    else:
        if r.lock_holder != request.values['user_id']:
            return success("*{}* is locked by {}.".format(r.name, r.lock_holder_at()))
        else:
            r.unlock()
            notify_channel("<@{}> unlocked *{}*.".format(request.values['user_id'], name))
            return ""


def help(group, args):
    return success("""
    Usage:
    * `/locker list|ls` -- List resources.
    * `/locker add|create <name> <name>...` -- Create a new resource.
    * `/locker delete|del|remove|rm <name>` -- Delete a resource.
    * `/locker lock|grab|take <name> <name>...` -- Lock a resource.
    * `/locker unlock|drop|release <name>` -- Unlock a resource.
    """)

@lock_ops.route('/go', methods=['GET','POST'])
def go():
    group = ResourceGroup.get_by_id(request.values['channel_id'])
    args = re.split("\s+", request.values['text'])
    print request.values
    if args[0].lower() in ["list", "ls"]:
        return list_resources(group, args[1:])
    elif args[0].lower() in ["create", "add"]:
        return create_resource(group, args[1:])
    elif args[0].lower() in ["delete", "del", "remove", "rm"]:
        return delete_resource(group, args[1:])
    elif args[0].lower() in ["take", "lock", "grab"]:
        return grab_resource(group, args[1:])
    elif args[0].lower() in ["help", "?"]:
        return help(group, args[1:])
    elif args[0].lower() in ["release", "unlock", "drop"]:
        return release_resource(group, args[1:])
    else:
        return "Unknown command: {}".format(request.values['text'])