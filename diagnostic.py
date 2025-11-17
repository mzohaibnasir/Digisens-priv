#!/usr/bin/env python3
"""
DIGIsens Diagnostic Tool
========================
Troubleshooting and diagnostic utility for DIGIsens weight sensors.

This tool helps identify and resolve common issues with the sensor system.
"""

import sys
import time
import serial
import serial.tools.list_ports
from digisens_interface import DigiSensInterface


def print_header(text):
    """Print formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_step(text):
    """Print formatted step."""
    print(f"\n>>> {text}")


def print_ok(text):
    """Print success message."""
    print(f"[OK] {text}")


def print_error(text):
    """Print error message."""
    print(f"[ERROR] {text}")


def print_warning(text):
    """Print warning message."""
    print(f"[WARNING] {text}")


def print_info(text):
    """Print info message."""
    print(f"[INFO] {text}")


def test_1_list_serial_ports():
    """Test 1: List available serial ports."""
    print_header("Test 1: Serial Port Detection")

    ports = serial.tools.list_ports.comports()

    if not ports:
        print_error("No serial ports found!")
        print_info("Solutions:")
        print("  1. Connect RS485-USB converter")
        print("  2. Install driver for your converter (FTDI, CH340, etc.)")
        print("  3. Check USB cable")
        return None

    print_ok(f"Found {len(ports)} serial port(s):")
    for i, port in enumerate(ports):
        print(f"\n  [{i}] {port.device}")
        print(f"      Description: {port.description}")
        print(f"      Hardware ID: {port.hwid}")

    return [p.device for p in ports]


def test_2_open_serial_port(port):
    """Test 2: Open serial port."""
    print_header(f"Test 2: Opening Serial Port {port}")

    try:
        ser = serial.Serial(
            port=port,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0
        )
        print_ok(f"Successfully opened {port}")
        print_info(f"Settings: 9600 8N1")
        ser.close()
        return True
    except serial.SerialException as e:
        print_error(f"Failed to open {port}: {e}")
        print_info("Solutions:")
        print("  1. Close any programs using this port (minicom, screen, etc.)")
        print("  2. Check permissions: sudo usermod -a -G dialout $USER")
        print("  3. Try a different port")
        return False


def test_3_basic_communication(port):
    """Test 3: Basic communication test using protocol broadcast."""
    print_header("Test 3: Communication Test (Protocol Broadcast)")

    try:
        with DigiSensInterface(port, timeout=2.0) as sensor:
            print_ok("Connection established")

            # Try to get MUX address using protocol broadcast
            print_step("Sending 'ag' broadcast command (extended mode)...")
            print_info("Note: Only works with ONE MUX connected")
            try:
                response = sensor.get_mux_address(use_extended=True)
                print_ok(f"Received manufacturer ID: {response}")
                return True
            except TimeoutError:
                print_error("No response from MUX")
                print_info("Possible issues:")
                print("  1. MUX not powered (check 12V supply)")
                print("  2. RS485 wiring incorrect (check pins 1-2)")
                print("  3. Baudrate mismatch (run: python test_baudrates.py)")
                print("  4. Multiple MUXes connected (broadcast forbidden)")
                return False

    except Exception as e:
        print_error(f"Communication failed: {e}")
        return False


def test_4_discover_mux(port):
    """Test 4: Discover MUX using protocol 'ag' broadcast command."""
    print_header("Test 4: MUX Discovery (Protocol Broadcast)")

    print_info("Using protocol 'ag' broadcast command (extended mode)...")
    print_warning("This ONLY works with ONE MUX connected (protocol requirement)")
    print_info("Manufacturer recommends extended addressing mode (16-char ID)")

    try:
        with DigiSensInterface(port, timeout=2.0) as sensor:
            try:
                # Use extended mode (16-char manufacturer ID) as recommended
                address = sensor.get_mux_address(use_extended=True)
                print_ok(f"MUX responded with manufacturer ID: {address}")
                print_info("This is the unique 16-character MUX ID")
                print_info("Use this ID with extended addressing mode (#) in your application")
                return address
            except TimeoutError:
                print_error("No response to 'ag' broadcast command")
                print_info("\nPossible causes:")
                print("  1. MUX not powered (check 12V supply, verify LED is lit)")
                print("  2. RS485 wiring incorrect (check pins 1-2 on RJ-45)")
                print("  3. Baudrate mismatch (run: python test_baudrates.py)")
                print("  4. RS485 polarity reversed (try swapping A/B)")
                print("  5. Multiple MUXes connected (broadcast forbidden per protocol)")
                print("\n** For systems with multiple MUXes: **")
                print("   The MUX ID must be obtained from the physical label")
                print("   on each MUX device (broadcast doesn't work with multiple MUXes)")
                return None

    except Exception as e:
        print_error(f"Discovery failed: {e}")
        print_info("Check hardware connections and power supply")
        return None


def test_5_get_mux_info(port, mux_id):
    """Test 5: Get MUX information."""
    print_header(f"Test 5: MUX Information (ID: {mux_id})")

    try:
        with DigiSensInterface(port, timeout=2.0) as sensor:
            try:
                model = sensor.get_model_number(mux_id)
                print_ok(f"Model: {model}")
            except:
                print_warning("Could not read model number")

            try:
                revision = sensor.get_software_revision(mux_id)
                print_ok(f"Software revision: {revision}")
            except:
                print_warning("Could not read software revision")

            try:
                address = sensor.get_mux_address(mux_id)
                print_ok(f"Address: {address}")
            except:
                print_warning("Could not read address")

            return True

    except Exception as e:
        print_error(f"Failed to get MUX info: {e}")
        return False


def test_6_read_sensors(port, mux_id):
    """Test 6: Read all sensors."""
    print_header(f"Test 6: Sensor Readings (MUX ID: {mux_id})")

    try:
        with DigiSensInterface(port, timeout=2.0) as sensor:
            print_step("Reading all sensors...")
            weights = sensor.get_all_weights(mux_id)

            print(f"\nFound {len(weights)} sensors:\n")

            ok_count = 0
            error_count = 0

            for i, reading in enumerate(weights):
                status_icon = "✓" if reading.is_valid else "✗"
                status_text = reading.status.name

                if reading.is_valid:
                    print(f"  [{status_icon}] Channel {i}: {reading.weight:8.3f} kg  ({status_text})")
                    ok_count += 1
                else:
                    print(f"  [{status_icon}] Channel {i}: {'N/A':>8s}     ({status_text})")
                    error_count += 1

                    if reading.status.name == 'NOT_CONNECTED':
                        print_warning(f"      Sensor {i} not connected - check cable")
                    elif reading.status.name == 'MOTION':
                        print_warning(f"      Sensor {i} has motion - unstable reading")
                    elif reading.status.name == 'EEPROM_ERROR':
                        print_error(f"      Sensor {i} EEPROM error - needs recalibration")

            print(f"\nSummary: {ok_count} OK, {error_count} errors")

            if ok_count > 0:
                print_ok("At least one sensor is working correctly")
                return True
            else:
                print_error("No working sensors found")
                return False

    except Exception as e:
        print_error(f"Failed to read sensors: {e}")
        return False


def test_7_stability_test(port, mux_id, channel=0, duration=10):
    """Test 7: Stability test."""
    print_header(f"Test 7: Stability Test (Channel {channel}, {duration}s)")

    print_info("This test checks for measurement stability")
    print_info("Keep sensor stable (no movement or weight changes)")

    input("\nPress Enter to start...")

    try:
        with DigiSensInterface(port, timeout=2.0) as sensor:
            readings = []
            start_time = time.time()

            print("\nReading...")
            while time.time() - start_time < duration:
                try:
                    reading = sensor.get_weight(mux_id, channel)
                    if reading.is_valid:
                        readings.append(reading.weight)
                        print(f"  {len(readings):2d}. {reading.weight:.3f} kg")
                    else:
                        print(f"  {len(readings):2d}. Error: {reading.status.name}")
                    time.sleep(0.5)
                except Exception as e:
                    print_warning(f"Read error: {e}")

            if len(readings) < 2:
                print_error("Not enough valid readings")
                return False

            # Calculate statistics
            avg = sum(readings) / len(readings)
            min_val = min(readings)
            max_val = max(readings)
            range_val = max_val - min_val

            print("\nResults:")
            print(f"  Readings: {len(readings)}")
            print(f"  Average:  {avg:.3f} kg")
            print(f"  Minimum:  {min_val:.3f} kg")
            print(f"  Maximum:  {max_val:.3f} kg")
            print(f"  Range:    {range_val:.3f} kg ({range_val*1000:.1f} g)")

            if range_val < 0.005:  # 5 grams
                print_ok("Excellent stability (< 5g variation)")
            elif range_val < 0.010:  # 10 grams
                print_ok("Good stability (< 10g variation)")
            elif range_val < 0.050:  # 50 grams
                print_warning("Moderate stability (< 50g variation)")
            else:
                print_error("Poor stability (> 50g variation)")
                print_info("Check for vibration, motion, or electrical noise")

            return True

    except Exception as e:
        print_error(f"Stability test failed: {e}")
        return False


def test_8_response_time(port, mux_id, channel=0):
    """Test 8: Response time test."""
    print_header(f"Test 8: Response Time Test (Channel {channel})")

    try:
        with DigiSensInterface(port, timeout=2.0) as sensor:
            times = []

            print_info("Measuring response time (10 readings)...")

            for i in range(10):
                start = time.time()
                sensor.get_weight(mux_id, channel)
                elapsed = (time.time() - start) * 1000  # Convert to ms
                times.append(elapsed)
                print(f"  Reading {i+1}: {elapsed:.1f} ms")

            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)

            print(f"\nResults:")
            print(f"  Average: {avg_time:.1f} ms")
            print(f"  Minimum: {min_time:.1f} ms")
            print(f"  Maximum: {max_time:.1f} ms")

            if avg_time < 300:
                print_ok("Good response time")
            elif avg_time < 500:
                print_warning("Acceptable response time")
            else:
                print_error("Slow response time")
                print_info("Consider increasing baudrate or checking cable quality")

            return True

    except Exception as e:
        print_error(f"Response time test failed: {e}")
        return False


def run_full_diagnostic():
    """Run complete diagnostic suite."""
    print("\n" + "=" * 70)
    print("  DIGIsens DIAGNOSTIC TOOL")
    print("  Automated troubleshooting for weight sensor systems")
    print("=" * 70)

    # Test 1: List ports
    ports = test_1_list_serial_ports()
    if not ports:
        return

    # Select port
    if len(ports) == 1:
        port = ports[0]
        print_info(f"Using port: {port}")
    else:
        print("\nSelect port number: ", end='')
        try:
            idx = int(input())
            port = ports[idx]
        except (ValueError, IndexError):
            print_error("Invalid selection")
            return

    # Test 2: Open port
    if not test_2_open_serial_port(port):
        return

    # Test 3: Basic communication
    if not test_3_basic_communication(port):
        print_info("\nTrying to discover MUX ID...")

    # Test 4: Discover MUX
    mux_id = test_4_discover_mux(port)
    if not mux_id:
        print("\nEnter MUX ID manually (or 'q' to quit): ", end='')
        mux_id = input().strip()
        if mux_id.lower() == 'q':
            return

    # Test 5: MUX info
    test_5_get_mux_info(port, mux_id)

    # Test 6: Read sensors
    if not test_6_read_sensors(port, mux_id):
        print_warning("Sensor reading failed. Stopping diagnostics.")
        return

    # Test 7: Stability test
    print("\nRun stability test? (y/n): ", end='')
    if input().lower() == 'y':
        test_7_stability_test(port, mux_id)

    # Test 8: Response time
    print("\nRun response time test? (y/n): ", end='')
    if input().lower() == 'y':
        test_8_response_time(port, mux_id)

    # Summary
    print_header("DIAGNOSTIC COMPLETE")
    print("\nNext steps:")
    print("  1. Review any errors or warnings above")
    print("  2. Consult README.md for troubleshooting")
    print("  3. Run examples: python examples.py")
    print("  4. Start monitoring: python digisens_interface.py {} {}".format(port, mux_id))


def quick_test(port, mux_id):
    """Quick connection test."""
    print_header("QUICK TEST")

    try:
        with DigiSensInterface(port, timeout=2.0) as sensor:
            print_step("Testing connection...")
            weights = sensor.get_all_weights(mux_id)

            ok_count = sum(1 for w in weights if w.is_valid)
            print_ok(f"Connected successfully! {ok_count}/{len(weights)} sensors OK")

            for i, w in enumerate(weights[:3]):  # Show first 3
                if w.is_valid:
                    print(f"  Channel {i}: {w.weight:.3f} kg")

            return True

    except Exception as e:
        print_error(f"Connection failed: {e}")
        return False


if __name__ == '__main__':
    if len(sys.argv) >= 3:
        # Quick test mode: python diagnostic.py <port> <mux_id>
        port = sys.argv[1]
        mux_id = sys.argv[2]
        quick_test(port, mux_id)
    else:
        # Full diagnostic mode
        run_full_diagnostic()
