import collections
import functools
import flask_login
import flask
import pytz
from flask import request

from smithers import config


def role_required(role):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if flask_login.current_user.has_role(role):
                return func(*args, **kwargs)
            else:
                t = flask.url_for("user_ops.wrong_role", url="{}/{}".format(flask.request.args["base_url"],
                                                                                              flask.request.args["full_path"]))
                return flask.redirect(t)
        return wrapper
    return decorator

def trunc_string(m, max_len=30):
    m = str(m)
    if m is None:
        return "na"
    if len(m) > max_len:
        return m[0:(max_len - 3)] + "..."
    else:
        return m

DataCell = collections.namedtuple("DataCell",['column', 'display','link','css_class','alt_txt','sort_key',"formatter"])


class DataCellFormatter(object):
    def __init__(self,
                 column_name,
                 show=True,
                 display=None,
                 display_format=lambda x:x,
                 ex_display="error",
                 link=lambda x: None,
                 ex_link="_missing",
                 css_class=lambda x: None,
                 ex_css_class="gtron-error",
                 alt_txt=lambda x: None,
                 ex_alt_txt=None,
                 sort_key=None,
                 ex_sort_key="_",
                 method=None
                 ):

        self.column_name = column_name
        self.css_class = css_class
        self.show = show
        self.link = link
        self.method = method
        self.ex_display=ex_display
        self.ex_css_class=ex_css_class
        self.ex_link=ex_link
        self.display_format = display_format
        self.sort_key = sort_key
        self.ex_sort_key = ex_sort_key
        self.alt_txt = alt_txt
        self.ex_alt_txt = ex_alt_txt

        if display is None:
            self.display = lambda j: getattr(j,column_name)
        else:
            self.display = display

        if sort_key is None:
            self.sort_key = self.display
        else:
            self.sort_key = sort_key

    def format(self,v):
        try:
            display = self.display_format(self.display(v))
        except Exception as e:
            #traceback.print_exc()
            if self.ex_display == "__EXCEPTION__":
                display = str(e)
            else:
                display = self.ex_link

        try:
            link = self.link(v)
        except Exception as e:
            #traceback.print_exc()
            if self.ex_link == "__EXCEPTION__":
                link = str(e)
            else:
                link = self.ex_link

        try:
            css_class = self.css_class(v)
        except Exception as e:
            #traceback.print_exc()
            css_class = self.ex_css_class

        try:
            alt_txt = self.alt_txt(v)
        except Exception as e:
            #traceback.print_exc()
            alt_txt = self.ex_alt_txt

        try:
            sort_key = self.sort_key(v)
        except Exception as e:
            #traceback.print_exc()
            sort_key = self.ex_sort_key


        return DataCell(column=self.column_name,
                        display=display,
                        link=link,
                        css_class=css_class,
                        alt_txt=alt_txt,
                        sort_key=sort_key,
                        formatter=self
                        )


DFC = DataCellFormatter
Time = functools.partial(DFC, display_format=lambda x: x.strftime("%x %X"))
Latency = functools.partial(DFC, display_format=lambda x: int(x.total_seconds()))
Truncator = functools.partial(DFC, display_format=lambda x: trunc_string(x))


class Bunch(dict):
    def __init__(self, **kw):
        dict.__init__(self, kw)
        self.__dict__.update(kw)


TableSpec = collections.namedtuple("TableSpec", ['name',
                                                 'records',
                                                 'headings',
                                                 'sort_field',
                                                 'sort_direction',
                                                 'filter_field',
                                                 'filter_value',
                                                 'selector_name'])
ListSpec = collections.namedtuple("ListSpec", ['name', 'record', 'labels'])


def build_list_spec(name,
                    entity,
                    fields):
    labels = [d.column_name for d in fields if d.show]
    record = Bunch(**{c.column_name: c.format(entity) for c in fields})

    list = ListSpec(name=name,
                    record=record,
                    labels=labels)
    return list


def build_table_spec(
                     table_name,
                     entities,
                     columns,
                     default_sort_key,
                     default_sort_reversed=False,
                     selector_name=lambda x: x):
    filter_field = request.args.get('{}:filter_field'.format(table_name))
    filter_value = request.args.get('{}:filter_value'.format(table_name))
    sort_field = request.args.get('{}:sort_field'.format(table_name), default_sort_key)
    sort_direction = bool(request.args.get('{}:sort_reversed'.format(table_name), default_sort_reversed))
    headings = [d.column_name for d in columns if d.show]
    records = []
    for j in entities:
        record = Bunch(**{c.column_name: c.format(j) for c in columns})

        if filter_field is not None and filter_field != "":
            if record.get(filter_field) == filter_value:
                records.append(record)
        else:
            records.append(record)
    table = TableSpec(name=table_name,
                      records=sorted(records, key=lambda x: x[sort_field].sort_key, reverse=sort_direction),
                      headings=headings,
                      sort_field=sort_field,
                      sort_direction=sort_direction,
                      filter_field=filter_field,
                      filter_value=filter_value,
                      selector_name=selector_name)
    return table



def next_url(default):
    return default if "next" not in request.args else request.args["next"];


def localize_time(time):
    return time.replace(tzinfo=pytz.UTC).astimezone(config.local_time_zone)