# API service for running [premailer](https://github.com/peterbe/premailer)

### License: Python

## Running in development

To start the website use:

    lineman run

This will start a server on http://localhost:8000

Next, start the API server:

    gunicorn --reload -b 127.0.0.1:5000 app:app
