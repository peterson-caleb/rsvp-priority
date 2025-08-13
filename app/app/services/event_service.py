# app/services/event_service.py
from datetime import datetime, timedelta
from bson import ObjectId
from ..models.event import Event
import logging
from logging.handlers import RotatingFileHandler
import os
import pytz
import secrets

class EventService:
    def __init__(self, db, sms_service=None, invitation_expiry_hours=24):
        self.db = db
        self.events_collection = db['events']
        self.sms_service = sms_service
        self.invitation_expiry_hours = invitation_expiry_hours
        self.timezone = pytz.timezone('UTC')
        
        self.logger = self._setup_logging()

    def _setup_logging(self):
        logger = logging.getLogger('event_service')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            if not os.path.exists('logs'):
                os.makedirs('logs')

            file_handler = RotatingFileHandler('logs/event_service.log', maxBytes=1024 * 1024, backupCount=5)
            console_handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
        return logger

    def get_current_time(self):
        return datetime.now(self.timezone)

    def check_expired_invitations(self):
        self.logger.info("Starting expired invitations check")
        events = self.events_collection.find({})
        for event_data in events:
            try:
                event = Event.from_dict(event_data)
                if self._check_event_expired_invitations(event):
                    self.update_event(str(event_data['_id']), {"invitees": event.invitees})
            except Exception as e:
                self.logger.error(f"Error checking expiration for event {event_data.get('_id')}: {str(e)}")

    def _check_event_expired_invitations(self, event):
        now = self.get_current_time()
        updated = False
        for invitee in event.invitees:
            if invitee.get('status') == 'invited' and 'invited_at' in invitee:
                invited_at = invitee['invited_at'].replace(tzinfo=self.timezone)
                hours_elapsed = (now - invited_at).total_seconds() / 3600
                if hours_elapsed > event.invitation_expiry_hours:
                    self.logger.info(f"Expiring invitation for {invitee.get('phone')} in event {event.event_code}")
                    invitee['status'] = 'EXPIRED'
                    invitee['expired_at'] = now
                    updated = True
        return updated

    def manage_event_capacity(self):
        self.logger.info("Starting event capacity management")
        events = self.events_collection.find({})
        for event_data in events:
            try:
                event = Event.from_dict(event_data)
                available_spots = self._calculate_available_spots(event)
                if available_spots > 0:
                    next_invitees = self._get_next_invitees(event, available_spots)
                    if next_invitees:
                        self._send_invitations(event, next_invitees)
            except Exception as e:
                self.logger.error(f"Error managing capacity for event {event_data.get('_id')}: {str(e)}")

    def _calculate_available_spots(self, event):
        confirmed_count = sum(1 for i in event.invitees if i.get('status') == 'YES')
        invited_count = sum(1 for i in event.invitees if i.get('status') == 'invited')
        return event.capacity - (confirmed_count + invited_count)

    def _get_next_invitees(self, event, limit):
        pending_invitees = [i for i in event.invitees if i.get('status') == 'pending']
        pending_invitees.sort(key=lambda x: x.get('priority', float('inf')))
        return pending_invitees[:limit]

    def _send_invitations(self, event, invitees):
        now = self.get_current_time()
        updates_made = False
        for invitee in invitees:
            try:
                rsvp_token = secrets.token_urlsafe(8)
                invitee_name = invitee.get('name', 'Guest')
                message_sid, status, error_message = self.sms_service.send_invitation(
                    phone_number=invitee['phone'],
                    event_name=event.name,
                    event_date=event.date,
                    invitee_name=invitee_name,
                    rsvp_token=rsvp_token
                )
                invitee['status'] = status
                invitee['invited_at'] = now
                invitee['rsvp_token'] = rsvp_token
                if message_sid: invitee['message_sid'] = message_sid
                if error_message: invitee['error_message'] = error_message
                updates_made = True
                self.logger.info(f"Updated invitee status to {status} for {invitee['phone']}")
            except Exception as e:
                self.logger.error(f"Failed to process invitation for {invitee['phone']}: {str(e)}")
                invitee['status'] = 'ERROR'
                invitee['error_message'] = str(e)
                updates_made = True
        if updates_made:
            self.update_event(str(event._id), {"invitees": event.invitees})

    def send_pending_reminders(self):
        self.logger.info("Starting pending reminder check...")
        now = self.get_current_time()
        events = self.events_collection.find({})
        for event_data in events:
            event = Event.from_dict(event_data)
            updates_made = False
            for invitee in event.invitees:
                if invitee.get('status') == 'invited' and not invitee.get('reminder_sent_at'):
                    invited_at = invitee['invited_at'].replace(tzinfo=self.timezone)
                    hours_since_invited = (now - invited_at).total_seconds() / 3600
                    reminder_threshold = event.invitation_expiry_hours / 2
                    if hours_since_invited >= reminder_threshold:
                        self.logger.info(f"Sending reminder to {invitee['name']} for event {event.event_code}")
                        hours_remaining = round(event.invitation_expiry_hours - hours_since_invited)
                        if hours_remaining <= 0: continue
                        sid, status, err = self.sms_service.send_reminder(
                            phone_number=invitee['phone'],
                            event_name=event.name,
                            expiry_hours=hours_remaining
                        )
                        if status == "SENT":
                            invitee['reminder_sent_at'] = now
                            updates_made = True
                        else:
                            self.logger.error(f"Failed to send reminder to {invitee['phone']}: {err}")
            if updates_made:
                self.update_event(str(event._id), {"invitees": event.invitees})

    def find_event_and_invitee_by_token(self, token):
        event_data = self.events_collection.find_one({"invitees.rsvp_token": token})
        if not event_data: return None, None
        event = Event.from_dict(event_data)
        invitee = next((i for i in event.invitees if i.get("rsvp_token") == token), None)
        return event, invitee

    def process_rsvp_from_url(self, token, response):
        event, invitee = self.find_event_and_invitee_by_token(token)
        if not event or not invitee: return False, "This invitation link is invalid."
        if invitee['status'] not in ['invited', 'ERROR']: return True, "You have already responded."
        response = response.upper()
        if response not in ['YES', 'NO']: return False, "Invalid response provided."
        invitee['status'] = response
        invitee['responded_at'] = self.get_current_time()
        self.update_event(str(event._id), {"invitees": event.invitees})
        return True, f"Thank you! Your response for {event.name} has been recorded."

    def get_event(self, event_id):
        event_data = self.events_collection.find_one({"_id": ObjectId(event_id)})
        return Event.from_dict(event_data) if event_data else None

    def get_events(self):
        return list(self.events_collection.find())

    def create_event(self, event_data):
        event = Event.from_dict(event_data, invitation_expiry_hours=self.invitation_expiry_hours)
        result = self.events_collection.insert_one(event.to_dict())
        return str(result.inserted_id)

    def update_event(self, event_id, event_data):
        self.events_collection.update_one({"_id": ObjectId(event_id)}, {"$set": event_data})
        return self.get_event(event_id)

    def delete_event(self, event_id):
        result = self.events_collection.delete_one({"_id": ObjectId(event_id)})
        return result.deleted_count > 0

    def add_invitees(self, event_id, invitees):
        event = self.get_event(event_id)
        if not event: raise ValueError("Event not found")
        current_phones = {i['phone'] for i in event.invitees}
        start_priority = max([i.get('priority', -1) for i in event.invitees] + [-1]) + 1
        for idx, invitee in enumerate(invitees):
            if invitee['phone'] in current_phones: continue
            new_invitee = {
                "_id": ObjectId(),
                "name": invitee['name'],
                "phone": invitee['phone'],
                "status": "pending",
                "priority": start_priority + idx,
                "added_at": self.get_current_time(),
                "contact_id": str(invitee['_id']) # <-- ADD THIS LINE
            }
            event.invitees.append(new_invitee)
        self.update_event(event_id, {"invitees": event.invitees})
        return event.invitees

    def delete_invitee(self, event_id, invitee_id):
        self.events_collection.update_one({"_id": ObjectId(event_id)}, {"$pull": {"invitees": {"_id": ObjectId(invitee_id)}}})

    def reorder_invitees(self, event_id, invitee_order):
        event = self.get_event(event_id)
        if not event: raise ValueError("Event not found")
        invitees_dict = {str(i['_id']): i for i in event.invitees}
        new_invitees = []
        priority = 0
        for invitee_id in invitee_order:
            if invitee_id in invitees_dict:
                invitee = invitees_dict.pop(invitee_id)
                invitee['priority'] = priority
                new_invitees.append(invitee)
                priority += 1
        for invitee in invitees_dict.values():
            invitee['priority'] = priority
            new_invitees.append(invitee)
            priority += 1
        self.update_event(event_id, {"invitees": new_invitees})
        return new_invitees