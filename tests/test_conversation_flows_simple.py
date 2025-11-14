"""
Simple test script for conversation flow state machine (without external dependencies).
"""

import sys
import os
from pathlib import Path

# Add server directory to path
server_dir = Path(__file__).parent.parent / "server"
sys.path.insert(0, str(server_dir))

# Import only the conversation manager (no external deps)
from app.services.conversation_manager import (
    ConversationManager,
    CallType,
    ConversationState,
    Intent,
)


def test_intent_detection():
    """Test intent detection from user messages"""
    print("\n" + "="*80)
    print("TEST: Intent Detection")
    print("="*80)

    manager = ConversationManager(
        call_type=CallType.INBOUND_NEW,
        caller_phone="+15551234567"
    )

    # Test cases: (message, expected_intent)
    test_cases = [
        ("I need to schedule an oil change", Intent.SCHEDULE_APPOINTMENT),
        ("I'd like to book an appointment", Intent.SCHEDULE_APPOINTMENT),
        ("I need to reschedule my appointment", Intent.RESCHEDULE_APPOINTMENT),
        ("Can I cancel my appointment?", Intent.CANCEL_APPOINTMENT),
        ("What are your hours?", Intent.CHECK_HOURS),
        ("How much does an oil change cost?", Intent.CHECK_PRICING),
        ("Do you offer brake service?", Intent.CHECK_SERVICES),
        ("I have a complaint about my last service", Intent.COMPLAINT),
    ]

    passed = 0
    failed = 0

    for message, expected_intent in test_cases:
        detected_intent = manager._detect_intent(message)
        if detected_intent == expected_intent:
            print(f"✓ '{message}' → {detected_intent.value}")
            passed += 1
        else:
            print(f"✗ '{message}' → Expected: {expected_intent.value}, Got: {detected_intent.value}")
            failed += 1

    print(f"\nPassed: {passed}/{len(test_cases)}")
    return failed == 0


def test_escalation_detection():
    """Test escalation trigger detection"""
    print("\n" + "="*80)
    print("TEST: Escalation Detection")
    print("="*80)

    manager = ConversationManager(
        call_type=CallType.INBOUND_NEW,
        caller_phone="+15551234567"
    )

    # Phrases that should trigger escalation
    escalation_phrases = [
        "I want to speak to a manager",
        "Let me talk to your supervisor",
        "This is ridiculous!",
        "I'm going to sue you",
        "I want to file a complaint",
        "Transfer me to a human",
    ]

    # Phrases that should NOT trigger escalation
    normal_phrases = [
        "I need an oil change",
        "What time do you close?",
        "How much does service cost?",
    ]

    passed = 0
    failed = 0

    print("\nShould trigger escalation:")
    for phrase in escalation_phrases:
        if manager.should_escalate(phrase):
            print(f"✓ Escalation detected: '{phrase}' (Reason: {manager.escalation_reason})")
            passed += 1
            # Reset for next test
            manager.escalation_triggered = False
            manager.escalation_reason = None
        else:
            print(f"✗ Escalation NOT detected: '{phrase}'")
            failed += 1

    print("\nShould NOT trigger escalation:")
    for phrase in normal_phrases:
        if not manager.should_escalate(phrase):
            print(f"✓ No escalation: '{phrase}'")
            passed += 1
        else:
            print(f"✗ False escalation: '{phrase}'")
            failed += 1

    total = len(escalation_phrases) + len(normal_phrases)
    print(f"\nPassed: {passed}/{total}")
    return failed == 0


def test_state_transitions():
    """Test state machine transitions"""
    print("\n" + "="*80)
    print("TEST: State Transitions")
    print("="*80)

    # Test new customer appointment flow
    manager = ConversationManager(
        call_type=CallType.INBOUND_NEW,
        caller_phone="+15551234567"
    )

    print("\nScenario: New customer scheduling appointment")
    print(f"Initial state: {manager.state.value}")

    # Simulate conversation turns
    messages = [
        "I need to schedule an oil change",
        "My name is John Smith",
        "Yes, that's correct",
    ]

    expected_states = [
        ConversationState.GREETING,
        ConversationState.INTENT_DETECTION,
        ConversationState.SLOT_COLLECTION,
    ]

    passed = 0
    failed = 0

    current_state = manager.state
    for i, message in enumerate(messages):
        if current_state == expected_states[i]:
            print(f"✓ State {i+1}: {current_state.value}")
            passed += 1
        else:
            print(f"✗ State {i+1}: Expected {expected_states[i].value}, Got {current_state.value}")
            failed += 1

        # Process message and transition
        current_state = manager.process_message(message)

    print(f"Final state: {current_state.value}")
    print(f"Intent: {manager.intent.value if manager.intent else 'None'}")
    print(f"\nPassed: {passed}/{len(expected_states)}")

    return failed == 0


def test_system_prompt_generation():
    """Test system prompt generation for different call types"""
    print("\n" + "="*80)
    print("TEST: System Prompt Generation")
    print("="*80)

    # Test 1: New customer
    manager1 = ConversationManager(
        call_type=CallType.INBOUND_NEW,
        caller_phone="+15551234567"
    )
    prompt1 = manager1.get_system_prompt()
    has_new_customer_text = "NEW CUSTOMER" in prompt1

    # Test 2: Existing customer
    customer_data = {
        "first_name": "John",
        "last_name": "Doe",
        "customer_since": "2023-01-01",
    }
    manager2 = ConversationManager(
        call_type=CallType.INBOUND_EXISTING,
        caller_phone="+15551234567",
        customer_data=customer_data
    )
    prompt2 = manager2.get_system_prompt()
    has_existing_customer_text = "EXISTING CUSTOMER" in prompt2 and "John" in prompt2

    # Test 3: Outbound reminder
    appointment_data = {
        "customer_name": "Jane Smith",
        "service_type": "Oil Change",
        "appointment_time": "tomorrow at 9:00 AM",
        "vehicle": "2020 Honda Civic",
    }
    manager3 = ConversationManager(
        call_type=CallType.OUTBOUND_REMINDER,
        customer_data={"first_name": "Jane", "last_name": "Smith"},
        appointment_data=appointment_data
    )
    prompt3 = manager3.get_system_prompt()
    has_reminder_text = "CALLING THE CUSTOMER" in prompt3 and "reminder" in prompt3.lower()

    results = [
        ("New customer prompt", has_new_customer_text),
        ("Existing customer prompt", has_existing_customer_text),
        ("Outbound reminder prompt", has_reminder_text),
    ]

    passed = sum(1 for _, result in results if result)
    failed = sum(1 for _, result in results if not result)

    for test_name, result in results:
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name}")

    print(f"\nPassed: {passed}/{len(results)}")
    return failed == 0


def test_slot_collection():
    """Test slot collection and validation"""
    print("\n" + "="*80)
    print("TEST: Slot Collection")
    print("="*80)

    manager = ConversationManager(
        call_type=CallType.INBOUND_NEW,
        caller_phone="+15551234567"
    )

    # Set intent to schedule appointment
    manager.intent = Intent.SCHEDULE_APPOINTMENT
    manager._set_required_slots()

    print(f"Required slots: {manager.required_slots}")

    # Simulate extracting slots from messages
    test_messages = [
        "I need an oil change",
        "I'd like to come in tomorrow",
        "How about 2pm?",
    ]

    for message in test_messages:
        manager._extract_slots(message)
        print(f"After '{message}': {manager.collected_slots}")

    # Check if service type was extracted
    has_service = "service_type" in manager.collected_slots
    print(f"\n✓ Service type extracted: {has_service}")

    return has_service


def print_state_machine_diagram():
    """Print state machine diagram"""
    print("\n" + "="*80)
    print("CONVERSATION STATE MACHINE DIAGRAM")
    print("="*80)

    diagram = """
    ┌─────────────┐
    │   GREETING  │ ◀── Start here
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │VERIFICATION?│ (only for existing customers + sensitive ops)
    └──────┬──────┘
           │
           ▼
    ┌──────────────┐
    │INTENT        │ ◀── Detect what customer wants
    │DETECTION     │
    └──────┬───────┘
           │
           ├──────────────────────┬────────────────────┐
           │                      │                    │
           ▼                      ▼                    ▼
    ┌─────────────┐       ┌─────────────┐      ┌────────────┐
    │SLOT         │       │EXECUTION    │      │ESCALATION  │
    │COLLECTION   │       │(for simple  │      │            │
    │             │       │ inquiries)  │      │            │
    └──────┬──────┘       └──────┬──────┘      └────────────┘
           │                     │
           ▼                     │
    ┌─────────────┐              │
    │CONFIRMATION │              │
    └──────┬──────┘              │
           │                     │
           ▼                     │
    ┌─────────────┐              │
    │EXECUTION    │◀─────────────┘
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │   CLOSING   │
    └──────┬──────┘
           │
           ▼
         [END]

    6 CONVERSATION FLOWS SUPPORTED:

    1. New Customer - First Appointment
       GREETING → INTENT → SLOT_COLLECTION → CONFIRMATION → EXECUTION → CLOSING

    2. Existing Customer - Service Appointment
       GREETING → INTENT → SLOT_COLLECTION → CONFIRMATION → EXECUTION → CLOSING

    3. Appointment Modification (Reschedule/Cancel)
       GREETING → VERIFICATION → INTENT → SLOT_COLLECTION → CONFIRMATION → EXECUTION → CLOSING

    4. General Inquiry
       GREETING → INTENT → EXECUTION → CLOSING

    5. Appointment Reminder (Outbound)
       GREETING → INTENT → CONFIRMATION → EXECUTION → CLOSING

    6. Post-Service Follow-Up (Outbound)
       GREETING → INTENT → CONFIRMATION → EXECUTION → CLOSING

    INTENTS SUPPORTED:

    ✓ Schedule Appointment
    ✓ Reschedule Appointment
    ✓ Cancel Appointment
    ✓ Check Hours
    ✓ Check Pricing
    ✓ Check Services
    ✓ General Inquiry
    ✓ Complaint (→ Escalation)
    """

    print(diagram)


def run_all_tests():
    """Run all conversation flow tests"""
    print("\n" + "╔"+ "="*78 + "╗")
    print("║" + " "*15 + "CONVERSATION FLOW TESTS (Simple)" + " "*27 + "║")
    print("╚"+ "="*78 + "╝")

    tests = [
        ("Intent Detection", test_intent_detection),
        ("Escalation Detection", test_escalation_detection),
        ("State Transitions", test_state_transitions),
        ("System Prompt Generation", test_system_prompt_generation),
        ("Slot Collection", test_slot_collection),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, "PASS" if result else "FAIL"))
        except Exception as e:
            results.append((test_name, f"ERROR: {str(e)}"))
            print(f"\n✗ {test_name} failed with error: {e}")
            import traceback
            traceback.print_exc()

    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    for test_name, status in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {test_name}: {status}")

    # Print state machine diagram
    print_state_machine_diagram()

    # Overall result
    all_passed = all(status == "PASS" for _, status in results)

    if all_passed:
        print("\n" + "╔"+ "="*78 + "╗")
        print("║" + " "*25 + "ALL TESTS PASSED ✓" + " "*32 + "║")
        print("╚"+ "="*78 + "╝")
    else:
        print("\n" + "╔"+ "="*78 + "╗")
        print("║" + " "*25 + "SOME TESTS FAILED ✗" + " "*31 + "║")
        print("╚"+ "="*78 + "╝")

    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
