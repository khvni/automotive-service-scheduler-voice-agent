# Enhanced Customer Data Schema

## Customer Information Requirements

Based on automotive dealership best practices, our system needs comprehensive customer data for:
1. **Identity Verification** - Confirm caller identity over the phone
2. **Service Personalization** - Reference past service history
3. **Appointment Scheduling** - Collect necessary details
4. **Compliance** - Meet dealership record-keeping requirements

## Updated Database Schema

### Customers Table
```sql
CREATE TABLE customers (
    -- Primary Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Contact Information
    phone VARCHAR(20) UNIQUE NOT NULL,
    email VARCHAR(200) UNIQUE,
    preferred_contact_method VARCHAR(10) DEFAULT 'phone', -- 'phone', 'email', 'text'

    -- Personal Information
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    date_of_birth DATE,  -- For verification

    -- Address Information
    street_address VARCHAR(200),
    city VARCHAR(100),
    state VARCHAR(2),
    zip_code VARCHAR(10),

    -- Customer Relationship
    customer_since DATE DEFAULT CURRENT_DATE,
    customer_type VARCHAR(20) DEFAULT 'retail', -- 'retail', 'fleet', 'referral'
    referral_source VARCHAR(100),  -- Who referred them
    preferred_service_advisor VARCHAR(100),

    -- Preferences
    receive_reminders BOOLEAN DEFAULT TRUE,
    receive_promotions BOOLEAN DEFAULT TRUE,
    preferred_appointment_time VARCHAR(20), -- 'morning', 'afternoon', 'evening'

    -- Notes
    notes TEXT,  -- Service advisor notes

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_contact_date TIMESTAMP,

    -- Indexes
    INDEX idx_phone (phone),
    INDEX idx_email (email),
    INDEX idx_last_name (last_name)
);
```

### Vehicles Table
```sql
CREATE TABLE vehicles (
    -- Primary Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE,

    -- Vehicle Identification
    vin VARCHAR(17) UNIQUE NOT NULL,
    license_plate VARCHAR(15),

    -- Vehicle Details
    year INTEGER NOT NULL,
    make VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    trim VARCHAR(50),
    color VARCHAR(50),

    -- Ownership
    purchase_date DATE,
    purchased_from_us BOOLEAN DEFAULT FALSE,

    -- Service Information
    current_mileage INTEGER,
    last_service_date DATE,
    last_service_mileage INTEGER,
    next_service_due_mileage INTEGER,

    -- Vehicle Status
    is_primary_vehicle BOOLEAN DEFAULT TRUE,
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'sold', 'totaled'

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Indexes
    INDEX idx_vin (vin),
    INDEX idx_customer_id (customer_id),
    INDEX idx_license_plate (license_plate)
);
```

### Appointments Table
```sql
CREATE TABLE appointments (
    -- Primary Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id),
    vehicle_id UUID REFERENCES vehicles(id),

    -- Appointment Details
    scheduled_at TIMESTAMP NOT NULL,
    duration_minutes INTEGER DEFAULT 60,
    service_type VARCHAR(100) NOT NULL,
    service_category VARCHAR(50), -- 'maintenance', 'repair', 'inspection', 'recall'

    -- Service Details
    service_description TEXT,
    customer_concerns TEXT,  -- What the customer reported
    recommended_services TEXT,  -- What we recommend
    estimated_cost DECIMAL(10,2),
    actual_cost DECIMAL(10,2),

    -- Status & Workflow
    status VARCHAR(20) DEFAULT 'scheduled', -- 'scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show'
    cancellation_reason VARCHAR(200),
    confirmation_sent BOOLEAN DEFAULT FALSE,
    reminder_sent BOOLEAN DEFAULT FALSE,

    -- External Integration
    calendar_event_id VARCHAR(255),  -- Google Calendar ID

    -- Assignment
    assigned_technician VARCHAR(100),
    service_bay VARCHAR(10),

    -- Communication History
    booking_method VARCHAR(20), -- 'phone', 'online', 'walk_in', 'ai_voice'
    booked_by VARCHAR(100),  -- Agent name or 'AI Voice Agent'

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,

    -- Indexes
    INDEX idx_scheduled_at (scheduled_at),
    INDEX idx_customer_id (customer_id),
    INDEX idx_vehicle_id (vehicle_id),
    INDEX idx_status (status)
);
```

### Call Logs Table
```sql
CREATE TABLE call_logs (
    -- Primary Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Call Information
    call_sid VARCHAR(100) UNIQUE NOT NULL,
    customer_id UUID REFERENCES customers(id),

    -- Call Details
    direction VARCHAR(10) NOT NULL, -- 'inbound', 'outbound'
    caller_phone VARCHAR(20) NOT NULL,
    call_type VARCHAR(50), -- 'new_appointment', 'reschedule', 'cancel', 'inquiry', 'reminder'

    -- Call Metadata
    duration_seconds INTEGER,
    recording_url TEXT,
    transcript TEXT,

    -- Conversation Analysis
    customer_sentiment VARCHAR(20), -- 'positive', 'neutral', 'negative'
    intent_detected VARCHAR(100),  -- What the customer wanted
    issue_resolved BOOLEAN,

    -- Outcome
    appointment_id UUID REFERENCES appointments(id),
    outcome VARCHAR(50), -- 'appointment_booked', 'rescheduled', 'cancelled', 'information_provided'

    -- AI Metadata
    llm_model_used VARCHAR(50),
    total_tokens_used INTEGER,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,

    -- Indexes
    INDEX idx_call_sid (call_sid),
    INDEX idx_customer_id (customer_id),
    INDEX idx_created_at (created_at)
);
```

### Service History Table (Optional - for context)
```sql
CREATE TABLE service_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id UUID REFERENCES vehicles(id),
    appointment_id UUID REFERENCES appointments(id),

    -- Service Performed
    service_date DATE NOT NULL,
    mileage INTEGER,
    services_performed TEXT[],  -- Array of services
    parts_replaced TEXT[],
    total_cost DECIMAL(10,2),

    -- Next Service Recommendation
    next_service_type VARCHAR(100),
    next_service_due_date DATE,
    next_service_due_mileage INTEGER,

    created_at TIMESTAMP DEFAULT NOW()
);
```

## Faker Data Generation - Enhanced

```python
# scripts/generate_mock_crm_data.py - UPDATED
from faker import Faker
from faker_vehicle import VehicleProvider
import random
from datetime import datetime, timedelta

fake = Faker('en_US')
fake.add_provider(VehicleProvider)

async def generate_customers(num_customers: int = 10000):
    """Generate comprehensive customer data"""
    customers = []

    for _ in range(num_customers):
        first_name = fake.first_name()
        last_name = fake.last_name()

        # Generate realistic date of birth (ages 18-75)
        age = random.randint(18, 75)
        dob = datetime.now() - timedelta(days=age*365 + random.randint(0, 365))

        # Customer since date (random between 6 months and 5 years ago)
        customer_since = fake.date_time_between(start_date='-5y', end_date='-6m')

        customer = {
            'id': str(uuid.uuid4()),

            # Contact
            'phone': fake.phone_number(),
            'email': f"{first_name.lower()}.{last_name.lower()}@{fake.free_email_domain()}",
            'preferred_contact_method': random.choice(['phone', 'phone', 'phone', 'email', 'text']),

            # Personal
            'first_name': first_name,
            'last_name': last_name,
            'date_of_birth': dob.date(),

            # Address
            'street_address': fake.street_address(),
            'city': fake.city(),
            'state': fake.state_abbr(),
            'zip_code': fake.zipcode(),

            # Relationship
            'customer_since': customer_since.date(),
            'customer_type': random.choices(
                ['retail', 'fleet', 'referral'],
                weights=[0.85, 0.05, 0.10]
            )[0],
            'referral_source': fake.name() if random.random() < 0.1 else None,
            'preferred_service_advisor': random.choice([
                'Mike Johnson', 'Sarah Chen', 'Robert Williams', None
            ]),

            # Preferences
            'receive_reminders': random.choice([True, True, True, False]),
            'receive_promotions': random.choice([True, True, False]),
            'preferred_appointment_time': random.choice([
                'morning', 'afternoon', 'evening', None
            ]),

            # Notes (occasionally)
            'notes': fake.sentence() if random.random() < 0.15 else None,

            # Timestamps
            'created_at': customer_since,
            'last_contact_date': fake.date_time_between(
                start_date=customer_since,
                end_date='now'
            ) if random.random() < 0.7 else None
        }
        customers.append(customer)

    return customers


async def generate_vehicles(customers: list):
    """Generate vehicles with service history awareness"""
    vehicles = []

    MAKES_MODELS = {
        'Toyota': ['Camry', 'Corolla', 'RAV4', 'Highlander', 'Tacoma', '4Runner'],
        'Honda': ['Accord', 'Civic', 'CR-V', 'Pilot', 'Odyssey', 'Ridgeline'],
        'Ford': ['F-150', 'Escape', 'Explorer', 'Mustang', 'Edge', 'Bronco'],
        'Chevrolet': ['Silverado', 'Equinox', 'Malibu', 'Tahoe', 'Traverse'],
        'BMW': ['3 Series', '5 Series', 'X3', 'X5', 'X7'],
        'Mercedes-Benz': ['C-Class', 'E-Class', 'GLC', 'GLE', 'GLS'],
    }

    for customer in customers:
        num_vehicles = random.choices([1, 2, 3], weights=[0.65, 0.25, 0.10])[0]

        for idx in range(num_vehicles):
            make = random.choice(list(MAKES_MODELS.keys()))
            model = random.choice(MAKES_MODELS[make])
            year = random.randint(2010, 2024)

            # Determine if purchased from us
            purchased_from_us = random.choice([True, False, False])
            purchase_date = None
            if purchased_from_us:
                purchase_date = fake.date_between(
                    start_date=customer['customer_since'],
                    end_date='today'
                )

            # Calculate mileage
            age = 2024 - year
            base_mileage = age * random.randint(10000, 15000)
            current_mileage = base_mileage + random.randint(0, 5000)

            # Last service (if they're a customer)
            last_service_date = None
            last_service_mileage = None
            if random.random() < 0.6:  # 60% have service history
                last_service_date = fake.date_between(
                    start_date=customer['customer_since'],
                    end_date='today'
                )
                last_service_mileage = current_mileage - random.randint(500, 3000)

            vehicle = {
                'id': str(uuid.uuid4()),
                'customer_id': customer['id'],

                # Identity
                'vin': fake.vin(),
                'license_plate': fake.license_plate(),

                # Details
                'year': year,
                'make': make,
                'model': model,
                'trim': random.choice(['Base', 'LX', 'EX', 'Limited', 'Premium', None]),
                'color': fake.color_name(),

                # Ownership
                'purchase_date': purchase_date,
                'purchased_from_us': purchased_from_us,

                # Service
                'current_mileage': current_mileage,
                'last_service_date': last_service_date,
                'last_service_mileage': last_service_mileage,
                'next_service_due_mileage': current_mileage + random.randint(2000, 5000),

                # Status
                'is_primary_vehicle': (idx == 0),  # First vehicle is primary
                'status': 'active',

                'created_at': customer['created_at']
            }
            vehicles.append(vehicle)

    return vehicles
```

## Customer Verification Questions

For phone identity verification, the AI agent can ask:
1. "Can I get your date of birth to verify your account?"
2. "What's the VIN or license plate of the vehicle you're calling about?"
3. "Can you confirm your address on file?"
4. "What's the last service you had done with us?"

These are stored in the database and can be cross-referenced during calls.