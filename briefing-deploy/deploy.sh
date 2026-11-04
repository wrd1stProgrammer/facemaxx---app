set -euo pipefail
cd /opt/facemaxx
old=$(docker inspect chartagent-api --format '{{.Config.Image}}')
other=$(docker inspect facemaxx-api --format '{{.Id}}')
export CHARTAGENT_IMAGE=chartagent-briefing:20261105
docker compose config --format json | python3 -c 'import json,sys; d=json.load(sys.stdin)["services"]["chartagent-api"]; assert d["image"]=="chartagent-briefing:20261105"; assert any(v.get("target")=="/app/advanced-data" for v in d.get("volumes",[])); print("Image and persistent mount verified")'
rollback() { CHARTAGENT_IMAGE="$old" docker compose up -d --no-deps chartagent-api; }
trap rollback ERR
docker compose up -d --no-deps chartagent-api
for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8010/health >/dev/null; then break; fi
  sleep 2
done
curl -fsS http://127.0.0.1:8010/health
docker exec -i chartagent-api python - <<'PY'
import httpx,secrets,time
from app import briefings as b
base='http://127.0.0.1:8010'
auth='Bearer '+secrets.token_hex(32)
headers={'Authorization':auth}
with httpx.Client(timeout=30) as c:
    r=c.get(base+'/v1/briefings',headers=headers);r.raise_for_status();assert r.json()['items']==[]
    r=c.get(base+'/v1/news',params={'symbol':'BTC','page':1});r.raise_for_status();print('LEGACY_NEWS_HTTP',r.status_code,flush=True)
    r=c.put(base+'/v1/briefings/preferences',headers=headers,json={'instruments':['BTCUSD'],'language':'ko'});r.raise_for_status()
    try:
        for i in range(36):
            r=c.get(base+'/v1/briefings',headers=headers);r.raise_for_status()
            item=r.json()['items'][0]
            if item.get('story'):
                print('LIVE_WORKER',item['story']['coverage'], 'RESET',item.get('next_refresh_at'),flush=True)
                break
            time.sleep(5)
        else: raise RuntimeError('Live briefing worker did not finish')
    finally:
        c.put(base+'/v1/briefings/preferences',headers=headers,json={'instruments':[],'language':'ko'}).raise_for_status()
        with b.repository().connect() as db:
            db.execute('DELETE FROM clients WHERE owner=?',(b.owner(auth),))
PY
test "$other" = "$(docker inspect facemaxx-api --format '{{.Id}}')"
sudo python3 - <<'PY'
from pathlib import Path
import re,shutil
p=Path('/opt/facemaxx/.env')
shutil.copy2(p,p.with_name('.env.before-briefing-20261105'))
s=p.read_text()
s=re.sub(r'^CHARTAGENT_IMAGE=.*\n?', '',s,flags=re.M)
p.write_text(s.rstrip()+'\nCHARTAGENT_IMAGE=chartagent-briefing:20261105\n')
PY
trap - ERR
printf 'DEPLOYED; FaceMaxx container unchanged; rollback image: %s\n' "$old"
