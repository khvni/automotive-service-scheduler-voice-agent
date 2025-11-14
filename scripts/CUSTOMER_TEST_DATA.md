# Test Customer Data for Voice Agent Testing

Use these customer profiles when testing the voice agent's lookup and appointment booking features.

## Test Customer #1: Sarah Johnson
- **Phone**: 408-555-0101 or (408) 555-0101
- **Vehicle**: 2018 Toyota Camry
- **VIN**: 4T1BF1FK5JU123456
- **Email**: sarah.johnson@email.com
- **Customer Since**: 2020

**Test Scenario**:
- Call as Sarah and say "Hi, this is Sarah Johnson"
- Agent should recognize your phone number (if calling from YOUR_TEST_NUMBER, pretend)
- Test appointment booking for oil change
- Try checking existing appointments

## Test Customer #2: Mike Chen
- **Phone**: 408-555-0102
- **Vehicle**: 2020 Honda Civic
- **VIN**: 2HGFC2F59LH123456
- **Email**: mike.chen@email.com
- **Customer Since**: 2021

**Test Scenario**:
- New customer calling about brake service
- Test VIN decoding
- Book appointment for specific date/time
- Test barge-in during booking

## Test Customer #3: Emily Rodriguez
- **Phone**: 408-555-0103
- **Vehicles**:
  - 2019 Ford F-150 (VIN: 1FTFW1ET5KFA12345)
  - 2021 Tesla Model 3 (VIN: 5YJ3E1EA5MF123456)
- **Email**: emily.rodriguez@email.com
- **Customer Since**: 2019
- **Last Service**: 2 months ago

**Test Scenario**:
- Returning customer with multiple vehicles
- Test which vehicle selection
- Check service history lookup
- Try rescheduling existing appointment

## Test Customer #4: David Kim (New Customer)
- **Phone**: YOUR_TEST_NUMBER (use your actual number)
- **Vehicle**: Tell agent what you drive
- **Email**: Your email

**Test Scenario**:
- First-time caller, not in system
- Agent should NOT find you initially
- Provide vehicle info when asked
- Test VIN decoding if you have your VIN
- Complete new customer booking flow

## Testing the Lookup Feature

When testing calls:

1. **Call from any phone and say**:
   - "Hi, my number is 408-555-0101" (agent will lookup)
   - "This is Sarah Johnson calling" (if from same number)

2. **Agent should respond with**:
   - "Welcome back, [Name]!"
   - Reference to your vehicle(s)
   - Last service date (if applicable)

3. **Test appointment booking**:
   - "I need an oil change"
   - "What's available next Tuesday?"
   - "Can we do 2pm on the 15th?"

## Common Phone Number Formats

The system accepts:
- `4085550101` (10 digits)
- `408-555-0101` (with dashes)
- `(408) 555-0101` (with parentheses)
- `+14085550101` (E.164 format)

## Testing Appointment Features

### Get Available Slots
- "What times are available on [date]?"
- "Do you have any openings next week?"
- "When can you fit me in for a brake service?"

### Book Appointment
- "I'd like to schedule an oil change for Tuesday at 2pm"
- "Book me for next Friday morning"
- "Can I come in tomorrow around 10am?"

### Check Appointments
- "Do I have anything scheduled?"
- "When is my next appointment?"
- "What appointments do I have coming up?"

### Cancel/Reschedule
- "I need to cancel my appointment"
- "Can we move my Tuesday appointment to Wednesday?"
- "I need to reschedule"

## Expected Agent Behavior

### For Known Customers
- Greets by name
- References their vehicle
- Shows service history awareness
- Faster booking (already has customer ID)

### For New Customers
- Asks for name and contact info
- Asks about their vehicle
- May offer VIN decoding
- Creates customer record during booking

## Barge-In Testing

Test interrupting Sophie mid-sentence:
1. Let her start talking
2. Start speaking before she finishes (say "Actually..." or "Wait...")
3. She should stop and listen to you
4. Your new input should be processed

**Note**: Needs minimum 3 words to trigger (prevents "uh", "um" false positives)

## Call Termination Testing

Test ending the conversation:
- Say "Goodbye" or "That's all, thanks"
- Say "We're done" or "I'm all set"
- Hang up manually

**Current Issue**: Call may loop with "Welcome!" instead of ending cleanly. This is being fixed.

## Database Notes

If you're running this locally and want to add these customers to your database, you'll need to:
1. Create a seed script or
2. Use the agent to create them naturally through conversations
3. Or manually insert via SQL

These are suggested test profiles - actual database may have different data depending on your setup.
