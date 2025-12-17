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
    
    # Debug: mostrar usuarios cargados
    print(f"[DEBUG] Usuarios cargados: {list(USERS.keys())}")
    return USERS 


def check_user(user, pwd):
    """Verifica si usuario y contraseña son correctos."""
    is_valid = USERS.get(user) == pwd
    
    # Debug detallado
    if user in USERS:
        print(f"[DEBUG] Usuario '{user}' existe. Password correcta: {is_valid}")
    else:
        print(f"[DEBUG] Usuario '{user}' NO existe en la base de datos")
        print(f"[DEBUG] Usuarios disponibles: {list(USERS.keys())}")
    
    return is_valid