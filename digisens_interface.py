#!/usr/bin/env python3
"""
DIGIsens Weight Sensor Interface
=================================
Python interface for LOWA DIGI SENS protocol over RS485.

This module provides a complete interface to interact with DIGIsens weight
sensors using the RS485 serial protocol.

Author: Generated for DIGIsens Project
Date: 2025-11-12
"""

import serial
import time
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from enum import Enum


class StatusFlag(Enum):
    """Weight measurement status flags."""
    OK = ' '           # Normal measurement
    MOTION = 'M'       # Motion detected (unreliable)
    NOT_CONNECTED = 'C'  # Sensor not connected
    EEPROM_ERROR = 'E'   # EEPROM error (calibration unreadable)


@dataclass
class WeightReading:
    """Represents a single weight measurement."""
    weight: float          # Weight in kg
    status: StatusFlag     # Measurement status
    raw_response: str      # Original response string

    @property
    def is_valid(self) -> bool:
        """Check if measurement is valid (no motion/connection issues)."""
        return self.status == StatusFlag.OK

    def __str__(self) -> str:
        status_str = {
            StatusFlag.OK: "OK",
            StatusFlag.MOTION: "MOTION DETECTED",
            StatusFlag.NOT_CONNECTED: "NOT CONNECTED",
            StatusFlag.EEPROM_ERROR: "EEPROM ERROR"
        }
        return f"{self.weight:.3f} kg [{status_str[self.status]}]"


class DigiSensInterface:
    """
    Interface for DIGIsens weight sensing system.

    This class implements the LOWA DIGI SENS protocol for communication
    with weight sensors via RS485.

    Example usage:
        with DigiSensInterface('/dev/ttyUSB0') as sensor:
            # Read single weight
            weight = sensor.get_weight('123', 0)
            print(f"Weight: {weight}")

            # Read all weights from shelf
            weights = sensor.get_all_weights('123')
            for i, w in enumerate(weights):
                print(f"Sensor {i}: {w}")
    """

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 1.0):
        """
        Initialize the DigiSens interface.

        Args:
            port: Serial port (e.g., '/dev/ttyUSB0', 'COM3')
            baudrate: Communication speed (default: 9600)
            timeout: Read timeout in seconds (default: 1.0)
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial: Optional[serial.Serial] = None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    def connect(self):
        """Open serial connection to the sensor."""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            # Flush any existing data
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            print(f"Connected to {self.port} at {self.baudrate} baud")
        except serial.SerialException as e:
            raise ConnectionError(f"Failed to connect to {self.port}: {e}")

    def disconnect(self):
        """Close serial connection."""
        if self.serial and self.serial.is_open:
            self.serial.close()
            print("Disconnected")

    def _calculate_checksum(self, message: str) -> str:
        """
        Calculate XOR checksum for LOWA protocol.

        Args:
            message: Message string (without checksum)

        Returns:
            Two-character hexadecimal checksum
        """
        checksum = 0
        for char in message:
            checksum ^= ord(char)
        return f"{checksum:02X}"

    def _build_command(self, command: str, mux_id: str, channel: Optional[int] = None,
                      use_extended: bool = False) -> str:
        """
        Build a complete command string with checksum.

        Args:
            command: Command code (e.g., 'gw', 'gl', 'sz')
            mux_id: MUX ID (3 digits for standard, 16 chars for extended)
            channel: Channel number (0-7) if applicable
            use_extended: Use extended addressing mode (#)

        Returns:
            Complete command string ready to send
        """
        # Determine addressing mode
        prefix = '#' if use_extended else '@'

        # Build data portion
        if channel is not None:
            data = f"{mux_id}{channel:02d}"
        else:
            data = mux_id

        # Calculate total length
        # Length = len(command) + len(data) + 2 (checksum)
        # Note: prefix and length field itself are NOT included in the length
        length = len(command) + len(data) + 2

        # Build message without checksum
        message = f"{prefix}{length:02d}{command}{data}"

        # Add checksum
        checksum = self._calculate_checksum(message)
        full_command = f"{message}{checksum}\r"

        return full_command

    def _send_command(self, command: str) -> str:
        """
        Send command and receive response.

        Args:
            command: Complete command string

        Returns:
            Response string (without CR)

        Raises:
            ConnectionError: If not connected
            TimeoutError: If no response received
        """
        if not self.serial or not self.serial.is_open:
            raise ConnectionError("Not connected to sensor")

        # Send command
        self.serial.write(command.encode('ascii'))
        self.serial.flush()

        # Read response (terminated by \r)
        response = self.serial.read_until(b'\r').decode('ascii').strip()

        if not response:
            raise TimeoutError("No response from sensor")

        return response

    def _parse_weight_response(self, response: str) -> WeightReading:
        """
        Parse weight response string.

        Format: @13 0002.130 5C
                @LL{sign}{weight}{status}{checksum}

        Args:
            response: Response string from sensor

        Returns:
            WeightReading object
        """
        # Remove prefix and length
        data = response[3:]  # Skip '@', length (2 digits)

        # Extract components
        # Format: {s}{wwwwwwww}{x}{checksum}
        # s = sign (1 char), w = weight (8 chars), x = status (1 char)
        sign = data[0]
        weight_str = data[1:9].strip()
        status_char = data[9]

        # Parse weight
        weight = float(weight_str)
        if sign == '-':
            weight = -weight

        # Parse status
        try:
            status = StatusFlag(status_char)
        except ValueError:
            status = StatusFlag.OK  # Default if unknown

        return WeightReading(weight=weight, status=status, raw_response=response)

    def get_weight(self, mux_id: str, channel: int, use_extended: bool = False) -> WeightReading:
        """
        Get weight from a single sensor.

        Args:
            mux_id: MUX ID (3 digits standard or 16 chars extended)
            channel: Sensor channel (0-7)
            use_extended: Use extended addressing mode

        Returns:
            WeightReading object

        Example:
            weight = sensor.get_weight('123', 0)
            if weight.is_valid:
                print(f"Weight: {weight.weight} kg")
        """
        command = self._build_command('gw', mux_id, channel, use_extended)
        response = self._send_command(command)
        return self._parse_weight_response(response)

    def get_all_weights(self, mux_id: str, use_extended: bool = False) -> List[WeightReading]:
        """
        Get all weights from a shelf (MUX unit).

        Args:
            mux_id: MUX ID (3 digits standard or 16 chars extended)
            use_extended: Use extended addressing mode

        Returns:
            List of WeightReading objects (typically 8 sensors)

        Example:
            weights = sensor.get_all_weights('123')
            for i, weight in enumerate(weights):
                print(f"Channel {i}: {weight}")
        """
        command = self._build_command('gl', mux_id, use_extended=use_extended)
        response = self._send_command(command)

        # Parse multiple weights
        # Response format: @LL{weight1}{weight2}...{weightN}
        # Each weight is 11 characters: {s}{wwwwwwww}{x}
        data = response[3:]  # Skip '@' and length (2 digits)

        # Remove checksum (last 2 chars)
        data = data[:-2]

        weights = []
        # Each weight block is 11 characters
        for i in range(0, len(data), 11):
            weight_block = data[i:i+11]
            if len(weight_block) == 11:
                # Create a fake response for parsing
                fake_response = f"@13{weight_block}00"
                weight = self._parse_weight_response(fake_response)
                weights.append(weight)

        return weights

    def zero_sensor(self, mux_id: str, channel: int, use_extended: bool = False) -> bool:
        """
        Zero/tare a sensor (writes to EEPROM - use sparingly!).

        WARNING: This command writes to EEPROM which has limited write cycles
        (100,000). Only use during installation and annual calibration.
        For daily operations, use software tare instead.

        Args:
            mux_id: MUX ID
            channel: Sensor channel (0-7)
            use_extended: Use extended addressing mode

        Returns:
            True if successful

        Example:
            # Only during installation!
            sensor.zero_sensor('123', 0)
        """
        command = self._build_command('sz', mux_id, channel, use_extended)
        response = self._send_command(command)
        # Successful response should echo the command
        return 'sz' in response.lower()

    def get_mux_address(self, use_extended: bool = True) -> str:
        """
        Get MUX address/ID using the protocol 'ag' broadcast command.

        IMPORTANT: This command is a broadcast and is FORBIDDEN when multiple
        MUXes are connected (per LOWA protocol specification page 18).
        Only use this when exactly ONE MUX is connected to the bus.

        For systems with multiple MUXes, the ID must be obtained from the
        physical label on each MUX device.

        Args:
            use_extended: Use extended addressing mode (16-char manufacturer ID).
                         Default True as recommended by manufacturer.

        Returns:
            MUX address string (3 digits for standard, 16 chars for extended)

        Raises:
            TimeoutError: No response (MUX not powered, wrong baudrate, or
                         multiple MUXes causing collision)
        """
        # Build broadcast 'ag' command per protocol specification
        # Standard: @05ag<checksum>  Extended: #05ag<checksum>
        prefix = '#' if use_extended else '@'
        message = f"{prefix}05ag"
        checksum = self._calculate_checksum(message)
        command = f"{message}{checksum}\r"

        response = self._send_command(command)
        # Parse address from response
        # Standard response: @06<nnn><CC>  Extended: #19<16-char-id><CC>
        return response[3:-2]  # Remove prefix, length, and checksum

    def get_model_number(self, mux_id: str, use_extended: bool = False) -> str:
        """
        Get MUX model number.

        Args:
            mux_id: MUX ID
            use_extended: Use extended addressing mode

        Returns:
            Model number string (e.g., "H1103")
        """
        command = self._build_command('gm', mux_id, use_extended=use_extended)
        response = self._send_command(command)
        return response[3:-2]  # Remove prefix, length, and checksum

    def get_software_revision(self, mux_id: str, use_extended: bool = False) -> str:
        """
        Get MUX software revision.

        Args:
            mux_id: MUX ID
            use_extended: Use extended addressing mode

        Returns:
            Software revision string (e.g., "2.1")
        """
        command = self._build_command('gr', mux_id, use_extended=use_extended)
        response = self._send_command(command)
        return response[3:-2]  # Remove prefix, length, and checksum

    def set_baudrate(self, mux_id: str, baudrate: int, use_extended: bool = False) -> bool:
        """
        Set MUX communication baudrate.

        Valid baudrates: 9600, 19200, 38400, 57600, 115200

        Args:
            mux_id: MUX ID
            baudrate: New baudrate
            use_extended: Use extended addressing mode

        Returns:
            True if successful
        """
        valid_baudrates = [9600, 19200, 38400, 57600, 115200]
        if baudrate not in valid_baudrates:
            raise ValueError(f"Invalid baudrate. Must be one of {valid_baudrates}")

        # Baudrate codes: 0=9600, 1=19200, 2=38400, 3=57600, 4=115200
        code = valid_baudrates.index(baudrate)

        command = self._build_command(f'br{code}', mux_id, use_extended=use_extended)
        response = self._send_command(command)
        return 'br' in response.lower()

    def poll_continuous(self, mux_id: str, channel: int, interval: float = 1.0,
                       callback=None, use_extended: bool = False):
        """
        Continuously poll a sensor and call callback with results.

        Args:
            mux_id: MUX ID
            channel: Sensor channel (0-7)
            interval: Polling interval in seconds (minimum 0.2)
            callback: Function to call with WeightReading (default: print)
            use_extended: Use extended addressing mode

        Example:
            def my_callback(reading):
                print(f"Weight changed: {reading.weight} kg")

            sensor.poll_continuous('123', 0, interval=1.0, callback=my_callback)
        """
        if interval < 0.2:
            print("Warning: Polling interval < 200ms may cause measurement issues")

        if callback is None:
            callback = lambda r: print(f"[{time.strftime('%H:%M:%S')}] {r}")

        print(f"Polling sensor {mux_id}:{channel} every {interval}s (Ctrl+C to stop)")

        try:
            while True:
                reading = self.get_weight(mux_id, channel, use_extended)
                callback(reading)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nPolling stopped")


class ShelfMonitor:
    """
    High-level interface for monitoring multiple shelves/sensors.

    This class provides a convenient interface for managing multiple
    sensors and tracking inventory changes.
    """

    def __init__(self, interface: DigiSensInterface):
        """
        Initialize shelf monitor.

        Args:
            interface: Connected DigiSensInterface instance
        """
        self.interface = interface
        self.shelves: Dict[str, List[float]] = {}  # MUX ID -> tare weights

    def add_shelf(self, mux_id: str, num_sensors: int = 8, tare_weights: Optional[List[float]] = None):
        """
        Register a shelf for monitoring.

        Args:
            mux_id: MUX ID for the shelf
            num_sensors: Number of sensors on the shelf
            tare_weights: Optional list of tare weights (empty shelf weights)
        """
        if tare_weights is None:
            tare_weights = [0.0] * num_sensors
        self.shelves[mux_id] = tare_weights
        print(f"Registered shelf {mux_id} with {num_sensors} sensors")

    def calibrate_shelf(self, mux_id: str) -> List[float]:
        """
        Calibrate shelf by reading empty weights (software tare).

        Args:
            mux_id: MUX ID for the shelf

        Returns:
            List of tare weights
        """
        print(f"Calibrating shelf {mux_id}... Ensure shelf is empty!")
        time.sleep(2)  # Give user time to prepare

        weights = self.interface.get_all_weights(mux_id)
        tare_weights = [w.weight for w in weights]
        self.shelves[mux_id] = tare_weights

        print(f"Calibration complete. Tare weights: {tare_weights}")
        return tare_weights

    def get_net_weights(self, mux_id: str) -> List[float]:
        """
        Get net weights (gross - tare) for all sensors on a shelf.

        Args:
            mux_id: MUX ID for the shelf

        Returns:
            List of net weights in kg
        """
        if mux_id not in self.shelves:
            raise ValueError(f"Shelf {mux_id} not registered. Call add_shelf() first.")

        weights = self.interface.get_all_weights(mux_id)
        tare_weights = self.shelves[mux_id]

        net_weights = []
        for i, (reading, tare) in enumerate(zip(weights, tare_weights)):
            if reading.is_valid:
                net_weights.append(reading.weight - tare)
            else:
                net_weights.append(None)  # Invalid reading

        return net_weights

    def monitor_shelf(self, mux_id: str, interval: float = 1.0, threshold: float = 0.05):
        """
        Monitor shelf and report weight changes.

        Args:
            mux_id: MUX ID for the shelf
            interval: Polling interval in seconds
            threshold: Minimum weight change to report (kg)
        """
        print(f"Monitoring shelf {mux_id} (threshold: {threshold} kg, Ctrl+C to stop)")

        previous_weights = self.get_net_weights(mux_id)

        try:
            while True:
                time.sleep(interval)
                current_weights = self.get_net_weights(mux_id)

                for i, (prev, curr) in enumerate(zip(previous_weights, current_weights)):
                    if prev is None or curr is None:
                        continue

                    change = curr - prev
                    if abs(change) > threshold:
                        action = "ADDED" if change > 0 else "REMOVED"
                        print(f"[{time.strftime('%H:%M:%S')}] Sensor {i}: {action} {abs(change):.3f} kg "
                              f"(now {curr:.3f} kg)")

                previous_weights = current_weights

        except KeyboardInterrupt:
            print("\nMonitoring stopped")


def main():
    """Example usage and testing."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python digisens_interface.py <serial_port> [mux_id]")
        print("Example: python digisens_interface.py /dev/ttyUSB0 123")
        return

    port = sys.argv[1]
    mux_id = sys.argv[2] if len(sys.argv) > 2 else '000'

    print("=" * 60)
    print("DIGIsens Weight Sensor Interface - Test Program")
    print("=" * 60)

    try:
        # Connect to sensor
        with DigiSensInterface(port) as sensor:
            print("\n1. Getting MUX information...")
            try:
                model = sensor.get_model_number(mux_id)
                print(f"   Model: {model}")
                revision = sensor.get_software_revision(mux_id)
                print(f"   Software: {revision}")
            except Exception as e:
                print(f"   Error: {e}")

            print("\n2. Reading single weight (channel 0)...")
            try:
                weight = sensor.get_weight(mux_id, 0)
                print(f"   {weight}")
            except Exception as e:
                print(f"   Error: {e}")

            print("\n3. Reading all weights...")
            try:
                weights = sensor.get_all_weights(mux_id)
                for i, w in enumerate(weights):
                    print(f"   Channel {i}: {w}")
            except Exception as e:
                print(f"   Error: {e}")

            print("\n4. Starting continuous monitoring...")
            print("   (Press Ctrl+C to stop)")
            sensor.poll_continuous(mux_id, 0, interval=1.0)

    except ConnectionError as e:
        print(f"Connection error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
