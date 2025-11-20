#!/bin/sh
#
# Router Monitoring Script for OpenWrt
# Collects metrics and sends to Railway for monitoring
#
# Usage: Run via cron every 5 minutes
# */5 * * * * /root/monitor_router.sh >> /tmp/monitor.log 2>&1
#

# Configuration
RAILWAY_URL="https://openwrtrouter-production.up.railway.app"
WEBHOOK_SECRET="9fde3ba2adf1c3d063291a508c9873edc879312363bf709424a7bbc63333573c"
RAM_THRESHOLD=85
CPU_THRESHOLD=3.0
LOG_PREFIX="[Monitor]"

# Keep only last 10 log entries
LOG_FILE="/tmp/monitor.log"
if [ -f "$LOG_FILE" ]; then
    tail -10 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi

echo "${LOG_PREFIX} $(date '+%Y-%m-%d %H:%M:%S') - Collecting metrics..."

# Collect RAM metrics
RAM_INFO=$(free | grep Mem)
RAM_TOTAL=$(echo "$RAM_INFO" | awk '{print $2}')
RAM_USED=$(echo "$RAM_INFO" | awk '{print $3}')
RAM_FREE=$(echo "$RAM_INFO" | awk '{print $4}')
RAM_PERCENT=$((RAM_USED * 100 / RAM_TOTAL))

echo "${LOG_PREFIX} RAM: ${RAM_USED}/${RAM_TOTAL} KB (${RAM_PERCENT}%)"

# Collect CPU metrics
LOAD_AVG=$(cat /proc/loadavg)
CPU_LOAD1=$(echo "$LOAD_AVG" | awk '{print $1}')
CPU_LOAD5=$(echo "$LOAD_AVG" | awk '{print $2}')
CPU_LOAD15=$(echo "$LOAD_AVG" | awk '{print $3}')

echo "${LOG_PREFIX} CPU Load: ${CPU_LOAD1} ${CPU_LOAD5} ${CPU_LOAD15}"

# Count WiFi clients
WIFI_CLIENTS=0
if command -v iw >/dev/null 2>&1; then
    # Try to count stations on all interfaces
    for iface in $(iw dev | grep Interface | awk '{print $2}'); do
        COUNT=$(iw dev "$iface" station dump 2>/dev/null | grep -c "^Station")
        WIFI_CLIENTS=$((WIFI_CLIENTS + COUNT))
    done
fi

echo "${LOG_PREFIX} WiFi Clients: ${WIFI_CLIENTS}"

# Check OpenClash status
OPENCLASH_STATUS="unknown"
OPENCLASH_MEMORY=0

if [ -f /etc/init.d/openclash ]; then
    if /etc/init.d/openclash status 2>/dev/null | grep -q "running"; then
        OPENCLASH_STATUS="running"
        
        # Get Clash process memory
        CLASH_PID=$(ps | grep '[c]lash -d' | awk '{print $1}')
        if [ -n "$CLASH_PID" ]; then
            # Get memory from ps (could be in format like "1235m" or "12345")
            MEM_RAW=$(ps | grep "^[ ]*${CLASH_PID}" | awk '{print $4}')
            # Extract number, remove 'm' or 'k' suffix
            OPENCLASH_MEMORY=$(echo "$MEM_RAW" | sed 's/[mk]$//' | sed 's/[^0-9]//g')
            # If empty or zero, set to 0
            if [ -z "$OPENCLASH_MEMORY" ]; then
                OPENCLASH_MEMORY=0
            fi
        fi
    else
        OPENCLASH_STATUS="stopped"
    fi
fi

echo "${LOG_PREFIX} OpenClash: ${OPENCLASH_STATUS} (${OPENCLASH_MEMORY}m)"

# Check for critical conditions
ALERT=false
ALERT_TYPE=""
ALERT_VALUE=0

if [ "$RAM_PERCENT" -gt "$RAM_THRESHOLD" ]; then
    ALERT=true
    ALERT_TYPE="ram"
    ALERT_VALUE=$RAM_PERCENT
    echo "${LOG_PREFIX} ALERT: RAM ${RAM_PERCENT}% > ${RAM_THRESHOLD}%"
fi

# Convert CPU load to integer for comparison (multiply by 100)
CPU_LOAD1_INT=$(echo "$CPU_LOAD1" | awk '{printf "%d", $1*100}')
CPU_THRESHOLD_INT=$(echo "$CPU_THRESHOLD" | awk '{printf "%d", $1*100}')

if [ "$CPU_LOAD1_INT" -gt "$CPU_THRESHOLD_INT" ]; then
    ALERT=true
    ALERT_TYPE="cpu"
    ALERT_VALUE=$CPU_LOAD1
    echo "${LOG_PREFIX} ALERT: CPU Load ${CPU_LOAD1} > ${CPU_THRESHOLD}"
fi

if [ "$OPENCLASH_STATUS" = "stopped" ]; then
    ALERT=true
    ALERT_TYPE="openclash"
    ALERT_VALUE=0
    echo "${LOG_PREFIX} ALERT: OpenClash is down"
fi

# Prepare JSON payload
TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

if [ "$ALERT" = "true" ]; then
    # Send alert webhook
    PAYLOAD=$(cat <<EOF
{
  "type": "${ALERT_TYPE}",
  "value": ${ALERT_VALUE},
  "threshold": ${RAM_THRESHOLD},
  "timestamp": "${TIMESTAMP}",
  "metrics": {
    "ram": {"total": ${RAM_TOTAL}, "used": ${RAM_USED}, "percent": ${RAM_PERCENT}},
    "cpu": {"load1": ${CPU_LOAD1}, "load5": ${CPU_LOAD5}, "load15": ${CPU_LOAD15}},
    "clients": ${WIFI_CLIENTS},
    "openclash": {"status": "${OPENCLASH_STATUS}", "memory": ${OPENCLASH_MEMORY}}
  },
  "alert": true
}
EOF
)
    ENDPOINT="/webhook/alert"
    echo "${LOG_PREFIX} Sending ALERT webhook..."
else
    # Send normal monitoring data
    PAYLOAD=$(cat <<EOF
{
  "timestamp": "${TIMESTAMP}",
  "ram": {"total": ${RAM_TOTAL}, "used": ${RAM_USED}, "free": ${RAM_FREE}, "percent": ${RAM_PERCENT}},
  "cpu": {"load1": ${CPU_LOAD1}, "load5": ${CPU_LOAD5}, "load15": ${CPU_LOAD15}},
  "clients": ${WIFI_CLIENTS},
  "openclash": {"status": "${OPENCLASH_STATUS}", "memory": ${OPENCLASH_MEMORY}},
  "alert": false
}
EOF
)
    ENDPOINT="/webhook/monitoring"
fi

# Send webhook to Railway
HTTP_CODE=$(curl -s -w "%{http_code}" -o /tmp/monitor_response.txt \
    -X POST \
    -H "Authorization: Bearer ${WEBHOOK_SECRET}" \
    -H "Content-Type: application/json" \
    -d "${PAYLOAD}" \
    "${RAILWAY_URL}${ENDPOINT}")

if [ "$HTTP_CODE" = "200" ]; then
    echo "${LOG_PREFIX} Data sent successfully (HTTP ${HTTP_CODE})"
else
    echo "${LOG_PREFIX} ERROR: Failed to send data (HTTP ${HTTP_CODE})"
    cat /tmp/monitor_response.txt
fi

echo "${LOG_PREFIX} Monitoring completed"
exit 0

