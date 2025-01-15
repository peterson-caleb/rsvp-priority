from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging
from datetime import datetime, timedelta
import os
from collections import deque
import threading

class SMSService:
    def __init__(self, twilio_sid, twilio_auth_token, twilio_phone):
        self.client = Client(twilio_sid, twilio_auth_token)
        self.twilio_phone = twilio_phone
        
        # Rate limiting settings
        self.max_messages_per_day = 100  # Twilio's default limit
        self.max_messages_per_second = 3   # Conservative rate limit
        
        # Initialize rate limiting trackers
        self.daily_message_count = 0
        self.daily_reset_time = datetime.now()
        self.recent_messages = deque(maxlen=100)  # Track recent message timestamps
        self.lock = threading.Lock()  # Thread-safe counter updates
        
        # Setup logging
        self._setup_logging()
        
    def _setup_logging(self):
        """Configure logging for SMS service"""
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        self.logger = logging.getLogger('sms_service')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            # File handler for SMS service logs
            file_handler = logging.FileHandler('logs/sms_service.log')
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            )
            self.logger.addHandler(file_handler)
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            )
            self.logger.addHandler(console_handler)

    def _check_rate_limits(self):
        """
        Check if we're within rate limits
        Returns: (bool, str) - (is_allowed, reason_if_not_allowed)
        """
        now = datetime.now()
        
        with self.lock:
            # Reset daily counter if needed
            if (now - self.daily_reset_time).days >= 1:
                self.daily_message_count = 0
                self.daily_reset_time = now
            
            # Check daily limit
            if self.daily_message_count >= self.max_messages_per_day:
                return False, "Daily message limit exceeded"
            
            # Check per-second rate limit
            recent_count = sum(1 for t in self.recent_messages 
                             if (now - t).total_seconds() < 1)
            if recent_count >= self.max_messages_per_second:
                return False, "Per-second rate limit exceeded"
            
            return True, None

    def _update_rate_limiting_stats(self):
        """Update rate limiting counters after successful send"""
        now = datetime.now()
        with self.lock:
            self.daily_message_count += 1
            self.recent_messages.append(now)

    def send_invitation(self, phone_number, event_name, event_date, event_code):
        """
        Send an invitation SMS with rate limiting and error handling
        Returns: (message_sid, status, error_message)
        """
        try:
            # Check rate limits
            is_allowed, limit_reason = self._check_rate_limits()
            if not is_allowed:
                self.logger.warning(f"Rate limit prevented sending to {phone_number}: {limit_reason}")
                return None, "ERROR", limit_reason
            
            # Send message
            message = self.client.messages.create(
                body=f"You're invited to {event_name} on {event_date}! "
                     f"Reply '{event_code} YES' to accept or '{event_code} NO' to decline.",
                from_=self.twilio_phone,
                to=phone_number
            )
            
            # Update rate limiting stats
            self._update_rate_limiting_stats()
            
            self.logger.info(f"Successfully sent invitation to {phone_number} for {event_name}")
            return message.sid, "SENT", None
            
        except TwilioRestException as e:
            error_msg = f"Twilio error sending SMS to {phone_number}: {str(e)}"
            self.logger.error(error_msg)
            
            # Categorize common Twilio errors
            if e.code == 21610:  # Invalid phone number
                return None, "ERROR", "Invalid phone number"
            elif e.code == 21611:  # Phone number incapable of receiving SMS
                return None, "ERROR", "Phone cannot receive SMS"
            elif e.code == 21612:  # Too many messages to this number
                return None, "ERROR", "Too many messages to this number"
            else:
                return None, "ERROR", f"Twilio error: {str(e)}"
                
        except Exception as e:
            error_msg = f"Unexpected error sending SMS to {phone_number}: {str(e)}"
            self.logger.error(error_msg)
            return None, "ERROR", f"Unexpected error: {str(e)}"

    def send_confirmation(self, phone_number, event_name, status):
        """
        Send a confirmation SMS with rate limiting and error handling
        Returns: (bool, error_message)
        """
        try:
            # Check rate limits
            is_allowed, limit_reason = self._check_rate_limits()
            if not is_allowed:
                self.logger.warning(f"Rate limit prevented confirmation to {phone_number}: {limit_reason}")
                return False, limit_reason

            # Prepare message based on status
            if status == 'YES':
                message_text = f"Great! You're confirmed for {event_name}. We'll send you more details soon."
            elif status == 'NO':
                message_text = f"Thanks for letting us know you can't make it to {event_name}."
            elif status == 'FULL':
                message_text = f"Sorry, {event_name} is now at full capacity. We'll add you to the waitlist."
            else:
                message_text = "Thanks for your response!"

            # Send message
            self.client.messages.create(
                body=message_text,
                from_=self.twilio_phone,
                to=phone_number
            )
            
            # Update rate limiting stats
            self._update_rate_limiting_stats()
            
            self.logger.info(f"Successfully sent confirmation to {phone_number} for {event_name}")
            return True, None
            
        except TwilioRestException as e:
            error_msg = f"Twilio error sending confirmation to {phone_number}: {str(e)}"
            self.logger.error(error_msg)
            return False, str(e)
            
        except Exception as e:
            error_msg = f"Unexpected error sending confirmation to {phone_number}: {str(e)}"
            self.logger.error(error_msg)
            return False, str(e)