# TitanSwarm — DigitalOcean Deployment Guide

Deploy TitanSwarm to a **DigitalOcean Droplet** using your $200 free credit.
Estimated cost: ~$24/month → credit covers ~8 months.

---

## Step 1 — Create a Droplet (5 minutes in browser)

1. Go to [cloud.digitalocean.com](https://cloud.digitalocean.com) and sign in.
2. Click **Create → Droplets**.
3. **Region:** Choose closest to you (e.g. San Francisco or Toronto).
4. **Image:** Ubuntu 24.04 (LTS) x64.
5. **Size:** Click "General Purpose" → **4 GB RAM / 2 vCPU** ($24/mo).
   - Do NOT pick the $6/mo 1GB — PyTorch + Playwright will OOM-crash.
6. **Authentication:** Select **SSH Key** → click "Add SSH Key".
   - On your local machine, run:
     ```bash
     cat ~/.ssh/id_rsa.pub
     ```
   - If that file doesn't exist, generate a key first:
     ```bash
     ssh-keygen -t rsa -b 4096
     cat ~/.ssh/id_rsa.pub
     ```
   - Paste the output into the DigitalOcean SSH key field.
7. **Hostname:** `titanswarm`
8. Click **Create Droplet** and wait ~1 minute.
9. Copy the **IPv4 address** shown on the droplet page.

---

## Step 2 — SSH Into the Droplet

On your local machine:

```bash
ssh root@YOUR_DROPLET_IP
```

You are now inside the Droplet.

---

## Step 3 — Install Docker

Run this entire block inside the Droplet:

```bash
apt-get update
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Verify:
```bash
docker --version
docker compose version
```

---

## Step 4 — Copy Your .env to the Droplet

On your **local machine** (new terminal tab):

```bash
scp /home/zen/my_projects/TitanSwarm/.env root@YOUR_DROPLET_IP:~/titanswarm.env
```

---

## Step 5 — Clone and Deploy

Back inside the Droplet:

```bash
git clone https://github.com/YOUR_USERNAME/TitanSwarm.git
cd TitanSwarm

# Place your .env file
cp ~/titanswarm.env .env

# Build the image (first build takes ~10–15 min — downloads ML models)
docker compose build

# Start in the background
docker compose up -d

# Watch logs to confirm startup
docker compose logs -f
```

When you see `You can now view your Streamlit app in your browser`, it is live.

---

## Step 6 — Open TitanSwarm

Navigate to:
```
http://YOUR_DROPLET_IP:8501
```

---

## Step 7 — Open the Firewall (if port 8501 is blocked)

DigitalOcean Droplets allow all inbound traffic by default, so this is usually not needed. But if the browser can't connect, run this on the Droplet:

```bash
ufw allow 8501/tcp
ufw reload
```

---

## Day-to-Day Commands

| Task | Command |
|---|---|
| Check status | `docker compose ps` |
| View all logs | `docker compose logs -f` |
| View scraper logs | `docker compose logs -f daemon` |
| Restart | `docker compose restart` |
| Stop | `docker compose down` |
| **Deploy new code** | `git pull && docker compose build && docker compose up -d` |

---

## Switching to Postgres Later (optional)

1. Edit `.env` on the Droplet:
   ```
   DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/titanswarm
   ```
2. `docker compose restart` — no code changes needed.
