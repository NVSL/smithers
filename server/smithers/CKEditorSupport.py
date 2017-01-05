import cloudstorage as gcs
from flask import request, Blueprint
import datetime
import random
import os

bucket = "nvsl-progress-reports.appspot.com"

ckeditor_ops = Blueprint("ckeditor_ops", __name__)

def gen_rnd_filename():
    """generate a random filename by time"""
    filename_prefix = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    return "%s%s" % (filename_prefix, str(random.randrange(1000, 10000)))


@ckeditor_ops.route("/cke/upload", methods=['POST', 'OPTIONS'])
def upload_ckeditor_file():
    filename = {}
    callback = request.args.get("CKEditorFuncNum")

    if request.method == 'POST' and 'upload' in request.files:
        fileobj = request.files['upload']
        fname, fext = os.path.splitext(fileobj.filename)
        rnd_name = '{}{}'.format(gen_rnd_filename(), fext)

        gcs_file = gcs.open("/{}/{}".format(bucket,
                                            rnd_name),
                            'w',
                            content_type=fileobj.mimetype)

        gcs_file.write(fileobj.read())
        gcs_file.close()


        if os.environ["SERVER_NAME"] == "localhost":
            url="http://localhost:8080/_ah/gcs/nvsl-progress-reports.appspot.com/{}".format(rnd_name)
        else:
            url="https://storage.cloud.google.com/nvsl-progress-reports.appspot.com/{}".format(rnd_name)
        error = ""
        # if not path:
        #     url = url_for('.static', filename='%s/%s' % (folder, rnd_name))
        # else:
        #     url = url_for('.uploaded_file', filename='%s/%s' % (folder, rnd_name))

    res = """
            <script type="text/javascript">
                window.parent.CKEDITOR.tools.callFunction('%s', '%s', '%s');
            </script>
         """ % (callback, url, error)

    return res



