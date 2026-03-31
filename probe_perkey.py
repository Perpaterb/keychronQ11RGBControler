"""Probe for per-key LED control commands on the Keychron Q11.
Tries various HID command formats to see if any set individual LED colors.
Watch your keyboard while this runs - if any single key changes color, we found it.
"""
import os
import sys
import time

VID = "3434"
PID = "01e0"
RAW_REPORT_SIZE = 32
CMD_SET = 0x07
CMD_GET = 0x08


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
    try:
        return os.read(fd, RAW_REPORT_SIZE)
    except:
        return None


path = find_hidraw()
if not path:
    print("Keyboard not found!")
    sys.exit(1)

fd = os.open(path, os.O_RDWR)

try:
    # First set to solid color so we can see changes
    print("Setting keyboard to dim solid white...")
    send(fd, [CMD_SET, 0x03, 0x02, 1])    # effect = Solid Color
    send(fd, [CMD_SET, 0x03, 0x01, 80])   # brightness = 80
    send(fd, [CMD_SET, 0x03, 0x04, 0, 0]) # hue=0, sat=0 (white)
    time.sleep(1)

    print("\n=== Test 1: Custom channel (0x00) with LED index as value_id ===")
    print("Trying to set LED 5 (F4 key area) to bright red...")
    send(fd, [CMD_SET, 0x00, 5, 255, 0, 0])
    time.sleep(2)

    print("\n=== Test 2: Custom channel with sub-command format ===")
    print("Trying format: [SET, 0x00, 0x10, led_idx, r, g, b]...")
    send(fd, [CMD_SET, 0x00, 0x10, 5, 255, 0, 0])
    time.sleep(2)

    print("\n=== Test 3: RGB matrix channel with value_id > 4 ===")
    print("Trying format: [SET, 0x03, 0x05, led_idx, r, g, b]...")
    send(fd, [CMD_SET, 0x03, 0x05, 5, 255, 0, 0])
    time.sleep(2)

    print("\n=== Test 4: RGB matrix channel, value_id = led_index ===")
    print("Trying format: [SET, 0x03, 5, 255, 0, 0]...")
    send(fd, [CMD_SET, 0x03, 5, 255, 0, 0])
    time.sleep(2)

    print("\n=== Test 5: Direct command byte 0x10 ===")
    print("Trying format: [0x10, led_idx, r, g, b]...")
    send(fd, [0x10, 5, 255, 0, 0])
    time.sleep(2)

    print("\n=== Test 6: OpenRGB-style direct mode ===")
    print("Trying format: [0x00, 0x00, led_idx, r, g, b]...")
    send(fd, [0x00, 0x00, 5, 255, 0, 0])
    time.sleep(2)

    print("\n=== Test 7: Batch LED data format ===")
    print("Trying: [0x07, 0x00, 0xFF, count=1, led=5, r=255, g=0, b=0]...")
    send(fd, [CMD_SET, 0x00, 0xFF, 1, 5, 255, 0, 0])
    time.sleep(2)

    print("\n=== Test 8: Effect NONE + direct set ===")
    print("Setting effect to NONE first, then trying direct LED set...")
    send(fd, [CMD_SET, 0x03, 0x02, 0])  # effect = NONE
    time.sleep(0.5)
    send(fd, [CMD_SET, 0x00, 5, 255, 0, 0])
    time.sleep(2)

    print("\n=== Test 9: Get protocol version ===")
    resp = send(fd, [0x01])
    if resp:
        print(f"Protocol version: {resp[1]}.{resp[2]}")
        # VIA V3 = protocol 12+

    print("\nDid any single key turn red during the tests? (keyboard should be dim white)")
    print("Restoring to solid white...")
    send(fd, [CMD_SET, 0x03, 0x02, 1])
    send(fd, [CMD_SET, 0x03, 0x01, 200])

finally:
    os.close(fd)
