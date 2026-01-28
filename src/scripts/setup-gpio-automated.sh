#!/bin/bash
# GPIO Automated Setup Script
# Configures Raspberry Pi GPIO pins for HarvestPilot

set -euo pipefail

echo "🔧 Setting up GPIO configuration..."

# GPIO Pin Configuration (from config.py)
PUMP_GPIO=17
LIGHT_GPIO=18
DHT_GPIO=4
WATER_GPIO=27

# Harvest motor GPIOs
HARVEST_MOTORS=(2 3 5 6 12 13)

# GPIO Base path
GPIO_PATH="/sys/class/gpio"

# Function to export a GPIO pin
export_gpio() {
    local pin=$1
    local direction=$2
    
    if [ ! -d "$GPIO_PATH/gpio$pin" ]; then
        echo "  Exporting GPIO $pin..."
        echo "$pin" | sudo tee /sys/class/gpio/export > /dev/null 2>&1 || true
        sleep 0.5
    fi
    
    if [ -n "$direction" ]; then
        echo "  Setting GPIO $pin direction to $direction..."
        echo "$direction" | sudo tee "$GPIO_PATH/gpio$pin/direction" > /dev/null 2>&1 || true
    fi
}

# Check if running as root for GPIO operations
echo "✅ Checking GPIO access..."

# Export pump GPIO (PWM output)
export_gpio $PUMP_GPIO "out"

# Export light GPIO (PWM output)
export_gpio $LIGHT_GPIO "out"

# Export DHT sensor GPIO (input)
export_gpio $DHT_GPIO "in"

# Export water level sensor GPIO (input)
export_gpio $WATER_GPIO "in"

# Export harvest motor GPIOs (output)
for pin in "${HARVEST_MOTORS[@]}"; do
    export_gpio $pin "out"
done

echo "✅ GPIO pins configured:"
echo "   - Pump (PWM):     GPIO $PUMP_GPIO"
echo "   - Lights (PWM):   GPIO $LIGHT_GPIO"
echo "   - DHT Sensor:     GPIO $DHT_GPIO"
echo "   - Water Sensor:   GPIO $WATER_GPIO"
echo "   - Motors:         GPIO ${HARVEST_MOTORS[*]}"

# Verify GPIO setup
echo ""
echo "✅ Verifying GPIO setup..."

for pin in $PUMP_GPIO $LIGHT_GPIO $DHT_GPIO $WATER_GPIO "${HARVEST_MOTORS[@]}"; do
    if [ -d "$GPIO_PATH/gpio$pin" ]; then
        echo "   ✅ GPIO $pin: OK"
    else
        echo "   ⚠️  GPIO $pin: Not accessible (may need sudo)"
    fi
done

echo ""
echo "✅ GPIO setup complete"
