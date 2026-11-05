set -euo pipefail
umask 077
dir=/opt/chartagent/.apns-transfer-20261105
sudo install -d -m 700 "$dir"
if ! sudo test -s "$dir/unwrap.pem"; then
  sudo openssl genrsa -out "$dir/unwrap.pem" 4096 2>/dev/null
fi
echo "WRAP_PUBLIC=$(sudo openssl rsa -in "$dir/unwrap.pem" -pubout 2>/dev/null | base64 -w0)"
