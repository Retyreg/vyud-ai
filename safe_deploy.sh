#!/bin/bash
# Safe deployment script for VYUD AI Bot

set -e
cd /var/www/vyud_app

# Optional commit message
COMMIT_MSG="${1:-auto-deploy $(date +%Y%m%d_%H%M)}"

echo "📦 Creating backup..."
BACKUP_NAME="/tmp/bot_backup_$(date +%Y%m%d_%H%M).py"
cp bot.py "$BACKUP_NAME"
echo "✅ Backup saved to: $BACKUP_NAME"

echo ""
echo "🧪 Running tests..."
/usr/bin/python3 -m pytest test_bot.py -v

if [ $? -ne 0 ]; then
    echo "❌ Tests failed! Deployment cancelled."
    exit 1
fi

echo ""
echo "📝 Committing to Git..."
git add -A
git commit -m "$COMMIT_MSG" || echo "Nothing to commit"
git push origin main 2>/dev/null || echo "⚠️ Push failed (check remote)"

echo ""
echo "🔄 Restarting bot..."
pkill -f bot.py || true
sleep 2
source venv/bin/activate
nohup python3 bot.py > bot.log 2>&1 &
sleep 3

echo ""
echo "✅ Checking status..."
if ps aux | grep -v grep | grep -q "bot.py"; then
    echo "🚀 Bot is running!"
    tail -10 bot.log
else
    echo "❌ Bot failed to start! Check logs:"
    tail -30 bot.log
    exit 1
fi

echo ""
echo "✨ Deployment complete!"
