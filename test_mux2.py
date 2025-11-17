#!/usr/bin/env python3
"""
Quick test for MUX 2 - Try multiple methods
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


print("=" * 70)
print("MUX 2 Diagnostic Test")
print("=" * 70)

port = "/dev/ttyUSB1"
mux_id = "0120221111083233"

print(f"\nPort: {port}")
print(f"MUX ID: {mux_id}")
print(f"Mode: Extended (16-char)")
print()

# Test 1: Try to detect MUX with broadcast
print("TEST 1: Broadcast MUX detection")
print("-" * 70)
try:
    ser = serial.Serial(port, baudrate=9600, timeout=1.0)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # Broadcast command to get MUX ID
    broadcast_cmd = "#05ag20\r"
    print(f"Sending: {repr(broadcast_cmd[:-1])}")
    ser.write(str.encode(broadcast_cmd))
    ser.flush()

    response = ser.read_until(b'\r')
    print(f"Response: {repr(response)}")

    if response:
        decoded = response.decode('utf-8')
        print(f"Decoded: {repr(decoded)}")
        detected_id = decoded[3:-3]  # Extract ID
        print(f"Detected MUX ID: {detected_id}")

        if detected_id != mux_id:
            print(f"⚠️  WARNING: Detected ID '{detected_id}' != Expected '{mux_id}'")
            print(f"    Using detected ID for further tests...")
            mux_id = detected_id
    else:
        print("✗ No response to broadcast")

    ser.close()
    time.sleep(0.1)
except Exception as e:
    print(f"✗ Error: {e}")

print()

# Test 2: Try 'gl' command (get all weights - faster, like fabio_2.py)
print("TEST 2: 'gl' command (Get All Weights)")
print("-" * 70)
try:
    ser = serial.Serial(port, baudrate=9600, timeout=1.0)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    msg = create_lowa_msg("#", mux_id, "gl", "")
    print(f"Command: {repr(msg[:-1])}")

    ser.write(str.encode(msg))
    ser.flush()

    response = ser.read_until(b'\r')
    print(f"Response length: {len(response)} bytes")

    if response:
        decoded = response.decode('utf-8')
        print(f"Response: {repr(decoded)}")

        # Parse response
        data = decoded[3:-3]  # Skip prefix+length, remove checksum+CR
        num_sensors = len(data) // 11
        print(f"Number of sensors: {num_sensors}")
        print()

        for i in range(num_sensors):
            block = data[i*11:(i+1)*11]
            if len(block) == 11:
                sign = block[0]
                weight_str = block[1:9].strip()
                status = block[9]
                try:
                    weight = float(weight_str)
                    if sign == '-':
                        weight = -weight
                    status_map = {' ': 'OK', 'M': 'MOTION', 'C': 'NOT_CONNECTED', 'E': 'EEPROM_ERROR'}
                    status_name = status_map.get(status, 'UNKNOWN')
                    valid = "✓" if status == ' ' else "✗"
                    print(f"  Channel {i}: {weight:8.3f} kg [{status_name}] {valid}")
                except:
                    print(f"  Channel {i}: Parse error")
    else:
        print("✗ No response (timeout)")

    ser.close()
    time.sleep(0.1)
except Exception as e:
    print(f"✗ Error: {e}")

print()

# Test 3: Try 'gd' command on channel 0
print("TEST 3: 'gd' command on Channel 0")
print("-" * 70)
try:
    ser = serial.Serial(port, baudrate=9600, timeout=1.0)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # gd command: channel 0, mode 0 (weight)
    msg = create_lowa_msg("#", mux_id, "gd", "00")
    print(f"Command: {repr(msg[:-1])}")

    ser.write(str.encode(msg))
    ser.flush()

    response = ser.read_until(b'\r')
    print(f"Response length: {len(response)} bytes")

    if response:
        decoded = response.decode('utf-8')
        print(f"Response: {repr(decoded)}")

        if len(decoded) >= 14:
            sign = decoded[3]
            weight_str = decoded[4:13].strip()
            status = decoded[13]

            weight = float(weight_str)
            if sign == '-':
                weight = -weight

            status_map = {' ': 'OK', 'M': 'MOTION', 'C': 'NOT_CONNECTED', 'E': 'EEPROM_ERROR'}
            status_name = status_map.get(status, f'UNKNOWN({repr(status)})')

            print(f"\nResult:")
            print(f"  Weight: {weight:.3f} kg")
            print(f"  Status: {status_name}")
    else:
        print("✗ No response (timeout)")

    ser.close()
except Exception as e:
    print(f"✗ Error: {e}")

print()
print("=" * 70)
print("DIAGNOSIS")
print("=" * 70)
print("If TEST 2 ('gl') works but TEST 3 ('gd') fails:")
print("  → MUX 2 may not support 'gd' command")
print("  → Solution: Use 'gl' command instead (read_two_muxes_multiport.py)")
print()
print("If all tests fail:")
print("  → Check physical connection to MUX 2")
print("  → Verify MUX 2 is powered (12V)")
print("  → Check MUX ID is correct")
print("  → Try different baudrate")
print("=" * 70)
