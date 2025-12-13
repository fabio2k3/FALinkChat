# test_portal.py
import socket
from urllib.parse import parse_qs

# Diccionario de usuarios válidos
USERS = {
    "admin": "admin123",
    "user1": "password1"
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

def run_server():
    host = "0.0.0.0"
    port = 8080

    print(f"[gateway] Portal cautivo escuchando en {host}:{port}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(5)

        while True:
            conn, addr = s.accept()
            client_ip = addr[0]
            with conn:
                request = conn.recv(1024).decode()
                
                # Detectar POST
                if "POST" in request:
                    try:
                        body = request.split("\r\n\r\n")[1]
                        data = parse_qs(body)
                        username = data.get("username", [""])[0]
                        password = data.get("password", [""])[0]

                        if USERS.get(username) == password:
                            AUTHENTICATED.add(client_ip)
                            conn.sendall(build_response(SUCCESS_PAGE))
                        else:
                            conn.sendall(build_response(LOGIN_PAGE))
                    except Exception:
                        conn.sendall(build_response(LOGIN_PAGE))
                else:
                    # GET: si autenticado, acceso libre
                    if client_ip in AUTHENTICATED:
                        conn.sendall(build_response("<h1>Acceso a Internet concedido</h1>"))
                    else:
                        conn.sendall(build_response(LOGIN_PAGE))

if __name__ == "__main__":
    run_server()
