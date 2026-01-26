#!/usr/bin/env python3
"""
GPIO Scheduling Examples
Demonstrates how to schedule PWM cycles and sensor reads on any GPIO pin
"""

from pin_config import PinConfigManager, ScheduleType


def example_1_light_schedule():
    """Example 1: Schedule lights to turn on at 6 AM and off at 10 PM"""
    print("\n" + "="*70)
    print("Example 1: Daily Light Schedule (6 AM - 10 PM)")
    print("="*70)
    
    manager = PinConfigManager()
    
    # Create PWM cycle schedule for light (GPIO 18)
    # Lights on at 6 AM (06:00), off at 10 PM (22:00) at 80% brightness
    manager.create_pwm_cycle_schedule(
        gpio_number=18,
        start_time="06:00",
        end_time="22:00",
        pwm_duty=80,
        description="Daily grow lights schedule"
    )
    
    print("\n✅ Light schedule created!")
    manager.print_schedules(gpio_number=18)


def example_2_irrigation_schedule():
    """Example 2: Schedule irrigation pump to run every 6 hours for 30 seconds"""
    print("\n" + "="*70)
    print("Example 2: Irrigation Schedule (Every 6 hours, 30 seconds)")
    print("="*70)
    
    manager = PinConfigManager()
    
    # Irrigate every 6 hours for 30 seconds at 70% pump speed
    manager.create_irrigation_schedule(
        gpio_number=17,  # Pump GPIO
        interval_hours=6,
        duration_seconds=30,
        pwm_speed=70,
        description="Regular irrigation cycle"
    )
    
    print("\n✅ Irrigation schedule created!")
    manager.print_schedules(gpio_number=17)


def example_3_sensor_read_schedule():
    """Example 3: Schedule sensor reads every 5 minutes"""
    print("\n" + "="*70)
    print("Example 3: Sensor Read Schedule (Every 5 minutes)")
    print("="*70)
    
    manager = PinConfigManager()
    
    # Read DHT22 sensor every 5 minutes (300 seconds)
    manager.create_sensor_read_schedule(
        gpio_number=4,  # DHT22 GPIO
        read_interval_seconds=300,  # 5 minutes
        store_readings=True,
        description="Temperature & Humidity monitoring"
    )
    
    # Read water level sensor every 30 minutes
    manager.create_sensor_read_schedule(
        gpio_number=27,  # Water level GPIO
        read_interval_seconds=1800,  # 30 minutes
        store_readings=True,
        description="Water level monitoring"
    )
    
    print("\n✅ Sensor schedules created!")
    manager.print_schedules()


def example_4_sunrise_sunset():
    """Example 4: Gradual sunrise/sunset fade for lights"""
    print("\n" + "="*70)
    print("Example 4: Sunrise/Sunset Fade (30 minute transitions)")
    print("="*70)
    
    manager = PinConfigManager()
    
    # Create sunrise at 6:00 AM (fade from 0% to 100% over 30 minutes)
    # Create sunset at 10:00 PM (fade from 100% to 0% over 30 minutes)
    manager.create_sunrise_sunset_schedule(
        gpio_number=18,  # Light GPIO
        sunrise_time="06:00",
        sunset_time="22:00",
        fade_minutes=30,
        description="Natural light cycle"
    )
    
    print("\n✅ Sunrise/sunset schedules created!")
    manager.print_schedules(gpio_number=18)


def example_5_custom_pwm_schedule():
    """Example 5: Custom PWM schedule with manual parameters"""
    print("\n" + "="*70)
    print("Example 5: Custom PWM Schedule")
    print("="*70)
    
    manager = PinConfigManager()
    
    # Run pump at 50% speed for 60 seconds, every 4 hours
    manager.add_schedule(
        gpio_number=17,
        schedule_type=ScheduleType.PWM_CYCLE.value,
        interval_seconds=14400,  # 4 hours
        duration_seconds=60,
        pwm_duty_start=50,
        description="Custom pump cycle"
    )
    
    # Pulsing light effect - fade from 30% to 90% over 2 minutes, every hour
    manager.add_schedule(
        gpio_number=18,
        schedule_type=ScheduleType.PWM_FADE.value,
        interval_seconds=3600,  # 1 hour
        pwm_duty_start=30,
        pwm_duty_end=90,
        pwm_fade_duration=120,  # 2 minutes
        description="Hourly pulse effect"
    )
    
    print("\n✅ Custom schedules created!")
    manager.print_schedules()


def example_6_multiple_sensors():
    """Example 6: Multiple sensor read schedules with different intervals"""
    print("\n" + "="*70)
    print("Example 6: Multiple Sensors at Different Intervals")
    print("="*70)
    
    manager = PinConfigManager()
    
    # Fast sensor (every 1 minute) - critical monitoring
    manager.create_sensor_read_schedule(
        gpio_number=4,
        read_interval_seconds=60,
        store_readings=True,
        description="Critical temp/humidity monitoring (1 min)"
    )
    
    # Medium sensor (every 15 minutes) - regular monitoring
    manager.create_sensor_read_schedule(
        gpio_number=27,
        read_interval_seconds=900,
        store_readings=True,
        description="Water level check (15 min)"
    )
    
    # Slow sensor (every hour) - trend monitoring
    manager.add_schedule(
        gpio_number=4,
        schedule_type=ScheduleType.SENSOR_READ.value,
        read_interval_seconds=3600,
        store_readings=True,
        description="Hourly trend sampling"
    )
    
    print("\n✅ Multiple sensor schedules created!")
    manager.print_schedules()


def example_7_weekday_schedule():
    """Example 7: Schedule that only runs on specific days"""
    print("\n" + "="*70)
    print("Example 7: Weekday-Only Schedule (Monday-Friday)")
    print("="*70)
    
    manager = PinConfigManager()
    
    # Lights on Monday-Friday (0-4), but not on weekends
    manager.add_schedule(
        gpio_number=18,
        schedule_type=ScheduleType.PWM_CYCLE.value,
        start_time="06:00",
        end_time="22:00",
        pwm_duty_start=80,
        days_of_week=[0, 1, 2, 3, 4],  # Monday=0, Friday=4
        description="Weekday light schedule (M-F only)"
    )
    
    # Different irrigation on weekends
    manager.add_schedule(
        gpio_number=17,
        schedule_type=ScheduleType.PWM_CYCLE.value,
        interval_seconds=7200,  # Every 2 hours
        duration_seconds=45,
        pwm_duty_start=60,
        days_of_week=[5, 6],  # Saturday=5, Sunday=6
        description="Weekend irrigation (more frequent)"
    )
    
    print("\n✅ Weekday-specific schedules created!")
    manager.print_schedules()


def example_8_manage_schedules():
    """Example 8: Enable, disable, and remove schedules"""
    print("\n" + "="*70)
    print("Example 8: Managing Schedules")
    print("="*70)
    
    manager = PinConfigManager()
    
    # Create a schedule
    manager.create_pwm_cycle_schedule(
        gpio_number=18,
        start_time="06:00",
        end_time="22:00",
        pwm_duty=80
    )
    
    # Get all schedules for this pin
    schedules = manager.get_schedules(18)
    if schedules:
        schedule_id = schedules[0].schedule_id
        
        print(f"\n✅ Schedule created: {schedule_id}")
        
        # Disable the schedule (pause it without deleting)
        manager.disable_schedule(18, schedule_id)
        print(f"⏸️  Schedule disabled")
        
        # Re-enable it
        manager.enable_schedule(18, schedule_id)
        print(f"▶️  Schedule re-enabled")
        
        # Remove it completely
        manager.remove_schedule(18, schedule_id)
        print(f"🗑️  Schedule removed")


def run_all_examples():
    """Run all examples"""
    print("\n" + "="*70)
    print("🚀 GPIO SCHEDULING EXAMPLES")
    print("="*70)
    
    examples = [
        ("Light Schedule", example_1_light_schedule),
        ("Irrigation Schedule", example_2_irrigation_schedule),
        ("Sensor Reads", example_3_sensor_read_schedule),
        ("Sunrise/Sunset", example_4_sunrise_sunset),
        ("Custom PWM", example_5_custom_pwm_schedule),
        ("Multiple Sensors", example_6_multiple_sensors),
        ("Weekday Schedule", example_7_weekday_schedule),
        ("Manage Schedules", example_8_manage_schedules),
    ]
    
    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    
    print("\nRun 'python3 schedule_examples.py <number>' to run a specific example")
    print("Or 'python3 schedule_examples.py all' to run all examples\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == "all":
            example_1_light_schedule()
            example_2_irrigation_schedule()
            example_3_sensor_read_schedule()
            example_4_sunrise_sunset()
            example_5_custom_pwm_schedule()
            example_6_multiple_sensors()
            example_7_weekday_schedule()
            example_8_manage_schedules()
        elif arg.isdigit():
            num = int(arg)
            examples = {
                1: example_1_light_schedule,
                2: example_2_irrigation_schedule,
                3: example_3_sensor_read_schedule,
                4: example_4_sunrise_sunset,
                5: example_5_custom_pwm_schedule,
                6: example_6_multiple_sensors,
                7: example_7_weekday_schedule,
                8: example_8_manage_schedules,
            }
            if num in examples:
                examples[num]()
            else:
                print(f"❌ Example {num} not found")
        else:
            print("❌ Invalid argument. Use 'all' or a number 1-8")
    else:
        run_all_examples()
