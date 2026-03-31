"""Check what's on each layer for the number row to find the Fn layer."""
import os

VID = "3434"
PID = "01e0"
RAW_REPORT_SIZE = 32
CMD_GET_KEYCODE = 0x04


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


def get_keycode(fd, layer, row, col):
    msg = bytearray(RAW_REPORT_SIZE)
    msg[0] = CMD_GET_KEYCODE
    msg[1] = layer
    msg[2] = row
    msg[3] = col
    os.write(fd, bytes(msg))
    resp = os.read(fd, RAW_REPORT_SIZE)
    return (resp[4] << 8) | resp[5]


path = find_hidraw()
if not path:
    print("Keyboard not found!")
    exit(1)

fd = os.open(path, os.O_RDWR)
try:
    # Check number key "1" position (row=1, col=2) on all 4 layers
    print("Probing key '1' (row=1, col=2) across all layers:\n")
    for layer in range(4):
        kc = get_keycode(fd, layer, 1, 2)
        print(f"  Layer {layer}: keycode=0x{kc:04X}")

    print("\nProbing first few number keys on each layer:\n")
    key_names = ["1", "2", "3", "4", "5", "6"]
    for layer in range(4):
        codes = []
        for i, col in enumerate(range(2, 8)):
            kc = get_keycode(fd, layer, 1, col)
            codes.append(f"{key_names[i]}=0x{kc:04X}")
        print(f"  Layer {layer}: {', '.join(codes)}")

    print("\n--- Key reference ---")
    print("  KC_1=0x001E  KC_F1=0x003A  KC_F13=0x0068")
    print("  KC_TRANSPARENT=0x0001  KC_NO=0x0000")
    print("  Layer with 0x0068-0x006D = our remapped F13-F18")
    print("  Layer with 0x0001 (transparent) = Fn layer (falls through to base)")
finally:
    os.close(fd)
