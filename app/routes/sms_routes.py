# app/routes/sms_routes.py
from flask import Blueprint, request, current_app
from twilio.twiml.messaging_response import MessagingResponse
from .. import event_service, sms_service
import logging
from datetime import datetime
import json
from logging.handlers import RotatingFileHandler
import os

bp = Blueprint('sms', __name__)

# Configure logging
def setup_sms_logger():
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Create a logger for SMS events
    logger = logging.getLogger('sms_logger')
    logger.setLevel(logging.INFO)

    # Create rotating file handler
    handler = RotatingFileHandler(
        'logs/sms.log',
        maxBytes=10000000,  # 10MB
        backupCount=5
    )
    
    # Create formatter and add it to the handler
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    
    # Add handler to logger if it doesn't already have one
    if not logger.handlers:
        logger.addHandler(handler)
    
    return logger

# Initialize logger
sms_logger = setup_sms_logger()

@bp.route('/sms', methods=['POST'])
def handle_sms():
    # Log incoming request
    request_data = {
        'from_number': request.form.get('From'),
        'to_number': request.form.get('To'),
        'message_body': request.form.get('Body'),
        'message_sid': request.form.get('MessageSid'),
        'timestamp': datetime.utcnow().isoformat(),
    }
    
    sms_logger.info(f"Incoming SMS: {json.dumps(request_data, indent=2)}")
    
    try:
        phone_number = request.form['From']
        message_body = request.form['Body'].strip()
        
        # Log parsed message components
        sms_logger.info(f"Parsed message - Phone: {phone_number}, Content: {message_body}")
        
        # Process the RSVP - now just handles status update
        result = event_service.process_rsvp(phone_number, message_body)
        
        # Log the processing result
        sms_logger.info(f"RSVP Processing Result - Phone: {phone_number}, Result: {result}")
        
        # Send appropriate response
        resp = MessagingResponse()
        if result == 'YES':
            message = "Thank you for your response! You're confirmed for the event."
            sms_logger.info(f"Confirmation sent to {phone_number}")
        elif result == 'NO':
            message = "Thank you for letting us know you can't make it."
            sms_logger.info(f"Decline confirmation sent to {phone_number}")
        else:
            message = "Sorry, we couldn't process your response. Please reply with 'EVENT_CODE YES' or 'EVENT_CODE NO'."
            sms_logger.warning(f"Invalid response from {phone_number}: {message_body}")
            
        resp.message(message)
        return str(resp)
        
    except KeyError as e:
        sms_logger.error(f"Missing required field in SMS webhook: {str(e)}")
        return "Missing required field", 400
        
    except Exception as e:
        sms_logger.error(f"Error processing SMS: {str(e)}", exc_info=True)
        # Send a user-friendly response
        resp = MessagingResponse()
        resp.message("Sorry, we encountered an error processing your response. Please try again later.")
        return str(resp)

# Optional: Add route to view recent logs (protected by admin access)
@bp.route('/sms/logs', methods=['GET'])
def view_logs():
    # This should be protected by authentication and admin check
    try:
        with open('logs/sms.log', 'r') as log_file:
            logs = log_file.readlines()[-100:]  # Get last 100 lines
        return {'logs': logs}
    except Exception as e:
        sms_logger.error(f"Error reading logs: {str(e)}")
        return {'error': 'Unable to read logs'}, 500