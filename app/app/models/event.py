# app/models/event.py
from datetime import datetime
from bson import ObjectId

class Event:
    def __init__(self, name, date, capacity, batch_size):
        self.name = name
        self.date = date
        self.capacity = capacity
        self.batch_size = batch_size
        self.invitees = []
        self.current_batch = 0
        self.created_at = datetime.utcnow()

    @classmethod
    def from_dict(cls, data):
        event = cls(
            name=data['name'],
            date=data['date'],
            capacity=data['capacity'],
            batch_size=data.get('batch_size', 10)
        )
        event.invitees = data.get('invitees', [])
        event.current_batch = data.get('current_batch', 0)
        event.created_at = data.get('created_at', datetime.utcnow())
        return event

    def to_dict(self):
        return {
            "name": self.name,
            "date": self.date,
            "capacity": self.capacity,
            "batch_size": self.batch_size,
            "invitees": self.invitees,
            "current_batch": self.current_batch,
            "created_at": self.created_at
        }

    def add_invitee(self, invitee):
        self.invitees.append({
            "_id": ObjectId(),
            "name": invitee['name'],
            "phone": invitee['phone'],
            "status": "pending",
            "batch": self.current_batch,
            "added_at": datetime.utcnow()
        })

    def get_next_batch(self):
        pending_invites = [i for i in self.invitees if i['status'] == 'pending']
        return pending_invites[:self.batch_size]

    def can_accept_more_rsvps(self):
        confirmed = sum(1 for i in self.invitees if i['status'] == 'YES')
        return confirmed < self.capacity