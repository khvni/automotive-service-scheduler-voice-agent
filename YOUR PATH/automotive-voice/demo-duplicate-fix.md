# Demo Call Log Duplicate Fix

## Problem
Demo 2 was failing with: `duplicate key value violates unique constraint "ix_call_logs_call_sid"` when run multiple times. The demo creates a call log with a hardcoded `call_sid` of "CA_demo_outbound_123", which already existed from a previous run.

## Root Cause
The demo didn't clean up test data before creating new records. When run multiple times, it tried to insert a call log with the same `call_sid`, violating the unique constraint.

## Fix Applied
Added cleanup logic in `verify_call_logging()` function:
1. Check if a call log with the demo call_sid already exists
2. Delete it if found
3. Then create the new demo call log

## Files Modified
- `demos/demo_2_outbound_reminder.py`

## Impact
Demos can now be run multiple times without database constraint errors. The cleanup ensures a fresh state for each demo run.
