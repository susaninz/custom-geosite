# 🤖 Geosite Manager Bot - Railway App

Telegram bot для автоматического управления custom geosite.dat и мониторинга роутера OpenWrt.

## 🚀 Quick Deploy to Railway

1. **Push этот код в GitHub**
2. **Подключите репозиторий к Railway**
3. **Настройте Environment Variables**

## 🔑 Environment Variables

Добавьте в Railway эти переменные:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
GITHUB_TOKEN=your_github_token_here
GITHUB_REPO=username/repository
WEBHOOK_SECRET=your_webhook_secret_here
GEOSITE_CATEGORIES=category-ads-all,google,youtube,apple,netflix,github
RAM_THRESHOLD=85
CPU_THRESHOLD=3.0
```

## 📡 Endpoints

- `GET /` - Main page with info
- `GET /health` - Health check
- `GET /status` - System status
- `POST /webhook/geosite-update` - Geosite update notifications
- `POST /webhook/monitoring` - Router metrics (every 5 min)
- `POST /webhook/alert` - Critical alerts
- `GET /metrics/latest` - Get latest metrics

## 🔐 Webhook Security

Все webhook endpoints защищены Bearer token:

```bash
Authorization: Bearer YOUR_WEBHOOK_SECRET
```

## 📊 Monitoring

Хранит последние 24 часа метрик в памяти (~100KB):
- RAM usage %
- CPU load average
- WiFi clients count
- OpenClash memory
- Alerts history

## 🛠️ Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python app.py
```

## 📝 Features (Coming Soon)

- ✅ Webhook endpoints
- ✅ Metrics storage
- ✅ Alerts tracking
- ⏳ Telegram bot integration
- ⏳ Dashboard generation
- ⏳ Geosite builder
- ⏳ GitHub releases

## 📚 Documentation

See main project docs: `../docs/GEOSITE_AUTO_UPDATE_PROJECT.md`

