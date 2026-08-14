#!/usr/bin/env bash
set -euo pipefail

readonly source_snippet="/opt/facemaxx/nginx-chartagent.conf.example"
readonly target_snippet="/etc/nginx/snippets/chartagent-location.conf"
readonly include_line="    include /etc/nginx/snippets/chartagent-location.conf;"
readonly server_name_pattern='^[[:space:]]*server_name[[:space:]][^;]*facemaxx\.nostalgia-drive\.com[^;]*;'

install -D -m 0644 "$source_snippet" "$target_snippet"

mapfile -t candidates < <(
  grep -RIlE "$server_name_pattern" /etc/nginx/sites-enabled /etc/nginx/conf.d 2>/dev/null || true
)

if [[ ${#candidates[@]} -eq 0 ]]; then
  echo "Could not locate the active facemaxx.nostalgia-drive.com Nginx server block" >&2
  exit 1
fi

declare -a targets=()
for candidate in "${candidates[@]}"; do
  target="$(readlink -f "$candidate")"
  if [[ ! " ${targets[*]} " =~ " ${target} " ]]; then
    targets+=("$target")
  fi
done

declare -a backups=()
declare -a changed_targets=()
for target in "${targets[@]}"; do
  if grep -Fq "$include_line" "$target"; then
    continue
  fi

  backup="$(mktemp /tmp/chartagent-nginx-backup.XXXXXX)"
  output="$(mktemp /tmp/chartagent-nginx-output.XXXXXX)"
  cp -a "$target" "$backup"
  awk -v pattern="$server_name_pattern" -v include_line="$include_line" '
    $0 ~ pattern { print; print include_line; next }
    { print }
  ' "$target" > "$output"
  install -m "$(stat -c '%a' "$target")" "$output" "$target"
  rm -f "$output"
  backups+=("$backup")
  changed_targets+=("$target")
done

if ! nginx -t; then
  for index in "${!changed_targets[@]}"; do
    cp -a "${backups[$index]}" "${changed_targets[$index]}"
  done
  nginx -t
  echo "ChartAgent Nginx route was rolled back because validation failed" >&2
  exit 1
fi

systemctl reload nginx
for backup in "${backups[@]}"; do
  rm -f "$backup"
done
