#!/usr/bin/env python
import cherrypy
from cherrypy._cpserver import Server
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import WebSocket
from time import sleep
import BaseHTTPServer
import argparse
from urllib import quote_plus
import json
from urlparse import urlparse, parse_qs
import Cookie
import base64

channels = {}
reply = None

PROXY_JS = """\

function _arrayBufferToBase64( buffer ) {{
    var binary = '';
    var bytes = new Uint8Array( buffer );
    var len = bytes.byteLength;
    for (var i = 0; i < len; i++) {{
        binary += String.fromCharCode( bytes[ i ] );
    }}
    return window.btoa( binary );
}}

var connection = new WebSocket('ws://{}/ws');

connection.onopen = function () {{
  connection.send('{{ "type": "register", "id": "{}" }}');
}};

connection.onerror = function (error) {{
  console.log('WebSocket Error ' + error);
}};

connection.onmessage = function (e) {{
  var request = JSON.parse(e.data);
  var method = request.method;
  var query = request.query;
  var data = request.data;
  var headers = request.headers;

  console.log(query);
  var xhr = new XMLHttpRequest();
  xhr.responseType = 'arraybuffer'
  xhr.onreadystatechange = function() {{
    if (xhr.readyState == 4) {{
        var msg = {{"type": "reply", "request": e.data, "reply": {{ "status": xhr.status, "data": _arrayBufferToBase64(xhr.response), "headers": xhr.getAllResponseHeaders() }} }};
        connection.send(JSON.stringify(msg));
    }}
  }}
  xhr.open(method, query, true);
  for (header in headers) {{
      xhr.setRequestHeader(header.name, header.value);
  }}
  xhr.send(data);
}};
"""

class Root(object):
    @cherrypy.expose
    def runproxy(self, id="default"):
        return '<script src="/proxy.js?id={}"></script>'.format(quote_plus(id))

    @cherrypy.expose
    def proxy_js(self, id="default"):
        cherrypy.response.headers['Content-Type'] = 'text/javascript'
        host = cherrypy.request.headers['Host']
        return PROXY_JS.format(host, id)

    @cherrypy.expose
    def ws(self):
        handler = cherrypy.request.ws_handler

class RequestChannel(object):
    def __init__(self, socket):
        self.socket = socket
        self.reply = None

class ProxyWebSocket(WebSocket):
    def handle_register(self, msg):
        self.id = msg['id']
        if self.id in channels:
            self.close()
            return
        self.channel = RequestChannel(self)
        channels[self.id] = self.channel

    def handle_reply(self, msg):
        self.channel.reply = msg["reply"]

    def closed(self, code, reason=None):
        try:
            del channels[self.id]
        except NameError:
            pass

    def received_message(self, message):
        msg = json.loads(message.data)
        if msg['type'] == 'register':
            self.handle_register(msg)
        elif msg['type'] == 'reply':
            self.handle_reply(msg)

FORWARD_HEADERS = ['set-cookie']

class ProxyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def _write_reply(self, reply):
        body = base64.b64decode(reply["data"])
        self.send_response(reply["status"])
        for header in reply["headers"].splitlines():
            name, value = map(lambda s: s.strip(), header.split(':', 1))
            if name.lower() in FORWARD_HEADERS:
                self.send_header(name, value)
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)
    def _write_html(self, html):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html)

    def getid(self):
        if "Cookie" in self.headers:
            c = Cookie.SimpleCookie(self.headers["Cookie"])
            if 'id' in c:
                return c['id'].value
        return None

    def setcookie(self, name, value):
        c = Cookie.SimpleCookie()
        c[name] = value
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.wfile.write(c.output()+'\n')
        self.end_headers()
        self.wfile.write("OK")

    def do_req(self, method):
        id = self.getid()
        if id == None:
            self._write_html("No cookie set, go to /_connect?id=ID")
            return

        if not id in channels:
            self._write_html("id not found, go to /_connect?id=ID")
            return

        channel = channels[id]

        content_len = int(self.headers.getheader('content-length', 0))
        body = self.rfile.read(content_len)
        headers = []
        for name, value in self.headers.dict.iteritems():
            headers.append({"name": name, "value": value})
        req = {"method": method, "query": self.path, "data": body, "headers": headers}
        channel.socket.send(json.dumps(req), False)

        while channel.reply == None:
            sleep(0.1)

        ret = channel.reply
        channel.reply = None
        self._write_reply(ret)

    def do_POST(self):
        self.do_req("POST")

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/_connect':
            self.setcookie("id", parse_qs(url.query)["id"][0])
            return

        self.do_req("GET")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='HTTP proxy between two clients using websockets. To connect the target, visit http://domain:targetport/runproxy or include http://domain:targetport/proxy.js')
    parser.add_argument('--targetport', default='18082', type=int)
    parser.add_argument('--proxyport', default='18083', type=int)
    args = parser.parse_args()

    cherrypy.config.update({'server.socket_host': '0.0.0.0', 'server.socket_port': args.targetport})
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
