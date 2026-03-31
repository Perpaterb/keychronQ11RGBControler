"""Remap M1-M5 keys on Keychron Q11 to F13-F17 using VIA protocol."""
import os
import sys

VID = "3434"
PID = "01e0"
RAW_REPORT_SIZE = 32

# VIA commands
CMD_GET_KEYCODE = 0x04
CMD_SET_KEYCODE = 0x05
CMD_CUSTOM_SAVE = 0x09

# M1-M5 matrix positions on Q11 (layer 0, column 0, rows 1-5)
M_KEYS = [
    {"name": "M1", "layer": 0, "row": 1, "col": 0},
    {"name": "M2", "layer": 0, "row": 2, "col": 0},
    {"name": "M3", "layer": 0, "row": 3, "col": 0},
    {"name": "M4", "layer": 0, "row": 4, "col": 0},
    {"name": "M5", "layer": 0, "row": 5, "col": 0},
]

# QMK keycodes for F13-F17
KC_F13 = 0x0068
KC_F14 = 0x0069
KC_F15 = 0x006A
KC_F16 = 0x006B
KC_F17 = 0x006C

TARGET_KEYCODES = [KC_F13, KC_F14, KC_F15, KC_F16, KC_F17]


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


def hid_command(fd, msg):
    os.write(fd, msg)
    return os.read(fd, RAW_REPORT_SIZE)


def get_keycode(fd, layer, row, col):
    msg = bytearray(RAW_REPORT_SIZE)
    msg[0] = CMD_GET_KEYCODE
    msg[1] = layer
    msg[2] = row
    msg[3] = col
    resp = hid_command(fd, bytes(msg))
    return (resp[4] << 8) | resp[5]


def set_keycode(fd, layer, row, col, keycode):
    msg = bytearray(RAW_REPORT_SIZE)
    msg[0] = CMD_SET_KEYCODE
    msg[1] = layer
    msg[2] = row
    msg[3] = col
    msg[4] = (keycode >> 8) & 0xFF
    msg[5] = keycode & 0xFF
    hid_command(fd, bytes(msg))


def save_eeprom(fd):
    msg = bytearray(RAW_REPORT_SIZE)
    msg[0] = CMD_CUSTOM_SAVE
    msg[1] = 0x03
    os.write(fd, bytes(msg))


path = find_hidraw()
if not path:
    print("Keychron Q11 not found!")
    sys.exit(1)

print(f"Found keyboard at {path}\n")
fd = os.open(path, os.O_RDWR)

try:
    # Read current keycodes
    print("Current M key mappings:")
    for key in M_KEYS:
        kc = get_keycode(fd, key["layer"], key["row"], key["col"])
        print(f"  {key['name']}  row={key['row']} col={key['col']}  keycode=0x{kc:04X}")

    print(f"\nRemapping M1-M5 to F13-F17...")
    for key, target_kc in zip(M_KEYS, TARGET_KEYCODES):
        set_keycode(fd, key["layer"], key["row"], key["col"], target_kc)
        print(f"  {key['name']} -> 0x{target_kc:04X} (F{13 + TARGET_KEYCODES.index(target_kc)})")

    # Verify
    print(f"\nVerifying:")
    for key in M_KEYS:
        kc = get_keycode(fd, key["layer"], key["row"], key["col"])
        print(f"  {key['name']}  keycode=0x{kc:04X}")

    save_eeprom(fd)
    print("\nSaved to EEPROM. M1-M5 now send F13-F17.")
finally:
    os.close(fd)
