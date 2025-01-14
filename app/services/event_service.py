# app/services/event_service.py
from datetime import datetime, timedelta
from bson import ObjectId
from ..models.event import Event
import logging
from logging.handlers import RotatingFileHandler
import os

class EventService:
    def __init__(self, db, sms_service=None, invitation_expiry_hours=24):
        self.db = db
        self.events_collection = db['events']
        self.sms_service = sms_service
        self.invitation_expiry_hours = invitation_expiry_hours
        
        # Setup logging
        self.logger = logging.getLogger('event_service')
        self.logger.setLevel(logging.INFO)

        # Create handlers if they don't exist
        if not self.logger.handlers:
            # Create logs directory if it doesn't exist
            if not os.path.exists('logs'):
                os.makedirs('logs')

            # File handler
            file_handler = RotatingFileHandler(
                'logs/event_service.log',
                maxBytes=1024 * 1024,  # 1MB
                backupCount=5
            )

            # Console handler
            console_handler = logging.StreamHandler()

            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)

            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def check_expired_invitations(self):
        """Check all events for expired invitations"""
        self.logger.info("Starting expired invitations check")
        events = self.events_collection.find({})
        
        for event_data in events:
            try:
                event_id = str(event_data['_id'])
                event = Event.from_dict(event_data)
                
                # Check for expired invitations
                updated = self._check_event_expired_invitations(event)
                
                if updated:
                    # Only update database if changes were made
                    self.update_event(event_id, {"invitees": event.invitees})
                    
            except Exception as e:
                self.logger.error(f"Error checking expiration for event {event_data.get('_id')}: {str(e)}")

    def _check_event_expired_invitations(self, event):
        """
        Check single event for expired invitations.
        Moved from Event model to service layer.
        """
        now = datetime.utcnow()
        updated = False

        for invitee in event.invitees:
            if invitee['status'] != 'invited':
                continue

            if 'invited_at' not in invitee:
                self.logger.warning(f"Found invited status but no invited_at timestamp for invitee in event {event.event_code}")
                continue

            hours_elapsed = (now - invitee['invited_at']).total_seconds() / 3600
            if hours_elapsed > event.invitation_expiry_hours:
                self.logger.info(f"Expiring invitation for {invitee.get('phone')} in event {event.event_code}")
                invitee['status'] = 'EXPIRED'
                invitee['expired_at'] = now
                updated = True

        return updated

    def manage_event_capacity(self):
        """Check all events for available capacity and send invitations"""
        self.logger.info("Starting event capacity management")
        events = self.events_collection.find({})
        
        for event_data in events:
            try:
                event_id = str(event_data['_id'])
                event = Event.from_dict(event_data)
                
                available_spots = self._calculate_available_spots(event)
                if available_spots > 0:
                    next_invitees = self._get_next_invitees(event, available_spots)
                    self._send_invitations(event, next_invitees)
                    
            except Exception as e:
                self.logger.error(f"Error managing capacity for event {event_data.get('_id')}: {str(e)}")

    def _calculate_available_spots(self, event):
        """Calculate available spots in an event"""
        confirmed_count = sum(1 for i in event.invitees if i['status'] == 'YES')
        return event.capacity - confirmed_count

    def _get_next_invitees(self, event, limit):
        """Get next set of invitees based on available capacity"""
        return [i for i in event.invitees if i['status'] == 'pending'][:limit]

    def _send_invitations(self, event, invitees):
        """Send invitations to specified invitees"""
        now = datetime.utcnow()
        updates_made = False

        for invitee in invitees:
            try:
                message_sid = self.sms_service.send_invitation(
                    phone_number=invitee['phone'],
                    event_name=event.name,
                    event_date=event.date,
                    event_code=event.event_code
                )
                
                if message_sid:
                    invitee['status'] = 'invited'
                    invitee['invited_at'] = now
                    invitee['message_sid'] = message_sid
                    updates_made = True
                    self.logger.info(f"Sent invitation to {invitee['phone']} for event {event.event_code}")
                    
            except Exception as e:
                self.logger.error(f"Failed to send invitation to {invitee['phone']}: {str(e)}")

        if updates_made:
            self.update_event(str(event._id), {"invitees": event.invitees})

    def process_rsvp(self, phone_number, response_text):
        """Process RSVP response - now only handles the response update"""
        parts = response_text.strip().upper().split()
        if len(parts) != 2:
            return None
            
        event_code, response = parts
        
        # Find event and invitee
        event_data = self.events_collection.find_one({"event_code": event_code})
        if not event_data:
            return None
            
        event = Event.from_dict(event_data)
        invitee = next((i for i in event.invitees if i['phone'] == phone_number), None)
        
        if not invitee or invitee['status'] != 'invited':
            return None

        # Just update the RSVP status
        if response in ['YES', 'NO']:
            invitee['status'] = response
            invitee['responded_at'] = datetime.utcnow()
            self.update_event(str(event_data['_id']), {"invitees": event.invitees})
            return response

        return None
    
    def get_event(self, event_id):
        """Get a single event by ID"""
        event_data = self.events_collection.find_one({"_id": ObjectId(event_id)})
        return Event.from_dict(event_data) if event_data else None

    def get_events(self):
        """Get all events"""
        return list(self.events_collection.find())

    def create_event(self, event_data):
        """Create a new event"""
        event = Event.from_dict(event_data, invitation_expiry_hours=self.invitation_expiry_hours)
        result = self.events_collection.insert_one(event.to_dict())
        return str(result.inserted_id)

    def update_event(self, event_id, event_data):
        """Update an event"""
        result = self.events_collection.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": event_data}
        )
        return self.get_event(event_id)

    def delete_event(self, event_id):
        """Delete an event"""
        result = self.events_collection.delete_one({"_id": ObjectId(event_id)})
        return result.deleted_count > 0

    def add_invitees(self, event_id, invitees):
        """Add new invitees to an event"""
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
                "status": "pending",
                "priority": start_priority + idx,
                "added_at": datetime.utcnow()
            }
            event.invitees.append(new_invitee)

        # Update event with new invitees
        self.update_event(event_id, {"invitees": event.invitees})
        return event.invitees

    def delete_invitee(self, event_id, invitee_id):
        """Remove an invitee from an event"""
        self.events_collection.update_one(
            {"_id": ObjectId(event_id)},
            {"$pull": {"invitees": {"_id": ObjectId(invitee_id)}}}
        )