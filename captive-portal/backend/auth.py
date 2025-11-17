USERS = {}

def load_users(path="config/users.txt"):
    """Carga las credenciales desde archivo: usuario:clave por línea."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                user, pwd = line.split(":", 1)
                USERS[user] = pwd

def check_user(user, pwd):
    """Verifica si usuario y contraseña son correctos."""
    return USERS.get(user) == pwd
