from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import ssl

server = ThreadingHTTPServer(("0.0.0.0", 8443), SimpleHTTPRequestHandler)
server.socket = ssl.wrap_socket(
    server.socket,
    keyfile="cert/server.key",
    certfile="cert/server.crt",
    server_side=True
)
print("HTTPS activo en 8443")
server.serve_forever()
