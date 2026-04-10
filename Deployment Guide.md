# Docker (Django + + Nginx) + PostgreSQL Deployment Guide

## Overview
This document explains:
- Changes made on **server vs local**
- Secure production deployment on **Ubuntu VPS**
- Running the project locally (with and without SSL)
- Docker, Nginx, PostgreSQL(in host machine) integration
- Common errors and solutions
- Final deployment checklist

---

## Tech Stack
- Django (WSGI / Gunicorn)
- Docker & Docker Compose
- Nginx (Dockerized)
- PostgreSQL (External / Host-based)
- Node.js (Vite + Tailwind)
- Certbot (Let's Encrypt SSL)

---

## Environment Differences

### Local Environment
- `DEBUG=True`
- HTTP (no SSL)
- Database can be SQLite or PostgreSQL
- `CSRF_TRUSTED_ORIGINS` includes localhost

Example:
```env
DEBUG=True
ENV=local
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost,http://127.0.0.1
```

### Production (Server)
- `DEBUG=False`
- HTTPS enabled
- External PostgreSQL
- Strict CSRF and security headers

Example:
```env
DEBUG=False
ENV=prod
ALLOWED_HOSTS=ksundaram.com,www.ksundaram.com
CSRF_TRUSTED_ORIGINS=https://ksundaram.com,https://www.ksundaram.com
```

---

## Server Changes Summary

### Installed Packages
```bash
sudo apt install docker docker-compose certbot ufw
```

### Firewall (UFW)
```bash
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow from 172.18.0.0/16 to any port 5432
sudo ufw enable
```

### PostgreSQL
- Running on host machine (not Docker)
- Listening on `172.17.0.1`
- User and DB created manually

---

## Docker Architecture

```
Internet
   ↓
Docker Nginx (80/443)
   ↓
Django (Gunicorn :8000)
   ↓
PostgreSQL (Host)
```

---

## Docker Compose (Production)

```yaml
services:
  web:
    build: .
    command: >
      sh -c "python manage.py wait_for_db &&
             python manage.py migrate &&
             gunicorn main.wsgi:application --bind 0.0.0.0:8000"
    env_file: .env
    volumes:
      - staticfiles:/app/staticfiles
      - media:/app/media
    expose:
      - "8000"
    extra_hosts:
      - "host.docker.internal:host-gateway"

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx:/etc/nginx
      - staticfiles:/app/staticfiles:ro
      - media:/app/media:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - web

volumes:
  staticfiles:
  media:
```

---

## Nginx Config for server with SSL

```nginx
server {
    listen 80;
    server_name ksundaram.com www.ksundaram.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name ksundaram.com www.ksundaram.com;

    ssl_certificate /etc/letsencrypt/live/ksundaram.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ksundaram.com/privkey.pem;

    location / {
        proxy_pass http://web:8000;
    }
}
```

---

## SSL Setup

```bash
sudo certbot certonly --standalone -d ksundaram.com -d www.ksundaram.com
```

Certificates mounted into Docker.

---

## CSRF Fix (Important)

Add to `.env`:
```env
CSRF_TRUSTED_ORIGINS=https://ksundaram.com,https://www.ksundaram.com,http://localhost
```

Restart containers after change.

---

## Local Development with Docker (No SSL)

```bash
docker compose up --build
```
Access:
```
http://localhost
```

Use separate `docker-compose.local.yml` if needed.

---

## Common Errors & Fixes

### 502 Bad Gateway
- Gunicorn not running
- DB connection failed

### CSRF 403
- Missing `CSRF_TRUSTED_ORIGINS`
- HTTPS mismatch

### PostgreSQL Connection Timeout
- `listen_addresses` not updated
- Firewall blocking 5432

---

## Final Deployment Checklist

- [ ] DEBUG=False
- [ ] HTTPS enabled
- [ ] CSRF trusted origins set
- [ ] Static files served by Nginx
- [ ] PostgreSQL reachable from Docker
- [ ] UFW configured
- [ ] Containers restart policy enabled

---

## Recommended Improvements
- Use Dockerized PostgreSQL
- Add healthchecks
- Enable HTTP/2
- Enable HSTS
- Add CI/CD pipeline

---

## Author Notes
This document reflects a **real-world production deployment** and is safe for team sharing.
