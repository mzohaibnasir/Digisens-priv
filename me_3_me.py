import serial
def create_lowa_msg(head, uid, command, data):
    # Calculate length
    c_length = str(len(head + "00" + command + uid + data))
    msg = head + c_length.zfill(2) + command + uid + data
    # Calculate XOR-CRC
    msg_crc = XOR_CRC_calculation(msg)
    # Add the CRC
    msg += msg_crc
    return msg + "\r"
 
def XOR_CRC_calculation(msg):
    checksum = 0
    byte_str = bytearray()
    byte_str.extend(map(ord, msg))
    for byte in byte_str:
        checksum ^= byte
    return str(hex(checksum)[2:]).upper()

ser = serial.Serial()
ser.baudrate = 9600
ser.timeout = 0.2
ser.port = "/dev/ttyUSB0"
ser.open()

#1 
# ser.write(str.encode("#05ag20\r"))
# # mux_answer = ser.read_until("\r")
# # print(f"{mux_answer=}")

# # mux_answer = mux_answer.decode("ascii")
# # mux_answer = mux_answer[3:-1]
# # print(mux_answer)

uid = '0120250925110711'
# print(f"{uid=}")                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      }")

msg = create_lowa_msg("#", uid, "gd", f"{0}" + f"{0}")
# msg = create_lowa_msg("#", uid, "gl", "")

print(msg)

ser.write(str.encode(msg))
mux_answer = ser.read_until("\r").decode("utf-8")
mux_answer = mux_answer[3:-1]
print(f"{mux_answer=}")
