from flask import Flask, render_template
from flask_pymongo import PyMongo
from flask_login import LoginManager, login_required
from .config import Config
import logging

mongo = PyMongo()
login_manager = LoginManager()
event_service = None
contact_service = None
sms_service = None
user_service = None
registration_code_service = None
task_scheduler = None

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Setup basic app logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize MongoDB
    mongo.init_app(app)

    # Initialize Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # Initialize services
    global event_service, contact_service, sms_service, user_service, registration_code_service, task_scheduler
    from .services.event_service import EventService
    from .services.contact_service import ContactService
    from .services.sms_service import SMSService
    from .services.user_service import UserService
    from .services.registration_code_service import RegistrationCodeService
    from .scheduler import TaskScheduler
    
    # Initialize SMS service first since EventService needs it
    sms_service = SMSService(
        app.config['TWILIO_SID'],
        app.config['TWILIO_AUTH_TOKEN'],
        app.config['TWILIO_PHONE']
    )
    
    # Initialize services
    event_service = EventService(
        db=mongo.db,
        sms_service=sms_service,
        invitation_expiry_hours=app.config['INVITATION_EXPIRY_HOURS']
    )
    contact_service = ContactService(mongo.db)
    user_service = UserService(mongo.db)
    registration_code_service = RegistrationCodeService(mongo.db)

    # Initialize scheduler with app context
    if app.config.get('SCHEDULER_ENABLED', True):
        task_scheduler = TaskScheduler.get_instance()
        task_scheduler.init_app(app, event_service, sms_service)
        app.logger.info('Task scheduler initialized and started')

    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return user_service.get_user(user_id)

    # Register blueprints
    from .routes.event_routes import bp as event_bp
    from .routes.contact_routes import bp as contact_bp
    from .routes.sms_routes import bp as sms_bp
    from .routes.auth_routes import bp as auth_bp
    
    app.register_blueprint(event_bp)
    app.register_blueprint(contact_bp)
    app.register_blueprint(sms_bp)
    app.register_blueprint(auth_bp)

    @app.route('/')
    @login_required
    def home():
        return render_template('home.html')

    @app.errorhandler(401)
    def unauthorized(error):
        return render_template('errors/401.html'), 401

    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404

    return app