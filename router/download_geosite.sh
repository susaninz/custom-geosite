#!/bin/sh
#
# Auto-update geosite.dat from GitHub Releases
# 
# Скрипт для автоматического скачивания и обновления geosite.dat
# с GitHub Releases в OpenClash
#
# Установка: см. README.md в этой папке
#

# ============================================================================
# НАСТРОЙКИ
# ============================================================================

GITHUB_REPO="susaninz/openwrtrouter"
GITHUB_API="https://api.github.com/repos/$GITHUB_REPO/releases/latest"

OPENCLASH_DIR="/etc/openclash"
GEOSITE_FILE="$OPENCLASH_DIR/geosite.dat"
VERSION_FILE="$OPENCLASH_DIR/.geosite_version"
BACKUP_DIR="$OPENCLASH_DIR/backups"

# Webhook для уведомлений в Telegram (через Railway)
WEBHOOK_URL="https://openwrtrouter-production.up.railway.app"
WEBHOOK_SECRET="9fde3ba2adf1c3d063291a508c9873edc879312363bf709424a7bbc63333573c"

# Логирование
LOG_FILE="/tmp/geosite_update.log"

# ============================================================================
# ФУНКЦИИ
# ============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

send_notification() {
    local status="$1"
    local message="$2"
    local version="$3"
    
    # Формируем JSON для webhook
    local json_data=$(cat <<EOF
{
  "event": "geosite_update",
  "status": "$status",
  "message": "$message",
  "version": "$version",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "router": "$(uci get system.@system[0].hostname 2>/dev/null || echo 'OpenWrt')"
}
EOF
)
    
    # Отправляем webhook
    curl -X POST "$WEBHOOK_URL/webhook/router-event" \
        -H "Authorization: Bearer $WEBHOOK_SECRET" \
        -H "Content-Type: application/json" \
        -d "$json_data" \
        --connect-timeout 10 \
        --max-time 30 \
        --silent \
        --show-error \
        >> "$LOG_FILE" 2>&1
    
    if [ $? -eq 0 ]; then
        log "✓ Notification sent successfully"
    else
        log "⚠ Failed to send notification"
    fi
}

check_dependencies() {
    local missing=""
    
    for cmd in curl; do
        if ! command -v $cmd >/dev/null 2>&1; then
            missing="$missing $cmd"
        fi
    done
    
    if [ -n "$missing" ]; then
        log "ERROR: Missing required commands:$missing"
        log "Install with: opkg update && opkg install$missing"
        return 1
    fi
    
    return 0
}

get_current_version() {
    if [ -f "$VERSION_FILE" ]; then
        cat "$VERSION_FILE"
    else
        echo "none"
    fi
}

get_latest_release() {
    log "Checking GitHub for latest release..."
    
    # Получаем информацию о последнем релизе
    local response=$(curl -s --connect-timeout 10 --max-time 30 "$GITHUB_API")
    
    if [ $? -ne 0 ] || [ -z "$response" ]; then
        log "ERROR: Failed to fetch release info from GitHub"
        return 1
    fi
    
    # Извлекаем tag_name (версию)
    local tag=$(echo "$response" | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": "\([^"]*\)".*/\1/')
    
    # Извлекаем download URL для geosite.dat
    local url=$(echo "$response" | grep '"browser_download_url".*geosite.dat"' | head -1 | sed 's/.*"browser_download_url": "\([^"]*\)".*/\1/')
    
    # Извлекаем размер файла
    local size=$(echo "$response" | grep '"size"' | head -1 | sed 's/.*"size": \([0-9]*\).*/\1/')
    
    if [ -z "$tag" ] || [ -z "$url" ]; then
        log "ERROR: Failed to parse release info"
        return 1
    fi
    
    # Сохраняем в переменные окружения для последующего использования
    export LATEST_TAG="$tag"
    export DOWNLOAD_URL="$url"
    export FILE_SIZE="$size"
    
    log "Latest release: $tag"
    log "Download URL: $url"
    log "File size: $size bytes"
    
    return 0
}

download_geosite() {
    local temp_file="/tmp/geosite.dat.new"
    
    log "Downloading geosite.dat..."
    log "URL: $DOWNLOAD_URL"
    
    # Скачиваем файл (используем curl с follow redirects)
    curl -L -o "$temp_file" "$DOWNLOAD_URL" --connect-timeout 30 --max-time 120 2>&1 | tee -a "$LOG_FILE"
    
    if [ $? -ne 0 ]; then
        log "ERROR: Download failed"
        rm -f "$temp_file"
        return 1
    fi
    
    # Проверяем что файл скачался и не пустой
    if [ ! -f "$temp_file" ]; then
        log "ERROR: Downloaded file not found"
        return 1
    fi
    
    # Получаем размер файла (совместимо с BusyBox)
    local downloaded_size=$(wc -c < "$temp_file" 2>/dev/null)
    
    if [ -z "$downloaded_size" ] || [ "$downloaded_size" -lt 10000 ]; then
        log "ERROR: Downloaded file is too small ($downloaded_size bytes)"
        rm -f "$temp_file"
        return 1
    fi
    
    log "✓ Downloaded successfully ($downloaded_size bytes)"
    
    # Сохраняем путь к временному файлу
    export TEMP_GEOSITE="$temp_file"
    
    return 0
}

backup_current() {
    if [ ! -f "$GEOSITE_FILE" ]; then
        log "No existing geosite.dat to backup"
        return 0
    fi
    
    # Создаём директорию для бэкапов
    mkdir -p "$BACKUP_DIR"
    
    # Создаём бэкап с timestamp
    local backup_file="$BACKUP_DIR/geosite.dat.$(date +%Y%m%d_%H%M%S)"
    
    cp "$GEOSITE_FILE" "$backup_file"
    
    if [ $? -eq 0 ]; then
        log "✓ Backup created: $backup_file"
        
        # Удаляем старые бэкапы (оставляем последние 5)
        ls -t "$BACKUP_DIR"/geosite.dat.* 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null
        
        return 0
    else
        log "ERROR: Failed to create backup"
        return 1
    fi
}

install_geosite() {
    log "Installing new geosite.dat..."
    
    # Создаём директорию если не существует
    mkdir -p "$OPENCLASH_DIR"
    
    # Копируем файл
    cp "$TEMP_GEOSITE" "$GEOSITE_FILE"
    
    if [ $? -eq 0 ]; then
        log "✓ File installed successfully"
        
        # Сохраняем версию
        echo "$LATEST_TAG" > "$VERSION_FILE"
        log "✓ Version saved: $LATEST_TAG"
        
        # Удаляем временный файл
        rm -f "$TEMP_GEOSITE"
        
        return 0
    else
        log "ERROR: Failed to install file"
        return 1
    fi
}

restart_openclash() {
    log "Restarting OpenClash..."
    
    # Проверяем что OpenClash установлен
    if ! command -v /etc/init.d/openclash >/dev/null 2>&1; then
        log "WARNING: OpenClash init script not found, skipping restart"
        return 0
    fi
    
    # Перезапускаем
    /etc/init.d/openclash restart >> "$LOG_FILE" 2>&1
    
    if [ $? -eq 0 ]; then
        log "✓ OpenClash restarted successfully"
        return 0
    else
        log "WARNING: OpenClash restart returned non-zero exit code"
        return 1
    fi
}

# ============================================================================
# ОСНОВНАЯ ЛОГИКА
# ============================================================================

main() {
    log "=========================================="
    log "Starting geosite.dat auto-update check"
    log "=========================================="
    
    # 1. Проверяем зависимости
    if ! check_dependencies; then
        send_notification "error" "Missing dependencies" "unknown"
        exit 1
    fi
    
    # 2. Получаем текущую версию
    CURRENT_VERSION=$(get_current_version)
    log "Current version: $CURRENT_VERSION"
    
    # 3. Проверяем последний релиз на GitHub
    if ! get_latest_release; then
        send_notification "error" "Failed to check GitHub" "$CURRENT_VERSION"
        exit 1
    fi
    
    # 4. Сравниваем версии
    if [ "$CURRENT_VERSION" = "$LATEST_TAG" ]; then
        log "Already up to date: $CURRENT_VERSION"
        log "No update needed"
        exit 0
    fi
    
    log "Update available: $CURRENT_VERSION → $LATEST_TAG"
    
    # 5. Скачиваем новый файл
    if ! download_geosite; then
        send_notification "error" "Download failed" "$LATEST_TAG"
        exit 1
    fi
    
    # 6. Создаём бэкап текущего файла
    if ! backup_current; then
        send_notification "error" "Backup failed" "$LATEST_TAG"
        rm -f "$TEMP_GEOSITE"
        exit 1
    fi
    
    # 7. Устанавливаем новый файл
    if ! install_geosite; then
        send_notification "error" "Installation failed" "$LATEST_TAG"
        exit 1
    fi
    
    # 8. Перезапускаем OpenClash
    if ! restart_openclash; then
        log "WARNING: OpenClash restart had issues, but file was updated"
    fi
    
    # 9. Отправляем уведомление об успехе
    log "=========================================="
    log "✓ Update completed successfully!"
    log "Version: $CURRENT_VERSION → $LATEST_TAG"
    log "=========================================="
    
    send_notification "success" "Updated to $LATEST_TAG" "$LATEST_TAG"
    
    exit 0
}

# Запуск
main

