from google.appengine.ext import ndb
from flask import redirect, url_for, request, render_template, Blueprint
from flask_wtf import FlaskForm
from wtforms_appengine.ndb import model_form
from wtforms.fields import SubmitField, StringField, HiddenField
from wtforms_components import read_only
from util import namedtuple_with_defaults

smart_model = Blueprint("smart_model", __name__)


FieldAnnotation = namedtuple_with_defaults("FieldAnnotation",
                                           ["label",
                                            "description",
                                            "validators",
                                            "read_only"],
                                           [None,
                                            None,
                                            [],
                                            False])

def smart_form(model, *args, **kwargs):
    base = model_form(model, *args, field_args=model.wtf_field_args(), **kwargs)
    class T(base):
        key=  StringField()
        urlsafe = StringField()
        submit = SubmitField()

        hidden_urlsafe = HiddenField()
        hidden_key = HiddenField()
        _modelType =  model

        def __init__(self, *args, **kwargs):
            super(base, self).__init__(*args, **kwargs)
            read_only(self.urlsafe)
            read_only(self.key)

            for key, annotations in model.field_annotations().items():
                if key in self:
                    if annotations.__dict__.get("read_only", False):
                        read_only(self[key])

    T.__name__ = model._get_kind() + "Form"
    return T

class SmartModel(ndb.Model):

    @classmethod
    def field_annotations(cls):
        return None

    @classmethod
    def formatted_members(cls):
        return []

    @classmethod
    def wtf_field_args(cls):
        return {x:y.__dict__ for (x,y) in cls.field_annotations().items() if x in ["label",
                                                                                  "validators",
                                                                                  "filters",
                                                                                  "description",
                                                                                  "id",
                                                                                  "default",
                                                                                  "widget"] }

@smart_model.route("/<key>", methods=["POST", "GET"])
def ndb_edit(key):
    entity = ndb.Key(urlsafe=key).get()
    the_type = type(entity)
    FormType = smart_form(the_type,
                          base_class=FlaskForm)
    form = FormType(request.form)

    form.key.data = request.form.get('hidden_key', 'aoe')
    form.urlsafe.data = request.form.get('hidden_urlsafe', "ffo")

    if request.method == "POST":
        if form.validate():
            try:
                form.populate_obj(entity)
                entity.put()
                return redirect(url_for(request.endpoint, notification="Update Saved", key=key))
            except:
                return redirect(url_for(request.endpoint, error="Not Saved", key=key))
        else:
            return render_template("generic_gae_model.jinja.html",
                                   form=form)
    else:
        form = FormType(obj=entity)
        form['urlsafe'].data = entity.key.urlsafe()
        form.hidden_key.data = entity.key
        form.hidden_urlsafe.data = entity.key.urlsafe()
        return render_template("generic_gae_model.jinja.html",
                               form=form)
