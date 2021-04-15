import datetime
import os
import sys
import time
import json
import contextlib
import logging
from io import StringIO
from wsgiref import simple_server

import requests
import falcon
import premailer
import peewee


# Models

db = peewee.PostgresqlDatabase(
    os.environ.get("PREMAILER_DATABASE_NAME", "premailer"),
    user=os.environ.get("PREMAILER_DATABASE_USER", "peterbe"),
    password=os.environ.get("PREMAILER_DATABASE_PASSWORD", "secret"),
    host=os.environ.get("PREMAILER_DATABASE_HOST", "localhost"),
    port=int(os.environ.get("PREMAILER_DATABASE_PORT", "5432")),
    # http://docs.peewee-orm.com/en/latest/peewee/database.html#using-autoconnect
    autoconnect=False,
)


class Post(peewee.Model):
    html = peewee.TextField()
    options = peewee.TextField()
    duration = peewee.FloatField(null=True)
    url = peewee.TextField(null=True)
    result = peewee.TextField(null=True)
    error = peewee.TextField(null=True)
    user_agent = peewee.TextField(null=True)
    created = peewee.DateTimeField(default=datetime.datetime.utcnow)

    class Meta:
        database = db


db.connect()
db.create_tables([Post])


def insert_post(html, options, url=None, user_agent=None):
    db.connect(reuse_if_open=True)
    row = Post(html=html, options=json.dumps(options), url=url, user_agent=user_agent)
    row.save()
    return row


def update_post(row, duration, error=None, result=None):
    assert error or result
    row.duration = duration
    if error:
        row.error = error
    else:
        row.result = result
    row.save()


# /Models

default_sample_html = """
<html>
<style>
p { color:red }
</style>
<body>
  <p>Text</p>
</body>
</html>
"""


CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "premailer.io")


@contextlib.contextmanager
def redirect_streams(stdout, stderr):
    sys.stdout = stdout
    sys.stderr = stderr
    yield
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__


class TransformResource:
    def on_post(self, req, resp):
        # req.stream corresponds to the WSGI wsgi.input environ variable,
        # and allows you to read bytes from the request body.
        #
        # See also: PEP 3333
        if req.content_length in (None, 0):
            # Nothing to do
            return

        body = req.stream.read()
        if not body:
            raise falcon.HTTPBadRequest(
                "Empty request body", "A valid JSON document is required."
            )
        body = json.loads(body.decode("utf-8"))

        url = None
        if body.get("url"):
            url = body.pop("url")
            html = self._download_url(url)
            if "html" in body:
                body.pop("html")

        else:
            html = body.pop("html")
            if "url" in body:
                body.pop("url")
        options = body

        if html.strip() != default_sample_html.strip():
            row = insert_post(html, options, url=url, user_agent=req.user_agent)
        else:
            print("Sample HTML used")

        pretty_print = options.pop("pretty_print", True)

        mylog = StringIO()
        logging_handler = logging.StreamHandler(mylog)
        logging_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        options["cssutils_logging_handler"] = logging_handler
        options["cssutils_logging_level"] = logging.WARNING

        try:
            p = premailer.Premailer(html, **options)
        except TypeError as exp:
            raise falcon.HTTPBadRequest("Invalid options to premailer", str(exp))
        error = None
        warnings = None
        t0 = time.time()
        try:
            result = p.transform(pretty_print=pretty_print)
        except Exception:
            exc_type, exc_value, __ = sys.exc_info()
            error = "{} ({})".format(exc_type.__name__, exc_value)

        warnings = mylog.getvalue()
        t1 = time.time()

        if html.strip() != default_sample_html.strip():
            if error is None:
                update_post(row, t1 - t0, result=result)
            else:
                update_post(row, t1 - t0, error=error)

        resp.status = falcon.HTTP_200
        resp.set_header("Access-Control-Allow-Origin", CORS_ORIGIN)
        resp.set_header("Content-Type", "application/json")
        took = (t1 - t0) * 1000
        if error:
            resp.body = json.dumps({"errors": [error], "took": took}, indent=2)
        else:
            resp.body = json.dumps(
                {"html": result, "took": took, "warnings": warnings}, indent=2
            )

        # cleaning up
        del p
        # mylog.close()

    def _download_url(self, url):
        return requests.get(url).text


class HealthcheckResource:
    def on_get(self, req, resp):
        db.close()
        # db.connect(reuse_if_open=True)
        db.connect()
        query = Post.select()
        resp.body = json.dumps(
            {"count": query.count(), "premailer version": premailer.__version__}
        )


# falcon.API instances are callable WSGI apps
app = falcon.API()

app.add_route("/api/transform", TransformResource())
app.add_route("/api/__healthcheck__", HealthcheckResource())


if __name__ == "__main__":
    httpd = simple_server.make_server("127.0.0.1", 5000, app)
    httpd.serve_forever()
