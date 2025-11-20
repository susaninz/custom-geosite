#!/bin/sh
#
# Geosite Update Checker for OpenWrt Router
# Checks domain-list-community for updates and notifies Railway
#
# Usage: Run via cron daily at 03:00
# 0 3 * * * /root/check_geosite_updates.sh >> /tmp/geosite_check.log 2>&1
#

# Configuration
RAILWAY_URL="https://openwrtrouter-production.up.railway.app"
WEBHOOK_SECRET="9fde3ba2adf1c3d063291a508c9873edc879312363bf709424a7bbc63333573c"
GITHUB_REPO="v2fly/domain-list-community"
STATE_FILE="/tmp/geosite_last_commit.txt"
LOG_PREFIX="[GeoSite Check]"

# GitHub API endpoint
GITHUB_API="https://api.github.com/repos/${GITHUB_REPO}/commits/master"

echo "${LOG_PREFIX} $(date '+%Y-%m-%d %H:%M:%S') - Starting check..."

# Get latest commit from GitHub
echo "${LOG_PREFIX} Fetching latest commit from GitHub..."
LATEST_COMMIT=$(curl -s "${GITHUB_API}" | grep -o '"sha": "[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$LATEST_COMMIT" ]; then
    echo "${LOG_PREFIX} ERROR: Failed to fetch latest commit from GitHub"
    exit 1
fi

echo "${LOG_PREFIX} Latest commit: ${LATEST_COMMIT}"

# Read saved commit
if [ -f "$STATE_FILE" ]; then
    SAVED_COMMIT=$(cat "$STATE_FILE")
    echo "${LOG_PREFIX} Saved commit: ${SAVED_COMMIT}"
else
    SAVED_COMMIT=""
    echo "${LOG_PREFIX} No saved commit found (first run)"
fi

# Compare commits
if [ "$LATEST_COMMIT" = "$SAVED_COMMIT" ]; then
    echo "${LOG_PREFIX} No updates available"
    exit 0
fi

echo "${LOG_PREFIX} UPDATE FOUND! Sending webhook to Railway..."

# Prepare webhook payload
TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
PAYLOAD=$(cat <<EOF
{
  "commit": "${LATEST_COMMIT}",
  "old_commit": "${SAVED_COMMIT}",
  "timestamp": "${TIMESTAMP}",
  "source": "router"
}
EOF
)

# Send webhook to Railway
HTTP_CODE=$(curl -s -w "%{http_code}" -o /tmp/webhook_response.txt \
    -X POST \
    -H "Authorization: Bearer ${WEBHOOK_SECRET}" \
    -H "Content-Type: application/json" \
    -d "${PAYLOAD}" \
    "${RAILWAY_URL}/webhook/geosite-update")

if [ "$HTTP_CODE" = "200" ]; then
    echo "${LOG_PREFIX} Webhook sent successfully (HTTP ${HTTP_CODE})"
    # Save new commit only if webhook was successful
    echo "${LATEST_COMMIT}" > "${STATE_FILE}"
    echo "${LOG_PREFIX} Saved new commit: ${LATEST_COMMIT}"
else
    echo "${LOG_PREFIX} ERROR: Webhook failed (HTTP ${HTTP_CODE})"
    cat /tmp/webhook_response.txt
    exit 1
fi

echo "${LOG_PREFIX} Check completed successfully"
exit 0

