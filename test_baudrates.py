#!/usr/bin/env python3
"""
Test multiple baudrates to find the correct one using protocol 'ag' broadcast.
Per LOWA protocol specification, this only works with ONE MUX connected.
"""
import serial
import time

def test_baudrate(port, baudrate, use_extended=True):
    """
    Test a specific baudrate using protocol 'ag' broadcast command.

    Args:
        port: Serial port path
        baudrate: Baudrate to test
        use_extended: Use extended mode (16-char ID) - recommended by manufacturer

    Returns:
        Response string if successful, None otherwise
    """
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5
        )

        # Build protocol 'ag' broadcast command per specification
        # Standard: @05ag<checksum>  Extended: #05ag<checksum>
        prefix = '#' if use_extended else '@'
        message = f"{prefix}05ag"
        checksum = 0
        for char in message:
            checksum ^= ord(char)
        command = f"{message}{checksum:02X}\r"

        # Send command
        ser.write(command.encode('ascii'))
        time.sleep(0.3)

        # Read response
        response = ser.read(100).decode('ascii', errors='ignore').strip()

        ser.close()

        return response

    except Exception as e:
        return None

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python test_baudrates.py /dev/ttyUSB0")
        print("\nNote: Uses protocol 'ag' broadcast (only works with ONE MUX)")
        print("      Extended addressing mode recommended by manufacturer")
        sys.exit(1)

    port = sys.argv[1]

    baudrates = [9600, 19200, 38400, 57600, 115200]

    print("Testing baudrates on", port)
    print("Using protocol 'ag' broadcast (extended mode)")
    print("IMPORTANT: Only ONE MUX should be connected")
    print("=" * 60)

    for baud in baudrates:
        print(f"\nTesting {baud:6d} baud...", end=' ')
        response = test_baudrate(port, baud, use_extended=True)

        if response:
            print(f"✓ RESPONSE: {repr(response)}")
            print(f"\n*** SUCCESS! MUX responds at {baud} baud ***")
            print(f"\nUpdate your code to use: baudrate={baud}")
            break
        else:
            print("✗ No response")
    else:
        print("\n" + "=" * 60)
        print("No response at any baudrate.")
        print("\nPossible issues:")
        print("  1. MUX not powered (check 12V supply, verify LED)")
        print("  2. RS485 wiring incorrect (check pins 1-2)")
        print("  3. Multiple MUXes connected (broadcast forbidden)")
        print("  4. RS485 converter polarity reversed (swap A/B)")
        print("\nFor systems with multiple MUXes:")
        print("  - Obtain MUX ID from physical device label")
        print("  - Broadcast 'ag' command doesn't work with multiple MUXes")
