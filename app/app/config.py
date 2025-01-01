# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key')
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/rsvp-system')
    TWILIO_SID = os.getenv('TWILIO_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE = os.getenv('TWILIO_PHONE')
    BATCH_SIZE = int(os.getenv('DEFAULT_BATCH_SIZE', '10'))
    INVITATION_EXPIRY_HOURS = int(os.getenv('INVITATION_EXPIRY_HOURS', '24'))