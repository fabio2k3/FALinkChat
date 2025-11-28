#!/usr/bin/env python3
import subprocess
import time

DB_FILE = "authorized_macs.db"

def load_mac_db():
    db = {}
    try:
        with open(DB_FILE, "r") as f:
            for line in f:
                ip, mac = line.strip().split()
                db[ip] = mac.lower()
    except FileNotFoundError:
        pass
    return db

def get_mac(ip):
    try:
        out = subprocess.check_output(["arp", "-n", ip]).decode()
        parts = out.split()
        for p in parts:
            if ":" in p and len(p) == 17:
                return p.lower()
    except:
        return None
    return None

def block_ip(ip):
    print(f"[ALERTA] IP {ip} está suplantando identidad → bloqueada.")
    subprocess.run(["sudo", "ipset", "del", "AUTHORIZED", ip])
    subprocess.run(["sudo", "iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"])
    subprocess.run(["sudo", "iptables", "-A", "FORWARD", "-s", ip, "-j", "DROP"])

def get_authorized_ips():
    try:
        out = subprocess.check_output(["sudo", "ipset", "list", "AUTHORIZED"]).decode()
        lines = out.splitlines()
        ips = []
        for ln in lines:
            if ln.startswith("    "):
                ips.append(ln.strip())
        return ips
    except:
        return []

def monitor():
    print("[*] Anti-Spoofing activo (monitoreando IP ↔ MAC)")
    while True:
        db = load_mac_db()
        authorized_ips = get_authorized_ips()

        for ip in authorized_ips:
            real_mac = get_mac(ip)
            if not real_mac:
                continue
            expected = db.get(ip)
            if expected and expected != real_mac:
                block_ip(ip)

        time.sleep(2)

if __name__ == "__main__":
    monitor()
