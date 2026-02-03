# Systemd Service Files

These files are for deploying VYUD AI with systemd instead of nohup for better reliability and automatic restart on failures.

## Installation

1. Copy service files to systemd directory:
```bash
sudo cp vyud_bot.service /etc/systemd/system/
sudo cp vyud_web.service /etc/systemd/system/
```

2. Create environment file at `/var/www/vyud_app/.env` with your secrets:
```
SUPABASE_URL=your_url_here
SUPABASE_KEY=your_key_here
TELEGRAM_BOT_TOKEN=your_token_here
OPENAI_API_KEY=your_api_key_here
```

3. Enable and start services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable vyud_bot vyud_web
sudo systemctl start vyud_bot vyud_web
```

4. Check status:
```bash
sudo systemctl status vyud_bot
sudo systemctl status vyud_web
```

5. View logs:
```bash
sudo journalctl -u vyud_bot -f
sudo journalctl -u vyud_web -f
```
