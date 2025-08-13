from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging
from datetime import datetime
import os
from collections import deque
import threading

class SMSService:
    def __init__(self, twilio_sid, twilio_auth_token, twilio_phone):
        self.client = Client(twilio_sid, twilio_auth_token)
        self.twilio_phone = twilio_phone
        self.max_messages_per_second = 3
        self.recent_messages = deque(maxlen=100)
        self.lock = threading.Lock()
        self._setup_logging()

    def _setup_logging(self):
        if not os.path.exists('logs'): os.makedirs('logs')
        self.logger = logging.getLogger('sms_service')
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            fh = logging.FileHandler('logs/sms_service.log')
            ch = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            fh.setFormatter(formatter)
            ch.setFormatter(formatter)
            self.logger.addHandler(fh)
            self.logger.addHandler(ch)

    def _check_rate_limits(self):
        now = datetime.now()
        with self.lock:
            recent_count = sum(1 for t in self.recent_messages if (now - t).total_seconds() < 1)
            if recent_count >= self.max_messages_per_second:
                return False, "Per-second rate limit exceeded"
            return True, None

    def _update_rate_limiting_stats(self):
        with self.lock:
            self.recent_messages.append(datetime.now())

    def send_invitation(self, phone_number, event_name, event_date, invitee_name, rsvp_token):
        try:
            is_allowed, reason = self._check_rate_limits()
            if not is_allowed:
                self.logger.warning(f"Rate limit hit for {phone_number}: {reason}")
                return None, "ERROR", reason

            # IMPORTANT: Replace 'your-domain.com' with your actual domain when deploying.
            # For Codespaces, this URL will be generated for you.
            rsvp_url = f"http://127.0.0.1:5000/rsvp/{rsvp_token}"
            message_body = f"{invitee_name} is invited to {event_name} on {event_date}. RSVP: {rsvp_url}"

            message = self.client.messages.create(body=message_body, from_=self.twilio_phone, to=phone_number)
            self._update_rate_limiting_stats()
            self.logger.info(f"Sent invitation to {phone_number} for {event_name}")
            return message.sid, "SENT", None
        except TwilioRestException as e:
            self.logger.error(f"Twilio error for {phone_number}: {e}")
            return None, "ERROR", str(e)
        except Exception as e:
            self.logger.error(f"Unexpected error for {phone_number}: {e}")
            return None, "ERROR", str(e)

    def send_reminder(self, phone_number, event_name, expiry_hours):
        try:
            is_allowed, reason = self._check_rate_limits()
            if not is_allowed:
                self.logger.warning(f"Rate limit hit for reminder to {phone_number}: {reason}")
                return None, "ERROR", reason

            message_text = (f"Reminder for {event_name}. Please respond soon. "
                            f"Your invitation will expire in {expiry_hours} hours "
                            f"and your spot will be offered to the next guest.")
            message = self.client.messages.create(body=message_text, from_=self.twilio_phone, to=phone_number)
            self._update_rate_limiting_stats()
            self.logger.info(f"Sent reminder to {phone_number} for {event_name}")
            return message.sid, "SENT", None
        except Exception as e:
            self.logger.error(f"Unexpected error sending reminder to {phone_number}: {e}")
            return None, "ERROR", str(e)