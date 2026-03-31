"""Remap Fn+1 through Fn+0 (layer 1, number row) to F13-F22."""
import os
import sys

VID = "3434"
PID = "01e0"
RAW_REPORT_SIZE = 32

CMD_GET_KEYCODE = 0x04
CMD_SET_KEYCODE = 0x05
CMD_CUSTOM_SAVE = 0x09

# Number row 1-0 matrix positions on Q11 (row 1, cols 2-11)
# Layout: M1, `, 1, 2, 3, 4, 5, 6  (left half cols 0-7)
# So 1=col2, 2=col3, 3=col4, 4=col5, 5=col6, 6=col7
# Right half continues: 7, 8, 9, 0 at cols 7-10 (in the full matrix)
NUMBER_KEYS = [
    {"name": "1", "row": 1, "col": 2},
    {"name": "2", "row": 1, "col": 3},
    {"name": "3", "row": 1, "col": 4},
    {"name": "4", "row": 1, "col": 5},
    {"name": "5", "row": 1, "col": 6},
    {"name": "6", "row": 1, "col": 7},
    {"name": "7", "row": 1, "col": 8},
    {"name": "8", "row": 1, "col": 9},
    {"name": "9", "row": 1, "col": 10},
    {"name": "0", "row": 1, "col": 11},
]

LAYER = 1  # Fn layer

# F13-F22 keycodes
TARGET_KEYCODES = [0x0068 + i for i in range(10)]  # F13=0x68 .. F22=0x71


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
    print("Current Fn+number key mappings (layer 1):")
    for key in NUMBER_KEYS:
        kc = get_keycode(fd, LAYER, key["row"], key["col"])
        print(f"  Fn+{key['name']}  row={key['row']} col={key['col']}  keycode=0x{kc:04X}")

    print(f"\nRemapping Fn+1..0 to F13-F22...")
    for key, target_kc in zip(NUMBER_KEYS, TARGET_KEYCODES):
        set_keycode(fd, LAYER, key["row"], key["col"], target_kc)
        fnum = 13 + TARGET_KEYCODES.index(target_kc)
        print(f"  Fn+{key['name']} -> F{fnum} (0x{target_kc:04X})")

    print(f"\nVerifying:")
    for key in NUMBER_KEYS:
        kc = get_keycode(fd, LAYER, key["row"], key["col"])
        print(f"  Fn+{key['name']}  keycode=0x{kc:04X}")

    save_eeprom(fd)
    print("\nSaved to EEPROM. Fn+1..0 now send F13-F22.")
finally:
    os.close(fd)
