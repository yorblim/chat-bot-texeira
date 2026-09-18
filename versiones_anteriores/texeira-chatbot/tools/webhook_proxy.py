"""Proxy local de demostración: publica únicamente /webhook, nunca el dashboard."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from http.client import HTTPConnection


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # No registrar tokens de verificación ni contenido de mensajes.

    def forward(self):
        self.connection.settimeout(15)
        if urlsplit(self.path).path != '/webhook':
            self.send_error(404)
            return
        if self.headers.get('Transfer-Encoding'):
            self.send_error(400)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            self.send_error(400)
            return
        if not 0 <= length <= 1048576:
            self.send_error(413)
            return
        upstream = HTTPConnection('127.0.0.1', 8000, timeout=110)
        try:
            body = self.rfile.read(length) if length else None
            headers = {'Content-Type': self.headers.get('Content-Type', 'application/json')}
            signature = self.headers.get('X-Hub-Signature-256')
            if signature:
                headers['X-Hub-Signature-256'] = signature
            upstream.request(self.command, self.path, body=body, headers=headers)
            response = upstream.getresponse()
            data = response.read()
            self.send_response(response.status)
            self.send_header('Content-Type', response.getheader('Content-Type', 'text/plain'))
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (OSError, TimeoutError):
            self.send_error(502)
        finally:
            upstream.close()

    do_GET = forward
    do_POST = forward


if __name__ == '__main__':
    print('Proxy webhook en 127.0.0.1:8001', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8001), Handler).serve_forever()
