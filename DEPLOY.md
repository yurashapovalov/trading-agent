# Deployment

## Infrastructure

- **Server**: Hetzner VPS (37.27.204.135:2222)
- **Path**: `/root/stock`
- **Service**: `trading-api` (systemd)
- **Auto-deploy**: GitHub Actions on push to `main`

## Auto Deployment

Push to `main` branch triggers automatic deployment:

```yaml
# .github/workflows/deploy.yml
on:
  push:
    branches: [main]
    paths:
      - 'agent/**'
      - 'data/**'
      - 'api.py'
      - 'config.py'
```

GitHub Actions will:
1. SSH to server
2. `git pull origin main`
3. `pip install -r requirements.txt`
4. `systemctl restart trading-api`

## Manual Deployment

```bash
ssh -p 2222 root@37.27.204.135
cd /root/stock
git pull
source venv/bin/activate
pip install -r requirements.txt
systemctl restart trading-api
```

## Check Status

```bash
# Service status
systemctl status trading-api

# Logs
journalctl -u trading-api -f

# Test API
curl http://localhost:8000/
```

## Environment Variables

Server `.env` file (`/root/stock/.env`):

```bash
GOOGLE_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
DATABASE_PATH=data/trading.duckdb
```

## Frontend

Frontend is on Vercel, auto-deploys from `frontend/` folder.

## Troubleshooting

```bash
# Restart service
systemctl restart trading-api

# Check Python errors
journalctl -u trading-api -n 100

# Test locally
python api.py
```
