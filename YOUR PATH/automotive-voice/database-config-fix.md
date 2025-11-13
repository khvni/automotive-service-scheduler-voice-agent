# Database Configuration Fix

## Problem
The server was trying to connect to a local PostgreSQL database (postgres@localhost:5432) instead of using the Neon cloud database configured in the .env file. This caused "role postgres does not exist" errors.

Additionally, demos running from project root couldn't find the .env file because the config used a static relative path.

## Root Cause
In `server/app/config.py`, the `env_file` path was set to `.env` (relative path), which looked for the .env file in the `server/` directory instead of the project root. Additionally, the `DATABASE_URL` had a hardcoded default pointing to local PostgreSQL.

When demos ran from project root and imported `from server.app.config import settings`, the relative path `../.env` didn't work because the working directory was different.

## Fix Applied
1. Created `find_env_file()` function that checks multiple locations:
   - `server/app/.env`
   - `server/.env`
   - `project-root/.env`
2. Changed the default `DATABASE_URL` from hardcoded local PostgreSQL to empty string with comment "Must be set in .env file"
3. Made config work from any execution context (server/ or project root)

## Files Modified
- `server/app/config.py` - Added robust .env file discovery

## Verification
Tested from both contexts:
- From server/: `python -c "from app.config import settings; print(settings.DATABASE_URL)"`
- From root: `python -c "from server.app.config import settings; print(settings.DATABASE_URL)"`

Both now correctly load the Neon database URL.

## Impact
All local development, server runs, and demo scripts now properly connect to the Neon cloud database instead of trying to use a non-existent local PostgreSQL instance.
