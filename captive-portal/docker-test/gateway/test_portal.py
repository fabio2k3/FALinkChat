import os
import socket
from urllib.parse import parse_qs, urlparse

# Diccionario de usuarios válidos desde variables de entorno
USERS = {
    os.environ.get("USER1", "admin"): os.environ.get("PASS1", "admin123"),
    os.environ.get("USER2", "user1"): os.environ.get("PASS2", "password1")
}

# Clientes autenticados (IP)
AUTHENTICATED = set()

LOGIN_PAGE = """\
<!DOCTYPE html>
<html>
<body>
<h1>Portal Cautivo</h1>
<form method='POST'>
Usuario: <input name='username'><br>
Password: <input name='password' type='password'><br>
<button type='submit'>Login</button>
</form>
</body>
</html>
"""

SUCCESS_PAGE = """\
<!DOCTYPE html>
<html>
<body>
<h1>¡Autenticación correcta!</h1>
<p>Ahora tienes acceso a Internet.</p>
</body>
</html>
"""

def build_response(body):
    response = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/html\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        "\r\n" +
        body
    )
    return response.encode()

def allow_client(ip):
    # Permitir tráfico HTTP hacia Internet
    os.system(f"iptables -t nat -I PREROUTING -s {ip} -p tcp --dport 80 -j ACCEPT")
    os.system(f"iptables -t nat -I POSTROUTING -s {ip} -o eth0 -j MASQUERADE")

def handle_request(request, client_ip):
    # Intentar extraer datos de POST
    if "POST" in request:
        try:
            body = request.split("\r\n\r\n")[1]
            data = parse_qs(body)
            username = data.get("username", [""])[0]
            password = data.get("password", [""])[0]
        except Exception:
            username = password = ""
    else:
        # Intentar extraer credenciales de query string GET /?username=...&password=...
        try:
            first_line = request.splitlines()[0]
            path = first_line.split()[1]  # GET /?... HTTP/1.1
            query = urlparse(path).query
            data = parse_qs(query)
            username = data.get("username", [""])[0]
            password = data.get("password", [""])[0]
        except Exception:
            username = password = ""

    if USERS.get(username) == password:
        AUTHENTICATED.add(client_ip)
        allow_client(client_ip)
        return build_response(SUCCESS_PAGE)
    else:
        if client_ip in AUTHENTICATED:
            return build_response("<h1>Acceso a Internet concedido</h1>")
        else:
            return build_response(LOGIN_PAGE)

def run_server():
    host = "0.0.0.0"
    port = 8080

    print(f"[gateway] Portal cautivo escuchando en {host}:{port}")
    print(f"[gateway] Usuarios válidos: {USERS}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(5)

        while True:
            conn, addr = s.accept()
            client_ip = addr[0]
            with conn:
                request = conn.recv(1024).decode()
                response = handle_request(request, client_ip)
                conn.sendall(response)

if __name__ == "__main__":
    run_server()
