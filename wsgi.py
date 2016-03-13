#!/usr/bin/env python
import os
from flask import Flask, request
from flask_restful import Resource, Api
from sqlalchemy import create_engine
import sqlite3

TABLE_FILE_NAME = "app-root/data/advantages.db"

app = Flask(__name__)
api = Api(app)

class HelloWorld(Resource):
    def get(self):
        return {'hello': 'world'}

api.add_resource(HelloWorld, '/')



def application(environ, start_response):

    c = None
    conn = None

    conn = sqlite3.connect(TABLE_FILE_NAME)
    c = conn.cursor()

    c.execute("SELECT name FROM Heroes WHERE Heroes._id = 5")
    oneEntry = c.fetchone()
   

    ctype = 'text/plain'
    if environ['PATH_INFO'] == '/health':
        response_body = "1"
    elif environ['PATH_INFO'] == '/env':
        response_body = ['%s: %s' % (key, value)
                    for key, value in sorted(environ.items())]
        response_body = '\n'.join(response_body)
    else:
        ctype = 'text/html'
        response_body = '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
  <title>Welcome to OpenShift</title>
</head>
<body>
        <h1>Hello world!</h1>
        <h2>{}</h2>
</body>
</html>'''.format(oneEntry)
    response_body = response_body.encode('utf-8')

    status = '200 OK'
    response_headers = [('Content-Type', ctype), ('Content-Length', str(len(response_body)))]
    #
    start_response(status, response_headers)
    return [response_body ]

#
# Below for testing only
#
if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    httpd = make_server('localhost', 8051, application)
    # Wait for a single request, serve it and quit.
    httpd.handle_request()
    app.run(debug=True)
