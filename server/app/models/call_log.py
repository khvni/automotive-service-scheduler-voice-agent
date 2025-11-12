"""Call log model."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum, JSON, Boolean
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base, TimestampMixin


class CallDirection(str, enum.Enum):
    """Call direction enum."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, enum.Enum):
    """Call status enum."""

    INITIATED = "initiated"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BUSY = "busy"
    NO_ANSWER = "no_answer"


class CallLog(Base, TimestampMixin):
    """Call log model for storing call history and metadata."""

    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))

    # Call details
    call_sid = Column(String(255), unique=True, index=True)  # Twilio Call SID
    direction = Column(SQLEnum(CallDirection), nullable=False)
    status = Column(SQLEnum(CallStatus), default=CallStatus.INITIATED)

    from_number = Column(String(20))
    to_number = Column(String(20))

    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    duration_seconds = Column(Integer)

    # AI interaction metadata
    transcript = Column(String(10000))  # Full conversation transcript
    summary = Column(String(2000))  # AI-generated summary
    intent = Column(String(100))  # Detected intent (booking, rescheduling, etc.)
    sentiment = Column(String(20))  # positive, neutral, negative

    # Tool usage tracking
    tools_used = Column(JSON)  # List of tools/functions called during the call

    # Appointment reference
    appointment_id = Column(Integer, ForeignKey("appointments.id"))

    # Quality metrics
    was_successful = Column(Boolean, default=False)
    required_human_transfer = Column(Boolean, default=False)
    customer_satisfaction_score = Column(Integer)  # 1-5 scale

    notes = Column(String(2000))

    # Relationships
    customer = relationship("Customer", back_populates="call_logs")

    def __repr__(self):
        return f"<CallLog(id={self.id}, call_sid='{self.call_sid}', direction='{self.direction}', status='{self.status}')>"
