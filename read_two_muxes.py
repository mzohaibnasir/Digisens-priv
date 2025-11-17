#!/usr/bin/env python3
"""
Read Weight Values from Two MUXes
==================================
Simple script to read all weight values from two specified MUX units.

Usage:
    python read_two_muxes.py

The script will prompt you for:
1. Serial port (e.g., /dev/ttyUSB0)
2. First MUX ID
3. Second MUX ID

Supports both standard (3-digit) and extended (16-char) MUX IDs.
"""

from digisens_interface import DigiSensInterface, WeightReading, StatusFlag
import sys


def detect_addressing_mode(mux_id: str) -> bool:
    """
    Detect if MUX ID uses extended addressing mode.

    Args:
        mux_id: MUX identifier

    Returns:
        True if extended mode (16 chars), False if standard (3 digits)
    """
    return len(mux_id) == 16


def print_weights(mux_id: str, weights: list, mux_label: str = "MUX"):
    """
    Print weight readings in a formatted table.

    Args:
        mux_id: MUX identifier
        weights: List of WeightReading objects
        mux_label: Label for display (e.g., "MUX 1", "MUX 2")
    """
    print(f"\n{'=' * 70}")
    print(f"{mux_label}: {mux_id}")
    print(f"{'=' * 70}")
    print(f"{'Channel':<10} {'Weight (kg)':<15} {'Status':<15} {'Valid':<10}")
    print(f"{'-' * 70}")

    for i, reading in enumerate(weights):
        status_icon = "✓" if reading.is_valid else "✗"
        status_name = reading.status.name
        print(f"{i:<10} {reading.weight:<15.3f} {status_name:<15} {status_icon:<10}")

    # Summary
    valid_count = sum(1 for w in weights if w.is_valid)
    total_weight = sum(w.weight for w in weights if w.is_valid)

    print(f"{'-' * 70}")
    print(f"Valid sensors: {valid_count}/{len(weights)}")
    print(f"Total weight: {total_weight:.3f} kg")
    print(f"{'=' * 70}\n")


def main():
    """Main function to read weights from two MUXes."""

    print("=" * 70)
    print("DIGIsens - Read Weight Values from Two MUXes")
    print("=" * 70)

    # Get serial port
    if len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        port = input("\nEnter serial port [/dev/ttyUSB0]: ").strip()
        if not port:
            port = "/dev/ttyUSB0"

    # Get MUX IDs
    if len(sys.argv) > 2:
        mux1_id = sys.argv[2]
    else:
        print("\nEnter first MUX ID:")
        print("  - Standard mode: 3 digits (e.g., 123)")
        print("  - Extended mode: 16 characters (e.g., 0120220429103142)")
        mux1_id = input("MUX 1 ID: ").strip()

    if len(sys.argv) > 3:
        mux2_id = sys.argv[3]
    else:
        mux2_id = input("MUX 2 ID: ").strip()

    # Validate inputs
    if not mux1_id or not mux2_id:
        print("\nError: Both MUX IDs are required!")
        sys.exit(1)

    # Detect addressing modes
    use_extended_1 = detect_addressing_mode(mux1_id)
    use_extended_2 = detect_addressing_mode(mux2_id)

    mode1 = "Extended (16-char)" if use_extended_1 else "Standard (3-digit)"
    mode2 = "Extended (16-char)" if use_extended_2 else "Standard (3-digit)"

    print(f"\nConfiguration:")
    print(f"  Serial Port: {port}")
    print(f"  MUX 1 ID: {mux1_id} ({mode1})")
    print(f"  MUX 2 ID: {mux2_id} ({mode2})")
    print(f"\nConnecting to sensor...")

    try:
        # Connect to the system
        with DigiSensInterface(port, baudrate=9600, timeout=1.0) as sensor:
            print("Connected successfully!\n")

            # Read weights from MUX 1
            print("Reading weights from MUX 1...")
            try:
                weights1 = sensor.get_all_weights(mux1_id, use_extended=use_extended_1)
                print_weights(mux1_id, weights1, "MUX 1")
            except Exception as e:
                print(f"\nError reading MUX 1: {e}\n")
                weights1 = None

            # Read weights from MUX 2
            print("Reading weights from MUX 2...")
            try:
                weights2 = sensor.get_all_weights(mux2_id, use_extended=use_extended_2)
                print_weights(mux2_id, weights2, "MUX 2")
            except Exception as e:
                print(f"\nError reading MUX 2: {e}\n")
                weights2 = None

            # Combined summary
            if weights1 and weights2:
                print("=" * 70)
                print("COMBINED SUMMARY")
                print("=" * 70)

                total_sensors = len(weights1) + len(weights2)
                valid_sensors = sum(1 for w in weights1 if w.is_valid) + \
                               sum(1 for w in weights2 if w.is_valid)
                total_weight = sum(w.weight for w in weights1 if w.is_valid) + \
                              sum(w.weight for w in weights2 if w.is_valid)

                print(f"Total sensors: {total_sensors}")
                print(f"Valid readings: {valid_sensors}/{total_sensors}")
                print(f"Combined weight: {total_weight:.3f} kg")
                print("=" * 70)

            print("\nReading complete!")

    except ConnectionError as e:
        print(f"\nConnection Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Check that the serial port is correct (ls /dev/ttyUSB*)")
        print("  2. Verify user permissions (sudo usermod -a -G dialout $USER)")
        print("  3. Check cable connection")
        print("  4. Ensure MUX units are powered (12V)")
        sys.exit(1)

    except TimeoutError as e:
        print(f"\nTimeout Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Check MUX IDs are correct")
        print("  2. Verify RS485 wiring (pins 1-2 on RJ-45)")
        print("  3. Try different baudrate (test_baudrates.py)")
        print("  4. Use 'ag' broadcast to get MUX ID (only works with ONE MUX):")
        print("     python -c \"from digisens_interface import *; s=DigiSensInterface('/dev/ttyUSB0'); s.connect(); print(s.get_mux_address(True))\"")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user")
        sys.exit(0)

    except Exception as e:
        print(f"\nUnexpected Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
