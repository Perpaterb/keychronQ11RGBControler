"""Fix: restore layers 0-2 to normal, only remap layer 3 (Fn) to F13-F18."""
import os
import sys

VID = "3434"
PID = "01e0"
RAW_REPORT_SIZE = 32
CMD_GET_KEYCODE = 0x04
CMD_SET_KEYCODE = 0x05
CMD_CUSTOM_SAVE = 0x09

KEYS = [
    {"name": "1", "row": 1, "col": 2},
    {"name": "2", "row": 1, "col": 3},
    {"name": "3", "row": 1, "col": 4},
    {"name": "4", "row": 1, "col": 5},
    {"name": "5", "row": 1, "col": 6},
    {"name": "6", "row": 1, "col": 7},
]

KC_ORIGINALS = [0x001E, 0x001F, 0x0020, 0x0021, 0x0022, 0x0023]
KC_F13_F18 = [0x0068, 0x0069, 0x006A, 0x006B, 0x006C, 0x006D]


def find_hidraw():
    for entry in sorted(os.listdir("/sys/class/hidraw")):
        uevent_path = f"/sys/class/hidraw/{entry}/device/uevent"
        if not os.path.exists(uevent_path):
            continue
        with open(uevent_path) as f:
            uevent = f.read()
        if "3434" not in uevent.upper() or "01E0" not in uevent.upper():
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


path = find_hidraw()
if not path:
    print("Keyboard not found!")
    sys.exit(1)

fd = os.open(path, os.O_RDWR)
try:
    # Restore layers 0, 1, 2 to normal number keys
    for layer in [0, 1, 2]:
        print(f"Restoring Layer {layer} to normal keycodes...")
        for key, orig_kc in zip(KEYS, KC_ORIGINALS):
            set_keycode(fd, layer, key["row"], key["col"], orig_kc)

    # Only remap layer 3 (the Fn layer with transparent keys)
    print("Remapping Layer 3 (Fn) to F13-F18...")
    for key, fkc in zip(KEYS, KC_F13_F18):
        set_keycode(fd, 3, key["row"], key["col"], fkc)
        print(f"  Fn+{key['name']} -> F{13 + KC_F13_F18.index(fkc)}")

    # Verify
    print("\nVerifying all layers:")
    for layer in range(4):
        codes = []
        for key in KEYS:
            kc = get_keycode(fd, layer, key["row"], key["col"])
            codes.append(f"{key['name']}=0x{kc:04X}")
        print(f"  Layer {layer}: {', '.join(codes)}")

    msg = bytearray(RAW_REPORT_SIZE)
    msg[0] = CMD_CUSTOM_SAVE
    msg[1] = 0x03
    os.write(fd, bytes(msg))
    print("\nSaved. Normal typing restored. Fn+1-6 on layer 3 = F13-F18.")
finally:
    os.close(fd)
