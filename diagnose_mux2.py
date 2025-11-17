#!/usr/bin/env python3
"""
Comprehensive MUX 2 Diagnostics
Tests multiple scenarios to identify the issue
"""

import serial
import time


def XOR_CRC_calculation(msg):
    checksum = 0
    byte_str = bytearray()
    byte_str.extend(map(ord, msg))
    for byte in byte_str:
        checksum ^= byte
    return str(hex(checksum)[2:]).upper().zfill(2)


def create_lowa_msg(head, uid, command, data):
    c_length = str(len(head + "00" + command + uid + data))
    msg = head + c_length.zfill(2) + command + uid + data
    msg_crc = XOR_CRC_calculation(msg)
    msg += msg_crc
    return msg + "\r"


print("=" * 80)
print("COMPREHENSIVE MUX 2 DIAGNOSTICS")
print("=" * 80)
print()

port = "/dev/ttyUSB1"
given_mux_id = "0120221111083233"

# Test 1: Check if port exists and can be opened
print("TEST 1: Serial Port Accessibility")
print("-" * 80)
try:
    ser = serial.Serial(port, baudrate=9600, timeout=0.5)
    print(f"✓ Port {port} opened successfully")
    print(f"  Baudrate: {ser.baudrate}")
    print(f"  Timeout: {ser.timeout}s")
    print(f"  Bytesize: {ser.bytesize}")
    print(f"  Parity: {ser.parity}")
    print(f"  Stopbits: {ser.stopbits}")
    ser.close()
except Exception as e:
    print(f"✗ Cannot open port: {e}")
    print("\nTroubleshooting:")
    print("  1. Check USB cable is connected")
    print("  2. Check USB-RS485 adapter is recognized")
    print("  3. Try: ls -l /dev/ttyUSB*")
    print("  4. Check permissions: sudo chmod 666 /dev/ttyUSB1")
    exit(1)

print()

# Test 2: Try broadcast detection with multiple timeouts
print("TEST 2: Broadcast MUX Detection (Multiple Attempts)")
print("-" * 80)

detected_ids = []
for attempt in range(3):
    try:
        ser = serial.Serial(port, baudrate=9600, timeout=1.5)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        print(f"Attempt {attempt + 1}/3: Sending broadcast '#05ag20'...")
        ser.write(str.encode("#05ag20\r"))
        ser.flush()

        time.sleep(0.1)  # Give MUX time to respond

        response = ser.read_until(b'\r')

        if response:
            decoded = response.decode('utf-8', errors='ignore')
            print(f"  Response: {repr(decoded)}")
            if len(decoded) >= 19:  # Minimum for extended ID
                detected_id = decoded[3:-3]
                detected_ids.append(detected_id)
                print(f"  Detected ID: {detected_id}")
        else:
            print(f"  No response")

        ser.close()
        time.sleep(0.2)
    except Exception as e:
        print(f"  Error: {e}")

if detected_ids:
    print(f"\n✓ Detected MUX ID(s): {set(detected_ids)}")
    actual_mux_id = detected_ids[0]
    if actual_mux_id != given_mux_id:
        print(f"⚠️  WARNING: Detected '{actual_mux_id}' != Given '{given_mux_id}'")
        print(f"    Using detected ID for remaining tests...")
else:
    print(f"\n✗ No MUX detected via broadcast")
    print(f"    Will try with given ID: {given_mux_id}")
    actual_mux_id = given_mux_id

print()

# Test 3: Try different baudrates
print("TEST 3: Baudrate Detection")
print("-" * 80)

baudrates = [9600, 19200, 38400, 4800]
for baud in baudrates:
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=0.8)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        msg = create_lowa_msg("#", actual_mux_id, "gl", "")
        ser.write(str.encode(msg))
        ser.flush()

        response = ser.read_until(b'\r')

        if response and len(response) > 10:
            print(f"✓ {baud} baud: RESPONSE RECEIVED ({len(response)} bytes)")
            decoded = response.decode('utf-8', errors='ignore')
            print(f"  Data: {repr(decoded[:50])}")
            ser.close()
            break
        else:
            print(f"✗ {baud} baud: No response")

        ser.close()
    except Exception as e:
        print(f"✗ {baud} baud: Error - {e}")

print()

# Test 4: Try standard addressing mode
print("TEST 4: Standard Addressing Mode (@ instead of #)")
print("-" * 80)

# Try extracting last 3 digits as standard ID
standard_id = actual_mux_id[-3:] if len(actual_mux_id) >= 3 else "001"
print(f"Trying standard ID: {standard_id}")

try:
    ser = serial.Serial(port, baudrate=9600, timeout=1.0)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    msg = create_lowa_msg("@", standard_id, "gl", "")
    print(f"Command: {repr(msg[:-1])}")

    ser.write(str.encode(msg))
    ser.flush()

    response = ser.read_until(b'\r')

    if response:
        print(f"✓ Response received: {len(response)} bytes")
        decoded = response.decode('utf-8', errors='ignore')
        print(f"  Data: {repr(decoded)}")
    else:
        print(f"✗ No response")

    ser.close()
except Exception as e:
    print(f"✗ Error: {e}")

print()

# Test 5: Compare with MUX 1
print("TEST 5: Compare with MUX 1 (Working)")
print("-" * 80)

mux1_port = "/dev/ttyUSB0"
mux1_id = "0120221125101002"

print(f"Testing MUX 1 on {mux1_port}...")
try:
    ser = serial.Serial(mux1_port, baudrate=9600, timeout=0.5)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    msg = create_lowa_msg("#", mux1_id, "gl", "")
    ser.write(str.encode(msg))
    ser.flush()

    response = ser.read_until(b'\r')

    if response:
        print(f"✓ MUX 1 responds: {len(response)} bytes")
    else:
        print(f"✗ MUX 1 no response (unexpected!)")

    ser.close()
except Exception as e:
    print(f"✗ MUX 1 error: {e}")

print(f"\nNow testing if MUX 2 hardware is on {mux1_port} (swapped cables?)...")
try:
    ser = serial.Serial(mux1_port, baudrate=9600, timeout=0.5)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # Try MUX 2's ID on MUX 1's port
    msg = create_lowa_msg("#", actual_mux_id, "gl", "")
    ser.write(str.encode(msg))
    ser.flush()

    response = ser.read_until(b'\r')

    if response:
        print(f"⚠️  MUX 2 ID responds on port {mux1_port}!")
        print(f"    → Cables may be swapped!")
    else:
        print(f"✓ MUX 2 ID does not respond on {mux1_port} (correct)")

    ser.close()
except Exception as e:
    print(f"  Error: {e}")

print()

# Test 6: Raw data check
print("TEST 6: Raw Serial Data Check")
print("-" * 80)
print("Sending command and reading ANY data (not just until CR)...")

try:
    ser = serial.Serial(port, baudrate=9600, timeout=1.0)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    msg = create_lowa_msg("#", actual_mux_id, "gl", "")
    print(f"Sending: {repr(msg[:-1])}")
    print(f"Hex: {msg[:-1].encode('ascii').hex()}")

    ser.write(str.encode(msg))
    ser.flush()

    time.sleep(0.5)  # Wait longer

    # Read whatever is available
    available = ser.in_waiting
    print(f"\nBytes available: {available}")

    if available > 0:
        raw_data = ser.read(available)
        print(f"Raw data: {repr(raw_data)}")
        print(f"Hex: {raw_data.hex()}")
    else:
        print("No data available (complete silence)")

    ser.close()
except Exception as e:
    print(f"✗ Error: {e}")

print()
print("=" * 80)
print("SUMMARY & RECOMMENDATIONS")
print("=" * 80)
print()
print("Based on the tests above:")
print()
print("If MUX 1 works but MUX 2 shows 'complete silence':")
print("  → Hardware issue with MUX 2 or its connection")
print("  → Check:")
print("    1. MUX 2 has 12V power supply connected and LED is on")
print("    2. RS485 cable is properly connected (A/B terminals)")
print("    3. USB-RS485 converter is working (try swapping with MUX 1's)")
print("    4. Cable integrity (try MUX 1's cable on MUX 2)")
print()
print("If cables are swapped:")
print("  → Swap the USB cables or update the port assignments")
print()
print("If different baudrate worked:")
print("  → Update scripts to use that baudrate for MUX 2")
print()
print("If standard addressing worked:")
print("  → MUX 2 uses standard mode, update MUX 2 ID to 3-digit version")
print("=" * 80)
