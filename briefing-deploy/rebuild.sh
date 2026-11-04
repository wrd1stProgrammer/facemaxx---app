set -euo pipefail
cd /tmp/chartagent-briefing-20261105
docker build --build-arg BASE=chartagent-strategy:20261104 --build-arg APP_USER=app -t chartagent-briefing:20261105 .
docker run --rm --env-file /opt/chartagent/.env -e PYTHONPATH=/app chartagent-briefing:20261105 python -c 'import app.main; print("APP_IMPORT_OK")'
docker run -d --name chartagent-briefing-preflight -e CHARTAGENT_BRIEFING_DB=/tmp/briefings.sqlite3 --env-file /opt/chartagent/.env -p 127.0.0.1:18010:8010 chartagent-briefing:20261105
trap 'docker logs --tail 30 chartagent-briefing-preflight; docker rm -f chartagent-briefing-preflight' EXIT
for i in $(seq 1 15); do
  if curl -fsS http://127.0.0.1:18010/health >/dev/null; then break; fi
  sleep 2
done
curl -fsS http://127.0.0.1:18010/health
bash deploy.sh
