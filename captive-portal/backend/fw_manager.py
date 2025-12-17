#!/usr/bin/env python3
import subprocess

IPSET_NAME = "portal_authorized"
IPSET_TIMEOUT = 3600  # segundos


def get_client_mac(ip: str) -> str:
    """
    Devuelve la MAC actual asociada a la IP usando la tabla ARP.
    Lanza RuntimeError si no la encuentra.
    """
    try:
        out = subprocess.check_output(
            ["arp", "-n", ip],
            stderr=subprocess.DEVNULL,
        ).decode()
    except Exception as e:
        raise RuntimeError(f"No se pudo ejecutar arp para {ip}: {e}")

    for line in out.splitlines():
        if ip in line and ":" in line:
            # Ejemplo típico:
            # 192.168.1.1  ether  7c:8b:ca:7a:fe:50  C  wlo1
            parts = line.split()
            if len(parts) >= 3:
                return parts[2].lower()

    raise RuntimeError(f"MAC no encontrada para {ip}")


def add_authorized(ip: str, timeout: int = IPSET_TIMEOUT) -> None:
    """
    Agrega (IP,MAC) al ipset portal_authorized.
    Requiere que el set exista como: hash:ip,mac timeout N.
    """
    mac = get_client_mac(ip)
    subprocess.run(
        [
            "sudo", "ipset", "add", IPSET_NAME,
            f"{ip},{mac}", "timeout", str(timeout), "--exist",
        ],
        check=True,
    )


def remove_authorized(ip: str) -> None:
    """
    Elimina la entrada (IP,MAC actual) del ipset.
    """
    mac = get_client_mac(ip)
    subprocess.run(
        ["sudo", "ipset", "del", IPSET_NAME, f"{ip},{mac}"],
        check=True,
    )


def is_authorized(ip: str) -> bool:
    """
    Verifica si la combinación (IP,MAC actual) está en el ipset.
    """
    mac = get_client_mac(ip)
    result = subprocess.run(
        ["sudo", "ipset", "test", IPSET_NAME, f"{ip},{mac}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0
