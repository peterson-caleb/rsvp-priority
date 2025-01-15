from datetime import datetime, timedelta
from bson import ObjectId
from ..models.event import Event
import logging
from logging.handlers import RotatingFileHandler
import os
import pytz

class EventService:
    def __init__(self, db, sms_service=None, invitation_expiry_hours=24):
        self.db = db
        self.events_collection = db['events']
        self.sms_service = sms_service
        self.invitation_expiry_hours = invitation_expiry_hours
        self.timezone = pytz.timezone('UTC')  # Default to UTC
        
        # Setup logging
        self.logger = self._setup_logging()

    def _setup_logging(self):
        """Configure logging for event service"""
        logger = logging.getLogger('event_service')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            if not os.path.exists('logs'):
                os.makedirs('logs')

            file_handler = RotatingFileHandler(
                'logs/event_service.log',
                maxBytes=1024 * 1024,  # 1MB
                backupCount=5
            )
            
            console_handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)

            logger.addHandler(file_handler)
            logger.addHandler(console_handler)

        return logger

    def set_timezone(self, timezone_str):
        """Set the timezone for the service"""
        try:
            self.timezone = pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            self.logger.error(f"Invalid timezone: {timezone_str}, defaulting to UTC")
            self.timezone = pytz.UTC

    def get_current_time(self):
        """Get current time in service timezone"""
        return datetime.now(self.timezone)

    def check_expired_invitations(self):
        """Check all events for expired invitations"""
        self.logger.info("Starting expired invitations check")
        events = self.events_collection.find({})
        
        for event_data in events:
            try:
                event_id = str(event_data['_id'])
                event = Event.from_dict(event_data)
                
                updated = self._check_event_expired_invitations(event)
                
                if updated:
                    self.update_event(event_id, {"invitees": event.invitees})
                    
            except Exception as e:
                self.logger.error(f"Error checking expiration for event {event_data.get('_id')}: {str(e)}")

    def _check_event_expired_invitations(self, event):
        """Check single event for expired invitations"""
        now = self.get_current_time()
        updated = False

        for invitee in event.invitees:
            if invitee['status'] not in ['invited', 'ERROR']:
                continue

            if 'invited_at' not in invitee:
                self.logger.warning(f"Found invited status but no invited_at timestamp for invitee in event {event.event_code}")
                continue

            # Convert invited_at to timezone-aware
            invited_at = invitee['invited_at'].replace(tzinfo=self.timezone)
            hours_elapsed = (now - invited_at).total_seconds() / 3600

            if hours_elapsed > event.invitation_expiry_hours:
                self.logger.info(f"Expiring invitation for {invitee.get('phone')} in event {event.event_code}")
                invitee['status'] = 'EXPIRED'
                invitee['expired_at'] = now
                updated = True

            # Retry failed invitations after 1 hour
            elif invitee['status'] == 'ERROR' and hours_elapsed > 1:
                self.logger.info(f"Retrying failed invitation for {invitee.get('phone')} in event {event.event_code}")
                invitee['status'] = 'pending'
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
        invited_count = sum(1 for i in event.invitees if i['status'] == 'invited')
        return event.capacity - (confirmed_count + invited_count)

    def _get_next_invitees(self, event, limit):
        """Get next set of invitees based on priority and available capacity"""
        pending_invitees = [i for i in event.invitees if i['status'] == 'pending']
        # Sort by priority (lower number = higher priority)
        pending_invitees.sort(key=lambda x: x.get('priority', float('inf')))
        return pending_invitees[:limit]

    def _send_invitations(self, event, invitees):
        """Send invitations to specified invitees"""
        now = self.get_current_time()
        updates_made = False

        for invitee in invitees:
            try:
                message_sid, status, error_message = self.sms_service.send_invitation(
                    phone_number=invitee['phone'],
                    event_name=event.name,
                    event_date=event.date,
                    event_code=event.event_code
                )
                
                invitee['status'] = status
                invitee['invited_at'] = now
                
                if message_sid:
                    invitee['message_sid'] = message_sid
                if error_message:
                    invitee['error_message'] = error_message
                    
                updates_made = True
                self.logger.info(f"Updated invitee status to {status} for {invitee['phone']}")
                    
            except Exception as e:
                self.logger.error(f"Failed to send invitation to {invitee['phone']}: {str(e)}")
                invitee['status'] = 'ERROR'
                invitee['error_message'] = str(e)
                updates_made = True

        if updates_made:
            self.update_event(str(event._id), {"invitees": event.invitees})

    def process_rsvp(self, phone_number, response_text):
        """Process RSVP response"""
        parts = response_text.strip().upper().split()
        if len(parts) != 2:
            return None
            
        event_code, response = parts
        
        event_data = self.events_collection.find_one({"event_code": event_code})
        if not event_data:
            return None
            
        event = Event.from_dict(event_data)
        invitee = next((i for i in event.invitees if i['phone'] == phone_number), None)
        
        if not invitee or invitee['status'] != 'invited':
            return None

        if response in ['YES', 'NO']:
            invitee['status'] = response
            invitee['responded_at'] = self.get_current_time()
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
                "added_at": self.get_current_time()
            }
            event.invitees.append(new_invitee)

        self.update_event(event_id, {"invitees": event.invitees})
        return event.invitees

    def delete_invitee(self, event_id, invitee_id):
        """Remove an invitee from an event"""
        self.events_collection.update_one(
            {"_id": ObjectId(event_id)},
            {"$pull": {"invitees": {"_id": ObjectId(invitee_id)}}}
        )

    def update_invitee_priority(self, event_id, invitee_id, new_priority):
        """Update the priority of an invitee"""
        event = self.get_event(event_id)
        if not event:
            raise ValueError("Event not found")

        for invitee in event.invitees:
            if str(invitee['_id']) == invitee_id:
                invitee['priority'] = new_priority
                break

        self.update_event(event_id, {"invitees": event.invitees})

    def reorder_invitees(self, event_id, invitee_order):
        """Reorder invitees based on provided order of invitee IDs"""
        event = self.get_event(event_id)
        if not event:
            raise ValueError("Event not found")

        # Create lookup of current invitees by ID
        invitees_dict = {str(i['_id']): i for i in event.invitees}
        
        # Create new ordered list while preserving invitees not in the order
        new_invitees = []
        priority = 0
        
        # First add invitees in the specified order
        for invitee_id in invitee_order:
            if invitee_id in invitees_dict:
                invitee = invitees_dict[invitee_id]
                invitee['priority'] = priority
                new_invitees.append(invitee)
                del invitees_dict[invitee_id]
                priority += 1
        
        # Then add any remaining invitees
        for invitee in invitees_dict.values():
            invitee['priority'] = priority
            new_invitees.append(invitee)
            priority += 1
        
        self.update_event(event_id, {"invitees": new_invitees})
        return new_invitees