# app/services/sms_service.py
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging

class SMSService:
    def __init__(self, twilio_sid, twilio_auth_token, twilio_phone):
        self.client = Client(twilio_sid, twilio_auth_token)
        self.twilio_phone = twilio_phone

    def send_invitation(self, phone_number, event_name, event_date, event_code):
        try:
            message = self.client.messages.create(
                body=f"You're invited to {event_name} on {event_date}! "
                     f"Reply '{event_code} YES' to accept or '{event_code} NO' to decline.",
                from_=self.twilio_phone,
                to=phone_number
            )
            return message.sid
        except TwilioRestException as e:
            logging.error(f"Error sending SMS to {phone_number}: {str(e)}")
            return None

    def send_confirmation(self, phone_number, event_name, status):
        try:
            if status == 'YES':
                message = f"Great! You're confirmed for {event_name}. We'll send you more details soon."
            elif status == 'NO':
                message = f"Thanks for letting us know you can't make it to {event_name}."
            elif status == 'FULL':
                message = f"Sorry, {event_name} is now at full capacity. We'll add you to the waitlist."
            else:
                message = "Thanks for your response!"

            self.client.messages.create(
                body=message,
                from_=self.twilio_phone,
                to=phone_number
            )
            return True
        except TwilioRestException:
            return False