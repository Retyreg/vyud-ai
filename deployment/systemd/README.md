# Systemd Service Files

These files are for deploying VYUD AI with systemd instead of nohup for better reliability and automatic restart on failures.

## Installation

1. Create a dedicated user for running the services (for security):
```bash
sudo useradd -r -s /bin/false vyud
sudo chown -R vyud:vyud /var/www/vyud_app
```

2. Copy service files to systemd directory:
```bash
sudo cp vyud_bot.service /etc/systemd/system/
sudo cp vyud_web.service /etc/systemd/system/
```

3. Create environment file at `/var/www/vyud_app/.env` with your secrets:
```
SUPABASE_URL=your_url_here
SUPABASE_KEY=your_key_here
TELEGRAM_BOT_TOKEN=your_token_here
OPENAI_API_KEY=your_api_key_here
```

4. Set proper permissions on the environment file:
```bash
sudo chown vyud:vyud /var/www/vyud_app/.env
sudo chmod 600 /var/www/vyud_app/.env
```

5. Enable and start services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable vyud_bot vyud_web
sudo systemctl start vyud_bot vyud_web
```

6. Check status:
```bash
sudo systemctl status vyud_bot
sudo systemctl status vyud_web
```

7. View logs:
```bash
sudo journalctl -u vyud_bot -f
sudo journalctl -u vyud_web -f
```

## Security Notes

- Services run as a dedicated `vyud` user (not root) for security
- Environment file contains secrets and should have 600 permissions
- The `vyud` user has no login shell (`/bin/false`) for additional security
