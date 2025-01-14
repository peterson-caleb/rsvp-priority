from datetime import datetime
from bson import ObjectId
import secrets
import string

class Event:
    def __init__(self, name, date, capacity, invitation_expiry_hours=None):
        self.name = name
        self.date = date
        self.capacity = capacity
        self.invitees = []
        self.created_at = datetime.utcnow()
        self.event_code = self._generate_event_code()
        self.invitation_expiry_hours = invitation_expiry_hours or 24

    def _generate_event_code(self):
        """Generate a unique event code"""
        prefix = ''.join(c for c in self.name.upper().split()[0] if c.isalpha())[:2]
        numbers = ''.join(secrets.choice(string.digits) for _ in range(3))
        return f"{prefix}{numbers}"

    @classmethod
    def from_dict(cls, data, invitation_expiry_hours=None):
        event = cls(
            name=data['name'],
            date=data['date'],
            capacity=data['capacity'],
            invitation_expiry_hours=invitation_expiry_hours
        )
        event.invitees = data.get('invitees', [])
        event.created_at = data.get('created_at', datetime.utcnow())
        event.event_code = data.get('event_code', event._generate_event_code())
        if 'invitation_expiry_hours' in data:
            event.invitation_expiry_hours = data['invitation_expiry_hours']
        return event

    def to_dict(self):
        """Convert event to dictionary for storage"""
        return {
            "name": self.name,
            "date": self.date,
            "capacity": self.capacity,
            "invitees": self.invitees,
            "created_at": self.created_at,
            "event_code": self.event_code,
            "invitation_expiry_hours": self.invitation_expiry_hours
        }