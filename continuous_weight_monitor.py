#!/usr/bin/env python3
"""
Continuous Weight Monitor for Multiple MUXes on Single Port
============================================================
- Reads from 5 MUXes on /dev/ttyUSB0
- Zero all MUXes first (empty scales)
- Continuously read weights using 'gd' command (9-digit precision)
- Display real-time weights with timestamps

Based on K321e-06_lowa_protocol.pdf Sections:
- 4.5.1 (Page 16-17): Zero scale command
- 4.8.1 (Page 22-23): Get data command

MUX Configuration (from user):
  MUX 1: 0120221125101002 (Extended 16-char)
  MUX 2: 0120221125084905 (Extended 16-char)
  MUX 3: 0120250919084626 (Extended 16-char)
  MUX 4: 0120221125075550 (Standard 3-digit) <- Extract last 3 digits: "550"
  MUX 5: 0120250925110711 (Extended 16-char)
"""

import serial
import time
import sys
from datetime import datetime
from typing import List, Tuple, Dict


# ============================================================================
# PROTOCOL FUNCTIONS
# ============================================================================

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
    """
    Parse 'gd' response: @|14|swwwwwwwwwx|CC|CR
    Per PDF Page 22-23, Section 4.8.1
    """
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


# ============================================================================
# MUX OPERATIONS
# ============================================================================

def zero_mux_all_channels(ser, mux_id, use_extended=True, num_channels=8):
    """
    Zero all channels of a MUX (Per PDF Page 16-17, Section 4.5.1)

    IMPORTANT: Call this ONLY when scales are empty!
    WARNING: This writes to EEPROM (100,000 write cycle limit)

    Returns: (success, failed_channels)
    """
    head = '#' if use_extended else '@'
    failed_channels = []

    print(f"  Zeroing {num_channels} channels...")

    for channel in range(num_channels):
        try:
            # Build sz (Scale Zero) command
            msg = create_lowa_msg(head, mux_id, "sz", str(channel))

            # Send command
            ser.write(str.encode(msg))
            ser.flush()

            # Read response (should be OK)
            response = ser.read_until(b"\r").decode("utf-8")

            if "OK" not in response:
                failed_channels.append(channel)
                print(f"    Channel {channel}: FAILED")
            else:
                print(f"    Channel {channel}: ✓ Zeroed")

            time.sleep(0.1)  # Small delay between channels

        except Exception as e:
            failed_channels.append(channel)
            print(f"    Channel {channel}: ERROR - {e}")

    success = len(failed_channels) == 0
    return (success, failed_channels)


def read_mux_weights_gd(ser, mux_id, use_extended=True, num_channels=8):
    """
    Read all weights from one MUX using 'gd' command.
    Returns: List of (channel, weight, status, valid) tuples
    """
    head = '#' if use_extended else '@'
    weights = []

    for channel in range(num_channels):
        try:
            # Build gd command: channel + mode(0=weight, 1=frequency)
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

            time.sleep(0.05)  # 50ms delay between channels

        except Exception as e:
            weights.append((channel, 0.0, f"ERROR({e})", False))

    return weights


# ============================================================================
# DISPLAY FUNCTIONS
# ============================================================================

def print_separator():
    """Print visual separator line."""
    print("=" * 100)


def print_mux_weights(mux_label, mux_id, weights, timestamp):
    """Print weights for one MUX in compact format."""
    # Calculate totals
    total_weight = sum(w for _, w, _, v in weights if v)
    valid_count = sum(1 for _, _, _, v in weights if v)

    # Header
    print(f"\n{mux_label} [{mux_id}] @ {timestamp}")
    print("-" * 100)

    # Weights (2 rows of 4 channels each for compact display)
    # Row 1: Channels 0-3
    row1 = ""
    for ch, weight, status, valid in weights[:4]:
        icon = "✓" if valid else "✗"
        row1 += f"Ch{ch}: {weight:8.3f}kg {icon:2}  "
    print(row1)

    # Row 2: Channels 4-7
    row2 = ""
    for ch, weight, status, valid in weights[4:8]:
        icon = "✓" if valid else "✗"
        row2 += f"Ch{ch}: {weight:8.3f}kg {icon:2}  "
    print(row2)

    # Summary
    print(f"Valid: {valid_count}/8  |  Total: {total_weight:8.3f} kg")

    # Show errors if any
    errors = [(ch, status) for ch, _, status, v in weights if not v]
    if errors:
        error_str = ", ".join([f"Ch{ch}:{status}" for ch, status in errors])
        print(f"⚠ Errors: {error_str}")


def print_all_mux_summary(all_weights, timestamp):
    """Print summary of all MUXes."""
    print_separator()
    print(f"SUMMARY @ {timestamp}")
    print_separator()

    total_weight_all = 0.0
    total_valid_all = 0
    total_sensors_all = 0

    for mux_data in all_weights:
        mux_label = mux_data['label']
        weights = mux_data['weights']

        total_weight = sum(w for _, w, _, v in weights if v)
        valid_count = sum(1 for _, _, _, v in weights if v)

        total_weight_all += total_weight
        total_valid_all += valid_count
        total_sensors_all += len(weights)

        print(f"{mux_label:8} | Total: {total_weight:8.3f} kg | Valid: {valid_count}/8")

    print_separator()
    print(f"COMBINED | Total: {total_weight_all:8.3f} kg | Valid: {total_valid_all}/{total_sensors_all}")
    print_separator()


# ============================================================================
# MAIN MONITORING LOOP
# ============================================================================

def main():
    """Main function."""

    # Configuration
    PORT = "/dev/ttyUSB0"
    BAUDRATE = 9600
    TIMEOUT = 0.5
    POLL_INTERVAL = 1.0  # Read every 1 second

    # MUX Configuration (from user)
    MUX_CONFIGS = [
        # {'id': '0120221125101002', 'label': 'MUX 1', 'extended': True},
        # {'id': '0120221125084905', 'label': 'MUX 2', 'extended': True},
        # {'id': '0120250919084626', 'label': 'MUX 3', 'extended': True},
        # {'id': '0120221124064344', 'label': 'MUX 4', 'extended': True},  # Standard mode: last 3 digits
        {'id': '0120250925110711', 'label': 'MUX 5', 'extended': True},
    ]

    print_separator()
    print("DIGISENS - Continuous Weight Monitor (5 MUXes)")
    print_separator()
    print(f"Port: {PORT}")
    print(f"Baudrate: {BAUDRATE}")
    print(f"Command: 'gd' (9-digit precision)")
    print(f"Poll interval: {POLL_INTERVAL}s")
    print_separator()

    print("\nMUX Configuration:")
    for i, mux in enumerate(MUX_CONFIGS, 1):
        mode = "Extended (16-char)" if mux['extended'] else "Standard (3-digit)"
        print(f"  {mux['label']}: {mux['id']} ({mode})")
    print()

    # Ask user if they want to zero all MUXes
    print_separator()
    print("⚠  ZEROING SCALES")
    print_separator()
    print("Zero command writes to EEPROM (100,000 cycle limit).")
    print("Only zero when:")
    print("  1. Scales are EMPTY")
    print("  2. First setup or after maintenance")
    print("  3. NOT for regular taring (do that in software)")
    print()

    zero_choice = input("Zero all MUXes now? (yes/no) [no]: ").strip().lower()

    if zero_choice in ['yes', 'y']:
        print("\n⚠  ENSURE ALL SCALES ARE EMPTY!")
        confirm = input("Confirm scales are empty (yes/no): ").strip().lower()

        if confirm in ['yes', 'y']:
            try:
                # Open serial port
                ser = serial.Serial(PORT, baudrate=BAUDRATE, timeout=TIMEOUT)
                print(f"\n✓ Opened {PORT}\n")

                # Zero each MUX
                for mux_config in MUX_CONFIGS:
                    print(f"Zeroing {mux_config['label']} ({mux_config['id']})...")
                    success, failed = zero_mux_all_channels(
                        ser,
                        mux_config['id'],
                        mux_config['extended']
                    )

                    if success:
                        print(f"  ✓ {mux_config['label']} zeroed successfully\n")
                    else:
                        print(f"  ⚠ {mux_config['label']} failed on channels: {failed}\n")

                    time.sleep(0.2)  # Delay between MUXes

                ser.close()
                print("✓ Zeroing complete!\n")

            except Exception as e:
                print(f"\n✗ Error during zeroing: {e}\n")
                return
        else:
            print("\n✗ Zeroing cancelled.\n")
    else:
        print("\nSkipping zeroing.\n")

    # Start continuous monitoring
    print_separator()
    print("STARTING CONTINUOUS MONITORING")
    print_separator()
    print("Press Ctrl+C to stop\n")

    time.sleep(2)

    try:
        # Open serial port for monitoring
        ser = serial.Serial(PORT, baudrate=BAUDRATE, timeout=TIMEOUT)
        print(f"✓ Monitoring on {PORT}\n")

        cycle_count = 0

        while True:
            cycle_count += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print(f"\n{'#' * 100}")
            print(f"CYCLE {cycle_count} @ {timestamp}")
            print(f"{'#' * 100}")

            all_weights = []

            # Read each MUX sequentially
            for mux_config in MUX_CONFIGS:
                try:
                    # Flush buffers before reading
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()

                    # Read weights
                    weights = read_mux_weights_gd(
                        ser,
                        mux_config['id'],
                        mux_config['extended']
                    )

                    # Store results
                    all_weights.append({
                        'label': mux_config['label'],
                        'id': mux_config['id'],
                        'weights': weights
                    })

                    # Display immediately
                    print_mux_weights(
                        mux_config['label'],
                        mux_config['id'],
                        weights,
                        timestamp
                    )

                except Exception as e:
                    print(f"\n✗ Error reading {mux_config['label']}: {e}")

                time.sleep(0.1)  # Small delay between MUXes

            # Display summary
            print_all_mux_summary(all_weights, timestamp)

            # Wait before next cycle
            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n✓ Monitoring stopped by user")
        ser.close()
        print(f"✓ Closed {PORT}")
        print_separator()

    except Exception as e:
        print(f"\n\n✗ Fatal error: {e}")
        if 'ser' in locals() and ser.is_open:
            ser.close()
        print_separator()


if __name__ == '__main__':
    main()
