from google.appengine.ext import ndb
from flask import redirect, url_for, request, render_template, Blueprint, flash
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

def smart_form(model, key_string, *args, **kwargs):
    base = model_form(model, *args, field_args=model.wtf_field_args(), **kwargs)
    class T(base):
        key=  StringField()
        urlsafe = StringField()
        save = SubmitField(label="Save")
        really_delete = StringField(label="To delete, enter urlsafe value")
        delete = SubmitField(label="Delete")

        hidden_urlsafe = HiddenField()
        hidden_key = HiddenField()
        _modelType =  model

        def __init__(self, *args, **kwargs):
            super(base, self).__init__(*args, **kwargs)
            read_only(self.urlsafe)
            read_only(self.key)

            for key, annotations in model.field_annotations().items():
                if key in self:
                    if annotations._asdict().get("read_only", False):
                        read_only(self[key])

    T.__name__ = model._get_kind() + "Form"
    return T

class SmartModel(ndb.Model):

    @classmethod
    def field_annotations(cls):
        return {}

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
    if entity is None:
        return ("",404)
    the_type = type(entity)
    FormType = smart_form(the_type,
                          key,
                          base_class=FlaskForm)
    form = FormType(request.form)

    form.key.data = request.form.get('hidden_key', 'aoe')
    form.urlsafe.data = request.form.get('hidden_urlsafe', "ffo")

    if request.method == "POST":
        if form.validate():
            if "save" in request.form:
                try:
                    form.populate_obj(entity)
                    entity.put()
                    flash("Update Succeeded", category='success')
                    return redirect(url_for(request.endpoint, key=key))
                except:
                    flash("Update failed",category="error")
                    return redirect(url_for(request.endpoint, key=key))
            elif "delete" in request.form:
                if request.form['really_delete'] != entity.key.urlsafe():
                    flash("Delete not confirmed.  Entity not deleted.", category='warning')
                    return redirect(url_for(request.endpoint, key=key))
                
                try:
                    entity.key.delete()
                    flash("Deleted entity", category='success')
                    return redirect("/")
                except:
                    flash("Deletion failed", category='error')
                    return redirect(url_for(request.endpoint, key=key))
            else:
                raise Exception("Illegal submission")
        else:
            return render_template("generic_gae_model.jinja.html",
                                   form=form,
                                   entity=entity)
    else:
        form = FormType(obj=entity)
        form['urlsafe'].data = entity.key.urlsafe()
        form.hidden_key.data = entity.key
        form.hidden_urlsafe.data = entity.key.urlsafe()
        return render_template("generic_gae_model.jinja.html",
                               form=form,
                               entity=entity)
