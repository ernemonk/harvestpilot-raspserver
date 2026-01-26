# GPIO Pin Testing Guide

## Your Configuration
- **GPIO 18** (Physical Pin 12) → LED Strip MOSFET (PWM Brightness Control)
- **GPIO 17** (Physical Pin 11) → Pump MOSFET (ON/OFF + PWM Speed)
- **GND** (Physical Pin 6, 9, 14, 20, 25, 30, 34, 39) → Both MOSFET boards

## Quick Test Commands

### Test All GPIO Pins Together
```bash
cd /home/monkphx/harvestpilot-raspserver
sudo python3 scripts/test_gpio_pins.py
```

### Test LED Brightness Only
```bash
sudo python3 scripts/test_led_brightness.py
```

### Test Pump Control Only
```bash
sudo python3 scripts/test_pump_control.py
```

## What Each Test Does

### test_gpio_pins.py (Complete Suite)
Tests:
1. **LED Brightness Levels** - 0%, 25%, 50%, 75%, 100%
2. **LED Fade In/Out** - Smooth brightness transitions
3. **Pump ON/OFF** - Basic motor control
4. **Pump PWM Speeds** - 30%, 60%, 100% speed
5. **Simultaneous Control** - LED + Pump together

### test_led_brightness.py (LED Focused)
Tests:
1. **Brightness Levels** - 0-100% in 25% increments
2. **Fade Effect** - Smooth fade in (0→100%) and fade out (100→0%)
3. **Rapid Pulse** - Fast blinking test
4. **Breathing Effect** - Realistic pulsing (like a breathing light)

### test_pump_control.py (Pump Focused)
Tests:
1. **On/Off Control** - Basic pump switching (3 cycles)
2. **PWM Speed Control** - 30%, 50%, 75%, 100% speeds
3. **Gradual Ramp** - Speed increase and decrease
4. **Irrigation Cycle** - Realistic 30-second watering cycle
5. **Long-Run Stability** - 30-second sustained operation at 70%

## GPIO Pin Layout (Raspberry Pi 4 - Top View)

```
              ╔═══════════════════════════════════╗
              ║   RASPBERRY PI 4 GPIO HEADER      ║
              ║                                   ║
PIN 1 (3.3V)  ║ ▮ ▮                               ║  PIN 2 (5V)
GPIO 2        ║ ▮ ● GND                           ║  PIN 3 (GPIO 2)
GPIO 3        ║ ▮ ▮ GPIO 4                        ║  PIN 4 (GPIO 3)
GND           ║ ▮ ▮                               ║  PIN 6
GPIO 17 ✓     ║ ● ▮ GPIO 27                       ║  PIN 11 ← PUMP MOSFET
GPIO 27       ║ ▮ ▮ GPIO 22                       ║  PIN 12
GPIO 22       ║ ▮ ▮ GND                           ║  PIN 13
GPIO 10       ║ ▮ ▮ GPIO 9                        ║  PIN 14
GPIO 9        ║ ▮ ▮ GND                           ║  PIN 16
GPIO 11       ║ ▮ ▮ GPIO 5                        ║  PIN 17
GPIO 5        ║ ▮ ▮ GPIO 6                        ║  PIN 18
GPIO 6        ║ ▮ ▮ GND                           ║  PIN 19
GPIO 13       ║ ▮ ▮ GPIO 12                       ║  PIN 20
GPIO 12       ║ ▮ ▮ GPIO 16                       ║  PIN 21
GPIO 16       ║ ▮ ▮ GND                           ║  PIN 22
GPIO 26       ║ ▮ ▮ GPIO 20                       ║  PIN 23
GPIO 20       ║ ▮ ▮ GPIO 21                       ║  PIN 24
GPIO 21       ║ ▮ ▮ GND                           ║  PIN 25
GPIO 19       ║ ▮ ▮ GPIO 26                       ║  PIN 26
GPIO 18 ✓     ║ ● ▮ GND                           ║  PIN 12 ← LED MOSFET
GPIO 23       ║ ▮ ▮ GPIO 24                       ║  PIN 27
GPIO 24       ║ ▮ ▮ GND                           ║  PIN 28
GPIO 25       ║ ▮                                 ║  PIN 29
GND           ║ ▮ ▮ GPIO 8                        ║  PIN 30
GPIO 8        ║ ▮ ▮ GPIO 7                        ║  PIN 31
GPIO 7        ║ ▮ ▮ GND                           ║  PIN 32
              ║ ▮ ▮                               ║
              ╚═══════════════════════════════════╝
```

✓ = Your selected pins

## Wiring Checklist

- [ ] GPIO 18 connected to LED MOSFET gate (with 1kΩ resistor)
- [ ] GPIO 17 connected to Pump MOSFET gate (with 1kΩ resistor)
- [ ] GND (any GND pin) connected to MOSFET board GND
- [ ] LED power supply connected to MOSFET output
- [ ] Pump power supply connected to MOSFET output
- [ ] All connections secure and tested

## Expected Test Output

### Successful LED Test
```
✅ LED Pin 18 (Physical Pin 12) configured
💡 LED Brightness: 0% - ✅
💡 LED Brightness: 25% - ✅
💡 LED Brightness: 50% - ✅
💡 LED Brightness: 75% - ✅
💡 LED Brightness: 100% - ✅
Fading in...
Fading out...
✅ LED test complete!
```

### Successful Pump Test
```
✅ Pump Pin 17 (Physical Pin 11) configured
Testing pump ON...
✅ Pump ON for 2 seconds
Testing pump OFF...
✅ Pump OFF
Testing pump PWM speeds...
💧 Pump Speed: 30% - ✅
💧 Pump Speed: 60% - ✅
💧 Pump Speed: 100% - ✅
✅ Pump test complete!
```

## Troubleshooting

### LED Not Responding
1. Check GPIO 18 connection to MOSFET gate
2. Verify 1kΩ resistor is in place
3. Test with: `sudo python3 scripts/test_led_brightness.py`

### Pump Not Responding
1. Check GPIO 17 connection to MOSFET gate
2. Verify 1kΩ resistor is in place
3. Test with: `sudo python3 scripts/test_pump_control.py`

### Permission Denied
Make sure to run tests with sudo:
```bash
sudo python3 scripts/test_gpio_pins.py
```

### GPIO Already In Use
Kill any existing GPIO processes:
```bash
ps aux | grep python3
sudo kill -9 <PID>
```

## Next Steps

After successful tests:
1. Integrate into main harvestpilot-raspserver
2. Use in irrigation/lighting controllers
3. Monitor GPIO pin stability during operation
4. Implement error handling for GPIO failures
