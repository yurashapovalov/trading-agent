# Deploy Trading Agent to VPS

## 1. Buy VPS

Recommended:
- **Hetzner** (cheapest): https://hetzner.cloud → CX22 (2 vCPU, 4GB RAM) — €4/month
- **DigitalOcean**: https://digitalocean.com → Basic Droplet — $6/month

Choose **Ubuntu 22.04** or **24.04**.

---

## 2. Connect to Server

```bash
ssh root@YOUR_SERVER_IP
```

---

## 3. Install Dependencies

```bash
# Update system
apt update && apt upgrade -y

# Install Python
apt install -y python3.12 python3.12-venv python3-pip git

# Create app user (optional but recommended)
useradd -m -s /bin/bash trading
su - trading
```

---

## 4. Clone and Setup

```bash
# Clone your repo
git clone https://github.com/YOUR_USERNAME/stock.git
cd stock

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 5. Configure

```bash
# Create .env file with your Anthropic API key
echo "ANTHROPIC_API_KEY=sk-ant-xxxxx" > .env
```

---

## 6. Load Data

```bash
# Initialize database
python -m agent.main init

# Load your CSV data
python -m agent.main load data/CL_train.csv --symbol CL

# Verify
python -m agent.main info
```

---

## 7. Test Locally

```bash
# Run server
python api.py

# In another terminal, test:
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "найди SHORT входы на CL"}'
```

---

## 8. Run in Production

### Option A: Simple (systemd service)

```bash
# Create service file
sudo tee /etc/systemd/system/trading-agent.service << EOF
[Unit]
Description=Trading Agent API
After=network.target

[Service]
User=trading
WorkingDirectory=/home/trading/stock
Environment="PATH=/home/trading/stock/.venv/bin"
ExecStart=/home/trading/stock/.venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl enable trading-agent
sudo systemctl start trading-agent

# Check status
sudo systemctl status trading-agent
```

### Option B: With Nginx (recommended for production)

```bash
# Install nginx
sudo apt install -y nginx

# Configure
sudo tee /etc/nginx/sites-available/trading << EOF
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/trading /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 9. API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| POST | `/chat` | Send message to agent |
| POST | `/reset` | Reset conversation |
| GET | `/data` | Get loaded data info |

### Example Request

```bash
curl -X POST "http://YOUR_SERVER:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "протестируй вход в 09:00 SHORT со стопом 20 тиков"}'
```

### Example Response

```json
{
  "response": "Результат бэктеста:\n- Всего сделок: 10\n- Winrate: 80%\n...",
  "session_id": "default"
}
```

---

## 10. Add HTTPS (optional)

```bash
# Install certbot
sudo apt install -y certbot python3-certbot-nginx

# Get certificate (replace with your domain)
sudo certbot --nginx -d yourdomain.com

# Auto-renewal is set up automatically
```

---

## Troubleshooting

### Check logs
```bash
sudo journalctl -u trading-agent -f
```

### Restart service
```bash
sudo systemctl restart trading-agent
```

### Check if port is open
```bash
sudo ufw allow 8000  # or 80 for nginx
```
