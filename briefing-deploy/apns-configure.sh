set -euo pipefail
umask 077
transfer=/opt/chartagent/.apns-transfer-20261105
appdir=/opt/chartagent/apns
test "$(docker exec chartagent-api sha256sum /app/app/briefings.py | cut -d' ' -f1)" = 5188ff2c0100a3c92d3dbbd629f4088f8dfeb93444eee7ad6eae9176ff2df933
base=$(docker inspect chartagent-api -f '{{.Config.Image}}')
other=$(docker inspect facemaxx-api -f '{{.Id}}')
gid=$(docker exec chartagent-api id -g)
new=chartagent-briefing:apns-20261105
mkdir build
cp briefings.py build/
printf 'ARG BASE\nFROM ${BASE}\nCOPY --chmod=0644 briefings.py /app/app/briefings.py\n' > build/Dockerfile
docker build -q --build-arg BASE="$base" -t "$new" build/
sudo install -d -m 750 -o root -g "$gid" "$appdir"
for env in production sandbox; do
 sudo openssl pkeyutl -decrypt -inkey "$transfer/unwrap.pem" -pkeyopt rsa_padding_mode:oaep -pkeyopt rsa_oaep_md:sha256 -pkeyopt rsa_mgf1_md:sha256 -in "apns-$env.enc" -out "$transfer/$env.tmp"
 sudo openssl pkey -in "$transfer/$env.tmp" -check -noout >/dev/null
 sudo install -m 440 -o root -g "$gid" "$transfer/$env.tmp" "$appdir/$env.p8"
 sudo rm -- "$transfer/$env.tmp"
done
cd /opt/facemaxx
compose=$(docker inspect chartagent-api --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}')
test -f "$compose"
backup=$(sudo mktemp -d /opt/chartagent/.apns-backup.XXXXXXXX)
sudo cp -p "$compose" "$backup/compose"
sudo cp -p .env "$backup/service-env"
sudo cp -p /opt/chartagent/.env "$backup/app-env"
rollback() {
  sudo cp -p "$backup/compose" "$compose"
  sudo cp -p "$backup/service-env" .env
  sudo cp -p "$backup/app-env" /opt/chartagent/.env
  CHARTAGENT_IMAGE="$base" docker compose up -d --no-deps chartagent-api
}
trap rollback ERR
sudo python3 - "$compose" "$new" <<'PY'
from pathlib import Path
import sys,re
p=Path(sys.argv[1]); s=p.read_text()
pat=r'(?m)^([ \t]+)- ["\']?/opt/chartagent/advanced-data:/app/advanced-data["\']?\s*$'
if '/run/chartagent-apns' not in s:
 s,n=re.subn(pat,lambda m:m[0].rstrip()+'\n'+m[1]+'- /opt/chartagent/apns:/run/chartagent-apns:ro',s)
 assert n==1,'missing ChartAgent mount'
 p.write_text(s)
def merge(file,values):
 p=Path(file); s=p.read_text()
 for k,v in values.items():
  s=re.sub('(?m)^'+k+'=.*\n?', '',s).rstrip()+'\n'+k+'='+v+'\n'
 p.write_text(s)
merge('/opt/chartagent/.env',{'CHARTAGENT_APNS_TEAM_ID':'U9QTM9L965','CHARTAGENT_APNS_TOPIC':'ai.chartagent.ios','CHARTAGENT_APNS_PRODUCTION_KEY_ID':'6PFQ7QSMX4','CHARTAGENT_APNS_SANDBOX_KEY_ID':'L4GZQ928FG','CHARTAGENT_APNS_PRODUCTION_KEY_PATH':'/run/chartagent-apns/production.p8','CHARTAGENT_APNS_SANDBOX_KEY_PATH':'/run/chartagent-apns/sandbox.p8'})
merge('.env',{'CHARTAGENT_IMAGE':sys.argv[2]})
PY
docker compose config --format json | python3 -c 'import json,sys; c=json.load(sys.stdin)["services"]["chartagent-api"]; assert any(x["target"]=="/run/chartagent-apns" and x["read_only"] for x in c["volumes"]); assert c["image"]=="chartagent-briefing:apns-20261105" and c["environment"]["CHARTAGENT_APNS_TOPIC"]=="ai.chartagent.ios"'
docker compose run --rm --no-deps --entrypoint python chartagent-api -c 'import app.main; from app.briefings import push_credentials; assert all(push_credentials(e)[2].is_file() for e in ("production","sandbox"))'
docker compose up -d --no-deps chartagent-api
for x in $(seq 1 60); do if curl -fs http://127.0.0.1:8010/health >/dev/null; then break; fi; sleep 1; done
curl -fsS http://127.0.0.1:8010/health >/dev/null
docker exec -i chartagent-api python - <<'PY'
import time, jwt, httpx, secrets
from app.briefings import push_credentials
for env,host in [('production','api.push.apple.com'),('sandbox','api.sandbox.push.apple.com')]:
 team,kid,path=push_credentials(env)
 token=jwt.encode({'iss':team,'iat':int(time.time())},path.read_bytes(),algorithm='ES256',headers={'kid':kid})
 with httpx.Client(http2=True,timeout=15) as c:
  r=c.post('https://'+host+'/3/device/'+secrets.token_hex(32),headers={'authorization':'bearer '+token,'apns-topic':'ai.chartagent.ios','apns-push-type':'alert'},json={'aps':{'alert':'Connection check'}})
 reason=r.json().get('reason')
 print(env,r.http_version,r.status_code,reason,flush=True)
 assert r.http_version=='HTTP/2' and reason=='BadDeviceToken', 'unexpected APNs response'
PY
test "$other" = "$(docker inspect facemaxx-api -f '{{.Id}}')"
trap - ERR
sudo rm -- "$transfer/unwrap.pem"
sudo rmdir "$transfer"
echo "ChartAgent healthy; both APNs environments checked"
