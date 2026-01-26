#!/usr/bin/env python3
"""
GPIO Schedule Executor
Runs scheduled operations on GPIO pins based on configurations
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path
import threading

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    print("⚠️  RPi.GPIO not available - running in simulation mode")

from pin_config import PinConfigManager, ScheduleType


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GPIOScheduler:
    """Execute scheduled operations on GPIO pins"""
    
    def __init__(self, config_dir: str = "/home/monkphx/harvestpilot-raspserver/config"):
        self.config_manager = PinConfigManager(config_dir=config_dir)
        self.running = False
        self.active_pwm = {}  # {gpio_number: PWM object}
        self.schedule_states = {}  # Track last run times
        
    def setup_gpio(self):
        """Initialize GPIO pins"""
        if not GPIO_AVAILABLE:
            logger.warning("GPIO not available - skipping GPIO setup")
            return
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        config = self.config_manager.load_config()
        if not config:
            logger.error("No GPIO configuration found")
            return
        
        # Setup each pin
        for pin in config.pins:
            if not pin.enabled:
                continue
            
            logger.info(f"Setting up GPIO {pin.gpio_number} ({pin.name})")
            
            if pin.mode == "OUTPUT" or pin.mode == "PWM":
                GPIO.setup(pin.gpio_number, GPIO.OUT)
                
                if pin.mode == "PWM" and pin.pwm_frequency:
                    pwm = GPIO.PWM(pin.gpio_number, pin.pwm_frequency)
                    pwm.start(0)  # Start at 0% duty cycle
                    self.active_pwm[pin.gpio_number] = pwm
            
            elif pin.mode == "INPUT" or pin.mode == "SENSOR":
                pull_mode = GPIO.PUD_UP if pin.pull_up else GPIO.PUD_DOWN
                GPIO.setup(pin.gpio_number, GPIO.IN, pull_up_down=pull_mode)
    
    def cleanup_gpio(self):
        """Cleanup GPIO pins"""
        if not GPIO_AVAILABLE:
            return
        
        # Stop all PWM
        for pwm in self.active_pwm.values():
            pwm.stop()
        
        self.active_pwm.clear()
        GPIO.cleanup()
        logger.info("GPIO cleaned up")
    
    def is_time_in_range(self, start_time: str, end_time: str) -> bool:
        """Check if current time is between start and end times"""
        now = datetime.now().time()
        
        # Parse times
        start_parts = start_time.split(":")
        end_parts = end_time.split(":")
        
        start = datetime.strptime(f"{start_parts[0]}:{start_parts[1]}", "%H:%M").time()
        end = datetime.strptime(f"{end_parts[0]}:{end_parts[1]}", "%H:%M").time()
        
        if start <= end:
            # Same day (e.g., 06:00 to 22:00)
            return start <= now <= end
        else:
            # Crosses midnight (e.g., 22:00 to 06:00)
            return now >= start or now <= end
    
    def should_run_today(self, days_of_week: Optional[list]) -> bool:
        """Check if schedule should run today"""
        if not days_of_week:
            return True  # Run every day
        
        today = datetime.now().weekday()  # 0=Monday, 6=Sunday
        return today in days_of_week
    
    def should_run_schedule(self, schedule, last_run: Optional[datetime]) -> bool:
        """Determine if a schedule should run now"""
        if not schedule.enabled:
            return False
        
        # Check day of week
        if not self.should_run_today(schedule.days_of_week):
            return False
        
        # Check time-based schedules
        if schedule.start_time and schedule.end_time:
            return self.is_time_in_range(schedule.start_time, schedule.end_time)
        
        # Check interval-based schedules
        if schedule.interval_seconds:
            if not last_run:
                return True  # First run
            
            elapsed = (datetime.now() - last_run).total_seconds()
            return elapsed >= schedule.interval_seconds
        
        # If only start_time is set (one-time daily trigger)
        if schedule.start_time and not schedule.end_time:
            now = datetime.now().time()
            target = datetime.strptime(schedule.start_time, "%H:%M").time()
            
            # Check if we're within 1 minute of target time and haven't run today
            if last_run:
                last_run_date = last_run.date()
                today = datetime.now().date()
                if last_run_date == today:
                    return False  # Already ran today
            
            # Within 1 minute window
            time_diff = abs((datetime.combine(datetime.today(), now) - 
                           datetime.combine(datetime.today(), target)).total_seconds())
            return time_diff < 60
        
        return False
    
    def execute_pwm_cycle(self, gpio_number: int, schedule):
        """Execute PWM cycle schedule"""
        if gpio_number not in self.active_pwm:
            logger.warning(f"No PWM configured for GPIO {gpio_number}")
            return
        
        pwm = self.active_pwm[gpio_number]
        duty_cycle = schedule.pwm_duty_start or 0
        
        logger.info(f"PWM cycle on GPIO {gpio_number}: {duty_cycle}% duty")
        pwm.ChangeDutyCycle(duty_cycle)
        
        # If duration is specified, turn off after duration
        if schedule.duration_seconds:
            def turn_off():
                time.sleep(schedule.duration_seconds)
                pwm.ChangeDutyCycle(0)
                logger.info(f"PWM cycle completed on GPIO {gpio_number}")
            
            threading.Thread(target=turn_off, daemon=True).start()
    
    def execute_pwm_fade(self, gpio_number: int, schedule):
        """Execute PWM fade schedule"""
        if gpio_number not in self.active_pwm:
            logger.warning(f"No PWM configured for GPIO {gpio_number}")
            return
        
        pwm = self.active_pwm[gpio_number]
        start_duty = schedule.pwm_duty_start or 0
        end_duty = schedule.pwm_duty_end or 100
        fade_duration = schedule.pwm_fade_duration or 60
        
        logger.info(f"PWM fade on GPIO {gpio_number}: {start_duty}% → {end_duty}% over {fade_duration}s")
        
        def fade():
            steps = 100  # Number of steps in fade
            step_delay = fade_duration / steps
            duty_range = end_duty - start_duty
            
            for i in range(steps + 1):
                current_duty = start_duty + (duty_range * i / steps)
                pwm.ChangeDutyCycle(current_duty)
                time.sleep(step_delay)
            
            logger.info(f"PWM fade completed on GPIO {gpio_number}")
        
        threading.Thread(target=fade, daemon=True).start()
    
    def execute_sensor_read(self, gpio_number: int, schedule):
        """Execute sensor read schedule"""
        logger.info(f"Reading sensor on GPIO {gpio_number}")
        
        if not GPIO_AVAILABLE:
            logger.info("Simulated sensor read (no GPIO)")
            return
        
        # Read the pin
        value = GPIO.input(gpio_number)
        logger.info(f"Sensor GPIO {gpio_number} value: {value}")
        
        # Store reading if enabled
        if schedule.store_readings:
            # TODO: Store to database
            logger.info(f"Storing sensor reading: GPIO {gpio_number} = {value}")
    
    def execute_schedule(self, gpio_number: int, schedule):
        """Execute a schedule based on its type"""
        logger.info(f"Executing schedule {schedule.schedule_id} on GPIO {gpio_number}")
        
        schedule_type = schedule.schedule_type
        
        if schedule_type == ScheduleType.PWM_CYCLE.value:
            self.execute_pwm_cycle(gpio_number, schedule)
        
        elif schedule_type == ScheduleType.PWM_FADE.value:
            self.execute_pwm_fade(gpio_number, schedule)
        
        elif schedule_type == ScheduleType.SENSOR_READ.value:
            self.execute_sensor_read(gpio_number, schedule)
        
        elif schedule_type == ScheduleType.DIGITAL_TOGGLE.value:
            if GPIO_AVAILABLE:
                state = schedule.digital_state if schedule.digital_state is not None else True
                GPIO.output(gpio_number, GPIO.HIGH if state else GPIO.LOW)
                logger.info(f"Digital output GPIO {gpio_number} set to {state}")
        
        else:
            logger.warning(f"Unknown schedule type: {schedule_type}")
        
        # Update last run time
        schedule.last_run_at = datetime.now().isoformat()
        self.schedule_states[schedule.schedule_id] = datetime.now()
    
    def run_cycle(self):
        """Run one scheduling cycle (check and execute schedules)"""
        config = self.config_manager.load_config()
        if not config:
            return
        
        for pin in config.pins:
            if not pin.enabled:
                continue
            
            if not hasattr(pin, 'schedules') or not pin.schedules:
                continue
            
            for schedule in pin.schedules:
                last_run = self.schedule_states.get(schedule.schedule_id)
                
                if self.should_run_schedule(schedule, last_run):
                    self.execute_schedule(pin.gpio_number, schedule)
    
    def start(self, check_interval: int = 10):
        """Start the scheduler
        
        Args:
            check_interval: Seconds between schedule checks (default 10)
        """
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        logger.info("Starting GPIO scheduler...")
        self.setup_gpio()
        self.running = True
        
        try:
            while self.running:
                self.run_cycle()
                time.sleep(check_interval)
        except KeyboardInterrupt:
            logger.info("Scheduler interrupted by user")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the scheduler"""
        logger.info("Stopping GPIO scheduler...")
        self.running = False
        self.cleanup_gpio()
        logger.info("Scheduler stopped")


def main():
    """Main entry point"""
    import sys
    
    config_dir = "/home/monkphx/harvestpilot-raspserver/config"
    if len(sys.argv) > 1:
        config_dir = sys.argv[1]
    
    logger.info(f"Starting scheduler with config from: {config_dir}")
    
    scheduler = GPIOScheduler(config_dir=config_dir)
    
    # Start scheduler (checks every 10 seconds)
    scheduler.start(check_interval=10)


if __name__ == "__main__":
    main()
