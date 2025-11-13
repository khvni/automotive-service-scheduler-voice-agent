# 🚀 Quick Start Guide - Run Demos in 5 Minutes

This guide will get you running functional demos of the voice agent system in under 5 minutes.

---

## ⚡ Prerequisites Check (1 minute)

Run these commands to verify everything is ready:

```bash
# Check PostgreSQL is running
psql -h localhost -U postgres -c "SELECT version();" 2>/dev/null && echo "✅ PostgreSQL OK" || echo "❌ PostgreSQL not running"

# Check Redis is running
redis-cli ping 2>/dev/null && echo "✅ Redis OK" || echo "❌ Redis not running"

# Check Python version
python3 --version | grep -E "3\.(11|12)" && echo "✅ Python OK" || echo "❌ Python 3.11+ required"
```

### Fix Issues:

**PostgreSQL not running:**
```bash
# macOS
brew services start postgresql@14

# Linux
sudo systemctl start postgresql
```

**Redis not running:**
```bash
# macOS
brew services start redis

# Linux
sudo systemctl start redis
```

**Python version wrong:**
```bash
# Install Python 3.11+
brew install python@3.11  # macOS
```

---

## 📦 Setup (2 minutes)

```bash
# 1. Navigate to project
cd /Users/khani/Desktop/projs/automotive-voice

# 2. Create virtual environment (if not exists)
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# or: venv\Scripts\activate  # Windows

# 3. Install dependencies
cd server
pip install -q -r requirements.txt

# 4. Initialize database
cd ..
python scripts/init_db.py

# 5. Verify setup
python -c "import app; print('✅ Setup complete!')"
```

---

## 🎬 Run Demo 1: Inbound Call (2 minutes)

```bash
cd demos
python demo_1_inbound_call.py
```

**What you'll see:**
1. Customer lookup (with caching)
2. Available slots query
3. Appointment booking
4. Database state verification
5. Full conversation transcript

**Press ENTER when prompted to see each step.**

---

## 🎬 Run Demo 2: Outbound Reminder (2 minutes)

```bash
python demo_2_outbound_reminder.py
```

**What you'll see:**
1. Worker finding tomorrow's appointments
2. Twilio API configuration
3. Two conversation scenarios:
   - Customer confirms
   - Customer reschedules
4. Call logging demonstration

**Press ENTER when prompted.**

---

## ✅ Success Indicators

Both demos should show:
- ✅ Green checkmarks for each operation
- ✅ JSON data outputs
- ✅ Database records created
- ✅ No error messages
- ✅ "DEMO COMPLETE" at the end

---

## ❌ Common Issues

### Issue: "ModuleNotFoundError: No module named 'app'"
**Solution:**
```bash
cd server
pip install -r requirements.txt
cd ..
```

### Issue: "database 'automotive_scheduler' does not exist"
**Solution:**
```bash
python scripts/init_db.py
```

### Issue: "Redis connection refused"
**Solution:**
```bash
# Start Redis
brew services start redis  # macOS
sudo systemctl start redis # Linux

# Verify
redis-cli ping  # should return "PONG"
```

### Issue: "Permission denied"
**Solution:**
```bash
chmod +x demos/*.py
```

---

## 🎯 What Gets Proven

After running both demos, you've proven:

| Component | Status |
|-----------|--------|
| Database integration | ✅ Working |
| Redis caching | ✅ Working |
| CRM tools (7 tools) | ✅ Working |
| Conversation logic | ✅ Simulated |
| Twilio setup | ✅ Configured |
| Worker job | ✅ Working |

---

## 📊 Expected Runtime

- **Demo 1:** ~30 seconds (interactive pauses)
- **Demo 2:** ~40 seconds (interactive pauses)
- **Total:** Under 2 minutes for both

---

## 🎓 Next Level: Live Phone Call

Want to test with a real phone call?

1. Start the server:
   ```bash
   cd server
   uvicorn app.main:app --reload
   ```

2. Expose with ngrok (separate terminal):
   ```bash
   ngrok http 8000
   ```

3. Configure Twilio:
   - Go to https://console.twilio.com/
   - Update phone number webhook
   - Set to: `https://your-ngrok-url.ngrok.io/api/v1/webhooks/inbound-call`

4. Call your Twilio number!

---

## 💡 Tips

- Run demos multiple times - they're idempotent
- Check `demos/README.md` for detailed explanations
- Each demo creates test data automatically
- Database persists between runs (expected behavior)
- Colors help identify different speakers/systems

---

## 📞 Need Help?

If demos fail consistently:
1. Check all prerequisites are running
2. Verify `.env` has correct DATABASE_URL and REDIS_URL
3. Try: `python scripts/init_db.py` to reset database
4. Review error messages - they're designed to help

---

**Ready? Run this:**

```bash
cd demos && python demo_1_inbound_call.py
```

Then:

```bash
python demo_2_outbound_reminder.py
```

**That's it! 🎉**
