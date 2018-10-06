import datetime
from google.appengine.ext import ndb
from SmartModel import SmartModel, FieldAnnotation
from flask import request, Blueprint, Response
import re
import functools
import json



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
    return Response(r, mimetype='application/json')

def invoke(f):
    @functools.wraps(f)
    def wrapper():
        group = ResourceGroup.get_by_id(request.values['channel_id'])
        return f(group, re.split("\s+", request.values['text']))
    return wrapper


def list_resources(group, args):
    resources = group.get_resources()
    return success("There are {} resources:\n".format(len(resources)),
                   list=map(lambda x: "{} owned by {}{}".format(x.name, "@" if x.lock_holder else "", x.lock_holder), resources))


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

    return success("",
                   [
                       created and "Created: {}".format(", ".join(map(lambda x: "'{}'".format(x),created))),
                       preexisting and "Already existing: {}".format(", ".join(map(lambda x: "'{}'".format(x), preexisting)))
                   ])
#    return success("Created '{}'".format(name))

#    return success("Resource '{}' already exists.".format(name))


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

    return success("",
                   [
                       existed and "Deleted: {}".format(", ".join(map(lambda x: "'{}'".format(x),existed))),
                       missing and "Does not exist: {}".format(", ".join(map(lambda x: "'{}'".format(x), missing)))
                   ])

def grab_resource(group, args):
    name = args[0]

    r = group.get_resource_by_name(name)
    if not r:
        return success("No resource named '{}'.".format(name))
    if r.is_locked():
        return success("Resource '{}' is locked by '{}'.".format(r.name, r.lock_holder))
    r.lock(request.values['user_name'])
    return success("Locked resource '{}'.".format(name))


def release_resource(group, args):
    name = args[0]

    r = group.get_resource_by_name(name)
    if not r:
        return success("No resource named '{}'.".format(name))
    if not r.is_locked():
        return success("Resource '{}' is locked by '{}'.".format(r.name, r.lock_holder))
    else:
        if r.lock_holder != request.values['user_name']:
            return success("Resource '{}' is locked by, but not by you.".format(name))
        else:
            r.unlock()
            r.put()
            return success("Locked resource '{}'.".format(name))


def help(group, args):
    return success("""
    Usage:
    * `/locker list|ls` -- List resources.
    * `/locker add|create <name> <name>...` -- Create a new resource.
    * `/locker delete|del|remove <name>` -- Delete a resource.
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
    elif args[0].lower() in ["delete", "del", "remove"]:
        return delete_resource(group, args[1:])
    elif args[0].lower() in ["take", "lock", "grab"]:
        return grab_resource(group, args[1:])
    elif args[0].lower() in ["help", "?"]:
        return help(group, args[1:])
    elif args[0].lower() in ["release", "unlock", "drop"]:
        return release_resource(group, args[1:])
    else:
        return "Unknown command: {}".format(request.values['text'])