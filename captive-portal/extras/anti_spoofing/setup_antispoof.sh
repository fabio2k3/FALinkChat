echo "[+] Creando ipset para suplantación..."
sudo ipset create AUTHORIZED hash:ip timeout 7200 -exist

echo "[+] Configurando reglas de anti-spoofing..."

# Asegura que solo las IP autorizadas pueden navegar
sudo iptables -A FORWARD -m set ! --match-set AUTHORIZED src -j DROP

# Opcional: bloquear tráficos maliciosos logueados
sudo iptables -A FORWARD -m set --match-set AUTHORIZED src -j ACCEPT

echo "[✔] Anti-spoofing configurado."
