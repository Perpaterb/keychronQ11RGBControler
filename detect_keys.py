import evdev
import select

devices = []
for path in evdev.list_devices():
    dev = evdev.InputDevice(path)
    if "keychron" in dev.name.lower():
        devices.append(dev)
        print(f"Listening on: {dev.path}  {dev.name}")

if not devices:
    print("No Keychron devices found!")
    exit(1)

print("\nPress M1-M5 keys one at a time, then Ctrl+C...\n")

dev_map = {dev.fd: dev for dev in devices}
while True:
    r, _, _ = select.select(dev_map.keys(), [], [])
    for fd in r:
        dev = dev_map[fd]
        for event in dev.read():
            if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                name = evdev.ecodes.KEY.get(event.code, "unknown")
                print(f"[{dev.name}]  keycode={event.code}  name={name}")
