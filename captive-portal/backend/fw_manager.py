import subprocess
def add_authorized(ip):
    """Agrega una IP al ipset portal_authorized, sin fallar si ya existe."""
    subprocess.run(["sudo", "ipset", "add", "portal_authorized", ip, "--exist"], check=True)

def remove_authorized(ip):
    """Quita una IP del ipset."""
    subprocess.run(["sudo", "ipset", "del", "portal_authorized", ip], check=True)

def is_authorized(ip):
    """Verifica si una IP ya está en portal_authorized."""
    result = subprocess.run(["sudo", "ipset", "test", "portal_authorized", ip])
    return result.returncode == 0
