#!/bin/bash
# Безопасный деплой VYUD AI Bot с Git

set -e
cd /var/www/vyud_app

# Получаем сообщение коммита (опционально)
COMMIT_MSG="${1:-auto-deploy $(date +%Y%m%d_%H%M)}"

echo "📦 Создаём бэкап..."
BACKUP_NAME="bot_backup_$(date +%Y%m%d_%H%M).py"
cp bot.py "$BACKUP_NAME"
echo "✅ Бэкап: $BACKUP_NAME"

echo ""
echo "🧪 Запускаем тесты..."
/usr/bin/python3 -m pytest test_bot.py -v

if [ $? -ne 0 ]; then
    echo "❌ Тесты провалены! Деплой отменён."
    exit 1
fi

echo ""
echo "📝 Коммитим в Git..."
git add -A
git commit -m "$COMMIT_MSG" || echo "Нет изменений для коммита"
git push origin main 2>/dev/null || echo "⚠️ Push не удался (проверь remote)"

echo ""
echo "🔄 Перезапускаем бота..."
pkill -f bot.py || true
sleep 2
source venv/bin/activate
nohup python3 bot.py > bot.log 2>&1 &
sleep 3

echo ""
echo "✅ Проверяем статус..."
if ps aux | grep -v grep | grep -q "bot.py"; then
    echo "🚀 Бот запущен!"
    tail -10 bot.log
else
    echo "❌ Бот не запустился! Смотри логи:"
    tail -30 bot.log
    exit 1
fi

echo ""
echo "✨ Деплой завершён!"
