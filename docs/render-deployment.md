# Render Deployment Guide

Complete guide for deploying the automotive voice agent to Render.

## Why Render?

Render is the recommended platform for this application because:
- Native support for web + worker services in one project
- Managed PostgreSQL and Redis included
- Excellent WebSocket support (critical for voice streaming)
- Simple environment variable management
- Free tier for testing (with limitations)
- Easy scaling to paid tiers

**Not recommended:** Vercel (no WebSocket support on hobby tier, 10s serverless timeout, no background workers)

## Prerequisites

1. [Render account](https://render.com) (free signup)
2. GitHub repository pushed with your code
3. All API keys ready (Twilio, Deepgram, OpenAI, Google Calendar)

## Deployment Steps

### 1. Create Render Account

1. Go to [render.com](https://render.com)
2. Sign up with GitHub
3. Authorize Render to access your repositories

### 2. Create PostgreSQL Database

1. In Render Dashboard, click **New +** → **PostgreSQL**
2. Configure:
   - **Name:** `automotive-voice-db`
   - **Database:** `automotive_voice`
   - **User:** `automotive_voice_user`
   - **Region:** Oregon (or closest to you)
   - **Plan:** Starter ($7/month) or Free (expires in 90 days)
3. Click **Create Database**
4. Wait for provisioning (2-3 minutes)
5. Copy the **Internal Database URL** (starts with `postgresql://`)

### 3. Create Redis Instance

1. Click **New +** → **Redis**
2. Configure:
   - **Name:** `automotive-voice-redis`
   - **Region:** Oregon (same as database)
   - **Plan:** Starter ($10/month) or Free (25MB, no persistence)
3. Click **Create Redis**
4. Wait for provisioning
5. Copy the **Internal Redis URL** (starts with `redis://`)

### 4. Deploy Web Service

1. Click **New +** → **Web Service**
2. Connect your GitHub repository
3. Configure:
   - **Name:** `automotive-voice-server`
   - **Region:** Oregon
   - **Branch:** `main`
   - **Root Directory:** Leave blank
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r server/requirements.txt`
   - **Start Command:** `cd server && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Starter ($7/month) or Free (spins down after 15 min inactivity)

4. **Set Environment Variables** (click "Advanced"):

   ```bash
   # Application
   APP_ENV=production
   DEBUG=false
   PYTHON_VERSION=3.11.0

   # Base URL (will be: https://automotive-voice-server.onrender.com)
   BASE_URL=https://automotive-voice-server.onrender.com

   # CORS Origins
   CORS_ORIGINS=["https://automotive-voice-server.onrender.com"]

   # Database (paste Internal Database URL from step 2)
   DATABASE_URL=postgresql://automotive_voice_user:xxx@xxx.oregon-postgres.render.com/automotive_voice

   # Redis (paste Internal Redis URL from step 3)
   REDIS_URL=redis://red-xxx:6379

   # Twilio
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_PHONE_NUMBER=+15551234567

   # Deepgram
   DEEPGRAM_API_KEY=your_deepgram_api_key

   # OpenAI
   OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxx

   # Google Calendar
   GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your_client_secret
   GOOGLE_REFRESH_TOKEN=your_refresh_token

   # Business Config
   SERVICE_CENTER_NAME=Otto's Auto
   SERVICE_CENTER_HOURS=Monday-Friday 8AM-6PM, Saturday 9AM-4PM
   CALENDAR_TIMEZONE=America/New_York
   DEFAULT_APPOINTMENT_DURATION=60
   REDIS_SESSION_TTL=3600
   ```

5. Click **Create Web Service**
6. Wait for deployment (3-5 minutes)

### 5. Deploy Worker Service

1. Click **New +** → **Background Worker**
2. Connect same GitHub repository
3. Configure:
   - **Name:** `automotive-voice-worker`
   - **Region:** Oregon (same as web service)
   - **Branch:** `main`
   - **Root Directory:** Leave blank
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r worker/requirements.txt`
   - **Start Command:** `cd worker && python main.py`
   - **Plan:** Starter ($7/month) or Free

4. **Set Environment Variables** (same as web service, plus):

   ```bash
   # Copy all variables from web service
   # Plus these worker-specific ones:

   # Worker Configuration
   REMINDER_CRON_SCHEDULE=0 9 * * *
   WORKER_REMINDER_TIMEZONE=America/Chicago
   SERVER_API_URL=https://automotive-voice-server.onrender.com/api/v1

   # For testing only - remove in production!
   YOUR_TEST_NUMBER=+15555555555
   ```

5. Click **Create Background Worker**

### 6. Run Database Migrations

1. In web service dashboard, go to **Shell** tab
2. Run migrations:
   ```bash
   cd server
   alembic upgrade head
   ```

3. Generate mock data (optional):
   ```bash
   cd ..
   python scripts/generate_mock_crm_data.py
   ```

### 7. Configure Twilio Webhook

1. Go to [Twilio Console](https://console.twilio.com/)
2. Navigate to **Phone Numbers** → **Manage** → **Active numbers**
3. Click your phone number
4. Under **Voice Configuration**, set **A CALL COMES IN**:
   ```
   https://automotive-voice-server.onrender.com/api/v1/webhooks/incoming-call
   ```
5. Method: **HTTP POST**
6. Click **Save**

### 8. Test Deployment

**Health Check:**
```bash
curl https://automotive-voice-server.onrender.com/health
# Expected: {"status":"healthy","database":"connected","redis":"connected"}
```

**Inbound Call:**
- Call your Twilio number
- AI should answer and respond

**Check Logs:**
- In Render Dashboard → Web Service → **Logs** tab
- Monitor real-time application logs

## Important Configuration Notes

### BASE_URL
Must match your Render web service URL exactly (no trailing slash):
```bash
BASE_URL=https://automotive-voice-server.onrender.com
```

### DATABASE_URL
Use the **Internal Database URL** (not External) for faster connections:
```bash
# Internal (faster)
DATABASE_URL=postgresql://user:pass@dpg-xxx-a.oregon-postgres.render.com/dbname

# Not External
```

### REDIS_URL
Use the **Internal Redis URL**:
```bash
REDIS_URL=redis://red-xxx:6379
```

### Free Tier Limitations

**Web Service (Free):**
- Spins down after 15 minutes of inactivity
- Cold start takes 30-60 seconds
- 750 hours/month free

**PostgreSQL (Free):**
- Expires after 90 days
- 1GB storage
- Good for testing only

**Redis (Free):**
- 25MB memory
- No persistence
- Good for testing only

**Recommendation:** Use free tier for testing, upgrade to Starter ($7/month web + $7/month db + $10/month redis = $24/month) for production.

## Upgrading to Production

1. **Upgrade Plans:**
   - Web Service: Starter ($7/month)
   - PostgreSQL: Starter ($7/month)
   - Redis: Starter ($10/month)
   - Worker: Starter ($7/month)
   - **Total: ~$31/month**

2. **Remove Test Restrictions:**
   - Delete `YOUR_TEST_NUMBER` environment variable from worker

3. **Enable Auto-Deploy:**
   - Render → Service Settings → Auto-Deploy: **Yes**
   - Deploys automatically on git push to main

4. **Setup Monitoring:**
   - Render provides basic metrics
   - Consider adding Sentry for error tracking
   - Setup UptimeRobot for uptime monitoring

## Environment Variables Reference

Full list of required environment variables:

```bash
# Core
APP_ENV=production
DEBUG=false
BASE_URL=https://automotive-voice-server.onrender.com
CORS_ORIGINS=["https://automotive-voice-server.onrender.com"]

# Database & Cache
DATABASE_URL=[Internal Database URL from Render]
REDIS_URL=[Internal Redis URL from Render]
REDIS_SESSION_TTL=3600

# Twilio
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
TWILIO_PHONE_NUMBER=+15551234567

# Voice & AI
DEEPGRAM_API_KEY=xxxxx
OPENAI_API_KEY=sk-proj-xxxxx
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.8
OPENAI_MAX_TOKENS=1000

# Google Calendar
GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxxxx
GOOGLE_REFRESH_TOKEN=xxxxx
CALENDAR_TIMEZONE=America/New_York

# Worker (for background worker service only)
REMINDER_CRON_SCHEDULE=0 9 * * *
WORKER_REMINDER_TIMEZONE=America/Chicago
SERVER_API_URL=https://automotive-voice-server.onrender.com/api/v1

# Business
SERVICE_CENTER_NAME=Otto's Auto
SERVICE_CENTER_HOURS=Monday-Friday 8AM-6PM, Saturday 9AM-4PM
DEFAULT_APPOINTMENT_DURATION=60
```

## Troubleshooting

### Service Won't Start
- Check logs in Render Dashboard
- Verify all environment variables are set
- Ensure DATABASE_URL and REDIS_URL are correct

### Database Connection Failed
- Use Internal Database URL (not External)
- Check database is running in Render Dashboard
- Verify database name matches

### WebSocket Connection Failed
- Verify BASE_URL matches Render web service URL
- Check Twilio webhook is configured correctly
- Ensure no trailing slash in BASE_URL

### Worker Not Running
- Check worker logs in Render Dashboard
- Verify SERVER_API_URL points to web service
- Ensure cron schedule syntax is correct

### Cold Starts (Free Tier)
- Web service spins down after 15 min inactivity
- First request after spin-down takes 30-60s
- Upgrade to Starter plan to eliminate cold starts

## Scaling

When you're ready to scale:

1. **Upgrade Instance Types:**
   - Web: Starter → Standard ($25/month for 2GB RAM)
   - Worker: Starter → Standard

2. **Add More Workers:**
   - Clone worker service
   - Adjust cron schedules to distribute load

3. **Upgrade Database:**
   - Increase connection limits
   - Add read replicas for scaling

4. **Add Redis Persistence:**
   - Upgrade to paid Redis plan
   - Enable persistence for session recovery

## Next Steps

- Review [docs/production-checklist.md](production-checklist.md) before going live
- Setup monitoring and alerting
- Test outbound calls thoroughly
- Remove YOUR_TEST_NUMBER restriction
- Configure custom domain (optional)
