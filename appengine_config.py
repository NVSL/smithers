from google.appengine.ext import vendor
import os

vendor.add(os.path.join(os.path.dirname(__file__),'server'))
vendor.add(os.path.join(os.path.dirname(__file__),'python_libs'))
