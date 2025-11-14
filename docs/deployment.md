# Deployment Guide - Otto's Auto Voice Agent

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Setup](#database-setup)
4. [Redis Setup](#redis-setup)
5. [Application Deployment](#application-deployment)
6. [Worker Deployment](#worker-deployment)
7. [Monitoring & Logging](#monitoring--logging)
8. [Production Checklist](#production-checklist)
9. [Scaling Guide](#scaling-guide)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- **Python:** 3.11 or higher
- **Database:** PostgreSQL 14+ (Neon Serverless recommended)
- **Cache:** Redis 6.0+
- **OS:** Linux (Ubuntu 22.04 LTS recommended) or macOS for development
- **Memory:** Minimum 2GB RAM per server instance
- **CPU:** Minimum 2 cores recommended

### Third-Party Services
- **Twilio:** Account with phone number and Media Streams enabled
- **Deepgram:** API key with STT and TTS access
- **OpenAI:** API key with GPT-4o access
- **Google Cloud:** OAuth2 credentials for Calendar API
- **Neon:** PostgreSQL database (or self-hosted Postgres)
- **Redis:** Cloud Redis instance (Upstash, Redis Cloud) or self-hosted

### Domain & DNS
- Domain name for your application
- SSL/TLS certificate (Let's Encrypt recommended)
- DNS records configured for webhooks

---

## Environment Setup

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd automotive-voice
```

### 2. Create Virtual Environment
```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
# Server dependencies
cd server
pip install -r requirements.txt

# Worker dependencies
cd ../worker
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create `.env` file in project root:

```bash
# === Application ===
ENV=production
BASE_URL=https://yourdomain.com
DEBUG=false

# === Database ===
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/automotive_voice  # pragma: allowlist secret
# For Neon: postgresql+asyncpg://user:password@host.neon.tech/automotive_voice?sslmode=require  # pragma: allowlist secret

# === Redis ===
REDIS_URL=redis://default:password@host:6379  # pragma: allowlist secret
# For Upstash: rediss://default:password@host.upstash.io:6379  # pragma: allowlist secret

# === Twilio ===
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  # pragma: allowlist secret
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+15555551234

# POC Safety (REMOVE IN PRODUCTION):
# YOUR_TEST_NUMBER=+15555559999  # Uncomment for POC mode

# === Deepgram ===
DEEPGRAM_API_KEY=your_deepgram_api_key

# === OpenAI ===
OPENAI_API_KEY=sk-proj-...

# === Google Calendar ===
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REFRESH_TOKEN=your_refresh_token

# === Worker ===
WORKER_REMINDER_HOUR=18  # 6 PM local time
WORKER_REMINDER_TIMEZONE=America/Chicago
```

### 5. Secure Environment File
```bash
chmod 600 .env
# Never commit .env to version control
echo ".env" >> .gitignore
```

---

## Database Setup

### Option A: Neon Serverless (Recommended for Production)

1. **Create Neon Project:**
   - Visit https://neon.tech
   - Create new project
   - Copy connection string

2. **Configure Connection:**
   ```bash
   # In .env
   DATABASE_URL=postgresql+asyncpg://user:password@host.neon.tech/automotive_voice?sslmode=require  # pragma: allowlist secret
   ```

3. **Run Migrations:**
   ```bash
   cd server
   alembic upgrade head
   ```

4. **Seed Database (Optional):**
   ```bash
   python scripts/seed_database.py
   ```

### Option B: Self-Hosted PostgreSQL

1. **Install PostgreSQL:**
   ```bash
   # Ubuntu
   sudo apt update
   sudo apt install postgresql postgresql-contrib

   # macOS
   brew install postgresql@14
   brew services start postgresql@14
   ```

2. **Create Database:**
   ```bash
   sudo -u postgres psql
   CREATE DATABASE automotive_voice;
   CREATE USER automotive_user WITH PASSWORD 'secure_password';  # pragma: allowlist secret
   GRANT ALL PRIVILEGES ON DATABASE automotive_voice TO automotive_user;
   \q
   ```

3. **Configure Connection:**
   ```bash
   # In .env
   DATABASE_URL=postgresql+asyncpg://automotive_user:secure_password@localhost:5432/automotive_voice  # pragma: allowlist secret
   ```

4. **Run Migrations:**
   ```bash
   cd server
   alembic upgrade head
   ```

### Database Performance Tuning

For production, optimize PostgreSQL settings:

```sql
-- Recommended settings for automotive_voice database
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = '0.9';
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = '100';
ALTER SYSTEM SET random_page_cost = '1.1';  -- For SSD storage
ALTER SYSTEM SET effective_io_concurrency = '200';

-- Restart PostgreSQL to apply
SELECT pg_reload_conf();
```

---

## Redis Setup

### Option A: Cloud Redis (Recommended)

**Upstash Redis:**
1. Visit https://upstash.com
2. Create Redis database
3. Copy connection string with TLS

```bash
# In .env
REDIS_URL=rediss://default:password@host.upstash.io:6379  # pragma: allowlist secret
```

**Redis Cloud:**
1. Visit https://redis.com/try-free
2. Create database
3. Copy connection details

```bash
# In .env
REDIS_URL=redis://default:password@host.cloud.redislabs.com:port
```

### Option B: Self-Hosted Redis

1. **Install Redis:**
   ```bash
   # Ubuntu
   sudo apt install redis-server
   sudo systemctl enable redis-server
   sudo systemctl start redis-server

   # macOS
   brew install redis
   brew services start redis
   ```

2. **Configure Redis:**
   ```bash
   # Edit /etc/redis/redis.conf
   maxmemory 512mb
   maxmemory-policy allkeys-lru
   requirepass your_secure_password
   ```

3. **Restart Redis:**
   ```bash
   sudo systemctl restart redis-server
   ```

4. **Configure Connection:**
   ```bash
   # In .env
   REDIS_URL=redis://:your_secure_password@localhost:6379
   ```

### Redis Performance Tuning

```bash
# Optimize for session management
redis-cli CONFIG SET maxmemory-policy allkeys-lru
redis-cli CONFIG SET maxmemory 512mb
redis-cli CONFIG SET tcp-backlog 511
```

---

## Application Deployment

### Option A: Railway (Simplest)

1. **Install Railway CLI:**
   ```bash
   npm install -g @railway/cli
   railway login
   ```

2. **Create Project:**
   ```bash
   railway init
   ```

3. **Add Environment Variables:**
   ```bash
   railway variables set DATABASE_URL="postgresql+asyncpg://..."
   railway variables set REDIS_URL="redis://..."
   # ... add all variables from .env
   ```

4. **Deploy:**
   ```bash
   railway up
   ```

### Option B: Docker + VPS

1. **Create Dockerfile:**
   ```dockerfile
   # Already created in server/Dockerfile
   ```

2. **Build Image:**
   ```bash
   cd server
   docker build -t automotive-voice-server .
   ```

3. **Run Container:**
   ```bash
   docker run -d \
     --name automotive-voice-server \
     --env-file ../.env \
     -p 8000:8000 \
     automotive-voice-server
   ```

### Option C: Systemd Service (Linux VPS)

1. **Create Service File:**
   ```bash
   sudo nano /etc/systemd/system/automotive-voice.service
   ```

2. **Service Configuration:**
   ```ini
   [Unit]
   Description=Otto's Auto Voice Agent
   After=network.target postgresql.service redis.service

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/var/www/automotive-voice/server
   Environment="PATH=/var/www/automotive-voice/venv/bin"
   EnvironmentFile=/var/www/automotive-voice/.env
   ExecStart=/var/www/automotive-voice/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

3. **Enable and Start:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable automotive-voice
   sudo systemctl start automotive-voice
   sudo systemctl status automotive-voice
   ```

### Nginx Reverse Proxy

1. **Install Nginx:**
   ```bash
   sudo apt install nginx
   ```

2. **Configure Site:**
   ```bash
   sudo nano /etc/nginx/sites-available/automotive-voice
   ```

3. **Nginx Configuration:**
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;
       return 301 https://$server_name$request_uri;
   }

   server {
       listen 443 ssl http2;
       server_name yourdomain.com;

       ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       location /api/v1/voice/media-stream {
           proxy_pass http://127.0.0.1:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_read_timeout 3600s;
       }
   }
   ```

4. **Enable Site:**
   ```bash
   sudo ln -s /etc/nginx/sites-available/automotive-voice /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

5. **Get SSL Certificate:**
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com
   ```

---

## Worker Deployment

### Docker Deployment (Recommended)

1. **Build Worker Image:**
   ```bash
   cd worker
   docker build -t automotive-voice-worker .
   ```

2. **Run Worker:**
   ```bash
   docker run -d \
     --name automotive-voice-worker \
     --env-file ../.env \
     automotive-voice-worker
   ```

### Systemd Service

1. **Create Service File:**
   ```bash
   sudo nano /etc/systemd/system/automotive-worker.service
   ```

2. **Service Configuration:**
   ```ini
   [Unit]
   Description=Automotive Voice Worker
   After=network.target postgresql.service redis.service

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/var/www/automotive-voice/worker
   Environment="PATH=/var/www/automotive-voice/venv/bin"
   EnvironmentFile=/var/www/automotive-voice/.env
   ExecStart=/var/www/automotive-voice/venv/bin/python main.py
   Restart=always
   RestartSec=30

   [Install]
   WantedBy=multi-user.target
   ```

3. **Enable and Start:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable automotive-worker
   sudo systemctl start automotive-worker
   sudo systemctl status automotive-worker
   ```

---

## Monitoring & Logging

### Application Logging

Configure structured logging in `server/app/core/config.py`:

```python
import logging
from pythonjsonlogger import jsonlogger

logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)
```

### Health Check Endpoint

Already implemented at `/health`:

```bash
curl https://yourdomain.com/health
# {"status": "healthy", "database": "connected", "redis": "connected"}
```

### Uptime Monitoring

**Option 1: UptimeRobot**
- Free monitoring service
- Configure HTTP monitor for https://yourdomain.com/health
- 5-minute intervals

**Option 2: Pingdom**
- Enterprise monitoring
- Real user monitoring
- Performance insights

### Application Monitoring

**Option 1: Sentry (Error Tracking)**

```bash
pip install sentry-sdk[fastapi]
```

```python
# In server/app/main.py
import sentry_sdk

sentry_sdk.init(
    dsn="your_sentry_dsn",
    traces_sample_rate=1.0,
    environment="production"
)
```

**Option 2: New Relic (APM)**

```bash
pip install newrelic
newrelic-admin generate-config YOUR_LICENSE_KEY newrelic.ini
NEW_RELIC_CONFIG_FILE=newrelic.ini newrelic-admin run-program uvicorn app.main:app
```

### Log Aggregation

**Option: Better Stack (Logtail)**

```bash
# Install logging integration
pip install logtail-python
```

```python
from logtail import LogtailHandler

handler = LogtailHandler(source_token='your_token')
logger.addHandler(handler)
```

### Metrics Dashboard

Create custom dashboard with key metrics:
- Active calls per minute
- Average call duration
- Customer lookup latency
- Appointment booking success rate
- Error rate
- API latency (STT, LLM, TTS)

---

## Production Checklist

### Pre-Launch
- [ ] All environment variables configured
- [ ] Database migrations applied
- [ ] Redis connection tested
- [ ] SSL certificate installed
- [ ] Domain DNS configured
- [ ] Twilio webhook URLs updated
- [ ] Test call completed successfully
- [ ] Error monitoring configured
- [ ] Backup strategy implemented
- [ ] Load testing completed
- [ ] Security audit completed

### Security
- [ ] `.env` file secured (chmod 600)
- [ ] Database credentials rotated
- [ ] Redis password configured
- [ ] API keys secured
- [ ] Rate limiting enabled
- [ ] CORS properly configured
- [ ] Input validation tested
- [ ] SQL injection tests passed
- [ ] XSS prevention verified

### Performance
- [ ] Database indexes created
- [ ] Redis caching enabled
- [ ] Connection pooling configured
- [ ] Worker processes optimized
- [ ] CDN configured (if applicable)
- [ ] Compression enabled
- [ ] Response times validated

### Monitoring
- [ ] Health check endpoint verified
- [ ] Error tracking configured
- [ ] Log aggregation set up
- [ ] Uptime monitoring active
- [ ] Alerts configured
- [ ] Metrics dashboard created

### Backup & Recovery
- [ ] Database backups scheduled
- [ ] Backup restoration tested
- [ ] Disaster recovery plan documented
- [ ] Failover strategy defined

### POC to Production Transition
- [ ] Remove `YOUR_TEST_NUMBER` restriction
- [ ] Update to production API keys
- [ ] Configure auto-scaling (if cloud)
- [ ] Enable production logging level
- [ ] Remove debug flags
- [ ] Update CORS origins
- [ ] Configure CDN
- [ ] Enable DDoS protection

---

## Scaling Guide

### Horizontal Scaling (Multiple Servers)

1. **Load Balancer Configuration:**
   ```nginx
   upstream automotive_voice {
       least_conn;
       server server1.internal:8000;
       server server2.internal:8000;
       server server3.internal:8000;
   }

   server {
       listen 443 ssl http2;
       server_name yourdomain.com;

       location / {
           proxy_pass http://automotive_voice;
       }
   }
   ```

2. **Sticky Sessions (for WebSocket):**
   ```nginx
   upstream automotive_voice {
       ip_hash;  # Route same IP to same server
       server server1.internal:8000;
       server server2.internal:8000;
   }
   ```

### Vertical Scaling (Larger Servers)

**Uvicorn Workers:**
```bash
# In systemd service or docker
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 8
# Rule of thumb: workers = (2 x CPU cores) + 1
```

**Database Connection Pool:**
```python
# In server/app/core/database.py
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,  # Increase for more workers
    max_overflow=40,
    pool_pre_ping=True
)
```

### Redis Scaling

**Redis Cluster (for > 100 concurrent calls):**
```bash
# Configure Redis Cluster
redis-cli --cluster create \
    node1:6379 node2:6379 node3:6379 \
    --cluster-replicas 1
```

### Database Scaling

**Read Replicas:**
```python
# Configure read/write split
WRITE_DATABASE_URL = "postgresql+asyncpg://..."
READ_DATABASE_URL = "postgresql+asyncpg://replica..."

write_engine = create_async_engine(WRITE_DATABASE_URL)
read_engine = create_async_engine(READ_DATABASE_URL)
```

**Connection Pooling:**
```python
# PgBouncer for connection pooling
DATABASE_URL = "postgresql+asyncpg://user:pass@pgbouncer:6432/db"  # pragma: allowlist secret
```

### Auto-Scaling (Cloud Platforms)

**Railway:**
```bash
# Configure in railway.json
{
  "autoscaling": {
    "minReplicas": 2,
    "maxReplicas": 10,
    "targetCPUUtilization": 70
  }
}
```

**AWS ECS:**
```bash
# Configure task auto-scaling
aws application-autoscaling register-scalable-target \
    --service-namespace ecs \
    --scalable-dimension ecs:service:DesiredCount \
    --min-capacity 2 \
    --max-capacity 10
```

---

## Troubleshooting

### Common Issues

**1. WebSocket Connection Fails**
```bash
# Check Nginx WebSocket configuration
# Ensure proxy_http_version 1.1 and Upgrade headers set

# Test WebSocket directly
wscat -c wss://yourdomain.com/api/v1/voice/media-stream
```

**2. Database Connection Pool Exhausted**
```bash
# Check active connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'automotive_voice';

# Increase pool size in database.py
pool_size=30
max_overflow=60
```

**3. Redis Connection Timeouts**
```bash
# Test Redis connection
redis-cli -h host -p 6379 -a password PING

# Check timeout settings
timeout 300
tcp-keepalive 60
```

**4. High Latency**
```bash
# Check database query performance
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

# Check Redis latency
redis-cli --latency -h host -p 6379
```

**5. Worker Not Running Jobs**
```bash
# Check worker logs
sudo journalctl -u automotive-worker -f

# Verify timezone configuration
python -c "from datetime import datetime; import pytz; print(datetime.now(pytz.timezone('America/Chicago')))"
```

### Debug Mode

Enable debug logging:
```bash
# In .env
DEBUG=true
LOG_LEVEL=DEBUG

# Restart service
sudo systemctl restart automotive-voice
```

### Health Checks

```bash
# Application health
curl https://yourdomain.com/health

# Database health
psql $DATABASE_URL -c "SELECT 1"

# Redis health
redis-cli -u $REDIS_URL PING
```

### Performance Profiling

```python
# Add to server/app/main.py for temporary profiling
from fastapi import Request
import time

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

---

## Support & Maintenance

### Regular Maintenance Tasks

**Daily:**
- Monitor error rates
- Check system health
- Review critical logs

**Weekly:**
- Review performance metrics
- Check disk space
- Update dependencies (security patches)
- Database vacuum (if self-hosted)

**Monthly:**
- Security audit
- Performance optimization review
- Cost analysis
- Backup restoration test

### Contact

For production support:
- Documentation: [Link to your docs]
- Support Email: support@yourdomain.com
- On-call: [Your on-call system]

---

## Additional Resources

- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Redis Best Practices](https://redis.io/docs/management/optimization/)
- [Twilio Media Streams](https://www.twilio.com/docs/voice/twiml/stream)
- [Deepgram API Docs](https://developers.deepgram.com/)
- [OpenAI API Best Practices](https://platform.openai.com/docs/guides/production-best-practices)
