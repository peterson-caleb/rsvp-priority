# app/services/event_service.py
from datetime import datetime
from bson import ObjectId
from ..models.event import Event

class EventService:
    def __init__(self, db, sms_service=None):
        self.db = db
        self.events_collection = db['events']
        self.sms_service = sms_service

    def create_event(self, event_data):
        event = Event.from_dict(event_data)
        result = self.events_collection.insert_one(event.to_dict())
        return str(result.inserted_id)

    def get_event(self, event_id):
        event_data = self.events_collection.find_one({"_id": ObjectId(event_id)})
        return Event.from_dict(event_data) if event_data else None

    def get_events(self):
        """Get all events"""
        events = list(self.events_collection.find())
        return events

    def update_event(self, event_id, event_data):
        self.events_collection.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": event_data}
        )
        return self.get_event(event_id)
        
    def delete_event(self, event_id):
        """Delete an event by ID"""
        result = self.events_collection.delete_one({"_id": ObjectId(event_id)})
        return result.deleted_count > 0

    def add_invitees(self, event_id, invitees):
        """Add new invitees to the event and send invitations if capacity allows"""
        event = self.get_event(event_id)
        if not event:
            raise ValueError("Event not found")

        # Get current phones for duplicate checking
        current_phones = {i['phone'] for i in event.invitees}
        
        # Add new invitees with priority based on order
        start_priority = len(event.invitees)
        for idx, invitee in enumerate(invitees):
            if invitee['phone'] in current_phones:
                continue

            new_invitee = {
                "_id": ObjectId(),
                "name": invitee['name'],
                "phone": invitee['phone'],
                "status": "pending",  # Start everyone as pending
                "priority": start_priority + idx,
                "added_at": datetime.utcnow()
            }
            event.invitees.append(new_invitee)
            current_phones.add(invitee['phone'])

        # Update event with new invitees
        self.update_event(event_id, {"invitees": event.invitees})
        
        # Process invitations immediately
        self._process_initial_invitations(event_id)
        
        return event.invitees

    def _process_initial_invitations(self, event_id):
        """Process and send invitations for an event"""
        event = self.get_event(event_id)
        if not event:
            return

        # Get available spots
        available_spots = event.get_available_spots()
        
        # Get pending invitees up to available spots
        pending_invitees = [i for i in event.invitees if i['status'] == 'pending']
        to_invite = pending_invitees[:available_spots]

        # Send invitations
        now = datetime.utcnow()
        for invitee in to_invite:
            try:
                # Attempt to send SMS
                message_sid = self.sms_service.send_invitation(
                    phone_number=invitee['phone'],
                    event_name=event.name,
                    event_date=event.date,
                    event_code=event.event_code
                )
                
                if message_sid:
                    # Update invitee status if SMS sent successfully
                    invitee['status'] = 'invited'
                    invitee['invited_at'] = now
                else:
                    logging.error(f"Failed to send SMS to {invitee['phone']} for event {event_id}")

            except Exception as e:
                logging.error(f"Error sending invitation to {invitee['phone']}: {str(e)}")

        # Update event with new statuses
        self.update_event(event_id, {"invitees": event.invitees})
    

    def delete_invitee(self, event_id, invitee_id):
        """Remove an invitee from an event"""
        self.events_collection.update_one(
            {"_id": ObjectId(event_id)},
            {"$pull": {"invitees": {"_id": ObjectId(invitee_id)}}}
        )
        
        # After removing invitee, process any pending invitations
        self.process_pending_invitations(event_id)

    def process_pending_invitations(self, event_id):
        """Process any pending invitations that can be sent"""
        event = self.get_event(event_id)
        if not event:
            return False

        # Check and expire old invitations
        if event.check_and_expire_invitations():
            self.update_event(event_id, {"invitees": event.invitees})

        # Get next set of invitees to invite
        next_invitees = event.get_next_invitees()
        if not next_invitees:
            return False

        # Update status and add timestamp for new invites
        now = datetime.utcnow()
        for invitee in next_invitees:
            invitee['status'] = 'invited'
            invitee['invited_at'] = now

        # Update event with new statuses
        self.update_event(event_id, {"invitees": event.invitees})
        return next_invitees

    def process_rsvp(self, phone_number, response_text):
        """Process an RSVP response from an SMS"""
        parts = response_text.strip().upper().split()
        if len(parts) != 2:
            return None
            
        event_code, response = parts
        
        # Find event by code
        event_data = self.events_collection.find_one({"event_code": event_code})
        if not event_data:
            return None
            
        event = Event.from_dict(event_data)
        
        # Find the invitee
        invitee = next((i for i in event.invitees if i['phone'] == phone_number), None)
        if not invitee or invitee['status'] != 'invited':
            return None

        # Process response
        if response == 'YES':
            if not event.can_accept_rsvp(str(invitee['_id'])):
                return 'FULL'
            invitee['status'] = 'YES'
        elif response == 'NO':
            invitee['status'] = 'NO'
        else:
            return None

        invitee['responded_at'] = datetime.utcnow()
        
        # Update the event
        self.update_event(str(event_data['_id']), {"invitees": event.invitees})
        
        # Process any new invitations that can now be sent
        self.process_pending_invitations(str(event_data['_id']))
        
        return response

    def check_expired_invitations(self):
        """Check all events for expired invitations and process new invites"""
        events = self.events_collection.find({})
        for event_data in events:
            try:
                event_id = str(event_data['_id'])
                event = Event.from_dict(event_data)
                
                # Check for expired invitations
                if event.check_and_expire_invitations():
                    self.update_event(event_id, {"invitees": event.invitees})
                    # Process new invitations if any invites expired
                    self.process_pending_invitations(event_id)
                    
            except Exception as e:
                print(f"Error processing event {event_data.get('_id')}: {str(e)}")