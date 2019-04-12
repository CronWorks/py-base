#!/usr/bin/env python

import SimpleHTTPServer
import SocketServer


class SampleProxy(SimpleHTTPServer.SimpleHTTPRequestHandler):

    def do_GET(self):
        # don't use json.dumps() because it breaks on non-primitive-ish
        dictLines = []
        for k in self.__dict__:
            dictLines.append('    "%s": "%s"' % (k, self.__dict__[k]))

        # NOTE: extra comma=bad JSON, so use join()
        result = '{\n%s\n}' % ',\n'.join(dictLines)
        self.wfile.write(result)


class HttpServer():

    def __init__(self, proxyClass, port=None):
        if port is None:
            port = 1234
        self.port = port
        self.server = SocketServer.ForkingTCPServer(('', self.port), proxyClass)

    def run(self):
        print "serving at port", self.port
        self.server.serve_forever()
        return self

    def stop(self):
        self.server.shutdown()


if __name__ == "__main__":
    '''
    the command line sample will just dump its own Python-object contents as a dict.
    To use this thing in real life, create a Proxy class with do_GET, etc. and pass in
    the class to a new HttpServer instance:

        class MyProxyClass(SimpleHTTPServer.SimpleHTTPRequestHandler):
            def do_GET(self):
                # whatever
                pass

        server = HttpServer(MyProxyClass).run()
    '''
    import sys
    port = None
    if len(sys.argv) == 2:
        port = int(sys.argv[1])
    HttpServer(SampleProxy, port).run()
