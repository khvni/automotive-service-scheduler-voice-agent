# Refactorings

## Demo Script Simplification
- **File**: `scripts/run_demo2_with_call.sh`
- **Change**: Removed verbose warning messages and extra output when making real calls
- **Reason**: User wanted to streamline the flow - after pressing Enter, script immediately makes the call without additional messaging about costs, warnings, etc.
- **Impact**: Faster workflow, less clutter in output