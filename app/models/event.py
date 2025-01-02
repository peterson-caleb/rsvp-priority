# app/models/event.py
from datetime import datetime, timedelta
from bson import ObjectId
import secrets
import string

class Event:
    def __init__(self, name, date, capacity):
        self.name = name
        self.date = date
        self.capacity = capacity
        self.invitees = []
        self.created_at = datetime.utcnow()
        self.event_code = self._generate_event_code()
        self.invitation_expiry_hours = 24  # Default expiry time

    def _generate_event_code(self):
        prefix = ''.join(c for c in self.name.upper().split()[0] if c.isalpha())[:2]
        numbers = ''.join(secrets.choice(string.digits) for _ in range(3))
        return f"{prefix}{numbers}"

    @classmethod
    def from_dict(cls, data):
        event = cls(
            name=data['name'],
            date=data['date'],
            capacity=data['capacity']
        )
        event.invitees = data.get('invitees', [])
        event.created_at = data.get('created_at', datetime.utcnow())
        event.event_code = data.get('event_code', event._generate_event_code())
        event.invitation_expiry_hours = data.get('invitation_expiry_hours', 24)
        return event

    def to_dict(self):
        return {
            "name": self.name,
            "date": self.date,
            "capacity": self.capacity,
            "invitees": self.invitees,
            "created_at": self.created_at,
            "event_code": self.event_code,
            "invitation_expiry_hours": self.invitation_expiry_hours
        }

    def get_confirmed_count(self):
        """Get number of confirmed attendees"""
        return sum(1 for i in self.invitees if i['status'] == 'YES')

    def get_available_spots(self):
        """Get number of spots still available"""
        return self.capacity - self.get_confirmed_count()

    def get_pending_invitees(self):
        """Get list of invitees who haven't been invited yet"""
        return [i for i in self.invitees if i['status'] == 'pending']

    def get_active_invites(self):
        """Get list of invitees with active invitations"""
        return [i for i in self.invitees if i['status'] == 'invited']

    def get_next_invitees(self):
        """Get next set of invitees to invite based on available capacity"""
        available_spots = self.get_available_spots()
        if available_spots <= 0:
            return []
            
        # Get pending invitees up to the number of available spots
        pending = self.get_pending_invitees()
        return pending[:available_spots]

    def check_and_expire_invitations(self):
        """Check and expire invitations that have passed the expiry time"""
        now = datetime.utcnow()
        updated = False

        for invitee in self.invitees:
            if (invitee['status'] == 'invited' and 
                'invited_at' in invitee and 
                now - invitee['invited_at'] > timedelta(hours=self.invitation_expiry_hours)):
                invitee['status'] = 'EXPIRED'
                invitee['expired_at'] = now
                updated = True

        return updated

    def can_accept_rsvp(self, invitee_id):
        """Check if we can accept an RSVP from this invitee"""
        invitee = next((i for i in self.invitees if str(i['_id']) == str(invitee_id)), None)
        if not invitee:
            return False
            
        # Can only accept if invitation is still active
        if invitee['status'] != 'invited':
            return False
            
        # Check if invitation has expired
        if 'invited_at' in invitee:
            time_elapsed = datetime.utcnow() - invitee['invited_at']
            if time_elapsed > timedelta(hours=self.invitation_expiry_hours):
                return False
                
        # Check if we still have capacity
        return self.get_available_spots() > 0