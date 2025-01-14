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