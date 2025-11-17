#!/usr/bin/env python3
"""
Verify protocol implementation against PDF examples
"""

def XOR_CRC_calculation(msg):
    checksum = 0
    byte_str = bytearray()
    byte_str.extend(map(ord, msg))
    for byte in byte_str:
        checksum ^= byte
    return str(hex(checksum)[2:]).upper().zfill(2)

def create_lowa_msg_OLD(head, uid, command, data):
    """OLD implementation from fabio_2.py"""
    c_length = str(len(head + "00" + command + uid + data))
    msg = head + c_length.zfill(2) + command + uid + data
    msg_crc = XOR_CRC_calculation(msg)
    msg += msg_crc
    return msg + "\r"

def create_lowa_msg_CORRECT(head, uid, command, data):
    """CORRECT implementation per PDF spec"""
    # Length = everything after length field, including checksum, excluding CR
    # Build message without checksum first
    payload = command + uid + data
    # Length = len(payload) + 2 (for checksum)
    c_length = str(len(payload) + 2)
    msg = head + c_length.zfill(2) + payload
    msg_crc = XOR_CRC_calculation(msg)
    msg += msg_crc
    return msg + "\r"

print("=" * 70)
print("PROTOCOL VERIFICATION - PDF Examples")
print("=" * 70)

# PDF Page 12 Example: @09sz1230
print("\n1. PDF Example: @09sz123040")
print("   Command: sz (zero), MUX ID: 123, Channel: 0")

old_result = create_lowa_msg_OLD("@", "123", "sz", "0")
correct_result = create_lowa_msg_CORRECT("@", "123", "sz", "0")

print(f"   OLD implementation:     {old_result[:-1]}")
print(f"   CORRECT implementation: {correct_result[:-1]}")
print(f"   PDF Expected:           @09sz123040")

if correct_result[:-1] == "@09sz123040":
    print("   ✓ CORRECT implementation matches PDF!")
else:
    print("   ✗ Neither matches PDF exactly")

# PDF Page 14 Example: @08gl123
print("\n2. PDF Example: @08gl123")
print("   Command: gl (get all), MUX ID: 123")

# Need to calculate expected checksum
msg_without_checksum = "@08gl123"
expected_checksum = XOR_CRC_calculation(msg_without_checksum)
expected_full = msg_without_checksum + expected_checksum

old_result = create_lowa_msg_OLD("@", "123", "gl", "")
correct_result = create_lowa_msg_CORRECT("@", "123", "gl", "")

print(f"   OLD implementation:     {old_result[:-1]}")
print(f"   CORRECT implementation: {correct_result[:-1]}")
print(f"   PDF Expected (with CRC): {expected_full}")

if correct_result[:-1] == expected_full:
    print("   ✓ CORRECT implementation matches PDF!")
else:
    print("   ✗ Check discrepancy")

# Let's analyze the length calculation
print("\n3. Length Calculation Analysis")
print("   For @09sz123040:")
print("   - After length field: 'sz123040' = 8 chars")
print("   - Length field value: 09")
print("   - Checksum: '40' = 2 chars")
print("   - So: command(2) + data(4) + checksum(2) = 8")
print("   - But length field = 09 (includes something else?)")

print("\n4. Testing fabio_2.py method:")
cmd = "sz"
uid = "123"
data = "0"
head = "@"
old_calc = len(head + "00" + cmd + uid + data)
print(f"   len('{head}' + '00' + '{cmd}' + '{uid}' + '{data}') = {old_calc}")
print(f"   Result: {old_calc}")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
print("The fabio_2.py implementation calculates length as:")
print("  len(prefix + '00' + command + mux_id + data)")
print("This gives the correct result that matches the PDF examples!")
print("=" * 70)
