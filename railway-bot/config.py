"""
Configuration for Geosite Manager Bot
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# GitHub Configuration  
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
GITHUB_REPO = os.getenv('GITHUB_REPO', 'susaninz/custom-geosite')

# Webhook Security
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'openwrt_yandex_stations_2025')

# Geosite Categories
GEOSITE_CATEGORIES = os.getenv(
    'GEOSITE_CATEGORIES',
    'category-ads-all,instagram,facebook,twitter,youtube,netflix,soundcloud,kinopub,category-ai-!cn,category-gov-ru'
).split(',')

# Monitoring Thresholds
RAM_THRESHOLD = int(os.getenv('RAM_THRESHOLD', '85'))
CPU_THRESHOLD = float(os.getenv('CPU_THRESHOLD', '3.0'))

# Yandex Stations Configuration
YANDEX_STATIONS = {
    'living_room': {
        'name': 'Мини в гостиной',
        'hostname': 'yandex-mini2-HR8G',
        'mac': 'ac:ba:c0:54:f2:16',
        'ip': '192.168.31.140',
        'icon': '📱',
        'notify': True  # проблемная станция
    },
    'bedroom': {
        'name': 'Мини в спальне',
        'hostname': 'yandex-mini2-VHCG',
        'mac': '3c:0b:4f:de:d8:3c',
        'ip': '192.168.31.102',
        'icon': '📱',
        'notify': True
    },
    'kitchen': {
        'name': 'Станция 2 на кухне',
        'hostname': 'Yandex-Station-gen2',
        'mac': '3c:0b:4f:5d:02:78',
        'ip': '192.168.31.131',
        'icon': '🔊',
        'notify': True
    }
}

# IoT Monitoring Settings
IOT_DISCONNECT_THRESHOLD = 3  # алерт если >3 отключений за час
IOT_CRITICAL_OFFLINE_MIN = 30  # критический алерт если офлайн >30 минут
IOT_MAX_EVENTS_PER_DEVICE = 100  # хранить последние 100 событий

# Port for Railway
PORT = int(os.getenv('PORT', '8080'))

