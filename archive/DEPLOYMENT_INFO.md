# 🚀 Deployment Information

## Railway Application

**URL:** https://openwrtrouter-production.up.railway.app

**Status:** ✅ Deployed and Running

**Deployed:** November 7, 2025

---

## Configuration

All tokens and secrets are stored in:
- Railway: Environment Variables
- Local: `railway-bot/.env` file

---

## Endpoints

- **Health:** https://openwrtrouter-production.up.railway.app/health
- **Status:** https://openwrtrouter-production.up.railway.app/status
- **Geosite Webhook:** /webhook/geosite-update
- **Monitoring Webhook:** /webhook/monitoring
- **Alert Webhook:** /webhook/alert

---

## For Router Scripts

Get values from `railway-bot/.env` file:

```bash
RAILWAY_URL="https://openwrtrouter-production.up.railway.app"
WEBHOOK_SECRET="<from .env file>"
```

---

## Next Steps

✅ **Phase 3 Complete:** Railway deployed

**Phase 4:** Create router scripts
- `check_geosite_updates.sh`
- `monitor_router.sh`

**Phase 5:** First geosite build  
**Phase 7:** Monitoring system
