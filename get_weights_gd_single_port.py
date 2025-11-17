#!/usr/bin/env python3
"""
Get Weight Values from Multiple MUXes on Single Port using 'gd' Command
========================================================================
For RS485 bus topology: Multiple MUXes on one serial port (e.g., /dev/ttyUSB0)

Based on K321e-06_lowa_protocol.pdf Section 4.8.1 (Page 22-23)

Usage:
    python get_weights_gd_single_port.py

Architecture:
    /dev/ttyUSB0 ──[RS485 Bus]── MUX 1 (ID: xxxx)
                              ├── MUX 2 (ID: yyyy)
                              ├── MUX 3 (ID: zzzz)
                              └── MUX N (ID: ...)

All MUXes share the same serial port but have unique IDs.
"""

import serial
import time
from typing import List, Tuple


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


def read_all_weights_gd_single_port(ser, mux_id, num_channels=8, use_extended=True, inter_command_delay=0.05):
    """
    Read all weights from ONE MUX using 'gd' command on shared serial port.

    Args:
        ser: Already opened serial port object
        mux_id: MUX identifier
        num_channels: Number of channels (default: 8)
        use_extended: Use extended addressing
        inter_command_delay: Delay between commands (seconds)

    Returns:
        Tuple of (success, weights_list, error_message)
        weights_list: List of tuples (channel, weight, status, valid)
    """
    weights = []

    try:
        # Flush buffers before starting
        ser.reset_input_buffer()
        ser.reset_output_buffer()

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

                # Small delay between commands on shared bus
                if inter_command_delay > 0:
                    time.sleep(inter_command_delay)

            except Exception as e:
                weights.append((channel, 0.0, f"ERROR({e})", False))

        return (True, weights, None)

    except Exception as e:
        return (False, [], f"Error reading MUX: {e}")


def read_multiple_muxes_single_port(port, mux_configs, baudrate=9600, timeout=0.5, inter_mux_delay=0.1):
    """
    Read weights from multiple MUXes on a single serial port.

    Args:
        port: Serial port (e.g., '/dev/ttyUSB0')
        mux_configs: List of dicts with 'id' and 'label' keys
        baudrate: Communication speed
        timeout: Read timeout per channel
        inter_mux_delay: Delay between MUXes (seconds)

    Returns:
        List of result dicts for each MUX
    """
    results = []

    try:
        # Open serial port ONCE for all MUXes
        ser = serial.Serial()
        ser.baudrate = baudrate
        ser.timeout = timeout
        ser.port = port
        ser.open()

        print(f"✓ Opened {port} @ {baudrate} baud\n")

        # Read each MUX sequentially on the shared bus
        for idx, mux_config in enumerate(mux_configs):
            mux_id = mux_config['id']
            label = mux_config['label']
            use_extended = len(mux_id) == 16

            print(f"[{label}] Reading MUX {mux_id}...")
            start_time = time.time()

            success, weights, error = read_all_weights_gd_single_port(
                ser, mux_id, 8, use_extended
            )

            elapsed = time.time() - start_time

            results.append({
                'port': port,
                'mux_id': mux_id,
                'label': label,
                'success': success,
                'weights': weights,
                'error': error,
                'elapsed': elapsed
            })

            if success:
                valid_count = sum(1 for _, _, _, v in weights if v)
                print(f"[{label}] ✓ {valid_count}/8 valid sensors in {elapsed:.3f}s")
            else:
                print(f"[{label}] ✗ Failed: {error}")

            # Delay between MUXes on shared bus
            if inter_mux_delay > 0 and idx < len(mux_configs) - 1:
                time.sleep(inter_mux_delay)

        # Close port after reading all MUXes
        ser.close()
        print(f"\n✓ Closed {port}\n")

        return results

    except Exception as e:
        print(f"\n✗ Serial port error: {e}\n")
        return []


def print_results(result):
    """Print formatted results for one MUX."""
    label = result['label']
    port = result['port']
    mux_id = result['mux_id']
    weights = result['weights']

    print(f"{'=' * 80}")
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
    print(f"{'=' * 80}\n")

    return total_weight, valid_count


def main():
    """Main function."""
    print("=" * 80)
    print("Get Weights Using 'gd' Command - Single Port / Multiple MUXes")
    print("=" * 80)
    print("For RS485 bus topology: Multiple MUXes on one serial port")
    print("Uses 'gd' command with 9-digit precision\n")

    # Get port configuration
    port = input("Serial port [/dev/ttyUSB0]: ").strip() or "/dev/ttyUSB0"
    baudrate = int(input("Baudrate [9600]: ").strip() or "9600")

    # Get number of MUXes
    num_muxes = int(input("Number of MUXes on this port: ").strip())

    if num_muxes < 1:
        print("Error: Must have at least 1 MUX!")
        return

    # Get MUX configurations
    mux_configs = []
    print()
    for i in range(num_muxes):
        print(f"=== MUX {i + 1} Configuration ===")
        mux_id = input(f"MUX {i + 1} ID: ").strip()

        if not mux_id:
            print("Error: MUX ID cannot be empty!")
            return

        mux_configs.append({
            'id': mux_id,
            'label': f"MUX {i + 1}"
        })
        print()

    # Display configuration summary
    print(f"{'=' * 80}")
    print("CONFIGURATION SUMMARY")
    print(f"{'=' * 80}")
    print(f"Port: {port}")
    print(f"Baudrate: {baudrate}")
    print(f"Command: 'gd' (Get Data) - 9-digit precision")
    print(f"Number of MUXes: {num_muxes}")
    print()
    for i, config in enumerate(mux_configs, 1):
        mode = "Extended (16-char)" if len(config['id']) == 16 else "Standard (3-digit)"
        print(f"  MUX {i}: {config['id']} ({mode})")
    print(f"{'=' * 80}\n")

    # Read all MUXes
    print(f"Reading {num_muxes} MUX(es) sequentially on {port}...\n")
    start_time = time.time()

    results = read_multiple_muxes_single_port(port, mux_configs, baudrate)

    total_time = time.time() - start_time
    print(f"Completed in {total_time:.3f}s\n")

    # Display results
    total_weight_all = 0.0
    valid_count_all = 0
    total_sensors = 0

    for result in results:
        if result and result['success']:
            weight, valid = print_results(result)
            total_weight_all += weight
            valid_count_all += valid
            total_sensors += len(result['weights'])
        elif result:
            print(f"{'=' * 80}")
            print(f"{result['label']} FAILED")
            print(f"{'=' * 80}")
            print(f"MUX ID: {result['mux_id']}")
            print(f"Error: {result['error']}")
            print(f"{'=' * 80}\n")

    # Combined summary
    if results:
        print("=" * 80)
        print("COMBINED SUMMARY")
        print("=" * 80)
        print(f"Port: {port}")
        print(f"Command: 'gd' (Get Data) with k=0 (weight mode)")
        print(f"Precision: 9-digit weight")
        print(f"Total MUXes: {len(results)}")
        print(f"Total sensors: {total_sensors}")
        print(f"Valid readings: {valid_count_all}/{total_sensors}")
        print(f"Combined weight: {total_weight_all:.3f} kg")
        print(f"Total time: {total_time:.3f}s (sequential on shared bus)")
        print("=" * 80)

    print("\nDone!")


if __name__ == '__main__':
    main()
