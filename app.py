import os
import sys
import time
import json
import contextlib
import logging
from cStringIO import StringIO
from wsgiref import simple_server

import requests
import falcon
import premailer


CORS_ORIGIN = os.environ.get('CORS_ORIGIN', 'premailer.io')


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
            raise falcon.HTTPBadRequest('Empty request body',
                                        'A valid JSON document is required.')
        body = json.loads(body.decode('utf-8'))

        if body.get('url'):
            html = self._download_url(body.pop('url'))
            if 'html' in body:
                body.pop('html')
        else:
            html = body.pop('html')
            if 'url' in body:
                body.pop('url')
        options = body
        pretty_print = options.pop('pretty_print', True)

        mylog = StringIO()
        logging_handler = logging.StreamHandler(mylog)
        logging_handler.setFormatter(logging.Formatter('%(levelname)s %(message)s'))
        options['cssutils_logging_handler'] = logging_handler
        options['cssutils_logging_level'] = logging.WARNING

        try:
            p = premailer.Premailer(html, **options)
        except TypeError as exp:
            raise falcon.HTTPBadRequest(
                'Invalid options to premailer',
                str(exp)
            )
        error = None
        warnings = None
        t0 = time.time()
        try:
            result = p.transform(pretty_print=pretty_print)
        except Exception:
            exc_type, exc_value, __ = sys.exc_info()
            error = '{} ({})'.format(exc_type.__name__, exc_value)
        warnings = mylog.getvalue()
        t1 = time.time()
        resp.status = falcon.HTTP_200
        resp.set_header('Access-Control-Allow-Origin', CORS_ORIGIN)
        resp.set_header('Content-Type', 'application/json')
        took = (t1 - t0) * 1000
        if error:
            resp.body = json.dumps({
              'errors': [error],
              'took': took,
            }, indent=2)
        else:
            resp.body = json.dumps({
              'html': result,
              'took': took,
              'warnings': warnings,
            }, indent=2)

        # cleaning up
        del p
        mylog.close()

    def _download_url(self, url):
        return requests.get(url).text


# falcon.API instances are callable WSGI apps
app = falcon.API()

app.add_route('/api/transform', TransformResource())


if __name__ == '__main__':
    httpd = simple_server.make_server('127.0.0.1', 5000, app)
    httpd.serve_forever()
