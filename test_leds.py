"""Light up left-half LEDs one at a time to map physical positions.
Watch the keyboard -- each LED lights up red for 1 second.
Press Ctrl+C when done.
"""
import os
import time
import sys

VID = "3434"
PID = "01e0"
RAW_REPORT_SIZE = 32


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


def send(fd, data):
    msg = bytearray(RAW_REPORT_SIZE)
    for i, b in enumerate(data):
        msg[i] = b
    os.write(fd, bytes(msg))
    return os.read(fd, RAW_REPORT_SIZE)


path = find_hidraw()
if not path:
    print("Keyboard not found!")
    sys.exit(1)

fd = os.open(path, os.O_RDWR)

try:
    # Enable direct mode
    send(fd, [0x12, 1])
    # Set all LEDs dim white
    send(fd, [0x13, 10, 10, 10])

    print("Cycling through left-half LEDs (0-41).")
    print("Each LED lights up RED for 1 second.")
    print("Write down which physical key lights up for each index.\n")

    for i in range(42):
        # Reset previous LED
        if i > 0:
            send(fd, [0x10, i - 1, 10, 10, 10])
        # Light up current LED bright red
        send(fd, [0x10, i, 255, 0, 0])

        key = input(f"  Index {i:2d} -> which key lit up? ")
        print(f"    Recorded: index {i} = {key}")

    # Disable direct mode
    send(fd, [0x12, 0])

finally:
    os.close(fd)
