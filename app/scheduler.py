from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from flask import current_app
import logging
import atexit
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

class TaskScheduler:
    _instance = None
    
    def __init__(self, app=None, event_service=None, sms_service=None):
        if not TaskScheduler._instance:
            self.event_service = event_service
            self.sms_service = sms_service
            self.app = app
            self.scheduler = BackgroundScheduler()
            self.is_running = False
            TaskScheduler._instance = self
            
            # Setup logging
            self._setup_logging()
            
            # Register the shutdown function
            atexit.register(self.shutdown)
            
            self.logger.info("TaskScheduler initialized")

    def _setup_logging(self):
        """Setup logging configuration"""
        # Create logs directory if it doesn't exist
        if not os.path.exists('logs'):
            os.makedirs('logs')

        # Create a logger
        self.logger = logging.getLogger('scheduler')
        self.logger.setLevel(logging.INFO)

        # Create rotating file handler
        file_handler = RotatingFileHandler(
            'logs/scheduler.log',
            maxBytes=1024 * 1024,  # 1MB
            backupCount=5
        )

        # Create console handler
        console_handler = logging.StreamHandler()

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers to logger if they haven't been added already
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    @classmethod
    def get_instance(cls):
        """Get or create singleton instance"""
        if not cls._instance:
            cls._instance = TaskScheduler()
        return cls._instance

    def init_app(self, app, event_service, sms_service):
        """Initialize with Flask app"""
        self.logger.info("Initializing scheduler with Flask app")
        self.app = app
        self.event_service = event_service
        self.sms_service = sms_service
        
        if not self.is_running:
            self.start()

    def start(self):
        """Start the scheduler with configurable intervals"""
        if not self.is_running:
            try:
                self.logger.info("Starting scheduler...")
                
                # Get intervals from config
                expiry_interval = self.app.config.get('EXPIRY_CHECK_INTERVAL', 1)
                capacity_interval = self.app.config.get('CAPACITY_CHECK_INTERVAL', 1)
                
                # Log configuration
                self.logger.info(f"Configured intervals - Expiry: {expiry_interval}min, "
                               f"Capacity: {capacity_interval}min")
                
                # Add job for checking expired invitations
                self.scheduler.add_job(
                    func=self._check_expired_invitations_job,
                    trigger=IntervalTrigger(minutes=expiry_interval),
                    id='check_expired_invitations',
                    name='Check expired invitations'
                )

                # Add separate job for managing event capacity
                self.scheduler.add_job(
                    func=self._manage_event_capacity_job,
                    trigger=IntervalTrigger(minutes=capacity_interval),
                    id='manage_event_capacity',
                    name='Manage event capacity'
                )

                self.scheduler.start()
                self.is_running = True
                self.logger.info("Scheduler started successfully")
                
                # Log next run times
                self._log_next_run_times()
                
            except Exception as e:
                self.logger.error(f"Error starting scheduler: {str(e)}", exc_info=True)
                self.is_running = False

    def _check_expired_invitations_job(self):
        """Job that only handles checking and marking expired invitations"""
        try:
            with self.app.app_context():
                self.logger.info("Starting expired invitations check...")
                self.event_service.check_expired_invitations()
                self.logger.info("Completed expired invitations check")
        except Exception as e:
            self.logger.error(f"Error in check_expired_invitations_job: {str(e)}", exc_info=True)

    def _manage_event_capacity_job(self):
        """Job that handles checking capacity and sending new invitations"""
        try:
            with self.app.app_context():
                self.logger.info("Starting event capacity management...")
                self.event_service.manage_event_capacity()
                self.logger.info("Completed event capacity management")
        except Exception as e:
            self.logger.error(f"Error in manage_event_capacity_job: {str(e)}", exc_info=True)

    def _log_next_run_times(self):
        """Helper method to log next scheduled run times"""
        jobs = self.scheduler.get_jobs()
        for job in jobs:
            self.logger.info(f"Job '{job.name}' next run time: {job.next_run_time}")

    def shutdown(self):
        """Shutdown the scheduler"""
        if self.is_running:
            try:
                self.logger.info("Shutting down scheduler...")
                self.scheduler.shutdown()
                self.is_running = False
                self.logger.info("Scheduler shutdown successfully")
            except Exception as e:
                self.logger.error(f"Error shutting down scheduler: {str(e)}")