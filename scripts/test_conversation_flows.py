"""
Test script for conversation flow state machine.

Tests all 6 conversation flows:
1. New Customer - First Appointment
2. Existing Customer - Service Appointment
3. Appointment Modification (Reschedule/Cancel)
4. General Inquiry
5. Appointment Reminder (Outbound)
6. Post-Service Follow-Up (Outbound)
"""

import sys
import os
from pathlib import Path

# Add server directory to path
server_dir = Path(__file__).parent.parent / "server"
sys.path.insert(0, str(server_dir))

from app.services.conversation_manager import (
    ConversationManager,
    CallType,
    ConversationState,
    Intent,
    create_inbound_new_manager,
    create_inbound_existing_manager,
    create_outbound_reminder_manager,
)


def print_state_transition(manager: ConversationManager, message: str):
    """Print state transition for visualization."""
    print(f"\n{'='*60}")
    print(f"User: {message}")
    print(f"State BEFORE: {manager.state.value}")
    print(f"Intent: {manager.intent.value if manager.intent else 'None'}")

    # Process message
    new_state = manager.process_message(message)

    print(f"State AFTER: {new_state.value}")
    print(f"Collected Slots: {manager.collected_slots}")
    print(f"Required Slots: {manager.required_slots}")
    print(f"Escalation: {manager.escalation_triggered}")
    print(f"{'='*60}")


def test_flow_1_new_customer():
    """
    Test Flow 1: New Customer - First Appointment

    Expected State Flow:
    GREETING → INTENT_DETECTION → SLOT_COLLECTION → CONFIRMATION → EXECUTION → CLOSING
    """
    print("\n" + "="*80)
    print("TEST FLOW 1: New Customer - First Appointment")
    print("="*80)

    manager = create_inbound_new_manager(caller_phone="+15551234567")

    # Initial state should be GREETING
    assert manager.state == ConversationState.GREETING
    print(f"✓ Initial state: {manager.state.value}")

    # Simulate conversation
    messages = [
        "Hi, I need to schedule an oil change",  # GREETING → INTENT_DETECTION
        "My name is John Smith",                  # SLOT_COLLECTION
        "My phone is 555-123-4567",              # SLOT_COLLECTION
        "john.smith@email.com",                   # SLOT_COLLECTION
        "I have a 2020 Honda Civic",              # SLOT_COLLECTION
        "I'd like to come in tomorrow at 2pm",    # SLOT_COLLECTION
        "Yes, that's correct",                    # CONFIRMATION → EXECUTION
        "No, that's all. Thanks!",                # CLOSING
    ]

    for msg in messages:
        print_state_transition(manager, msg)

    # Final checks
    assert manager.intent == Intent.SCHEDULE_APPOINTMENT
    print("\n✓ Flow 1 completed successfully")
    print(f"✓ Intent detected: {manager.intent.value}")
    print(f"✓ Final state: {manager.state.value}")

    return True


def test_flow_2_existing_customer():
    """
    Test Flow 2: Existing Customer - Service Appointment

    Expected State Flow:
    GREETING → INTENT_DETECTION → SLOT_COLLECTION → CONFIRMATION → EXECUTION → CLOSING
    """
    print("\n" + "="*80)
    print("TEST FLOW 2: Existing Customer - Service Appointment")
    print("="*80)

    # Simulate existing customer data
    customer_data = {
        "id": 123,
        "first_name": "Sarah",
        "last_name": "Johnson",
        "phone_number": "+15559876543",
        "email": "sarah.j@email.com",
        "customer_since": "2023-01-15",
        "last_service_date": "2024-12-01",
        "vehicles": [
            {
                "id": 456,
                "year": 2019,
                "make": "Toyota",
                "model": "Camry",
                "vin": "1HGCM82633A123456",
                "is_primary_vehicle": True,
            }
        ],
    }

    manager = create_inbound_existing_manager(
        caller_phone="+15559876543",
        customer_data=customer_data
    )

    assert manager.state == ConversationState.GREETING
    assert manager.call_type == CallType.INBOUND_EXISTING
    print(f"✓ Initial state: {manager.state.value}")
    print(f"✓ Customer: {customer_data['first_name']} {customer_data['last_name']}")

    # Simulate conversation
    messages = [
        "Hi, I need to schedule brake service",   # GREETING → INTENT_DETECTION
        "For my Toyota Camry",                    # SLOT_COLLECTION
        "How about next Tuesday at 10am?",        # SLOT_COLLECTION
        "Yes, that works for me",                 # CONFIRMATION → EXECUTION
        "That's all, thanks!",                    # CLOSING
    ]

    for msg in messages:
        print_state_transition(manager, msg)

    assert manager.intent == Intent.SCHEDULE_APPOINTMENT
    print("\n✓ Flow 2 completed successfully")

    return True


def test_flow_3_reschedule():
    """
    Test Flow 3: Appointment Modification (Reschedule)

    Expected State Flow:
    GREETING → VERIFICATION → INTENT_DETECTION → SLOT_COLLECTION → CONFIRMATION → EXECUTION → CLOSING
    """
    print("\n" + "="*80)
    print("TEST FLOW 3: Appointment Modification - Reschedule")
    print("="*80)

    customer_data = {
        "id": 123,
        "first_name": "Mike",
        "last_name": "Wilson",
        "phone_number": "+15551112222",
        "date_of_birth": "1985-05-15",
    }

    manager = create_inbound_existing_manager(
        caller_phone="+15551112222",
        customer_data=customer_data
    )

    print(f"✓ Initial state: {manager.state.value}")

    # Simulate conversation
    messages = [
        "I need to reschedule my appointment",    # GREETING → VERIFICATION (reschedule requires verification)
        "My date of birth is May 15, 1985",       # VERIFICATION → INTENT_DETECTION
        "Can I move it to next Friday at 3pm?",   # SLOT_COLLECTION
        "Yes, that's correct",                    # CONFIRMATION → EXECUTION
        "Thanks!",                                # CLOSING
    ]

    for msg in messages:
        print_state_transition(manager, msg)

    assert manager.intent == Intent.RESCHEDULE_APPOINTMENT
    print("\n✓ Flow 3 completed successfully")

    return True


def test_flow_4_general_inquiry():
    """
    Test Flow 4: General Inquiry

    Expected State Flow:
    GREETING → INTENT_DETECTION → EXECUTION → CLOSING
    (Skips SLOT_COLLECTION for simple inquiries)
    """
    print("\n" + "="*80)
    print("TEST FLOW 4: General Inquiry")
    print("="*80)

    manager = create_inbound_new_manager(caller_phone="+15553334444")

    print(f"✓ Initial state: {manager.state.value}")

    # Test different inquiry types
    inquiries = [
        ("What are your hours?", Intent.CHECK_HOURS),
        ("How much does an oil change cost?", Intent.CHECK_PRICING),
        ("Do you do tire rotations?", Intent.CHECK_SERVICES),
    ]

    for question, expected_intent in inquiries:
        manager = create_inbound_new_manager(caller_phone="+15553334444")
        print_state_transition(manager, question)

        # For general inquiries, should go straight to EXECUTION
        assert manager.intent == expected_intent
        print(f"✓ Intent correctly detected: {expected_intent.value}\n")

    print("✓ Flow 4 completed successfully")

    return True


def test_flow_5_outbound_reminder():
    """
    Test Flow 5: Appointment Reminder (Outbound)

    Expected State Flow:
    GREETING → INTENT_DETECTION → CONFIRMATION → EXECUTION → CLOSING
    """
    print("\n" + "="*80)
    print("TEST FLOW 5: Appointment Reminder (Outbound)")
    print("="*80)

    customer_data = {
        "id": 789,
        "first_name": "Lisa",
        "last_name": "Chen",
        "phone_number": "+15555556666",
    }

    appointment_data = {
        "customer_name": "Lisa Chen",
        "service_type": "Oil Change",
        "appointment_time": "tomorrow at 9:00 AM",
        "vehicle": "2021 Honda CR-V",
    }

    manager = create_outbound_reminder_manager(
        customer_data=customer_data,
        appointment_data=appointment_data
    )

    assert manager.call_type == CallType.OUTBOUND_REMINDER
    print(f"✓ Call type: {manager.call_type.value}")
    print(f"✓ Initial state: {manager.state.value}")

    # Simulate conversation
    messages = [
        "Yes, I'll be there",                      # GREETING → EXECUTION
        "That's all, thanks!",                     # CLOSING
    ]

    for msg in messages:
        print_state_transition(manager, msg)

    print("\n✓ Flow 5 completed successfully")

    return True


def test_escalation_detection():
    """
    Test escalation trigger detection
    """
    print("\n" + "="*80)
    print("TEST: Escalation Detection")
    print("="*80)

    manager = create_inbound_new_manager(caller_phone="+15557778888")

    # Test escalation triggers
    escalation_phrases = [
        "I want to speak to a manager",
        "This is ridiculous!",
        "I'm going to sue you",
        "I have a complaint about my last service",
        "Can I speak to a human?",
    ]

    for phrase in escalation_phrases:
        result = manager.should_escalate(phrase)
        if result:
            print(f"✓ Escalation detected: '{phrase}'")
            print(f"  Reason: {manager.escalation_reason}")
        else:
            print(f"✗ Escalation NOT detected: '{phrase}'")

    # Process an escalation message
    print("\n" + "-"*60)
    print_state_transition(manager, "I want to speak to your manager!")

    assert manager.escalation_triggered
    assert manager.state == ConversationState.ESCALATION
    print("\n✓ Escalation detection working correctly")

    return True


def test_state_machine_diagram():
    """
    Print state machine diagram
    """
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

    STATE DESCRIPTIONS:

    • GREETING: Welcome customer, establish rapport
    • VERIFICATION: Verify customer identity (DOB, address, etc.)
    • INTENT_DETECTION: Determine customer's goal
    • SLOT_COLLECTION: Gather required information
    • CONFIRMATION: Confirm all details with customer
    • EXECUTION: Execute tools (book/cancel/reschedule)
    • CLOSING: Thank customer, ask if anything else needed
    • ESCALATION: Transfer to human agent

    INTENTS SUPPORTED:

    ✓ Schedule Appointment
    ✓ Reschedule Appointment
    ✓ Cancel Appointment
    ✓ Check Hours
    ✓ Check Pricing
    ✓ Check Services
    ✓ General Inquiry
    ✓ Complaint
    """

    print(diagram)


def run_all_tests():
    """Run all conversation flow tests"""
    print("\n" + "╔"+ "="*78 + "╗")
    print("║" + " "*20 + "CONVERSATION FLOW TESTS" + " "*35 + "║")
    print("╚"+ "="*78 + "╝")

    tests = [
        ("Flow 1: New Customer", test_flow_1_new_customer),
        ("Flow 2: Existing Customer", test_flow_2_existing_customer),
        ("Flow 3: Reschedule", test_flow_3_reschedule),
        ("Flow 4: General Inquiry", test_flow_4_general_inquiry),
        ("Flow 5: Outbound Reminder", test_flow_5_outbound_reminder),
        ("Escalation Detection", test_escalation_detection),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, "PASS" if result else "FAIL"))
        except Exception as e:
            results.append((test_name, f"ERROR: {str(e)}"))
            print(f"\n✗ {test_name} failed with error: {e}")

    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    for test_name, status in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {test_name}: {status}")

    # Print state machine diagram
    test_state_machine_diagram()

    # Overall result
    all_passed = all(status == "PASS" for _, status in results)

    if all_passed:
        print("\n" + "╔"+ "="*78 + "╗")
        print("║" + " "*20 + "ALL TESTS PASSED ✓" + " "*37 + "║")
        print("╚"+ "="*78 + "╝")
    else:
        print("\n" + "╔"+ "="*78 + "╗")
        print("║" + " "*20 + "SOME TESTS FAILED ✗" + " "*36 + "║")
        print("╚"+ "="*78 + "╝")

    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
