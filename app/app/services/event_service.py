# app/services/event_service.py
from datetime import datetime
from bson import ObjectId
from ..models.event import Event

class EventService:
    def __init__(self, db):
        self.db = db
        self.events_collection = db['events']

    def create_event(self, event_data):
        event = Event.from_dict(event_data)
        result = self.events_collection.insert_one(event.to_dict())
        return str(result.inserted_id)

    def get_event(self, event_id):
        event_data = self.events_collection.find_one({"_id": ObjectId(event_id)})
        return Event.from_dict(event_data) if event_data else None

    def update_event(self, event_id, event_data):
        self.events_collection.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": event_data}
        )
        return self.get_event(event_id)

    def delete_event(self, event_id):
        return self.events_collection.delete_one({"_id": ObjectId(event_id)})

    def add_invitees(self, event_id, invitees):
        print(f"Adding invitees to event {event_id}:", invitees)  # Debug print
        
        # Get event directly from MongoDB
        event_data = self.events_collection.find_one({"_id": ObjectId(event_id)})
        if not event_data:
            raise ValueError("Event not found")
        
        # Get current invitees or initialize empty list
        current_invitees = event_data.get('invitees', [])
        
        # Create set of current phone numbers for checking duplicates
        current_phones = {invitee['phone'] for invitee in current_invitees}
        
        # Add new invitees, skipping duplicates
        for invitee in invitees:
            # Check if phone number already exists
            if invitee['phone'] in current_phones:
                continue  # Skip this invitee
                
            new_invitee = {
                "_id": ObjectId(),
                "name": invitee['name'],
                "phone": invitee['phone'],
                "status": "pending",
                "added_at": datetime.utcnow()
            }
            current_invitees.append(new_invitee)
            current_phones.add(invitee['phone'])  # Add to our tracking set
        
        print("Updated invitees list:", current_invitees)  # Debug print
        
        # Update the event in MongoDB
        self.events_collection.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {"invitees": current_invitees}}
        )
        
        return current_invitees

    def process_rsvp(self, phone_number, response):
        event = self.events_collection.find_one({"invitees.phone": phone_number})
        if not event:
            return None
        
        event_obj = Event.from_dict(event)
        for invitee in event_obj.invitees:
            if invitee['phone'] == phone_number:
                if response.lower() == 'yes' and not event_obj.can_accept_more_rsvps():
                    return 'FULL'
                invitee['status'] = response.upper()
                invitee['responded_at'] = datetime.utcnow()
                break
        
        self.events_collection.update_one(
            {"_id": event['_id']},
            {"$set": {"invitees": event_obj.invitees}}
        )
        return response.upper()

    def get_events(self):
        return list(self.events_collection.find())

    def delete_invitee(self, event_id, invitee_id):
        self.events_collection.update_one(
            {"_id": ObjectId(event_id)},
            {"$pull": {"invitees": {"_id": ObjectId(invitee_id)}}}
        )

    def send_invitations(self, event_id):
        event = self.get_event(event_id)
        if not event:
            raise ValueError("Event not found")
        
        for invitee in event.get_next_batch():
            if invitee['status'] == 'pending':
                # Here you would integrate with SMS service
                # For now, just mark as invited
                invitee['status'] = 'invited'
                invitee['invited_at'] = datetime.utcnow()
        
        self.events_collection.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {"invitees": event.invitees, "current_batch": event.current_batch + 1}}
        )