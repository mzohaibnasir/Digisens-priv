#!/usr/bin/env python3
"""
DIGIsens Usage Examples
=======================
Practical examples for using the DIGIsens interface.
"""

from digisens_interface import DigiSensInterface, ShelfMonitor, WeightReading
import time


def example_1_basic_reading():
    """Example 1: Basic weight reading from a single sensor."""
    print("\n" + "=" * 60)
    print("Example 1: Basic Weight Reading")
    print("=" * 60)

    # Connect to sensor
    with DigiSensInterface('/dev/ttyUSB0', baudrate=9600) as sensor:
        # Read weight from MUX 123, channel 0
        reading = sensor.get_weight('123', 0)

        print(f"Weight: {reading.weight:.3f} kg")
        print(f"Status: {reading.status.name}")
        print(f"Valid: {reading.is_valid}")


def example_2_all_sensors():
    """Example 2: Read all sensors on a shelf."""
    print("\n" + "=" * 60)
    print("Example 2: Read All Sensors on Shelf")
    print("=" * 60)

    with DigiSensInterface('/dev/ttyUSB0') as sensor:
        # Read all weights from shelf with MUX ID 123
        weights = sensor.get_all_weights('123')

        print(f"Found {len(weights)} sensors:\n")
        for i, reading in enumerate(weights):
            status_icon = "✓" if reading.is_valid else "✗"
            print(f"  [{status_icon}] Channel {i}: {reading.weight:8.3f} kg ({reading.status.name})")


def example_3_continuous_monitoring():
    """Example 3: Continuously monitor a sensor."""
    print("\n" + "=" * 60)
    print("Example 3: Continuous Monitoring")
    print("=" * 60)

    def on_weight_change(reading: WeightReading):
        """Custom callback for weight changes."""
        timestamp = time.strftime('%H:%M:%S')
        if reading.is_valid:
            print(f"[{timestamp}] Weight: {reading.weight:.3f} kg")
        else:
            print(f"[{timestamp}] Error: {reading.status.name}")

    with DigiSensInterface('/dev/ttyUSB0') as sensor:
        # Poll every 1 second
        sensor.poll_continuous('123', 0, interval=1.0, callback=on_weight_change)


def example_4_inventory_monitoring():
    """Example 4: Monitor inventory changes on a shelf."""
    print("\n" + "=" * 60)
    print("Example 4: Inventory Monitoring")
    print("=" * 60)

    with DigiSensInterface('/dev/ttyUSB0') as sensor:
        monitor = ShelfMonitor(sensor)

        # Register shelf
        monitor.add_shelf('123', num_sensors=8)

        # Calibrate (measure empty shelf)
        print("\nStep 1: Calibration")
        print("Remove all items from shelf...")
        input("Press Enter when ready...")
        tare_weights = monitor.calibrate_shelf('123')

        # Monitor for changes
        print("\nStep 2: Monitoring")
        print("Add or remove items. Changes will be detected.\n")
        monitor.monitor_shelf('123', interval=1.0, threshold=0.05)


def example_5_extended_addressing():
    """Example 5: Using extended addressing mode."""
    print("\n" + "=" * 60)
    print("Example 5: Extended Addressing Mode")
    print("=" * 60)

    with DigiSensInterface('/dev/ttyUSB0') as sensor:
        # Use 16-character manufacturer ID
        mux_id = '0120220429103142'  # Example ID

        # Read weight using extended addressing
        reading = sensor.get_weight(mux_id, 0, use_extended=True)
        print(f"Weight from {mux_id}:00 = {reading.weight:.3f} kg")


def example_6_multi_sensor_item():
    """Example 6: Measure item using multiple sensors (differential measurement)."""
    print("\n" + "=" * 60)
    print("Example 6: Multi-Sensor Item Measurement")
    print("=" * 60)

    with DigiSensInterface('/dev/ttyUSB0') as sensor:
        # For items spanning multiple sensors, read all simultaneously
        mux_id = '123'
        sensors = [0, 1, 2]  # Item spans channels 0, 1, 2

        # Read all sensors at once to avoid time skew
        all_weights = sensor.get_all_weights(mux_id)

        # Sum weights from specific sensors
        total_weight = sum(all_weights[i].weight for i in sensors)
        print(f"Total weight across sensors {sensors}: {total_weight:.3f} kg")


def example_7_error_handling():
    """Example 7: Proper error handling."""
    print("\n" + "=" * 60)
    print("Example 7: Error Handling")
    print("=" * 60)

    try:
        with DigiSensInterface('/dev/ttyUSB0', timeout=2.0) as sensor:
            reading = sensor.get_weight('123', 0)

            # Check for errors
            if reading.status.name == 'NOT_CONNECTED':
                print("ERROR: Sensor not connected. Check cable!")
            elif reading.status.name == 'MOTION':
                print("WARNING: Motion detected. Waiting for stabilization...")
                time.sleep(1)
                # Retry
                reading = sensor.get_weight('123', 0)
            elif reading.status.name == 'EEPROM_ERROR':
                print("CRITICAL: EEPROM error. Sensor needs recalibration!")
            else:
                print(f"Weight: {reading.weight:.3f} kg")

    except ConnectionError as e:
        print(f"Failed to connect: {e}")
        print("Check:")
        print("  1. RS485 converter is connected")
        print("  2. Correct serial port (/dev/ttyUSB0)")
        print("  3. User has permission to access serial port")
    except TimeoutError:
        print("No response from sensor. Check:")
        print("  1. MUX ID is correct")
        print("  2. Power is connected (12V)")
        print("  3. RS485 wiring is correct")


def example_8_configuration():
    """Example 8: Configure MUX settings."""
    print("\n" + "=" * 60)
    print("Example 8: MUX Configuration")
    print("=" * 60)

    with DigiSensInterface('/dev/ttyUSB0') as sensor:
        mux_id = '123'

        # Get MUX information
        print("MUX Information:")
        address = sensor.get_mux_address(mux_id)
        print(f"  Address: {address}")

        model = sensor.get_model_number(mux_id)
        print(f"  Model: {model}")

        revision = sensor.get_software_revision(mux_id)
        print(f"  Software: {revision}")

        # Change baudrate (be careful!)
        # Uncomment to actually change baudrate
        # sensor.set_baudrate(mux_id, 115200)
        # print("Baudrate changed to 115200")


def example_9_zeroing():
    """Example 9: Zero/tare a sensor (USE SPARINGLY!)."""
    print("\n" + "=" * 60)
    print("Example 9: Sensor Zeroing (EEPROM Write)")
    print("=" * 60)

    print("WARNING: This writes to EEPROM (limited to 100,000 cycles)")
    print("Only use during installation or annual calibration!")
    print("\nFor daily operations, use software tare instead.")

    response = input("\nContinue with zeroing? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        return

    with DigiSensInterface('/dev/ttyUSB0') as sensor:
        mux_id = '123'
        channel = 0

        print(f"\nEnsure sensor {mux_id}:{channel} is empty...")
        input("Press Enter when ready...")

        # Zero the sensor
        success = sensor.zero_sensor(mux_id, channel)
        if success:
            print("Sensor zeroed successfully!")
        else:
            print("Zeroing failed.")


def example_10_software_tare():
    """Example 10: Software tare (recommended for daily use)."""
    print("\n" + "=" * 60)
    print("Example 10: Software Tare (Recommended)")
    print("=" * 60)

    with DigiSensInterface('/dev/ttyUSB0') as sensor:
        mux_id = '123'
        channel = 0

        # Read empty weight
        print("Remove all items from sensor...")
        input("Press Enter when ready...")

        empty_reading = sensor.get_weight(mux_id, channel)
        tare_weight = empty_reading.weight
        print(f"Tare weight recorded: {tare_weight:.3f} kg")

        # Now read with items
        print("\nPlace item on sensor...")
        input("Press Enter when ready...")

        current_reading = sensor.get_weight(mux_id, channel)
        net_weight = current_reading.weight - tare_weight
        print(f"Gross weight: {current_reading.weight:.3f} kg")
        print(f"Tare weight:  {tare_weight:.3f} kg")
        print(f"Net weight:   {net_weight:.3f} kg")


def example_11_parallel_shelves():
    """Example 11: Monitor multiple shelves in parallel."""
    print("\n" + "=" * 60)
    print("Example 11: Multiple Shelf Monitoring")
    print("=" * 60)

    with DigiSensInterface('/dev/ttyUSB0') as sensor:
        shelf_ids = ['123', '124', '125']

        print("Reading all shelves...\n")

        for shelf_id in shelf_ids:
            print(f"Shelf {shelf_id}:")
            try:
                weights = sensor.get_all_weights(shelf_id)
                for i, w in enumerate(weights):
                    if w.is_valid:
                        print(f"  Channel {i}: {w.weight:.3f} kg")
            except Exception as e:
                print(f"  Error: {e}")
            print()


def example_12_product_tracking():
    """Example 12: Real-world product tracking scenario."""
    print("\n" + "=" * 60)
    print("Example 12: Product Tracking System")
    print("=" * 60)

    # Define products and their weights
    PRODUCTS = {
        'Product A': 0.500,  # 500g
        'Product B': 1.200,  # 1.2kg
        'Product C': 0.350,  # 350g
    }

    with DigiSensInterface('/dev/ttyUSB0') as sensor:
        monitor = ShelfMonitor(sensor)

        # Setup shelf
        monitor.add_shelf('123')
        print("Calibrating empty shelf...")
        time.sleep(1)
        monitor.calibrate_shelf('123')

        print("\nMonitoring stock levels...")
        print("Add or remove products. System will detect changes.\n")

        previous_weights = monitor.get_net_weights('123')

        try:
            while True:
                time.sleep(1)
                current_weights = monitor.get_net_weights('123')

                for i, (prev, curr) in enumerate(zip(previous_weights, current_weights)):
                    if prev is None or curr is None:
                        continue

                    change = curr - prev
                    if abs(change) > 0.05:  # 50g threshold
                        # Identify product
                        product = None
                        for name, weight in PRODUCTS.items():
                            if abs(abs(change) - weight) < 0.05:
                                product = name
                                break

                        if change > 0:
                            action = "ADDED"
                            if product:
                                print(f"[{time.strftime('%H:%M:%S')}] Sensor {i}: {product} restocked")
                        else:
                            action = "REMOVED"
                            if product:
                                print(f"[{time.strftime('%H:%M:%S')}] Sensor {i}: {product} sold")

                        if not product:
                            print(f"[{time.strftime('%H:%M:%S')}] Sensor {i}: Unknown item {action} "
                                  f"({abs(change):.3f} kg)")

                previous_weights = current_weights

        except KeyboardInterrupt:
            print("\nMonitoring stopped")


if __name__ == '__main__':
    import sys

    examples = {
        '1': ('Basic Reading', example_1_basic_reading),
        '2': ('All Sensors', example_2_all_sensors),
        '3': ('Continuous Monitoring', example_3_continuous_monitoring),
        '4': ('Inventory Monitoring', example_4_inventory_monitoring),
        '5': ('Extended Addressing', example_5_extended_addressing),
        '6': ('Multi-Sensor Item', example_6_multi_sensor_item),
        '7': ('Error Handling', example_7_error_handling),
        '8': ('Configuration', example_8_configuration),
        '9': ('Zeroing (EEPROM)', example_9_zeroing),
        '10': ('Software Tare', example_10_software_tare),
        '11': ('Parallel Shelves', example_11_parallel_shelves),
        '12': ('Product Tracking', example_12_product_tracking),
    }

    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        if example_num in examples:
            examples[example_num][1]()
        else:
            print(f"Unknown example: {example_num}")
            sys.exit(1)
    else:
        print("\nDIGIsens Usage Examples")
        print("=" * 60)
        print("\nAvailable examples:")
        for num, (name, _) in examples.items():
            print(f"  {num:2s}. {name}")
        print("\nUsage: python examples.py <example_number>")
        print("Example: python examples.py 1")
