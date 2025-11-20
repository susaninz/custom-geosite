"""
Geosite Manager Bot - Main Application
Railway Flask App with Telegram Bot Integration
"""
from flask import Flask, request, jsonify
import logging
import sys
from datetime import datetime, timezone, timedelta
import requests
import json

# Import configuration
import config

# Moscow timezone (UTC+3)
MOSCOW_TZ = timezone(timedelta(hours=3))

def to_moscow_time(dt):
    """Convert datetime to Moscow timezone"""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MOSCOW_TZ)

def format_moscow_time(dt, fmt='%d.%m.%Y %H:%M'):
    """Format datetime in Moscow timezone"""
    moscow_dt = to_moscow_time(dt)
    return moscow_dt.strftime(fmt)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Telegram Bot API URL
TELEGRAM_API = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"

def send_telegram_message(text, parse_mode='HTML', reply_markup=None):
    """Send message to Telegram chat"""
    try:
        payload = {
            'chat_id': config.TELEGRAM_CHAT_ID,
            'text': text,
            'parse_mode': parse_mode
        }
        if reply_markup:
            payload['reply_markup'] = reply_markup
        
        response = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"Telegram message sent successfully")
            return True
        else:
            logger.error(f"Failed to send Telegram message: HTTP {response.status_code}, {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}", exc_info=True)
        return False

def edit_telegram_message(chat_id, message_id, text, parse_mode='HTML', reply_markup=None):
    """Edit existing Telegram message"""
    try:
        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'parse_mode': parse_mode
        }
        if reply_markup:
            payload['reply_markup'] = reply_markup
        
        response = requests.post(f"{TELEGRAM_API}/editMessageText", json=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"Message edited successfully: {message_id}")
            return True
        else:
            logger.error(f"Failed to edit message: HTTP {response.status_code}, {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error editing Telegram message: {e}", exc_info=True)
        return False

# In-memory storage for metrics (last 24 hours)
metrics_history = {
    'timestamps': [],
    'ram_percent': [],
    'cpu_load1': [],
    'clients': [],
    'openclash_memory': [],
    'alerts': []
}

# In-memory storage for IoT devices
iot_devices_history = {}
for room_id, device_config in config.YANDEX_STATIONS.items():
    iot_devices_history[room_id] = {
        'name': device_config['name'],
        'hostname': device_config['hostname'],
        'mac': device_config['mac'],
        'ip': device_config['ip'],
        'icon': device_config['icon'],
        'status': 'unknown',  # unknown, connected, disconnected
        'last_seen': None,
        'uptime_start': None,
        'signal': None,
        'events': [],  # последние 100 событий
        'stats_24h': {
            'disconnects': 0,
            'connects': 0,
            'avg_uptime': '0m',
            'total_uptime_seconds': 0
        },
        'muted_until': None  # timestamp для функции "тихо 1ч"
    }

@app.route('/')
def index():
    """Main page"""
    return jsonify({
        'status': 'online',
        'service': 'Geosite Manager Bot',
        'version': '1.0.0',
        'endpoints': {
            'health': '/health',
            'status': '/status',
            'geosite_webhook': '/webhook/geosite-update',
            'monitoring_webhook': '/webhook/monitoring',
            'alert_webhook': '/webhook/alert'
        }
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'version': '1.1.0-iot-monitoring',
        'timestamp': datetime.utcnow().isoformat(),
        'metrics_count': len(metrics_history['timestamps'])
    })

@app.route('/status')
def status():
    """Status endpoint"""
    return jsonify({
        'bot_configured': bool(config.TELEGRAM_BOT_TOKEN),
        'github_configured': bool(config.GITHUB_TOKEN),
        'webhook_configured': bool(config.WEBHOOK_SECRET),
        'metrics_stored': len(metrics_history['timestamps']),
        'iot_devices': iot_devices_history,
        'config': {
            'geosite_categories': config.GEOSITE_CATEGORIES,
            'ram_threshold': config.RAM_THRESHOLD,
            'cpu_threshold': config.CPU_THRESHOLD
        }
    })

@app.route('/webhook/geosite-update', methods=['POST'])
def geosite_update_webhook():
    """Handle geosite update notifications from router"""
    
    # Verify webhook secret
    auth_header = request.headers.get('Authorization')
    expected = f"Bearer {config.WEBHOOK_SECRET}"
    
    if auth_header != expected:
        logger.warning(f"Unauthorized webhook attempt from {request.remote_addr}")
        return jsonify({'error': 'unauthorized'}), 401
    
    data = request.json
    logger.info(f"Geosite update webhook received: {data}")
    
    # Send beautiful notification
    commit = data.get('commit', 'unknown')[:8]
    old_commit = data.get('old_commit', 'none')[:8]
    
    notification_text = (
        "🔔 <b>Обновление Geosite!</b>\n\n"
        f"📦 Новая версия domain-list-community\n\n"
        f"🔹 <b>Commit:</b> <code>{commit}</code>\n"
        f"🔹 <b>Прошлый:</b> <code>{old_commit}</code>\n\n"
        "Хотите собрать новый geosite.dat?"
    )
    
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔨 Собрать сейчас", "callback_data": f"build_{commit}"},
            ],
            [
                {"text": "⏰ Позже", "callback_data": "build_later"},
                {"text": "❌ Пропустить", "callback_data": "build_skip"}
            ]
        ]
    }
    
    send_telegram_message(notification_text, reply_markup=keyboard)
    
    return jsonify({'status': 'received', 'message': 'Update notification processed'})

@app.route('/webhook/monitoring', methods=['POST'])
def monitoring_webhook():
    """Handle monitoring data from router (every 5 minutes)"""
    
    # Verify webhook secret
    auth_header = request.headers.get('Authorization')
    expected = f"Bearer {config.WEBHOOK_SECRET}"
    
    if auth_header != expected:
        logger.warning(f"Unauthorized monitoring webhook from {request.remote_addr}")
        return jsonify({'error': 'unauthorized'}), 401
    
    data = request.json
    timestamp = data.get('timestamp', datetime.utcnow().isoformat())
    
    # Store metrics in memory (keep last 288 records = 24 hours)
    metrics_history['timestamps'].append(timestamp)
    metrics_history['ram_percent'].append(data.get('ram', {}).get('percent', 0))
    metrics_history['cpu_load1'].append(data.get('cpu', {}).get('load1', 0))
    metrics_history['clients'].append(data.get('clients', 0))
    metrics_history['openclash_memory'].append(
        data.get('openclash', {}).get('memory', 0)
    )
    
    # Keep only last 288 records (24 hours * 12 per hour)
    max_records = 288
    for key in metrics_history:
        if len(metrics_history[key]) > max_records:
            metrics_history[key] = metrics_history[key][-max_records:]
    
    logger.info(f"Monitoring data stored: RAM={data.get('ram', {}).get('percent')}%, "
                f"CPU={data.get('cpu', {}).get('load1')}, "
                f"Clients={data.get('clients')}")
    
    return jsonify({'status': 'stored', 'records': len(metrics_history['timestamps'])})

@app.route('/webhook/alert', methods=['POST'])
def alert_webhook():
    """Handle critical alerts from router"""
    
    # Verify webhook secret
    auth_header = request.headers.get('Authorization')
    expected = f"Bearer {config.WEBHOOK_SECRET}"
    
    if auth_header != expected:
        logger.warning(f"Unauthorized alert webhook from {request.remote_addr}")
        return jsonify({'error': 'unauthorized'}), 401
    
    data = request.json
    alert_type = data.get('type', 'unknown')
    value = data.get('value', 0)
    threshold = data.get('threshold', 0)
    
    # Store alert in history
    alert_record = {
        'timestamp': data.get('timestamp', datetime.utcnow().isoformat()),
        'type': alert_type,
        'value': value,
        'threshold': threshold,
        'severity': 'critical' if value > threshold * 1.1 else 'warning'
    }
    metrics_history['alerts'].append(alert_record)
    
    # Keep only last 100 alerts
    if len(metrics_history['alerts']) > 100:
        metrics_history['alerts'] = metrics_history['alerts'][-100:]
    
    logger.warning(f"ALERT: {alert_type} = {value} (threshold: {threshold})")
    
    # Send beautiful alert notification
    severity_icon = '🔴' if alert_record['severity'] == 'critical' else '🟡'
    type_icons = {
        'ram': '💾',
        'cpu': '🔥',
        'openclash': '🌐'
    }
    icon = type_icons.get(alert_type.lower(), '⚠️')
    
    alert_text = (
        f"{severity_icon} <b>КРИТИЧЕСКИЙ АЛЕРТ!</b>\n\n"
        f"{icon} <b>{alert_type.upper()}</b>\n\n"
        f"📊 <b>Текущее:</b> {value}\n"
        f"⚠️ <b>Порог:</b> {threshold}\n"
        f"📈 <b>Превышение:</b> {((value/threshold - 1) * 100):.1f}%\n\n"
        f"🕐 {alert_record['timestamp'][:16]}"
    )
    
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📊 Dashboard", "callback_data": "dashboard"},
                {"text": "📈 Stats", "callback_data": "stats"}
            ],
            [
                {"text": "✅ Понятно", "callback_data": "alert_ack"}
            ]
        ]
    }
    
    send_telegram_message(alert_text, reply_markup=keyboard)
    
    return jsonify({'status': 'alert_received', 'severity': alert_record['severity']})

@app.route('/metrics/latest')
def get_latest_metrics():
    """Get latest metrics (API endpoint)"""
    if not metrics_history['timestamps']:
        return jsonify({'error': 'no data'}), 404
    
    return jsonify({
        'timestamp': metrics_history['timestamps'][-1] if metrics_history['timestamps'] else None,
        'ram_percent': metrics_history['ram_percent'][-1] if metrics_history['ram_percent'] else 0,
        'cpu_load1': metrics_history['cpu_load1'][-1] if metrics_history['cpu_load1'] else 0,
        'clients': metrics_history['clients'][-1] if metrics_history['clients'] else 0,
        'openclash_memory': metrics_history['openclash_memory'][-1] if metrics_history['openclash_memory'] else 0,
        'recent_alerts': metrics_history['alerts'][-5:] if metrics_history['alerts'] else []
    })

@app.route('/webhook/build-complete', methods=['POST'])
def build_complete_webhook():
    """Handle build completion notifications from GitHub Actions"""
    
    # Verify webhook secret
    auth_header = request.headers.get('Authorization')
    expected = f"Bearer {config.WEBHOOK_SECRET}"
    
    if auth_header != expected:
        logger.warning(f"Unauthorized build webhook from {request.remote_addr}")
        return jsonify({'error': 'unauthorized'}), 401
    
    data = request.json
    status = data.get('status', 'unknown')
    version = data.get('version', 'unknown')
    commit = data.get('commit', 'unknown')[:8]
    size = data.get('size', 'unknown')
    
    logger.info(f"Build complete webhook: {status} - {version}")
    
    # Send Telegram notification
    if status == 'success':
        notification_text = (
            f"✅ <b>Сборка завершена!</b>\n\n"
            f"📦 <b>Версия:</b> {version}\n"
            f"💾 <b>Размер:</b> {size}\n"
            f"🔹 <b>Commit:</b> <code>{commit}</code>\n\n"
            f"🔗 <a href=\"{data.get('url', '')}\">Скачать релиз</a>\n\n"
            f"🔄 Роутер автоматически обновится при следующей проверке"
        )
    else:
        error = data.get('error', 'Unknown error')
        notification_text = (
            f"❌ <b>Сборка не удалась!</b>\n\n"
            f"📦 <b>Версия:</b> {version}\n"
            f"🔹 <b>Commit:</b> <code>{commit}</code>\n"
            f"❗ <b>Ошибка:</b> {error}\n\n"
            f"Проверьте логи GitHub Actions"
        )
    
    send_telegram_message(notification_text)
    
    return jsonify({'status': 'notification_sent'})

@app.route('/webhook/router-event', methods=['POST'])
def router_event_webhook():
    """Handle router events (geosite updates, etc.)"""
    
    # Verify webhook secret
    auth_header = request.headers.get('Authorization')
    expected = f"Bearer {config.WEBHOOK_SECRET}"
    
    if auth_header != expected:
        logger.warning(f"Unauthorized router event from {request.remote_addr}")
        return jsonify({'error': 'unauthorized'}), 401
    
    data = request.json
    event = data.get('event', 'unknown')
    status = data.get('status', 'unknown')
    message = data.get('message', '')
    version = data.get('version', 'unknown')
    router = data.get('router', 'OpenWrt')
    
    logger.info(f"Router event: {event} - {status} - {message}")
    
    # Send Telegram notification
    if event == 'geosite_update':
        if status == 'success':
            notification_text = (
                f"🔄 <b>Geosite обновлён!</b>\n\n"
                f"📦 <b>Версия:</b> {version}\n"
                f"💾 <b>Размер:</b> 91 KB\n"
                f"🤖 <b>Роутер:</b> {router}\n\n"
                f"✅ OpenClash перезапущен"
            )
        else:
            notification_text = (
                f"❌ <b>Ошибка обновления Geosite</b>\n\n"
                f"<b>Причина:</b> {message}\n"
                f"📦 <b>Версия:</b> {version}\n"
                f"🤖 <b>Роутер:</b> {router}\n\n"
                f"Проверьте логи на роутере"
            )
        
        send_telegram_message(notification_text)
    
    return jsonify({'status': 'processed'})

@app.route('/webhook/yandex-station', methods=['POST'])
def yandex_station_webhook():
    """Handle Yandex Station connection events from router"""
    from datetime import datetime, timedelta
    
    # Verify webhook secret
    auth_header = request.headers.get('X-Webhook-Secret')
    
    if auth_header != config.WEBHOOK_SECRET:
        logger.warning(f"Unauthorized yandex-station webhook from {request.remote_addr}")
        return jsonify({'error': 'unauthorized'}), 401
    
    data = request.json
    event_type = data.get('event', 'unknown')  # disconnect, connected, dhcp
    room = data.get('room', 'unknown')
    device_name = data.get('device_name', 'Unknown')
    mac = data.get('mac', '')
    ip = data.get('ip', '')
    timestamp_str = data.get('timestamp', '')
    signal = data.get('signal', 'unknown')
    uptime = data.get('uptime', '0m')
    reason = data.get('reason', '')
    
    logger.info(f"Yandex Station event: {event_type} - {device_name} ({room})")
    
    # Check if device exists in our config
    if room not in iot_devices_history:
        logger.warning(f"Unknown room: {room}")
        return jsonify({'status': 'unknown_device'}), 400
    
    device = iot_devices_history[room]
    timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()
    
    # Create event record
    event_record = {
        'timestamp': timestamp.isoformat(),
        'type': event_type,
        'signal': signal,
        'uptime': uptime,
        'reason': reason
    }
    
    # Add event to history (keep last 100)
    device['events'].insert(0, event_record)
    if len(device['events']) > config.IOT_MAX_EVENTS_PER_DEVICE:
        device['events'] = device['events'][:config.IOT_MAX_EVENTS_PER_DEVICE]
    
    # Update device status
    device['last_seen'] = timestamp.isoformat()
    device['signal'] = signal
    device['ip'] = ip
    
    # Handle different event types
    if event_type == 'disconnect':
        device['status'] = 'disconnected'
        device['disconnect_time'] = timestamp.isoformat()  # Save disconnect time
        device['stats_24h']['disconnects'] += 1
        
        # Check if device is muted
        if device['muted_until']:
            mute_until = datetime.fromisoformat(device['muted_until'])
            if datetime.now() < mute_until:
                logger.info(f"Device {device_name} is muted until {device['muted_until']}")
                return jsonify({'status': 'muted'})
        
        # Count disconnects in last hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_disconnects = sum(1 for e in device['events'] 
                                if e['type'] == 'disconnect' 
                                and datetime.fromisoformat(e['timestamp']) > one_hour_ago)
        
        # Send notification ONLY for frequent disconnects (critical issue)
        if recent_disconnects >= config.IOT_DISCONNECT_THRESHOLD:
            # Frequent disconnects - critical alert
            notification_text = (
                f"🚨 <b>ПРОБЛЕМА: {device_name}</b>\n\n"
                f"🏠 Комната: {device_name.split()[-1]}\n"
                f"⚠️ Отключений за час: {recent_disconnects} раз\n"
                f"⏱ Последнее время работы: {uptime}\n"
                f"📡 Последний сигнал: {signal}\n\n"
                f"🔍 Возможные причины:\n"
                f"• Проблема с прошивкой станции\n"
                f"• Конфликт IP в сети\n"
                f"• Проблема с облаком Яндекс\n"
                f"• Плохой сигнал Wi-Fi"
            )
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "📊 Полная история", "callback_data": f"iot_history_{room}"},
                    ],
                    [
                        {"text": "🔧 Диагностика", "callback_data": f"iot_diagnose_{room}"},
                        {"text": "✅ Принято", "callback_data": "alert_ack"}
                    ]
                ]
            }
            send_telegram_message(notification_text, reply_markup=keyboard)
        # Normal disconnect - DON'T send notification immediately
        # Will check on next connect if offline was > 3 minutes
    
    elif event_type == 'connected':
        # Check if device was offline > 3 minutes
        was_offline_long = False
        offline_duration = None
        
        if device.get('disconnect_time'):
            disconnect_dt = datetime.fromisoformat(device['disconnect_time'])
            offline_duration = timestamp - disconnect_dt
            offline_minutes = offline_duration.total_seconds() / 60
            
            if offline_minutes > 3:
                was_offline_long = True
        
        device['status'] = 'connected'
        device['uptime_start'] = timestamp.isoformat()
        device['disconnect_time'] = None  # Clear disconnect time
        device['stats_24h']['connects'] += 1
        
        # Send notification ONLY if device was offline > 3 minutes
        if was_offline_long and offline_duration:
            offline_minutes = int(offline_duration.total_seconds() / 60)
            notification_text = (
                f"⚠️ <b>{device_name} была офлайн</b>\n\n"
                f"🏠 Комната: {device_name.split()[-1]}\n"
                f"⏱ Была офлайн: {offline_minutes} мин\n"
                f"📡 Сигнал: {signal}\n"
                f"🔄 IP: {ip}\n"
                f"⏰ {format_moscow_time(timestamp)}"
            )
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "📊 История", "callback_data": f"iot_history_{room}"},
                        {"text": "✅ Принято", "callback_data": "alert_ack"}
                    ]
                ]
            }
            send_telegram_message(notification_text, reply_markup=keyboard)
    
    return jsonify({'status': 'processed', 'device': device_name})

def get_main_menu():
    """Get main menu inline keyboard"""
    return {
        "inline_keyboard": [
            [
                {"text": "📊 Dashboard", "callback_data": "dashboard"},
                {"text": "⚙️ Status", "callback_data": "status"}
            ],
            [
                {"text": "🚨 Alerts", "callback_data": "alerts"},
                {"text": "📈 Stats", "callback_data": "stats"}
            ],
            [
                {"text": "🏠 IoT Devices", "callback_data": "iot_menu"}
            ],
            [
                {"text": "🔄 Refresh", "callback_data": "refresh"}
            ]
        ]
    }

def get_back_button():
    """Get back to menu button"""
    return {
        "inline_keyboard": [
            [{"text": "◀️ Назад в меню", "callback_data": "menu"}]
        ]
    }

def get_iot_menu():
    """Get IoT devices menu"""
    return {
        "inline_keyboard": [
            [
                {"text": "📱 Спальня", "callback_data": "iot_device_bedroom"},
                {"text": "📱 Гостиная", "callback_data": "iot_device_living_room"}
            ],
            [
                {"text": "🔊 Кухня", "callback_data": "iot_device_kitchen"},
                {"text": "📊 История", "callback_data": "iot_history"}
            ],
            [
                {"text": "⚙️ Настройки", "callback_data": "iot_settings"},
                {"text": "◀️ Главное меню", "callback_data": "menu"}
            ]
        ]
    }

def get_iot_device_buttons(room):
    """Get buttons for specific IoT device"""
    return {
        "inline_keyboard": [
            [
                {"text": "📊 История", "callback_data": f"iot_history_{room}"},
                {"text": "🔄 Обновить", "callback_data": f"iot_refresh_{room}"}
            ],
            [
                {"text": "🔇 Тихо 1ч", "callback_data": f"iot_mute_1h_{room}"},
                {"text": "◀️ К устройствам", "callback_data": "iot_menu"}
            ]
        ]
    }

def get_iot_back_button():
    """Get back to IoT menu button"""
    return {
        "inline_keyboard": [
            [{"text": "◀️ К устройствам", "callback_data": "iot_menu"}]
        ]
    }

@app.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    """Handle Telegram bot webhook"""
    try:
        update = request.json
        logger.info(f"Telegram update received: {update}")
        
        # Handle callback queries (button presses)
        if 'callback_query' in update:
            callback_query = update['callback_query']
            callback_data = callback_query.get('data', '')
            callback_id = callback_query.get('id')
            
            # Get message and chat info safely
            message = callback_query.get('message', {})
            message_id = message.get('message_id')
            chat = message.get('chat', {})
            chat_id = chat.get('id')
            
            # Verify we have required data
            if not callback_id or not message_id or not chat_id:
                logger.error(f"Missing required callback data: {callback_query}")
                return jsonify({'error': 'missing data'}), 400
            
            # Verify chat
            if str(chat_id) != str(config.TELEGRAM_CHAT_ID):
                logger.warning(f"Unauthorized callback from chat: {chat_id}")
                return jsonify({'status': 'ignored'})
            
            # Answer callback to remove loading state
            answer_result = requests.post(
                f"{TELEGRAM_API}/answerCallbackQuery",
                json={'callback_query_id': callback_id}
            )
            logger.info(f"Callback answer result: {answer_result.status_code}")
            
            # Handle different callbacks
            if callback_data == 'menu' or callback_data == 'refresh':
                welcome_text = (
                    "🤖 <b>Geosite Manager</b>\n\n"
                    "Управление OpenWrt роутером\n\n"
                    "🔹 <b>Мониторинг:</b> RAM, CPU, WiFi\n"
                    "🔹 <b>Geosite:</b> Автообновления\n"
                    "🔹 <b>Алерты:</b> Критические события\n\n"
                    "Выберите действие:"
                )
                edit_telegram_message(chat_id, message_id, welcome_text, reply_markup=get_main_menu())
            
            elif callback_data == 'status':
                status_text = (
                    "⚙️ <b>Статус системы</b>\n\n"
                    f"✅ <b>Railway:</b> Online\n"
                    f"✅ <b>Webhooks:</b> Активны\n"
                    f"📊 <b>Метрик:</b> {len(metrics_history['timestamps'])}\n"
                    f"🚨 <b>Алертов:</b> {len(metrics_history['alerts'])}\n\n"
                    f"🔧 <b>Конфигурация:</b>\n"
                    f"├ RAM limit: {config.RAM_THRESHOLD}%\n"
                    f"├ CPU limit: {config.CPU_THRESHOLD}\n"
                    f"└ Категорий: {len(config.GEOSITE_CATEGORIES)}\n\n"
                    f"🌐 <b>Router:</b> 192.168.31.1\n"
                    f"📡 <b>Updates:</b> Каждые 5 мин"
                )
                edit_telegram_message(chat_id, message_id, status_text, reply_markup=get_back_button())
            
            elif callback_data == 'dashboard':
                if not metrics_history['timestamps']:
                    dashboard_text = (
                        "📊 <b>Dashboard</b>\n\n"
                        "⏳ Метрики еще не собраны.\n"
                        "Ожидайте первого обновления\n"
                        "(каждые 5 минут)"
                    )
                else:
                    ram = metrics_history['ram_percent'][-1] if metrics_history['ram_percent'] else 0
                    cpu = metrics_history['cpu_load1'][-1] if metrics_history['cpu_load1'] else 0
                    clients = metrics_history['clients'][-1] if metrics_history['clients'] else 0
                    clash_mem = metrics_history['openclash_memory'][-1] if metrics_history['openclash_memory'] else 0
                    
                    # RAM bar
                    ram_bars = '█' * (int(ram) // 10) + '░' * (10 - int(ram) // 10)
                    ram_status = '🟢' if ram < 70 else '🟡' if ram < 85 else '🔴'
                    
                    dashboard_text = (
                        "📊 <b>Router Dashboard</b>\n\n"
                        f"💾 <b>RAM:</b> {ram}% {ram_status}\n"
                        f"{ram_bars}\n\n"
                        f"🔥 <b>CPU Load:</b> {cpu}\n"
                        f"{'🟢 Normal' if cpu < 2.0 else '🟡 High' if cpu < 3.0 else '🔴 Critical'}\n\n"
                        f"📡 <b>WiFi:</b> {clients} клиентов\n"
                        f"🌐 <b>OpenClash:</b> {clash_mem}m\n\n"
                        f"📈 Собрано метрик: {len(metrics_history['timestamps'])}"
                    )
                edit_telegram_message(chat_id, message_id, dashboard_text, reply_markup=get_back_button())
            
            elif callback_data == 'alerts':
                if not metrics_history['alerts']:
                    alerts_text = (
                        "🚨 <b>Алерты</b>\n\n"
                        "✅ Алертов нет\n\n"
                        "Всё работает нормально!"
                    )
                else:
                    recent_alerts = metrics_history['alerts'][-5:]
                    alerts_text = "🚨 <b>Последние алерты</b>\n\n"
                    for i, alert in enumerate(recent_alerts, 1):
                        icon = '🔴' if alert.get('severity') == 'critical' else '🟡'
                        alerts_text += (
                            f"{icon} <b>{alert['type'].upper()}</b>\n"
                            f"├ Значение: {alert['value']}\n"
                            f"├ Порог: {alert['threshold']}\n"
                            f"└ {alert['timestamp'][:16]}\n\n"
                        )
                edit_telegram_message(chat_id, message_id, alerts_text, reply_markup=get_back_button())
            
            elif callback_data == 'stats':
                if metrics_history['timestamps']:
                    # Calculate statistics
                    avg_ram = sum(metrics_history['ram_percent']) / len(metrics_history['ram_percent'])
                    max_ram = max(metrics_history['ram_percent']) if metrics_history['ram_percent'] else 0
                    avg_cpu = sum(metrics_history['cpu_load1']) / len(metrics_history['cpu_load1'])
                    max_cpu = max(metrics_history['cpu_load1']) if metrics_history['cpu_load1'] else 0
                    
                    stats_text = (
                        "📈 <b>Статистика за 24ч</b>\n\n"
                        f"💾 <b>RAM:</b>\n"
                        f"├ Средняя: {avg_ram:.1f}%\n"
                        f"└ Максимум: {max_ram:.1f}%\n\n"
                        f"🔥 <b>CPU:</b>\n"
                        f"├ Средняя: {avg_cpu:.2f}\n"
                        f"└ Максимум: {max_cpu:.2f}\n\n"
                        f"📊 <b>Данных:</b>\n"
                        f"├ Метрик: {len(metrics_history['timestamps'])}\n"
                        f"└ Алертов: {len(metrics_history['alerts'])}"
                    )
                else:
                    stats_text = (
                        "📈 <b>Статистика</b>\n\n"
                        "⏳ Недостаточно данных\n"
                        "Подождите накопления метрик"
                    )
                edit_telegram_message(chat_id, message_id, stats_text, reply_markup=get_back_button())
            
            elif callback_data.startswith('build_'):
                commit = callback_data.replace('build_', '')
                if commit == 'later':
                    response_text = "⏰ Хорошо, напомню позже!"
                elif commit == 'skip':
                    response_text = "❌ Обновление пропущено"
                else:
                    # TODO: Trigger actual build via GitHub Actions
                    response_text = (
                        f"🔨 <b>Сборка запущена!</b>\n\n"
                        f"Commit: <code>{commit}</code>\n\n"
                        "⏳ Это займёт ~2-3 минуты\n"
                        "Я уведомлю когда будет готово!"
                    )
                    logger.info(f"Build triggered for commit: {commit}")
                
                edit_telegram_message(chat_id, message_id, response_text)
            
            elif callback_data == 'alert_ack':
                # Answer callback to show "Принято" notification
                requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
                    'callback_query_id': callback_id,
                    'text': '✅ Алерт отмечен как прочитанный',
                    'show_alert': False
                }, timeout=10)
                
                # Update button to show it was acknowledged
                requests.post(f"{TELEGRAM_API}/editMessageReplyMarkup", json={
                    'chat_id': chat_id,
                    'message_id': message_id,
                    'reply_markup': {'inline_keyboard': [[{"text": "✅ Прочитано", "callback_data": "none"}]]}
                }, timeout=10)
            
            # Handle IoT menu
            elif callback_data == 'iot_menu':
                from datetime import datetime
                
                # Build status summary
                status_lines = []
                online_count = 0
                for room, device in iot_devices_history.items():
                    status_icon = "✅" if device['status'] == 'connected' else "⚠️" if device['status'] == 'disconnected' else "❓"
                    if device['status'] == 'connected':
                        online_count += 1
                    
                    # Calculate uptime
                    uptime = "unknown"
                    if device['uptime_start']:
                        try:
                            start = datetime.fromisoformat(device['uptime_start'])
                            delta = datetime.now() - start
                            days = delta.days
                            hours = delta.seconds // 3600
                            if days > 0:
                                uptime = f"{days}д {hours}ч"
                            else:
                                uptime = f"{hours}ч {(delta.seconds % 3600) // 60}м"
                        except:
                            uptime = "unknown"
                    
                    status_lines.append(f"{status_icon} {device['name']}   (uptime: {uptime})")
                
                iot_menu_text = (
                    "🏠 <b>IoT Устройства</b>\n\n"
                    "📊 Статус всех устройств:\n"
                    + "\n".join(status_lines) + "\n\n"
                    f"Всего устройств: {len(iot_devices_history)}\n"
                    f"Онлайн: {online_count} | Офлайн: {len(iot_devices_history) - online_count}\n\n"
                    "Выберите устройство:"
                )
                edit_telegram_message(chat_id, message_id, iot_menu_text, reply_markup=get_iot_menu())
            
            # Handle IoT device details
            elif callback_data.startswith('iot_device_'):
                from datetime import datetime
                room = callback_data.replace('iot_device_', '')
                
                if room in iot_devices_history:
                    device = iot_devices_history[room]
                    status_icon = "✅" if device['status'] == 'connected' else "❌"
                    
                    # Calculate uptime
                    uptime = "unknown"
                    if device['uptime_start'] and device['status'] == 'connected':
                        try:
                            start = datetime.fromisoformat(device['uptime_start'])
                            delta = datetime.now() - start
                            hours = delta.seconds // 3600
                            minutes = (delta.seconds % 3600) // 60
                            if delta.days > 0:
                                uptime = f"{delta.days}д {hours}ч"
                            else:
                                uptime = f"{hours}ч {minutes}м"
                        except:
                            uptime = "unknown"
                    
                    # Get stats
                    disconnects_24h = device['stats_24h']['disconnects']
                    
                    device_text = (
                        f"{device['icon']} <b>{device['name']}</b>\n\n"
                        f"📊 Статус: {status_icon} {'Подключена' if device['status'] == 'connected' else 'Отключена'}\n"
                        f"🕐 Работает: {uptime}\n"
                        f"📡 Сигнал: {device['signal'] or 'unknown'}\n"
                        f"🔄 IP: {device['ip']}\n"
                        f"🏠 Комната: {device['name'].split()[-1]}\n"
                    )
                    
                    if device['last_seen']:
                        try:
                            device_text += f"⏰ Последнее событие: {format_moscow_time(device['last_seen'], '%d.%m %H:%M')}\n"
                        except:
                            pass
                    
                    device_text += (
                        f"\n📈 За 24 часа:\n"
                        f"├ Отключений: {disconnects_24h} раз\n"
                    )
                    
                    # Last event
                    if device['events']:
                        last_event = device['events'][0]
                        event_type = last_event['type']
                        event_icon = "❌" if event_type == 'disconnect' else "✅"
                        device_text += f"└ Последнее событие: {event_icon} {event_type}\n"
                    
                    edit_telegram_message(chat_id, message_id, device_text, reply_markup=get_iot_device_buttons(room))
                else:
                    error_text = f"❌ Устройство не найдено: {room}"
                    edit_telegram_message(chat_id, message_id, error_text, reply_markup=get_iot_back_button())
            
            # Handle IoT history
            elif callback_data.startswith('iot_history'):
                from datetime import datetime
                
                if callback_data == 'iot_history':
                    # All devices history
                    all_events = []
                    for room, device in iot_devices_history.items():
                        for event in device['events'][:10]:  # Last 10 per device
                            all_events.append({
                                'device': device['name'],
                                'icon': device['icon'],
                                'timestamp': event['timestamp'],
                                'type': event['type'],
                                'uptime': event.get('uptime', ''),
                                'signal': event.get('signal', '')
                            })
                    
                    # Sort by timestamp descending
                    all_events.sort(key=lambda x: x['timestamp'], reverse=True)
                    
                    history_text = "📊 <b>История IoT устройств</b>\n\nПоследние 20 событий:\n\n"
                    
                    for event in all_events[:20]:
                        try:
                            event_icon = "❌" if event['type'] == 'disconnect' else "✅"
                            history_text += f"{format_moscow_time(event['timestamp'], '%d.%m %H:%M')} {event['icon']} {event['device']}\n"
                            history_text += f"{event_icon} {event['type']}"
                            if event.get('uptime'):
                                history_text += f" ({event['uptime']})"
                            history_text += "\n\n"
                        except:
                            pass
                    
                    edit_telegram_message(chat_id, message_id, history_text, reply_markup=get_iot_back_button())
                else:
                    # Specific device history
                    room = callback_data.replace('iot_history_', '')
                    if room in iot_devices_history:
                        device = iot_devices_history[room]
                        history_text = f"📊 <b>История: {device['name']}</b>\n\nПоследние 10 событий:\n\n"
                        
                        for event in device['events'][:10]:
                            try:
                                event_icon = "❌" if event['type'] == 'disconnect' else "✅"
                                history_text += f"{format_moscow_time(event['timestamp'], '%d.%m %H:%M')} {event_icon} {event['type']}\n"
                                if event.get('uptime'):
                                    history_text += f"├ Работала: {event['uptime']}\n"
                                if event.get('signal'):
                                    history_text += f"└ Сигнал: {event['signal']}\n"
                                history_text += "\n"
                            except:
                                pass
                        
                        edit_telegram_message(chat_id, message_id, history_text, reply_markup=get_iot_device_buttons(room))
                    else:
                        error_text = f"❌ Устройство не найдено: {room}"
                        edit_telegram_message(chat_id, message_id, error_text, reply_markup=get_iot_back_button())
            
            # Handle IoT mute
            elif callback_data.startswith('iot_mute_1h_'):
                from datetime import datetime, timedelta
                room = callback_data.replace('iot_mute_1h_', '')
                
                if room in iot_devices_history:
                    device = iot_devices_history[room]
                    mute_until = datetime.now() + timedelta(hours=1)
                    device['muted_until'] = mute_until.isoformat()
                    
                    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
                        'callback_query_id': callback_id,
                        'text': f'🔇 {device["name"]} - уведомления выключены на 1 час',
                        'show_alert': False
                    }, timeout=10)
                    
                    # Update message to show muted status
                    muted_text = (
                        f"🔇 <b>{device['name']}</b>\n\n"
                        f"Уведомления отключены до {format_moscow_time(mute_until, '%H:%M')}\n\n"
                        f"Устройство будет продолжать мониториться,\n"
                        f"но уведомления не будут отправляться."
                    )
                    edit_telegram_message(chat_id, message_id, muted_text, reply_markup=get_iot_device_buttons(room))
            
            # Handle IoT settings
            elif callback_data == 'iot_settings':
                settings_text = (
                    "⚙️ <b>Настройки IoT мониторинга</b>\n\n"
                )
                
                for room, device in iot_devices_history.items():
                    notify_status = "✅ Включены" if device.get('notify', True) else "❌ Выключены"
                    muted = ""
                    if device.get('muted_until'):
                        try:
                            mute_until = datetime.fromisoformat(device['muted_until'])
                            if datetime.now() < mute_until:
                                muted = f"\n├ 🔇 Тихо до {format_moscow_time(mute_until, '%H:%M')}"
                        except:
                            pass
                    
                    settings_text += (
                        f"{device['icon']} <b>{device['name']}</b>\n"
                        f"├ Уведомления: {notify_status}{muted}\n"
                        f"└ Отключение: ✅ Каждое\n\n"
                    )
                
                settings_text += (
                    f"🔔 Общие настройки:\n"
                    f"├ Частые отключения: >{config.IOT_DISCONNECT_THRESHOLD}/час\n"
                    f"└ Критичный офлайн: >{config.IOT_CRITICAL_OFFLINE_MIN} мин"
                )
                
                edit_telegram_message(chat_id, message_id, settings_text, reply_markup=get_iot_back_button())
            
            return jsonify({'status': 'ok'})
        
        # Handle regular messages
        message = update.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '')
        
        # Only respond to configured chat
        if str(chat_id) != str(config.TELEGRAM_CHAT_ID):
            logger.warning(f"Unauthorized chat: {chat_id}")
            return jsonify({'status': 'ignored'})
        
        # Handle /start or any text message
        welcome_text = (
            "🤖 <b>Geosite Manager</b>\n\n"
            "Управление OpenWrt роутером\n\n"
            "🔹 <b>Мониторинг:</b> RAM, CPU, WiFi\n"
            "🔹 <b>Geosite:</b> Автообновления\n"
            "🔹 <b>Алерты:</b> Критические события\n\n"
            "Выберите действие:"
        )
        send_telegram_message(welcome_text, reply_markup=get_main_menu())
        
        return jsonify({'status': 'ok'})
    
    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting Geosite Manager Bot...")
    logger.info(f"Bot Token configured: {bool(config.TELEGRAM_BOT_TOKEN)}")
    logger.info(f"GitHub configured: {bool(config.GITHUB_TOKEN)}")
    logger.info(f"Webhook secret configured: {bool(config.WEBHOOK_SECRET)}")
    
    app.run(host='0.0.0.0', port=config.PORT, debug=False)

