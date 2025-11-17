#!/usr/bin/env python3
"""
Get Weight Values using 'gd' Command - FIXED VERSION
====================================================
Keeps serial port open while reading all channels (like fabio_2.py)

Based on K321e-06_lowa_protocol.pdf Section 4.8.1 (Page 22-23)
"""

import serial
import threading
import time


def XOR_CRC_calculation(msg):
    """Calculate XOR checksum per PDF Page 12."""
    checksum = 0
    byte_str = bytearray()
    byte_str.extend(map(ord, msg))
    for byte in byte_str:
        checksum ^= byte
    return str(hex(checksum)[2:]).upper().zfill(2)


def create_lowa_msg(head, uid, command, data):
    """Build LOWA protocol message per PDF Page 12."""
    c_length = str(len(head + "00" + command + uid + data))
    msg = head + c_length.zfill(2) + command + uid + data
    msg_crc = XOR_CRC_calculation(msg)
    msg += msg_crc
    return msg + "\r"


def parse_gd_response(response, channel_idx):
    """Parse 'gd' response: @|14|swwwwwwwwwx|CC|CR"""
    try:
        data = response[3:]  # Skip prefix and length
        sign = data[0]
        weight_str = data[1:10].strip()  # 9 chars
        status_char = data[10]

        weight = float(weight_str)
        if sign == '-':
            weight = -weight

        status_map = {' ': 'OK', 'M': 'MOTION', 'C': 'NOT_CONNECTED', 'E': 'EEPROM_ERROR'}
        status = status_map.get(status_char, 'UNKNOWN')
        valid = (status_char == ' ')

        return (channel_idx, weight, status, valid)
    except Exception as e:
        return (channel_idx, 0.0, f"PARSE_ERROR({e})", False)


def read_all_weights_gd(port, mux_id, num_channels=8, baudrate=9600, use_extended=True):
    """
    Read all weights using 'gd' command.
    FIXED: Keeps serial port open for all reads (like fabio_2.py).
    """
    weights = []

    try:
        # Open serial port ONCE
        ser = serial.Serial()
        ser.baudrate = baudrate
        ser.timeout = 0.5  # 500ms timeout per channel
        ser.port = port
        ser.open()

        # Flush buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        # Read each channel
        head = '#' if use_extended else '@'

        for channel in range(num_channels):
            try:
                # Build command: gd + channel + mode(0=weight)
                msg = create_lowa_msg(head, mux_id, "gd", str(channel) + "0")

                # Send command
                ser.write(str.encode(msg))
                ser.flush()

                # Read response
                response = ser.read_until(b"\r").decode("utf-8")

                if response and len(response) >= 14:
                    ch, weight, status, valid = parse_gd_response(response, channel)
                    weights.append((ch, weight, status, valid))
                else:
                    weights.append((channel, 0.0, "NO_RESPONSE", False))

            except Exception as e:
                weights.append((channel, 0.0, f"ERROR({e})", False))

        # Close port after all reads
        ser.close()

        return (True, weights, None)

    except Exception as e:
        return (False, [], f"Serial error: {e}")


def read_mux_thread(port, mux_id, baudrate, use_extended, results, index, label):
    """Thread function for parallel reading."""
    print(f"[{label}] Reading from {port}...")
    start_time = time.time()

    success, weights, error = read_all_weights_gd(port, mux_id, 8, baudrate, use_extended)

    elapsed = time.time() - start_time

    results[index] = {
        'port': port,
        'mux_id': mux_id,
        'label': label,
        'success': success,
        'weights': weights,
        'error': error,
        'elapsed': elapsed
    }

    if success:
        valid_count = sum(1 for _, _, _, v in weights if v)
        print(f"[{label}] Success! {valid_count}/8 valid sensors in {elapsed:.3f}s")
    else:
        print(f"[{label}] Failed: {error}")


def print_results(result):
    """Print formatted results."""
    label = result['label']
    port = result['port']
    mux_id = result['mux_id']
    weights = result['weights']

    print(f"\n{'=' * 80}")
    print(f"{label}: {mux_id} (Port: {port})")
    print(f"{'=' * 80}")
    print(f"{'Ch':<5} {'Weight (kg)':<15} {'Status':<20} {'Valid':<5}")
    print(f"{'-' * 80}")

    total_weight = 0.0
    valid_count = 0

    for ch, weight, status, valid in weights:
        icon = "✓" if valid else "✗"
        print(f"{ch:<5} {weight:<15.3f} {status:<20} {icon:<5}")
        if valid:
            total_weight += weight
            valid_count += 1

    print(f"{'-' * 80}")
    print(f"Valid: {valid_count}/8  |  Total weight: {total_weight:.3f} kg  |  Time: {result['elapsed']:.3f}s")
    print(f"{'=' * 80}")

    return total_weight, valid_count


def main():
    """Main function."""
    print("=" * 80)
    print("Get Weights Using 'gd' Command - FIXED VERSION")
    print("=" * 80)
    print("Uses 'gd' command with port kept open (like fabio_2.py)\n")

    # Get configuration
    port1 = input("Port for MUX 1 [/dev/ttyUSB0]: ").strip() or "/dev/ttyUSB0"
    mux1_id = input("MUX 1 ID: ").strip()

    port2 = input("Port for MUX 2 [/dev/ttyUSB1]: ").strip() or "/dev/ttyUSB1"
    mux2_id = input("MUX 2 ID: ").strip()

    baudrate = int(input("Baudrate [9600]: ").strip() or "9600")

    if not mux1_id or not mux2_id:
        print("Error: Both MUX IDs required!")
        return

    # Detect addressing
    use_ext1 = len(mux1_id) == 16
    use_ext2 = len(mux2_id) == 16

    print(f"\n{'=' * 80}")
    print("CONFIGURATION")
    print(f"{'=' * 80}")
    print(f"MUX 1: {mux1_id} @ {port1} ({'Extended' if use_ext1 else 'Standard'})")
    print(f"MUX 2: {mux2_id} @ {port2} ({'Extended' if use_ext2 else 'Standard'})")
    print(f"Baudrate: {baudrate}")
    print(f"Command: 'gd' (9-digit precision)")
    print(f"{'=' * 80}\n")

    # Read in parallel
    results = [None, None]

    t1 = threading.Thread(target=read_mux_thread, args=(port1, mux1_id, baudrate, use_ext1, results, 0, "MUX 1"))
    t2 = threading.Thread(target=read_mux_thread, args=(port2, mux2_id, baudrate, use_ext2, results, 1, "MUX 2"))

    print("Reading both MUXes in parallel...\n")
    start = time.time()

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    total_time = time.time() - start
    print(f"\nCompleted in {total_time:.3f}s\n")

    # Display results
    total_weight = 0.0
    total_valid = 0
    total_sensors = 0

    for result in results:
        if result and result['success']:
            weight, valid = print_results(result)
            total_weight += weight
            total_valid += valid
            total_sensors += len(result['weights'])
        elif result:
            print(f"\n{'=' * 80}")
            print(f"{result['label']} FAILED: {result['error']}")
            print(f"{'=' * 80}")

    # Summary
    if results[0] and results[1]:
        print(f"\n{'=' * 80}")
        print("SUMMARY")
        print(f"{'=' * 80}")
        print(f"Total sensors: {total_sensors}")
        print(f"Valid readings: {total_valid}/{total_sensors}")
        print(f"Combined weight: {total_weight:.3f} kg")
        print(f"Total time: {total_time:.3f}s (parallel)")
        print(f"{'=' * 80}\n")


if __name__ == '__main__':
    main()
