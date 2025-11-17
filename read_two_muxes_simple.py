#!/usr/bin/env python3
"""
Simple Script to Read Weight Values from Two MUXes
===================================================
Direct serial communication approach (similar to fabio_2.py)

Usage:
    python read_two_muxes_simple.py

This script uses direct serial communication without the digisens_interface library.
Based on the working fabio_2.py implementation.
"""

import serial


def XOR_CRC_calculation(msg):
    """
    Calculate XOR checksum for LOWA protocol.

    Args:
        msg: Message string without checksum

    Returns:
        Hexadecimal checksum string (2 chars, uppercase)
    """
    checksum = 0
    byte_str = bytearray()
    byte_str.extend(map(ord, msg))
    for byte in byte_str:
        checksum ^= byte
    return str(hex(checksum)[2:]).upper().zfill(2)


def create_lowa_msg(head, uid, command, data):
    """
    Build a complete LOWA protocol message with checksum.

    Args:
        head: Message prefix ('#' for extended, '@' for standard)
        uid: MUX unique identifier
        command: Command code (e.g., 'gl', 'gw', 'sz')
        data: Additional data (e.g., channel number)

    Returns:
        Complete message string with checksum and CR
    """
    # Calculate length (command + uid + data + 2 for checksum)
    c_length = str(len(head + "00" + command + uid + data))
    msg = head + c_length.zfill(2) + command + uid + data

    # Calculate and add XOR-CRC
    msg_crc = XOR_CRC_calculation(msg)
    msg += msg_crc

    return msg + "\r"


def parse_weight_response(response, channel_idx):
    """
    Parse a single weight value from the response.

    Args:
        response: 11-character weight block
        channel_idx: Channel number for display

    Returns:
        Tuple of (channel, weight, status, valid)
    """
    # Format: {sign}{8-char-weight}{status}
    # Example: " 0002.130 " or "-0001.250M"
    sign = response[0]
    weight_str = response[1:9].strip()
    status_char = response[9]

    # Parse weight
    try:
        weight = float(weight_str)
        if sign == '-':
            weight = -weight
    except ValueError:
        weight = 0.0
        status_char = 'E'

    # Parse status
    status_map = {
        ' ': 'OK',
        'M': 'MOTION',
        'C': 'NOT_CONNECTED',
        'E': 'EEPROM_ERROR'
    }
    status = status_map.get(status_char, 'UNKNOWN')
    valid = (status_char == ' ')

    return (channel_idx, weight, status, valid)


def read_mux_weights(ser, mux_id, use_extended=True):
    """
    Read all weights from a single MUX.

    Args:
        ser: Serial connection object
        mux_id: MUX identifier (3-digit or 16-char)
        use_extended: Use extended addressing mode (default: True)

    Returns:
        List of tuples: (channel, weight, status, valid)
    """
    # Build command to get all weights
    head = '#' if use_extended else '@'
    msg = create_lowa_msg(head, mux_id, "gl", "")

    # Send command
    ser.write(str.encode(msg))

    # Read response
    mux_answer = ser.read_until(b"\r").decode("utf-8")

    # Parse response
    # Response format: #LL{weight0}{weight1}...{weight7}{checksum}\r
    # Skip prefix (1 char) and length (2 chars) = 3 chars
    # Remove checksum (2 chars) and CR (1 char) from end = -3 chars
    data = mux_answer[3:-3]

    # Each weight is 11 characters
    weights = []
    for i in range(0, len(data), 11):
        weight_block = data[i:i+11]
        if len(weight_block) == 11:
            channel_idx = i // 11
            parsed = parse_weight_response(weight_block, channel_idx)
            weights.append(parsed)

    return weights


def print_mux_results(mux_id, weights, label="MUX"):
    """
    Print formatted results for one MUX.

    Args:
        mux_id: MUX identifier
        weights: List of (channel, weight, status, valid) tuples
        label: Display label
    """
    print(f"\n{'=' * 70}")
    print(f"{label}: {mux_id}")
    print(f"{'=' * 70}")
    print(f"{'Channel':<10} {'Weight (kg)':<15} {'Status':<15} {'Valid':<10}")
    print(f"{'-' * 70}")

    total_weight = 0.0
    valid_count = 0

    for channel, weight, status, valid in weights:
        status_icon = "✓" if valid else "✗"
        print(f"{channel:<10} {weight:<15.3f} {status:<15} {status_icon:<10}")

        if valid:
            total_weight += weight
            valid_count += 1

    print(f"{'-' * 70}")
    print(f"Valid sensors: {valid_count}/{len(weights)}")
    print(f"Total weight: {total_weight:.3f} kg")
    print(f"{'=' * 70}\n")

    return total_weight, valid_count


def main():
    """Main function."""
    print("=" * 70)
    print("DIGIsens - Read Weight Values from Two MUXes (Simple Version)")
    print("=" * 70)

    # Configuration
    port = input("\nEnter serial port [/dev/ttyUSB0]: ").strip() or "/dev/ttyUSB0"
    baudrate = input("Enter baudrate [9600]: ").strip() or "9600"
    baudrate = int(baudrate)

    print("\nEnter first MUX ID:")
    print("  - Standard mode: 3 digits (e.g., 123)")
    print("  - Extended mode: 16 characters (e.g., 0120220429103142)")
    mux1_id = input("MUX 1 ID: ").strip()

    mux2_id = input("MUX 2 ID: ").strip()

    if not mux1_id or not mux2_id:
        print("\nError: Both MUX IDs are required!")
        return

    # Detect addressing modes
    use_extended_1 = len(mux1_id) == 16
    use_extended_2 = len(mux2_id) == 16

    mode1 = "Extended (16-char)" if use_extended_1 else "Standard (3-digit)"
    mode2 = "Extended (16-char)" if use_extended_2 else "Standard (3-digit)"

    print(f"\nConfiguration:")
    print(f"  Serial Port: {port}")
    print(f"  Baudrate: {baudrate}")
    print(f"  MUX 1 ID: {mux1_id} ({mode1})")
    print(f"  MUX 2 ID: {mux2_id} ({mode2})")

    # Open serial connection
    print(f"\nConnecting to {port}...")

    try:
        ser = serial.Serial()
        ser.baudrate = baudrate
        ser.timeout = 0.5  # 500ms timeout
        ser.port = port
        ser.open()

        print("Connected successfully!\n")

        # Read from MUX 1
        print("Reading weights from MUX 1...")
        try:
            weights1 = read_mux_weights(ser, mux1_id, use_extended_1)
            total1, valid1 = print_mux_results(mux1_id, weights1, "MUX 1")
        except Exception as e:
            print(f"Error reading MUX 1: {e}\n")
            weights1 = []
            total1, valid1 = 0.0, 0

        # Read from MUX 2
        print("Reading weights from MUX 2...")
        try:
            weights2 = read_mux_weights(ser, mux2_id, use_extended_2)
            total2, valid2 = print_mux_results(mux2_id, weights2, "MUX 2")
        except Exception as e:
            print(f"Error reading MUX 2: {e}\n")
            weights2 = []
            total2, valid2 = 0.0, 0

        # Combined summary
        if weights1 or weights2:
            print("=" * 70)
            print("COMBINED SUMMARY")
            print("=" * 70)
            print(f"Total sensors: {len(weights1) + len(weights2)}")
            print(f"Valid readings: {valid1 + valid2}/{len(weights1) + len(weights2)}")
            print(f"Combined weight: {total1 + total2:.3f} kg")
            print("=" * 70)

        # Close connection
        ser.close()
        print("\nReading complete!")

    except serial.SerialException as e:
        print(f"\nSerial Port Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Check that the serial port is correct (ls /dev/ttyUSB*)")
        print("  2. Verify user permissions (sudo usermod -a -G dialout $USER)")
        print("  3. Check cable connection")
        print("  4. Ensure no other program is using the port")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
