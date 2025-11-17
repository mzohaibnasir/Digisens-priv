#!/usr/bin/env python3
"""
Get Weight Values from Two MUXes using 'gd' (Get Data) Command
===============================================================
Uses the 'gd' command for higher precision weight readings (9 digits vs 8).

Based on K321e-06_lowa_protocol.pdf Section 4.8.1 (Page 22-23)

Usage:
    python get_weights_gd.py

Command Format:
    Standard:  @|10|gd|nnn|h|k|CC|CR  where k=0 for weight, k=1 for frequency
    Extended:  #|23|gd|nnnnnnnnnnnnnnnn|h|k|CC|CR

Response Format:
    @|14|swwwwwwwwwx|CC|CR
    - 14 = length
    - s = sign (space or -)
    - wwwwwwwww = 9 characters (higher precision!)
    - x = status flag
"""

import serial
import threading
import time
from typing import List, Tuple, Optional


def XOR_CRC_calculation(msg):
    """
    Calculate XOR checksum per PDF Page 12, Section 4.3.

    "The checksum is a XOR on all previous bytes (including "@") modulo 0xFF,
    in Hexadecimal ASCII."
    """
    checksum = 0
    byte_str = bytearray()
    byte_str.extend(map(ord, msg))
    for byte in byte_str:
        checksum ^= byte
    return str(hex(checksum)[2:]).upper().zfill(2)


def create_lowa_msg(head, uid, command, data):
    """
    Build LOWA protocol message per PDF Page 12, Section 4.2.

    Verified against PDF examples:
    - @09sz123040 (Page 12)
    - @08gl12373 (Page 14)
    """
    c_length = str(len(head + "00" + command + uid + data))
    msg = head + c_length.zfill(2) + command + uid + data
    msg_crc = XOR_CRC_calculation(msg)
    msg += msg_crc
    return msg + "\r"


def parse_gd_weight_response(response, channel_idx):
    """
    Parse 'gd' command response per PDF Page 22-23, Section 4.8.1.

    Response format: @|14|swwwwwwwwwx|CC|CR
    - Position 0: @ or #
    - Position 1-2: Length (14)
    - Position 3: Sign (space or -)
    - Position 4-12: Weight (9 chars with decimal)
    - Position 13: Status flag
    - Position 14-15: Checksum

    Args:
        response: Full response string (e.g., "@14 14000.000 6E")
        channel_idx: Channel number

    Returns:
        Tuple of (channel, weight, status, valid)
    """
    # Remove prefix and length: skip first 3 chars
    data = response[3:]

    # Extract components
    sign = data[0]
    weight_str = data[1:10].strip()  # 9 characters for weight
    status_char = data[10]

    # Parse weight
    try:
        weight = float(weight_str)
        if sign == '-':
            weight = -weight
    except ValueError:
        weight = 0.0
        status_char = 'E'

    # Parse status per PDF Page 24-26
    status_map = {
        ' ': 'OK',
        'M': 'MOTION',
        'C': 'NOT_CONNECTED',
        'E': 'EEPROM_ERROR'
    }
    status = status_map.get(status_char, 'UNKNOWN')
    valid = (status_char == ' ')

    return (channel_idx, weight, status, valid)


def read_single_weight_gd(port, mux_id, channel, baudrate=9600, use_extended=True, timeout=0.5):
    """
    Read single weight using 'gd' command per PDF Page 22-23.

    Command: @|10|gd|nnn|h|0|CC|CR  (0 = weight mode, 1 = frequency mode)
    Extended: #|23|gd|nnnnnnnnnnnnnnnn|h|0|CC|CR

    Args:
        port: Serial port
        mux_id: MUX identifier
        channel: Channel number (0-7)
        baudrate: Communication speed (default: 9600)
        use_extended: Use extended addressing
        timeout: Read timeout

    Returns:
        Tuple of (success, channel, weight, status, valid, error_msg)
    """
    try:
        # Open serial connection
        ser = serial.Serial()
        ser.baudrate = baudrate
        ser.timeout = timeout
        ser.port = port
        ser.open()

        # Build 'gd' command
        # k = 0 for weight, k = 1 for frequency
        head = '#' if use_extended else '@'
        channel_str = str(channel)
        data_mode = "0"  # 0 = weight mode

        msg = create_lowa_msg(head, mux_id, "gd", channel_str + data_mode)

        # Send command
        ser.write(str.encode(msg))

        # Read response
        response = ser.read_until(b"\r").decode("utf-8")

        if not response or len(response) < 5:
            ser.close()
            return (False, channel, 0.0, "TIMEOUT", False, "No response or timeout")

        # Parse response
        channel_idx, weight, status, valid = parse_gd_weight_response(response, channel)

        ser.close()
        return (True, channel_idx, weight, status, valid, None)

    except serial.SerialException as e:
        return (False, channel, 0.0, "ERROR", False, f"Serial error: {e}")
    except Exception as e:
        return (False, channel, 0.0, "ERROR", False, f"Error: {e}")


def read_all_weights_gd(port, mux_id, num_channels=8, baudrate=9600, use_extended=True, timeout=0.5):
    """
    Read all weights from a MUX using 'gd' command.

    Reads each channel sequentially with 'gd' command for higher precision.

    Args:
        port: Serial port
        mux_id: MUX identifier
        num_channels: Number of channels (default: 8)
        baudrate: Communication speed
        use_extended: Use extended addressing
        timeout: Read timeout

    Returns:
        Tuple of (success, weights_list, error_message)
        weights_list: List of tuples (channel, weight, status, valid)
    """
    weights = []

    for channel in range(num_channels):
        success, ch, weight, status, valid, error = read_single_weight_gd(
            port, mux_id, channel, baudrate, use_extended, timeout
        )

        if success:
            weights.append((ch, weight, status, valid))
        else:
            weights.append((channel, 0.0, "ERROR", False))

    all_success = len(weights) == num_channels
    return (all_success, weights, None if all_success else "Some channels failed")


def read_mux_parallel(port, mux_id, baudrate, use_extended, results, index, mux_label):
    """
    Thread function to read MUX weights in parallel.
    """
    print(f"[{mux_label}] Reading from {port} using 'gd' command...")
    start_time = time.time()

    success, weights, error = read_all_weights_gd(port, mux_id, 8, baudrate, use_extended)

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
    """
    label = result['label']
    port = result['port']
    mux_id = result['mux_id']
    weights = result['weights']

    print(f"\n{'=' * 80}")
    print(f"{label}: {mux_id} (Port: {port})")
    print(f"{'=' * 80}")
    print(f"{'Channel':<10} {'Weight (kg)':<20} {'Status':<15} {'Valid':<10}")
    print(f"{'-' * 80}")

    total_weight = 0.0
    valid_count = 0

    for channel, weight, status, valid in weights:
        status_icon = "✓" if valid else "✗"
        # Show full precision (9 digits)
        print(f"{channel:<10} {weight:<20.3f} {status:<15} {status_icon:<10}")

        if valid:
            total_weight += weight
            valid_count += 1

    print(f"{'-' * 80}")
    print(f"Valid sensors: {valid_count}/{len(weights)}")
    print(f"Total weight: {total_weight:.3f} kg")
    print(f"Read time: {result['elapsed']:.3f}s")
    print(f"{'=' * 80}\n")

    return total_weight, valid_count


def main():
    """Main function."""
    print("=" * 80)
    print("DIGIsens - Get Weights Using 'gd' Command (Higher Precision)")
    print("=" * 80)
    print("\nUsing 'gd' (Get Data) command per PDF Section 4.8.1 (Page 22-23)")
    print("Advantage: 9-digit weight precision (vs 8-digit in 'gw'/'gl')\n")

    # Configuration for MUX 1
    print("=== MUX 1 Configuration ===")
    port1 = input("Enter serial port for MUX 1 [/dev/ttyUSB0]: ").strip() or "/dev/ttyUSB0"
    mux1_id = input("Enter MUX 1 ID: ").strip()

    # Configuration for MUX 2
    print("\n=== MUX 2 Configuration ===")
    port2 = input("Enter serial port for MUX 2 [/dev/ttyUSB1]: ").strip() or "/dev/ttyUSB1"
    mux2_id = input("Enter MUX 2 ID: ").strip()

    # Baudrate
    print("\n=== Communication Settings ===")
    baudrate = input("Enter baudrate [9600]: ").strip() or "9600"
    baudrate = int(baudrate)

    if not mux1_id or not mux2_id:
        print("\nError: Both MUX IDs are required!")
        return

    # Detect addressing modes
    use_extended_1 = len(mux1_id) == 16
    use_extended_2 = len(mux2_id) == 16

    mode1 = "Extended (16-char)" if use_extended_1 else "Standard (3-digit)"
    mode2 = "Extended (16-char)" if use_extended_2 else "Standard (3-digit)"

    print(f"\n{'=' * 80}")
    print("CONFIGURATION SUMMARY")
    print(f"{'=' * 80}")
    print(f"Command: 'gd' (Get Data) - Higher precision weight reading")
    print(f"MUX 1:")
    print(f"  Port: {port1}")
    print(f"  ID: {mux1_id} ({mode1})")
    print(f"MUX 2:")
    print(f"  Port: {port2}")
    print(f"  ID: {mux2_id} ({mode2})")
    print(f"Baudrate: {baudrate}")
    print(f"{'=' * 80}\n")

    # Prepare for parallel reading
    results = [None, None]

    # Create threads
    thread1 = threading.Thread(
        target=read_mux_parallel,
        args=(port1, mux1_id, baudrate, use_extended_1, results, 0, "MUX 1")
    )

    thread2 = threading.Thread(
        target=read_mux_parallel,
        args=(port2, mux2_id, baudrate, use_extended_2, results, 1, "MUX 2")
    )

    # Start parallel reading
    print("Starting parallel polling with 'gd' command...\n")
    start_time = time.time()

    thread1.start()
    thread2.start()

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
            print(f"\n{'=' * 80}")
            print(f"{result['label']}: FAILED")
            print(f"{'=' * 80}")
            print(f"Port: {result['port']}")
            print(f"MUX ID: {result['mux_id']}")
            print(f"Error: {result['error']}")
            print(f"{'=' * 80}\n")

    # Combined summary
    if results[0] and results[1]:
        print("=" * 80)
        print("COMBINED SUMMARY")
        print("=" * 80)
        print(f"Command used: 'gd' (Get Data) with k=0 (weight mode)")
        print(f"Precision: 9-digit weight (vs 8-digit in 'gl')")
        print(f"Total sensors: {total_sensors}")
        print(f"Valid readings: {valid_count_all}/{total_sensors}")
        print(f"Combined weight: {total_weight_all:.3f} kg")
        print(f"Total read time: {total_time:.3f}s (parallel)")
        print("=" * 80)

        # Calculate performance
        seq_time = sum(r['elapsed'] for r in results if r and r['success'])
        speedup = seq_time / total_time if total_time > 0 else 0
        print(f"\nPerformance:")
        print(f"  Parallel time: {total_time:.3f}s")
        print(f"  Sequential time (estimated): {seq_time:.3f}s")
        print(f"  Speedup: {speedup:.2f}x")
        print("=" * 80)

    print("\nReading complete!")


if __name__ == '__main__':
    main()
