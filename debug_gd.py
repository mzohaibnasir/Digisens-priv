#!/usr/bin/env python3
"""
Debug 'gd' command - Test single channel with verbose output
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


def test_gd_command():
    """Test gd command with verbose debugging."""

    port = input("Enter serial port [/dev/ttyUSB0]: ").strip() or "/dev/ttyUSB0"
    mux_id = input("Enter MUX ID: ").strip()
    channel = input("Enter channel [0]: ").strip() or "0"

    print(f"\n{'='*70}")
    print("DEBUG: Testing 'gd' command")
    print(f"{'='*70}")
    print(f"Port: {port}")
    print(f"MUX ID: {mux_id}")
    print(f"Channel: {channel}")
    print(f"{'='*70}\n")

    # Build command
    use_extended = len(mux_id) == 16
    head = '#' if use_extended else '@'
    mode = "0"  # 0 = weight

    msg = create_lowa_msg(head, mux_id, "gd", channel + mode)

    print(f"Command built:")
    print(f"  Raw: {repr(msg)}")
    print(f"  Hex: {msg[:-1].encode('ascii').hex()}")
    print(f"  Length: {len(msg)-1} bytes (excluding CR)")
    print()

    # Open serial port
    print("Opening serial port...")
    try:
        ser = serial.Serial(
            port=port,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=2.0  # 2 second timeout
        )
        print(f"✓ Serial port opened: {ser.name}")
        print(f"  Baudrate: {ser.baudrate}")
        print(f"  Timeout: {ser.timeout}s")
        print()
    except Exception as e:
        print(f"✗ Failed to open serial port: {e}")
        return

    # Flush buffers
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    print("Buffers flushed")
    print()

    # Send command
    print(f"Sending command: {repr(msg[:-1])}")
    start_time = time.time()
    ser.write(str.encode(msg))
    ser.flush()
    print(f"✓ Command sent ({time.time()-start_time:.3f}s)")
    print()

    # Read response
    print("Waiting for response...")
    read_start = time.time()
    response = ser.read_until(b'\r')
    read_time = time.time() - read_start

    print(f"Response received ({read_time:.3f}s):")
    print(f"  Raw bytes: {repr(response)}")
    print(f"  Length: {len(response)} bytes")

    if response:
        print(f"  Hex: {response.hex()}")
        try:
            decoded = response.decode('utf-8')
            print(f"  Decoded: {repr(decoded)}")
            print()

            # Parse response
            if len(decoded) >= 14:
                print("Parsing response:")
                print(f"  Prefix: '{decoded[0]}'")
                print(f"  Length: '{decoded[1:3]}'")
                print(f"  Sign: '{decoded[3]}'")
                print(f"  Weight: '{decoded[4:13]}'")
                print(f"  Status: '{decoded[13]}'")
                if len(decoded) >= 16:
                    print(f"  Checksum: '{decoded[14:16]}'")

                # Extract weight
                try:
                    sign = decoded[3]
                    weight_str = decoded[4:13].strip()
                    status = decoded[13]
                    weight = float(weight_str)
                    if sign == '-':
                        weight = -weight

                    status_map = {' ': 'OK', 'M': 'MOTION', 'C': 'NOT_CONNECTED', 'E': 'EEPROM_ERROR'}
                    status_name = status_map.get(status, f'UNKNOWN({repr(status)})')

                    print()
                    print(f"{'='*70}")
                    print(f"RESULT:")
                    print(f"  Weight: {weight:.3f} kg")
                    print(f"  Status: {status_name}")
                    print(f"{'='*70}")
                except Exception as e:
                    print(f"\n✗ Error parsing weight: {e}")
            else:
                print(f"\n✗ Response too short (expected >= 14 chars)")
        except Exception as e:
            print(f"\n✗ Error decoding response: {e}")
    else:
        print(f"\n✗ No response received (timeout)")
        print()
        print("Troubleshooting:")
        print("  1. Check MUX is powered (12V)")
        print("  2. Verify MUX ID is correct")
        print("  3. Check RS485 wiring")
        print("  4. Try different baudrate")
        print("  5. Test with fabio_2.py using 'gl' command")

    ser.close()
    print(f"\nSerial port closed")


def test_gl_command():
    """Test 'gl' command for comparison."""

    port = input("\nEnter serial port [/dev/ttyUSB0]: ").strip() or "/dev/ttyUSB0"
    mux_id = input("Enter MUX ID: ").strip()

    print(f"\n{'='*70}")
    print("DEBUG: Testing 'gl' command (Get All Weights)")
    print(f"{'='*70}")

    use_extended = len(mux_id) == 16
    head = '#' if use_extended else '@'

    msg = create_lowa_msg(head, mux_id, "gl", "")

    print(f"Command: {repr(msg[:-1])}")
    print()

    try:
        ser = serial.Serial(port, baudrate=9600, timeout=2.0)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        print("Sending command...")
        ser.write(str.encode(msg))
        ser.flush()

        print("Waiting for response...")
        response = ser.read_until(b'\r')

        if response:
            decoded = response.decode('utf-8')
            print(f"Response: {repr(decoded)}")
            print(f"Length: {len(decoded)} bytes")

            # Parse
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
                        print(f"  Channel {i}: {weight:.3f} kg [{status_name}]")
                    except:
                        print(f"  Channel {i}: Parse error")
        else:
            print("✗ No response")

        ser.close()
    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == '__main__':
    print("=" * 70)
    print("DIGIsens - Debug gd/gl Commands")
    print("=" * 70)

    print("\nWhat do you want to test?")
    print("1. 'gd' command (Get Data - single channel)")
    print("2. 'gl' command (Get All - 8 channels)")

    choice = input("\nEnter choice [1]: ").strip() or "1"

    if choice == "1":
        test_gd_command()
    elif choice == "2":
        test_gl_command()
    else:
        print("Invalid choice")
