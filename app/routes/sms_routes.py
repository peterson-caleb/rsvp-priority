# app/routes/sms_routes.py
from flask import Blueprint, request
from twilio.twiml.messaging_response import MessagingResponse
from .. import event_service, sms_service

bp = Blueprint('sms', __name__)

@bp.route('/sms', methods=['POST'])
def handle_sms():
    phone_number = request.form['From']
    message_body = request.form['Body'].strip().lower()
    
    # Process the RSVP
    result = event_service.process_rsvp(phone_number, message_body)
    
    # Send appropriate response
    resp = MessagingResponse()
    if result == 'FULL':
        resp.message("Sorry, this event is now at full capacity. We'll add you to the waitlist.")
    elif result:
        resp.message("Thank you for your response!")
    else:
        resp.message("Sorry, we couldn't process your response. Please try again.")
    
    return str(resp)