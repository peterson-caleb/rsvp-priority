from flask import Flask, render_template
from flask_pymongo import PyMongo
from .config import Config

mongo = PyMongo()
event_service = None
contact_service = None
sms_service = None

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize MongoDB
    mongo.init_app(app)

    # Initialize services
    global event_service, contact_service, sms_service
    from .services.event_service import EventService
    from .services.contact_service import ContactService
    from .services.sms_service import SMSService
    
    event_service = EventService(mongo.db)
    contact_service = ContactService(mongo.db)
    sms_service = SMSService(
        app.config['TWILIO_SID'],
        app.config['TWILIO_AUTH_TOKEN'],
        app.config['TWILIO_PHONE']
    )

    # Register blueprints
    from .routes.event_routes import bp as event_bp
    from .routes.contact_routes import bp as contact_bp
    from .routes.sms_routes import bp as sms_bp
    
    app.register_blueprint(event_bp)
    app.register_blueprint(contact_bp)
    app.register_blueprint(sms_bp)

    @app.route('/')
    def home():
        return render_template('home.html')

    return app