#!/usr/bin/env bash
# Ежедневный бэкап Postgres (Sotka) с ротацией и опциональной выгрузкой в S3.
#
# Установка на сервере (72.56.245.67):
#   chmod +x /app/scripts/backup_db.sh
#   crontab -e  →  добавить строку:
#   30 2 * * * /app/scripts/backup_db.sh >> /var/log/sotka-backup.log 2>&1
#
# S3 (Timeweb Object Storage) подключается через переменные в /app/.env:
#   BACKUP_S3_BUCKET=...      (имя бакета)
#   BACKUP_S3_ENDPOINT=...    (https://s3.twcstorage.ru)
#   BACKUP_S3_ACCESS_KEY=...
#   BACKUP_S3_SECRET_KEY=...
# Без этих переменных скрипт делает только локальные бэкапы (7 дней ротация).
# Для S3 нужен установленный s3cmd: apt-get install -y s3cmd

set -euo pipefail

APP_DIR="/app"
BACKUP_DIR="/var/backups/sotka"
KEEP_DAYS=7
STAMP=$(date +%Y%m%d_%H%M%S)
FILE="$BACKUP_DIR/sotka_$STAMP.sql.gz"

mkdir -p "$BACKUP_DIR"

# .env для S3-переменных (не обязателен)
if [ -f "$APP_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$APP_DIR/.env" 2>/dev/null || true
    set +a
fi

echo "[$(date '+%F %T')] pg_dump start"
cd "$APP_DIR"
docker compose exec -T db pg_dump -U sotka -d sotka | gzip > "$FILE"

SIZE=$(du -h "$FILE" | cut -f1)
echo "[$(date '+%F %T')] dump done: $FILE ($SIZE)"

# Минимальная проверка целостности: gzip распаковывается и дамп не пустой
if ! gzip -t "$FILE" || [ "$(stat -c%s "$FILE")" -lt 10240 ]; then
    echo "[$(date '+%F %T')] ERROR: backup file invalid or suspiciously small" >&2
    exit 1
fi

# Ротация локальных бэкапов
find "$BACKUP_DIR" -name 'sotka_*.sql.gz' -mtime +"$KEEP_DAYS" -delete

# Выгрузка в S3, если настроено
if [ -n "${BACKUP_S3_BUCKET:-}" ] && command -v s3cmd >/dev/null 2>&1; then
    s3cmd put "$FILE" "s3://$BACKUP_S3_BUCKET/db/" \
        --host="${BACKUP_S3_ENDPOINT#https://}" \
        --host-bucket="%(bucket)s.${BACKUP_S3_ENDPOINT#https://}" \
        --access_key="$BACKUP_S3_ACCESS_KEY" \
        --secret_key="$BACKUP_S3_SECRET_KEY" \
        && echo "[$(date '+%F %T')] uploaded to s3://$BACKUP_S3_BUCKET/db/" \
        || echo "[$(date '+%F %T')] WARN: s3 upload failed (local copy kept)" >&2
else
    echo "[$(date '+%F %T')] s3 not configured — local backup only"
fi

echo "[$(date '+%F %T')] backup complete"
