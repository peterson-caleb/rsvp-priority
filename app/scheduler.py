# app/scheduler.py
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
        """Start the scheduler"""
        if not self.is_running:
            try:
                self.logger.info("Starting scheduler...")
                
                # Log configuration details
                self.logger.info("Scheduler configuration:")
                self.logger.info("- Check interval: 1 minutes")
                
                # Add job for checking expired invitations
                self.scheduler.add_job(
                    func=self._check_expired_invitations,
                    trigger=IntervalTrigger(minutes=1),
                    id='check_expired_invitations',
                    name='Check expired invitations'
                )

                self.scheduler.start()
                self.is_running = True
                self.logger.info("Scheduler started successfully")
                
                # Log next run time
                jobs = self.scheduler.get_jobs()
                for job in jobs:
                    self.logger.info(f"Job '{job.name}' next run time: {job.next_run_time}")
                
            except Exception as e:
                self.logger.error(f"Error starting scheduler: {str(e)}", exc_info=True)
                self.is_running = False

    def shutdown(self):
        """Shutdown the scheduler"""
        if self.is_running:
            try:
                self.logger.info("Shutting down scheduler...")
                self.scheduler.shutdown()
                self.is_running = False
                self.logger.info("Scheduler shutdown successfully")
            except Exception as e:
                self.logger.error(f"Error shutting down scheduler: {str(e)}", exc_info=True)

    def _check_expired_invitations(self):
        """Check for expired invitations across all events"""
        try:
            with self.app.app_context():
                start_time = datetime.now()
                self.logger.info("Starting expired invitations check...")
                
                # Get count of events before processing
                events_before = len(list(self.event_service.events_collection.find()))
                self.logger.info(f"Found {events_before} events to check")
                
                # Process expired invitations
                self.event_service.check_expired_invitations()
                
                # Calculate processing time
                end_time = datetime.now()
                processing_time = (end_time - start_time).total_seconds()
                
                self.logger.info(f"Completed expired invitations check in {processing_time:.2f} seconds")
                
                # Log next scheduled run
                next_run = None
                for job in self.scheduler.get_jobs():
                    if job.id == 'check_expired_invitations':
                        next_run = job.next_run_time
                        break
                
                if next_run:
                    self.logger.info(f"Next check scheduled for: {next_run}")
                    
        except Exception as e:
            self.logger.error(f"Error in _check_expired_invitations: {str(e)}", exc_info=True)