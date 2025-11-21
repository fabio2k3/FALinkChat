import subprocess

def add_authorized(ip):
    """Agrega una IP al ipset AUTHORIZED, sin fallar si ya existe."""
    subprocess.run(["sudo", "ipset", "add", "AUTHORIZED", ip, "--exist"], check=True)

def remove_authorized(ip):
    """Quita una IP del ipset."""
    subprocess.run(["sudo", "ipset", "del", "AUTHORIZED", ip], check=True)

def is_authorized(ip):
    """Verifica si una IP ya está en AUTHORIZED."""
    result = subprocess.run(["sudo", "ipset", "test", "AUTHORIZED", ip])
    return result.returncode == 0