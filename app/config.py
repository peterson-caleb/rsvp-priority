# app/config.py
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
    
    # RSVP System Configuration
    DEFAULT_BATCH_SIZE = int(os.getenv('DEFAULT_BATCH_SIZE', '10'))
    INVITATION_EXPIRY_HOURS = float(os.getenv('INVITATION_EXPIRY_HOURS', '24'))
    AUTO_PROGRESS_BATCHES = os.getenv('AUTO_PROGRESS_BATCHES', 'true').lower() == 'true'
    WAITLIST_ENABLED = os.getenv('WAITLIST_ENABLED', 'true').lower() == 'true'
    
    # Scheduler Configuration
    SCHEDULER_ENABLED = os.getenv('SCHEDULER_ENABLED', 'true').lower() == 'true'
    EXPIRY_CHECK_INTERVAL = int(os.getenv('EXPIRY_CHECK_INTERVAL', '1'))  # minutes
    CAPACITY_CHECK_INTERVAL = int(os.getenv('CAPACITY_CHECK_INTERVAL', '1'))  # minutes
    REMINDER_CHECK_INTERVAL = int(os.getenv('REMINDER_CHECK_INTERVAL', '30')) # minutes
    
    # Logging configuration
    SMS_LOG_FILE = 'logs/sms.log'
    SMS_LOG_LEVEL = 'INFO'
    SMS_LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
    SMS_LOG_MAX_BYTES = 10000000  # 10MB
    SMS_LOG_BACKUP_COUNT = 5