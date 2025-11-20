# 🤖 Router Scripts - Installation Guide

Скрипты для автоматизации OpenWrt роутера.

---

## 📋 Содержание

### 1. `check_geosite_updates.sh`
- **Назначение:** Проверка обновлений domain-list-community
- **Частота:** Раз в день (03:00)
- **Действие:** Отправляет webhook на Railway при наличии обновлений

### 2. `monitor_router.sh`
- **Назначение:** Мониторинг системы роутера
- **Частота:** Каждые 5 минут
- **Метрики:** RAM, CPU, WiFi клиенты, статус OpenClash
- **Действие:** Отправляет метрики на Railway, алерты при критических значениях

---

## 🚀 Установка на роутер

### Шаг 1: Подключитесь к роутеру

```bash
ssh root@192.168.31.1
```

### Шаг 2: Загрузите скрипты

**С вашего компьютера:**

```bash
# Из директории проекта
cd "/Users/ivanslezkin/Cursor/Open wrt router"

# Загрузка check_geosite_updates.sh
scp plugins/openclash/geosite-manager/router/check_geosite_updates.sh root@192.168.31.1:/root/

# Загрузка monitor_router.sh
scp plugins/openclash/geosite-manager/router/monitor_router.sh root@192.168.31.1:/root/
```

### Шаг 3: Установите права

**На роутере:**

```bash
chmod 700 /root/check_geosite_updates.sh
chmod 700 /root/monitor_router.sh
```

### Шаг 4: Настройте cron

**На роутере:**

```bash
# Откройте crontab
crontab -e

# Добавьте эти строки:
# Проверка geosite обновлений (каждый день в 03:00)
0 3 * * * /root/check_geosite_updates.sh >> /tmp/geosite_check.log 2>&1

# Мониторинг роутера (каждые 5 минут)
*/5 * * * * /root/monitor_router.sh >> /tmp/monitor.log 2>&1

# Сохраните (Ctrl+O, Enter, Ctrl+X)
```

### Шаг 5: Перезапустите cron

```bash
/etc/init.d/cron restart
```

---

## 🧪 Тестирование

### Тест 1: Проверка geosite обновлений

```bash
# Запустите вручную
/root/check_geosite_updates.sh

# Проверьте лог
cat /tmp/geosite_check.log
```

**Ожидаемый результат:**
```
[GeoSite Check] 2025-11-07 03:00:05 - Starting check...
[GeoSite Check] Fetching latest commit from GitHub...
[GeoSite Check] Latest commit: abc123...
[GeoSite Check] Saved commit: xyz789...
[GeoSite Check] UPDATE FOUND! Sending webhook to Railway...
[GeoSite Check] Webhook sent successfully (HTTP 200)
[GeoSite Check] Saved new commit: abc123...
[GeoSite Check] Check completed successfully
```

### Тест 2: Мониторинг

```bash
# Запустите вручную
/root/monitor_router.sh

# Проверьте лог
cat /tmp/monitor.log
```

**Ожидаемый результат:**
```
[Monitor] 2025-11-07 15:00:00 - Collecting metrics...
[Monitor] RAM: 126420/245360 KB (51%)
[Monitor] CPU Load: 0.45 0.52 0.38
[Monitor] WiFi Clients: 8
[Monitor] OpenClash: running (1234m)
[Monitor] Data sent successfully (HTTP 200)
[Monitor] Monitoring completed
```

---

## 📊 Проверка на Railway

После запуска скриптов проверьте:

### 1. Health endpoint
```bash
curl https://openwrtrouter-production.up.railway.app/health
```

### 2. Latest metrics
```bash
curl https://openwrtrouter-production.up.railway.app/metrics/latest
```

### 3. Railway Logs
```
Railway Dashboard → Your Project → Logs
```

Вы должны увидеть:
```
[INFO] Monitoring data stored: RAM=51%, CPU=0.45, Clients=8
```

---

## 🔍 Проверка cron

### Убедитесь что cron работает:

```bash
# Проверьте статус cron
/etc/init.d/cron status

# Проверьте crontab
crontab -l

# Проверьте логи cron
logread | grep cron
```

### Ручной запуск для тестирования:

```bash
# Запустите geosite check
/root/check_geosite_updates.sh

# Запустите monitoring
/root/monitor_router.sh
```

---

## 🛠️ Troubleshooting

### Проблема: "Permission denied"

**Решение:**
```bash
chmod 700 /root/check_geosite_updates.sh
chmod 700 /root/monitor_router.sh
```

### Проблема: Webhook не отправляется

**Проверьте:**
```bash
# Интернет работает?
ping -c 3 8.8.8.8

# Railway доступен?
curl -I https://openwrtrouter-production.up.railway.app/health

# Правильный webhook secret?
# Проверьте в скриптах переменную WEBHOOK_SECRET
```

### Проблема: Cron не запускается

**Решение:**
```bash
# Перезапустите cron
/etc/init.d/cron restart

# Проверьте синтаксис crontab
crontab -l

# Проверьте что cron enabled
/etc/init.d/cron enable
```

### Проблема: "curl: command not found"

**Решение:**
```bash
# Установите curl (должен быть в OpenWrt)
opkg update
opkg install curl
```

---

## 📝 Логи

### Просмотр логов:

```bash
# Geosite check log
tail -20 /tmp/geosite_check.log

# Monitoring log
tail -20 /tmp/monitor.log

# Последние логи OpenClash
tail -20 /tmp/openclash.log
```

### Очистка логов:

```bash
# Очистить geosite log
> /tmp/geosite_check.log

# Очистить monitoring log
> /tmp/monitor.log
```

---

## 🔄 Обновление скриптов

Если скрипты обновились в репозитории:

```bash
# С вашего компьютера
cd "/Users/ivanslezkin/Cursor/Open wrt router"
git pull

# Загрузите обновленные скрипты
scp plugins/openclash/geosite-manager/router/*.sh root@192.168.31.1:/root/

# На роутере
chmod 700 /root/*.sh
```

---

## ✅ Чеклист установки

- [ ] SSH доступ к роутеру работает
- [ ] Скрипты загружены на роутер
- [ ] Права установлены (chmod 700)
- [ ] Crontab настроен
- [ ] Cron перезапущен
- [ ] Тестовый запуск успешен
- [ ] Webhook на Railway работает
- [ ] Логи показывают успешную отправку

---

## 📞 Поддержка

Если что-то не работает:
1. Проверьте логи на роутере
2. Проверьте логи Railway
3. Проверьте что роутер имеет доступ в интернет
4. Проверьте что Railway приложение работает

