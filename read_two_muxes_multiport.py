#!/usr/bin/env python3
"""
Read Weight Values from Two MUXes on SEPARATE Serial Ports
===========================================================
For setups where each MUX is connected to its own RS485 bus and USB converter.

This allows PARALLEL polling for faster performance.

Architecture:
    Computer
    ├── /dev/ttyUSB0 (USB Converter 1) → RS485 Bus 1 → MUX 1 (8 sensors)
    └── /dev/ttyUSB1 (USB Converter 2) → RS485 Bus 2 → MUX 2 (8 sensors)

Usage:
    python read_two_muxes_multiport.py

Reference: qna.txt line 65 - "multiple converters which correspond to multiple RS485 buses"
"""

import serial
import threading
import time
from typing import List, Tuple, Optional


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


def read_mux_weights(port, mux_id, baudrate=9600, use_extended=True, timeout=0.5):
    """
    Read all weights from a single MUX on a specific serial port.

    Args:
        port: Serial port (e.g., '/dev/ttyUSB0')
        mux_id: MUX identifier (3-digit or 16-char)
        baudrate: Communication speed (default: 9600)
        use_extended: Use extended addressing mode (default: True)
        timeout: Read timeout in seconds (default: 0.5)

    Returns:
        Tuple of (success, weights_list, error_message)
        weights_list: List of tuples (channel, weight, status, valid)
    """
    try:
        # Open serial connection
        ser = serial.Serial()
        ser.baudrate = baudrate
        ser.timeout = timeout
        ser.port = port
        ser.open()

        # Build command to get all weights
        head = '#' if use_extended else '@'
        msg = create_lowa_msg(head, mux_id, "gl", "")

        # Send command
        ser.write(str.encode(msg))

        # Read response
        mux_answer = ser.read_until(b"\r").decode("utf-8")

        if not mux_answer or len(mux_answer) < 5:
            ser.close()
            return (False, [], "No response or timeout")

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

        ser.close()
        return (True, weights, None)

    except serial.SerialException as e:
        return (False, [], f"Serial error: {e}")
    except Exception as e:
        return (False, [], f"Error: {e}")


def read_mux_thread(port, mux_id, baudrate, use_extended, results, index, mux_label):
    """
    Thread function to read MUX weights in parallel.

    Args:
        port: Serial port
        mux_id: MUX identifier
        baudrate: Communication speed
        use_extended: Use extended addressing
        results: Shared list to store results
        index: Index in results list
        mux_label: Label for display
    """
    print(f"[{mux_label}] Reading from {port}...")
    start_time = time.time()

    success, weights, error = read_mux_weights(port, mux_id, baudrate, use_extended)

    elapsed = time.time() - start_time

    results[index] = {
        'port': port,
        'mux_id': mux_id,
        'label': mux_label,
        'success': success,
        'weights': weights,
        'error': error,
        'elapsed': elapsed
    }

    if success:
        print(f"[{mux_label}] Success! Read {len(weights)} sensors in {elapsed:.3f}s")
    else:
        print(f"[{mux_label}] Failed: {error}")


def print_mux_results(result):
    """
    Print formatted results for one MUX.

    Args:
        result: Dictionary with MUX reading results
    """
    label = result['label']
    port = result['port']
    mux_id = result['mux_id']
    weights = result['weights']

    print(f"\n{'=' * 70}")
    print(f"{label}: {mux_id} (Port: {port})")
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
    print(f"Read time: {result['elapsed']:.3f}s")
    print(f"{'=' * 70}\n")

    return total_weight, valid_count


def main():
    """Main function."""
    print("=" * 70)
    print("DIGIsens - Read Two MUXes on Separate Serial Ports (Parallel)")
    print("=" * 70)
    print("\nThis script is for setups where each MUX has its own USB converter.")
    print("Advantage: Parallel polling for faster performance!\n")

    # Configuration for MUX 1
    print("=== MUX 1 Configuration ===")
    port1 = input("Enter serial port for MUX 1 [/dev/ttyUSB0]: ").strip() or "/dev/ttyUSB0"
    mux1_id = input("Enter MUX 1 ID: ").strip()

    # Configuration for MUX 2
    print("\n=== MUX 2 Configuration ===")
    port2 = input("Enter serial port for MUX 2 [/dev/ttyUSB1]: ").strip() or "/dev/ttyUSB1"
    mux2_id = input("Enter MUX 2 ID: ").strip()

    # Baudrate (usually same for both)
    print("\n=== Communication Settings ===")
    baudrate = input("Enter baudrate [9600]: ").strip() or "9600"
    baudrate = int(baudrate)

    if not mux1_id or not mux2_id:
        print("\nError: Both MUX IDs are required!")
        return

    if port1 == port2:
        print("\nWARNING: Both MUXes are on the same port!")
        print("This script is for SEPARATE ports. Use read_two_muxes.py instead.")
        proceed = input("Continue anyway? (y/n): ").strip().lower()
        if proceed != 'y':
            return

    # Detect addressing modes
    use_extended_1 = len(mux1_id) == 16
    use_extended_2 = len(mux2_id) == 16

    mode1 = "Extended (16-char)" if use_extended_1 else "Standard (3-digit)"
    mode2 = "Extended (16-char)" if use_extended_2 else "Standard (3-digit)"

    print(f"\n{'=' * 70}")
    print("CONFIGURATION SUMMARY")
    print(f"{'=' * 70}")
    print(f"MUX 1:")
    print(f"  Port: {port1}")
    print(f"  ID: {mux1_id} ({mode1})")
    print(f"MUX 2:")
    print(f"  Port: {port2}")
    print(f"  ID: {mux2_id} ({mode2})")
    print(f"Baudrate: {baudrate}")
    print(f"{'=' * 70}\n")

    # Prepare for parallel reading
    results = [None, None]  # Shared list for thread results

    # Create threads for parallel reading
    thread1 = threading.Thread(
        target=read_mux_thread,
        args=(port1, mux1_id, baudrate, use_extended_1, results, 0, "MUX 1")
    )

    thread2 = threading.Thread(
        target=read_mux_thread,
        args=(port2, mux2_id, baudrate, use_extended_2, results, 1, "MUX 2")
    )

    # Start both threads (parallel polling!)
    print("Starting parallel polling...\n")
    start_time = time.time()

    thread1.start()
    thread2.start()

    # Wait for both threads to complete
    thread1.join()
    thread2.join()

    total_time = time.time() - start_time
    print(f"\nBoth MUXes read in {total_time:.3f}s (parallel operation)\n")

    # Display results
    total_weight_all = 0.0
    valid_count_all = 0
    total_sensors = 0

    for result in results:
        if result and result['success']:
            total_weight, valid_count = print_mux_results(result)
            total_weight_all += total_weight
            valid_count_all += valid_count
            total_sensors += len(result['weights'])
        elif result:
            print(f"\n{'=' * 70}")
            print(f"{result['label']}: FAILED")
            print(f"{'=' * 70}")
            print(f"Port: {result['port']}")
            print(f"MUX ID: {result['mux_id']}")
            print(f"Error: {result['error']}")
            print(f"{'=' * 70}\n")

    # Combined summary
    if results[0] and results[1]:
        print("=" * 70)
        print("COMBINED SUMMARY")
        print("=" * 70)
        print(f"Total sensors: {total_sensors}")
        print(f"Valid readings: {valid_count_all}/{total_sensors}")
        print(f"Combined weight: {total_weight_all:.3f} kg")
        print(f"Total read time: {total_time:.3f}s (parallel)")
        print(f"{'=' * 70}")

        # Calculate sequential time for comparison
        seq_time = sum(r['elapsed'] for r in results if r and r['success'])
        speedup = seq_time / total_time if total_time > 0 else 0
        print(f"\nPerformance:")
        print(f"  Parallel time: {total_time:.3f}s")
        print(f"  Sequential time (estimated): {seq_time:.3f}s")
        print(f"  Speedup: {speedup:.2f}x")
        print("=" * 70)

    print("\nReading complete!")


if __name__ == '__main__':
    main()
