from google.appengine.ext import vendor
import os

vendor.add(os.path.join(os.path.dirname(__file__),'server'))
vendor.add(os.path.join(os.path.dirname(__file__),'python_libs'))


# GAE doesn't support SpooledTemporaryFile and the normal TemporaryFile doesn't take max_size.  Drop max_size.
import tempfile
def MonkeyTempFile(max_size=None, *args, **kwargs):
    return tempfile.TemporaryFile(*args, **kwargs)

tempfile.SpooledTemporaryFile = MonkeyTempFile
