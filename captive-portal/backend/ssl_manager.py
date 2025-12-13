"""
ssl_manager.py - Gestión de certificados SSL/TLS autofirmados

Genera certificados autofirmados para HTTPS sin dependencias externas.
Utiliza openssl del sistema operativo (disponible en Linux).
"""

import subprocess
import os
import sys
from datetime import datetime, timedelta


def generate_self_signed_cert(certfile: str, keyfile: str, 
                               days: int = 365,
                               common_name: str = "192.168.50.1"):
    """
    Genera un certificado SSL/TLS autofirmado usando openssl.
    
    Args:
        certfile: Ruta donde guardar el certificado (.pem)
        keyfile: Ruta donde guardar la clave privada (.key)
        days: Validez del certificado en días
        common_name: Nombre común (CN) del certificado (típicamente la IP o dominio)
        
    Returns:
        True si se generó exitosamente, False en caso contrario
    """
    
    # Verificar si openssl está disponible
    try:
        subprocess.run(["which", "openssl"], check=True, 
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("[ERROR] openssl no está instalado. Instálalo con: sudo apt-get install openssl")
        return False
    
    # Si ya existen, no regenerar
    if os.path.exists(certfile) and os.path.exists(keyfile):
        print(f"[INFO] Certificado y clave ya existen: {certfile}, {keyfile}")
        return True
    
    print(f"[INFO] Generando certificado autofirmado...")
    print(f"  CN: {common_name}")
    print(f"  Validez: {days} días")
    
    # Crear directorio si no existe
    os.makedirs(os.path.dirname(certfile) or ".", exist_ok=True)
    
    # Comando openssl para generar certificado autofirmado
    # Generamos tanto la clave como el certificado en un solo comando
    cmd = [
        "openssl", "req",
        "-x509",                    # Self-signed certificate
        "-newkey", "rsa:2048",      # RSA 2048 bits
        "-keyout", keyfile,         # Guardar clave privada
        "-out", certfile,           # Guardar certificado
        "-days", str(days),         # Validez
        "-nodes",                   # Sin contraseña (no encrypted)
        "-subj", f"/C=CU/ST=Cuba/L=Cuba/O=PortalCautivo/CN={common_name}"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True)
        
        print(f"[OK] Certificado generado exitosamente")
        print(f"  Certificado: {certfile}")
        print(f"  Clave privada: {keyfile}")
        
        # Proteger la clave privada
        os.chmod(keyfile, 0o600)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] No se pudo generar el certificado: {e.stderr}")
        return False
    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")
        return False


def create_certificate_if_needed(cert_dir: str = "config/certs",
                                 cert_name: str = "portal") -> tuple:
    """
    Crea certificado autofirmado si no existe.
    
    Args:
        cert_dir: Directorio donde almacenar los certificados
        cert_name: Nombre base del certificado
        
    Returns:
        Tupla (certfile, keyfile) con las rutas, o (None, None) si falla
    """
    
    os.makedirs(cert_dir, exist_ok=True)
    
    certfile = os.path.join(cert_dir, f"{cert_name}.pem")
    keyfile = os.path.join(cert_dir, f"{cert_name}.key")
    
    if generate_self_signed_cert(certfile, keyfile, 
                                days=365, 
                                common_name="192.168.50.1"):
        return certfile, keyfile
    else:
        return None, None


def get_certificate_info(certfile: str) -> dict:
    """
    Obtiene información del certificado usando openssl.
    
    Args:
        certfile: Ruta al certificado
        
    Returns:
        Dict con información: subject, issuer, not_before, not_after, etc.
    """
    
    info = {}
    
    try:
        cmd = ["openssl", "x509", "-in", certfile, "-noout", "-text"]
        result = subprocess.run(cmd, check=True, 
                               stdout=subprocess.PIPE, 
                               text=True)
        
        output = result.stdout
        
        # Extraer información básica
        for line in output.split('\n'):
            if 'Subject:' in line:
                info['subject'] = line.split('Subject:')[1].strip()
            elif 'Issuer:' in line:
                info['issuer'] = line.split('Issuer:')[1].strip()
            elif 'Not Before:' in line:
                info['not_before'] = line.split('Not Before:')[1].strip()
            elif 'Not After:' in line:
                info['not_after'] = line.split('Not After:')[1].strip()
        
        return info
        
    except Exception as e:
        print(f"[ERROR] No se pudo leer certificado: {e}")
        return {}


def is_certificate_valid(certfile: str) -> bool:
    """
    Verifica si un certificado es válido (no expirado).
    
    Args:
        certfile: Ruta al certificado
        
    Returns:
        True si el certificado es válido, False si expiró
    """
    
    try:
        cmd = ["openssl", "x509", "-in", certfile, "-noout", "-checkend", "0"]
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
        
    except Exception as e:
        print(f"[ERROR] No se pudo verificar certificado: {e}")
        return False


if __name__ == "__main__":
    # Prueba: generar certificado
    cert_dir = "config/certs"
    certfile, keyfile = create_certificate_if_needed(cert_dir)
    
    if certfile:
        print("\n[INFO] Información del certificado:")
        info = get_certificate_info(certfile)
        for key, value in info.items():
            print(f"  {key}: {value}")
        
        print(f"\n[INFO] Certificado válido: {is_certificate_valid(certfile)}")