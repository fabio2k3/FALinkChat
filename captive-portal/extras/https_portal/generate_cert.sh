CERT_DIR="cert"

mkdir -p $CERT_DIR

echo "[+] Generando clave privada..."
openssl genrsa -out $CERT_DIR/server.key 2048

echo "[+] Generando CSR..."
openssl req -new -key $CERT_DIR/server.key -out $CERT_DIR/server.csr \
  -subj "/C=US/ST=NA/L=NA/O=CaptivePortal/OU=IT/CN=portal.local"

echo "[+] Generando certificado autofirmado válido por 1 año..."
openssl x509 -req -days 365 -in $CERT_DIR/server.csr \
  -signkey $CERT_DIR/server.key -out $CERT_DIR/server.crt

echo "[+] Certificados generados:"
echo " - $CERT_DIR/server.key"
echo " - $CERT_DIR/server.csr"
echo " - $CERT_DIR/server.crt"

echo "[✔] Certificado autofirmado creado correctamente."
