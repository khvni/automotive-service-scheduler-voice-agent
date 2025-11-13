# Demo Setup Documentation

## Summary
Created executable runner scripts for both Demo 1 (inbound call) and Demo 2 (outbound reminder) to make testing the POC functionality easy and reliable. Both demos are now fully functional!

## Changes Made

### 1. Created `scripts/run_demo1.sh`
- Executable script for running the inbound call demonstration
- Checks all prerequisites:
  - PostgreSQL running (using `pg_isready`)
  - Redis running (using `redis-cli ping`)
  - .env file exists
  - Virtual environment exists
- Auto-detects virtual environment (venv, .venv, venv-py311, venv-new)
- Color-coded output for better visibility
- Usage: `./scripts/run_demo1.sh`

### 2. Created `scripts/run_demo2.sh`
- Executable script for running the outbound reminder demonstration
- Same prerequisite checks as Demo 1
- Supports optional `--make-call` flag to make actual phone calls
- When `--make-call` is used:
  - Warns user about real phone call
  - Makes actual Twilio API call to YOUR_TEST_NUMBER
  - Costs ~$0.01-0.02 per minute
- Usage: 
  - `./scripts/run_demo2.sh` (simulation only)
  - `./scripts/run_demo2.sh --make-call` (real call)

### 3. Fixed Database Configuration
- **Issue**: asyncpg doesn't accept `sslmode` parameter
- **Fix**: Changed from `?ssl=true` to `?ssl=require` in DATABASE_URL
- This was causing errors when connecting to Neon database

### 4. Fixed Critical Timezone Issues
- **Root Cause**: Database `scheduled_at` column is `TIMESTAMP WITHOUT TIME ZONE` but code was trying to use timezone-aware datetimes
- **Fixes Applied**:
  - `demo_2_outbound_reminder.py`: All datetime operations now strip timezone info before DB queries
  - `server/app/tools/crm_tools.py`: 
    - `book_appointment()`: Now removes timezone instead of adding it
    - `reschedule_appointment()`: Now removes timezone instead of adding it
  - These changes ensure compatibility with naive datetime storage in PostgreSQL

### 5. Fixed Demo 2 Import Issue
- **Issue**: `async_session_maker` was None after init_db() due to Python import mechanics
- **Fix**: Changed to import the database module itself: `from app.services import database`
- Then use `database.async_session_maker()` to get the initialized session maker

### 6. Fixed CallLog Model Usage
- **Issue**: Demo 2 was using non-existent `call_type` field
- **Fix**: Changed to use `intent` field (which exists in the model)
- Also fixed datetime fields to be naive for CallLog timestamps

### 7. Installed Dependencies
- Installed Redis locally: `brew install redis && brew services start redis`
- Started PostgreSQL: `brew services start postgresql@14`
- Installed missing Python packages:
  - google-auth
  - google-auth-oauthlib
  - google-auth-httplib2
  - google-api-python-client
  - redis (Python package)
  - All requirements from server/requirements.txt

## Demo Status
- ✅ Demo 1 script created and tested - **FULLY WORKING**
- ✅ Demo 2 script created and tested - **FULLY WORKING**
- ✅ All prerequisites installed and running
- ✅ Database connection working with Neon
- ✅ All timezone issues resolved
- ✅ CRM tools updated to work correctly with database

## How to Run Demos

### Demo 1: Inbound Call
```bash
./scripts/run_demo1.sh
```
This demonstrates:
- Customer lookup by phone
- Intent detection
- Available slots query
- Appointment booking
- Database persistence

### Demo 2: Outbound Reminder
```bash
# Simulation mode (no actual call)
./scripts/run_demo2.sh

# Real call mode (requires server running and ngrok)
./scripts/run_demo2.sh --make-call
```
This demonstrates:
- Worker job finding appointments
- Twilio API integration
- Outbound call flow (2 scenarios: confirm & reschedule)
- Appointment rescheduling via tool
- Call logging

## Prerequisites
Both scripts automatically check for:
1. PostgreSQL running on localhost:5432
2. Redis running on localhost:6379
3. .env file exists in project root
4. Virtual environment with dependencies installed

## Important Learnings

### Database Timezone Handling
The application uses `TIMESTAMP WITHOUT TIME ZONE` for appointment times in PostgreSQL. This means:
1. All datetime values sent to the database must be **timezone-naive**
2. When creating datetime objects with timezone info, strip it before DB operations
3. Pattern: `datetime.now(timezone.utc).replace(tzinfo=None)`

### Why Not Use Timezone-Aware?
- Simpler for appointment scheduling (no DST confusion)
- All times are implicit UTC
- No need for timezone conversions in queries
- Aligns with how business operates (UTC timestamps)

## Bug Fixes Summary
1. ✅ Database SSL parameter (`ssl=require` for asyncpg)
2. ✅ Timezone handling in demo_2_outbound_reminder.py (3 locations)
3. ✅ Timezone handling in book_appointment CRM tool
4. ✅ Timezone handling in reschedule_appointment CRM tool
5. ✅ Database session maker import issue
6. ✅ CallLog field name (intent vs call_type)

## Next Steps
- ✅ Both demos are ready for POC presentations
- Consider: Update database schema to use timezone-aware columns OR
- Alternative: Document that all times are UTC and keep naive datetimes
