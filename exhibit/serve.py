#!/usr/bin/env python3
"""Static server for the object. Stdlib only, no nginx, no network.

The page uses history routing, so any unknown path has to return index.html
or /drift 404s on a cold boot.

    python3 serve.py [port]
"""

import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def send_head(self):
        path = self.translate_path(self.path)
        if not os.path.exists(path) and '.' not in os.path.basename(path):
            self.path = '/index.html'
        return super().send_head()

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
