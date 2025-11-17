#!/usr/bin/env python3
"""
Hardware test for RS485 converter
"""
import serial
import time

def test_loopback(port):
    """
    Test if RS485 converter is working.

    For this test to work:
    1. Disconnect from MUX
    2. Short RS485 A and B pins together (loopback)
    3. Run this test
    """
    print("RS485 Converter Hardware Test")
    print("=" * 60)
    print("\nPREPARATION:")
    print("  1. Disconnect from MUX unit")
    print("  2. Short RS485 A and B pins together")
    print("  3. Press Enter to continue...")
    input()

    try:
        ser = serial.Serial(
            port=port,
            baudrate=9600,
            timeout=0.5
        )

        test_message = "HELLO123\r\n"

        print("\nSending test message:", repr(test_message))
        ser.write(test_message.encode('ascii'))
        time.sleep(0.2)

        response = ser.read(100).decode('ascii', errors='ignore')

        if response:
            print("✓ Received:", repr(response))
            print("\n*** RS485 converter is working! ***")
            print("\nNext steps:")
            print("  1. Remove the A-B short")
            print("  2. Reconnect to MUX")
            print("  3. Check MUX power supply")
        else:
            print("✗ No echo received")
            print("\nPossible issues:")
            print("  1. RS485 converter not in loopback mode")
            print("  2. A and B not properly shorted")
            print("  3. Converter hardware failure")

        ser.close()

    except Exception as e:
        print(f"Error: {e}")

def test_direct_read(port):
    """
    Just listen on the port to see if MUX is sending anything.
    """
    print("\n" + "=" * 60)
    print("Direct Port Monitor")
    print("=" * 60)
    print("\nListening for any data from MUX...")
    print("Press Ctrl+C to stop\n")

    try:
        ser = serial.Serial(
            port=port,
            baudrate=9600,
            timeout=1.0
        )

        count = 0
        while count < 30:  # 30 seconds
            if ser.in_waiting:
                data = ser.read(ser.in_waiting)
                print(f"Received {len(data)} bytes:", data.hex(), repr(data.decode('ascii', errors='ignore')))
            time.sleep(1)
            count += 1
            print(f"  {count}s - Waiting...", end='\r')

        print("\n\nNo data received in 30 seconds.")
        print("\nThis confirms MUX is not sending data.")
        print("Check:")
        print("  1. MUX power (12V)")
        print("  2. RS485 wiring")

        ser.close()

    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python test_hardware.py /dev/ttyUSB0 [loopback|listen]")
        print("\nModes:")
        print("  loopback - Test RS485 converter with A-B shorted")
        print("  listen   - Listen for any data from MUX")
        sys.exit(1)

    port = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else 'listen'

    if mode == 'loopback':
        test_loopback(port)
    else:
        test_direct_read(port)
