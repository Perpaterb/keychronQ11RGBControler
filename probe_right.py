"""Probe the right half matrix to find number keys 7-0."""
import os
import sys

VID = "3434"
PID = "01e0"
RAW_REPORT_SIZE = 32
CMD_GET_KEYCODE = 0x04

# QMK keycodes for 7, 8, 9, 0
KC_7 = 0x0024
KC_8 = 0x0025
KC_9 = 0x0026
KC_0 = 0x0027
TARGETS = {KC_7: "7", KC_8: "8", KC_9: "9", KC_0: "0"}


def find_hidraw():
    for entry in sorted(os.listdir("/sys/class/hidraw")):
        uevent_path = f"/sys/class/hidraw/{entry}/device/uevent"
        if not os.path.exists(uevent_path):
            continue
        with open(uevent_path) as f:
            uevent = f.read()
        if VID.upper() not in uevent.upper() or PID.upper() not in uevent.upper():
            continue
        rdesc_path = f"/sys/class/hidraw/{entry}/device/report_descriptor"
        if os.path.exists(rdesc_path):
            with open(rdesc_path, "rb") as f:
                rdesc = f.read()
            if b'\x06\x60\xff' in rdesc:
                return f"/dev/{entry}"
    return None


def get_keycode(fd, layer, row, col):
    msg = bytearray(RAW_REPORT_SIZE)
    msg[0] = CMD_GET_KEYCODE
    msg[1] = layer
    msg[2] = row
    msg[3] = col
    resp = os.read(fd, RAW_REPORT_SIZE) if os.write(fd, bytes(msg)) else None
    return (resp[4] << 8) | resp[5] if resp else 0


path = find_hidraw()
if not path:
    print("Not found!")
    sys.exit(1)

fd = os.open(path, os.O_RDWR)
try:
    print("Scanning layer 0 for number keys 7, 8, 9, 0...\n")
    for row in range(0, 14):
        for col in range(0, 16):
            kc = get_keycode(fd, 0, row, col)
            if kc in TARGETS:
                print(f"  Found '{TARGETS[kc]}' at row={row} col={col}  keycode=0x{kc:04X}")
finally:
    os.close(fd)
