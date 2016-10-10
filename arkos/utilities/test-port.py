"""
Script to test port connectivity with the arkOS GRM server.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

from flask import Flask, Response, request
import logging
import sys

exit_code = 1

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


@app.route("/" + sys.argv[2], methods=["POST", ])
def hello():
    global exit_code
    exit_code = 0
    func = request.environ.get('werkzeug.server.shutdown')
    func()
    return Response("")


if __name__ == "__main__":
    app.run(port=int(sys.argv[1]))
    sys.exit(exit_code)
