# Deployment

## Infrastructure

- **Server**: Hetzner VPS (37.27.204.135:2222)
- **Path**: `/root/stock`
- **Service**: Docker Compose
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
      - 'Dockerfile'
      - 'docker-compose.yml'
      - 'requirements.txt'
```

GitHub Actions will:
1. SSH to server
2. `git pull origin main`
3. `docker compose down`
4. `docker compose up --build -d`

## Manual Deployment

```bash
ssh -p 2222 root@37.27.204.135
cd /root/stock
git pull
docker compose down
docker compose up --build -d
```

## Check Status

```bash
# Container status
docker compose ps

# Logs
docker compose logs -f

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

## Domain Configuration

- **Frontend**: askbar.ai (Vercel)
- **API**: api.askbar.ai → 37.27.204.135 (Hetzner)

DNS A-record needed:
```
api.askbar.ai → 37.27.204.135
```

## Troubleshooting

```bash
# Restart container
docker compose restart

# Rebuild container
docker compose up --build -d

# Check container logs
docker compose logs --tail=100

# Enter container shell
docker compose exec api bash
```
