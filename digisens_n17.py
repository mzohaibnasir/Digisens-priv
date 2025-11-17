"""
Config.json

{
    "rack1": {
        "shelf1": {
            "uid": "0120250925110711"
        },
        "shelf2": {
            "uid": "0120221124064344"
        }
    }
}


"""



# Actutal script

import serial
import json
import time

# ------------------------------
# LOWA Message Creation
# ------------------------------
def create_lowa_msg(head, uid, command, data):
    c_length = str(len(head + "00" + command + uid + data))
    msg = head + c_length.zfill(2) + command + uid + data
    msg_crc = XOR_CRC_calculation(msg)
    return msg + msg_crc + "\r"

def XOR_CRC_calculation(msg):
    checksum = 0
    for b in msg.encode():
        checksum ^= b
    return str(hex(checksum)[2:]).upper()


# ------------------------------
# Load Configuration
# ------------------------------
def load_config(path="config.json"):
    with open(path, "r") as f:
        return json.load(f)


# ------------------------------
# Initialize Serial
# ------------------------------
def init_serial(port="/dev/ttyUSB0"):
    ser = serial.Serial()
    ser.baudrate = 9600
    ser.timeout = 0.2
    ser.port = port
    ser.open()
    return ser


# ------------------------------
# Read Weight for specific scale
# ------------------------------
def read_scale(ser, uid, scale_number):
    scale_str = f"{scale_number:02d}"   # 00 → 07
    msg = create_lowa_msg("#", uid, "gd", scale_str)

    ser.write(msg.encode())

    reply = ser.read_until(b"\r").decode("utf-8")
    if len(reply) < 5:
        return None

    # Strip header + CRC
    return reply[3:-1]


# ------------------------------
# Read all racks → shelves → 8 scales
# ------------------------------
def read_all_shelves(ser, config):
    results = {}

    for rack, shelves in config.items():
        results[rack] = {}

        for shelf_name, shelf_data in shelves.items():
            uid = shelf_data["uid"]

            results[rack][shelf_name] = {}

            # Loop 0 → 7 (8 scales)
            for scale in range(8):
                weight = read_scale(ser, uid, scale)
                results[rack][shelf_name][f"{scale:02d}"] = weight

    return results


# ------------------------------
# Main Loop
# ------------------------------
def main():
    config = load_config()
    ser = init_serial()

    print("📡 Reading weights using GD from all shelves...\n")

    while True:
        data = read_all_shelves(ser, config)
        print(json.dumps(data, indent=4))
        time.sleep(1)


if __name__ == "__main__":
    main()









"""
Expected Response

{
    "rack1": {
        "shelf1": {
            "00": "12.45",
            "01": "0.00",
            "02": "0.00",
            "03": "0.00",
            "04": "0.00",
            "05": "0.00",
            "06": "0.00",
            "07": "0.00"
        },
        "shelf2": {
            "00": "5.21",
            "01": "0.00",
            "02": "0.00",
            "03": "0.00",
            "04": "0.00",
            "05": "0.00",
            "06": "0.00",
            "07": "0.00"
        }
    }
}


"""