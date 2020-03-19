#!/usr/bin/env python

import os
from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from ctplot.wsgi import application


def main():
    address = os.environ['CTPLOT_ADDRESS'] if 'CTPLOT_ADDRESS' in os.environ else ''
    port = int(os.environ['CTPLOT_PORT']) if 'CTPLOT_PORT' in os.environ else 8080
    print 'listening on %s:%d' % (address, port)

    http_server = HTTPServer(WSGIContainer(application))
    http_server.listen(port, address=address)
    IOLoop.instance().start()

if __name__ == '__main__':
    main()
