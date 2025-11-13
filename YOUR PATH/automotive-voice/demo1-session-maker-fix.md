# Demo 1 Session Maker Fix

## Problem
Demo 1 was failing with: `TypeError: 'NoneType' object is not callable` when trying to use `async_session_maker()`.

## Root Cause
The demo imported `async_session_maker` directly at the top of the file:
```python
from app.services.database import async_session_maker, init_db
```

However, `async_session_maker` is initialized to `None` in `database.py` and only gets set when `init_db()` is called. By importing it directly, the demo captured the `None` value before initialization.

## Fix Applied
Changed the import to import the entire `database` module instead:
```python
from app.services import database
from app.services.database import init_db
```

Then access the session maker via the module after `init_db()` runs:
```python
async with database.async_session_maker() as db:
```

This ensures we're accessing the initialized session maker, not the captured `None` value.

## Files Modified
- `demos/demo_1_inbound_call.py`

## Impact
Demo 1 can now properly initialize and use the database session after calling `init_db()`.
