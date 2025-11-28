import subprocess
import sys

ip = sys.argv[1]

def get_mac(ip):
    out = subprocess.check_output(["arp", "-n", ip]).decode()
    parts = out.split()
    for p in parts:
        if ":" in p and len(p) == 17:
            return p.lower()
    return None

mac = get_mac(ip)

if not mac:
    print("MAC no encontrada")
    exit(1)

with open("authorized_macs.db", "a") as f:
    f.write(f"{ip} {mac}\n")

print(f"[OK] MAC registrada: {ip} → {mac}")
