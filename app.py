import json
import os
import threading
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static")

# Keychron Q11 USB identifiers
VID = "3434"
PID = "01e0"
RAW_REPORT_SIZE = 32

# VIA protocol commands
CMD_CUSTOM_SET_VALUE = 0x07
CMD_CUSTOM_GET_VALUE = 0x08
CMD_CUSTOM_SAVE = 0x09

# Channel
CH_RGB_MATRIX = 0x03

# RGB Matrix value IDs
VAL_BRIGHTNESS = 0x01
VAL_EFFECT = 0x02
VAL_EFFECT_SPEED = 0x03
VAL_COLOR = 0x04  # 2 bytes: hue, saturation

# QMK RGB Matrix effects (common ones enabled in Keychron firmware)
RGB_EFFECTS = [
    {"id": 0, "name": "Off"},
    {"id": 1, "name": "Solid Color"},
    {"id": 2, "name": "Breathing"},
    {"id": 3, "name": "Band Spiral Val"},
    {"id": 4, "name": "Cycle All"},
    {"id": 5, "name": "Cycle Left Right"},
    {"id": 6, "name": "Cycle Up Down"},
    {"id": 7, "name": "Rainbow Moving Chevron"},
    {"id": 8, "name": "Cycle Out In"},
    {"id": 9, "name": "Cycle Out In Dual"},
    {"id": 10, "name": "Cycle Pinwheel"},
    {"id": 11, "name": "Cycle Spiral"},
    {"id": 12, "name": "Dual Beacon"},
    {"id": 13, "name": "Rainbow Beacon"},
    {"id": 14, "name": "Jellybean Raindrops"},
    {"id": 15, "name": "Pixel Rain"},
    {"id": 16, "name": "Typing Heatmap"},
    {"id": 17, "name": "Digital Rain"},
    {"id": 18, "name": "Solid Reactive Simple"},
    {"id": 19, "name": "Solid Reactive"},
    {"id": 20, "name": "Solid Reactive Multiwide"},
    {"id": 21, "name": "Solid Reactive Multicross"},
    {"id": 22, "name": "Solid Reactive Multinexus"},
    {"id": 23, "name": "Multisplash"},
    {"id": 24, "name": "Solid Multisplash"},
]

# Presets config file
PRESETS_FILE = Path(__file__).parent / "presets.json"

DEFAULT_PRESETS = {
    str(i): {
        "name": f"Preset {i}",
        "mode": "effect",
        "effect": i,
        "brightness": 200,
        "speed": 128,
        "hue": 0,
        "saturation": 255,
        "keys": {},
    }
    for i in range(1, 7)
}

# F13-F18 keycodes (Linux evdev)
PRESET_KEYCODES = {
    183: 1,  # KEY_F13 -> preset 1
    184: 2,  # KEY_F14 -> preset 2
    185: 3,  # KEY_F15 -> preset 3
    186: 4,  # KEY_F16 -> preset 4
    187: 5,  # KEY_F17 -> preset 5
    188: 6,  # KEY_F18 -> preset 6
}


def load_presets():
    if PRESETS_FILE.exists():
        with open(PRESETS_FILE) as f:
            return json.load(f)
    save_presets(DEFAULT_PRESETS)
    return DEFAULT_PRESETS


def save_presets(presets):
    with open(PRESETS_FILE, "w") as f:
        json.dump(presets, f, indent=2)


def find_hidraw_device():
    for entry in sorted(os.listdir("/sys/class/hidraw")):
        device_dir = f"/sys/class/hidraw/{entry}/device"
        uevent_path = os.path.join(device_dir, "uevent")
        if not os.path.exists(uevent_path):
            continue
        with open(uevent_path) as f:
            uevent = f.read()
        if VID.upper() not in uevent.upper() or PID.upper() not in uevent.upper():
            continue
        rdesc_path = os.path.join(device_dir, "report_descriptor")
        if os.path.exists(rdesc_path):
            with open(rdesc_path, "rb") as f:
                rdesc = f.read()
            if b'\x06\x60\xff' in rdesc:
                return f"/dev/{entry}"
    return None


def build_msg(command, channel, value_id, *values):
    msg = bytearray(RAW_REPORT_SIZE)
    msg[0] = command
    msg[1] = channel
    msg[2] = value_id
    for i, v in enumerate(values):
        msg[3 + i] = v & 0xFF
    return bytes(msg)


def send_and_receive(msg):
    path = find_hidraw_device()
    if not path:
        raise ConnectionError("Keychron Q11 not found. Is it connected?")
    fd = os.open(path, os.O_RDWR)
    try:
        os.write(fd, msg)
        return os.read(fd, RAW_REPORT_SIZE)
    finally:
        os.close(fd)


def send_only(msg):
    path = find_hidraw_device()
    if not path:
        raise ConnectionError("Keychron Q11 not found. Is it connected?")
    fd = os.open(path, os.O_RDWR)
    try:
        os.write(fd, msg)
    finally:
        os.close(fd)


def apply_preset(preset_num):
    presets = load_presets()
    preset = presets.get(str(preset_num))
    if not preset:
        return
    print(f"Applying preset {preset_num}: {preset['name']}")
    try:
        mode = preset.get("mode", "effect")
        if mode == "per_key" and preset.get("keys"):
            apply_per_key(preset)
        else:
            # Disable direct mode if switching back to effects
            try:
                msg = bytearray(RAW_REPORT_SIZE)
                msg[0] = 0x12  # HID_CMD_DIRECT_MODE
                msg[1] = 0     # disable
                send_and_receive(bytes(msg))
            except Exception:
                pass
            send_only(build_msg(CMD_CUSTOM_SET_VALUE, CH_RGB_MATRIX, VAL_EFFECT, preset["effect"]))
            send_only(build_msg(CMD_CUSTOM_SET_VALUE, CH_RGB_MATRIX, VAL_BRIGHTNESS, preset["brightness"]))
            send_only(build_msg(CMD_CUSTOM_SET_VALUE, CH_RGB_MATRIX, VAL_EFFECT_SPEED, preset["speed"]))
            send_only(build_msg(CMD_CUSTOM_SET_VALUE, CH_RGB_MATRIX, VAL_COLOR, preset["hue"], preset["saturation"]))
    except ConnectionError as e:
        print(f"Failed to apply preset: {e}")


def apply_per_key(preset):
    """Apply per-key colors using custom firmware HID commands."""
    keys = preset.get("keys", {})
    brightness = preset.get("brightness", 255)

    if not keys:
        return

    path = find_hidraw_device()
    if not path:
        raise ConnectionError("Keychron Q11 not found.")

    fd = os.open(path, os.O_RDWR)
    try:
        # Set brightness via VIA
        msg = build_msg(CMD_CUSTOM_SET_VALUE, CH_RGB_MATRIX, VAL_BRIGHTNESS, brightness)
        os.write(fd, msg)
        os.read(fd, RAW_REPORT_SIZE)

        # Enable direct mode (custom firmware command 0x12)
        msg = bytearray(RAW_REPORT_SIZE)
        msg[0] = 0x12  # HID_CMD_DIRECT_MODE
        msg[1] = 1     # enable
        os.write(fd, bytes(msg))
        os.read(fd, RAW_REPORT_SIZE)

        # Send LED colors in batches of 9 (max per 32-byte message)
        led_items = sorted([(int(k), v) for k, v in keys.items()])
        i = 0
        while i < len(led_items):
            # Find contiguous runs for batch sending
            batch_start = led_items[i][0]
            batch = []
            while i < len(led_items) and len(batch) < 9:
                idx, rgb = led_items[i]
                if idx == batch_start + len(batch):
                    batch.append(rgb)
                    i += 1
                else:
                    break

            if len(batch) > 1:
                # Batch send: [0x11, start, count, R,G,B, R,G,B, ...]
                msg = bytearray(RAW_REPORT_SIZE)
                msg[0] = 0x11  # HID_CMD_SET_LED_BATCH
                msg[1] = batch_start
                msg[2] = len(batch)
                for j, rgb in enumerate(batch):
                    msg[3 + j * 3] = rgb[0]
                    msg[4 + j * 3] = rgb[1]
                    msg[5 + j * 3] = rgb[2]
                os.write(fd, bytes(msg))
                os.read(fd, RAW_REPORT_SIZE)
            else:
                # Single LED: [0x10, index, R, G, B]
                idx, rgb = led_items[i - 1][0], batch[0]
                msg = bytearray(RAW_REPORT_SIZE)
                msg[0] = 0x10  # HID_CMD_SET_LED
                msg[1] = idx
                msg[2] = rgb[0]
                msg[3] = rgb[1]
                msg[4] = rgb[2]
                os.write(fd, bytes(msg))
                os.read(fd, RAW_REPORT_SIZE)

        print(f"  Per-key preset applied: {len(keys)} LEDs set")
    finally:
        os.close(fd)


def start_key_listener():
    try:
        import evdev
        import select
    except ImportError:
        print("evdev not installed, key listener disabled")
        return

    def listener():
        while True:
            try:
                devices = []
                for path in evdev.list_devices():
                    dev = evdev.InputDevice(path)
                    if "keychron" in dev.name.lower():
                        devices.append(dev)
                if not devices:
                    print("No Keychron input devices found, retrying in 5s...")
                    import time
                    time.sleep(5)
                    continue

                print(f"Key listener active on {len(devices)} device(s)")
                dev_map = {dev.fd: dev for dev in devices}
                while True:
                    r, _, _ = select.select(list(dev_map.keys()), [], [])
                    for fd in r:
                        dev = dev_map[fd]
                        for event in dev.read():
                            if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                                if event.code in PRESET_KEYCODES:
                                    apply_preset(PRESET_KEYCODES[event.code])
            except PermissionError:
                print("Key listener: permission denied on input device. Run with sudo or add user to input group.")
                return
            except Exception as e:
                print(f"Key listener error: {e}, restarting...")
                import time
                time.sleep(2)

    t = threading.Thread(target=listener, daemon=True)
    t.start()


# --- API Routes ---


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/effects")
def get_effects():
    return jsonify(RGB_EFFECTS)


@app.route("/api/state")
def get_state():
    try:
        resp = send_and_receive(build_msg(CMD_CUSTOM_GET_VALUE, CH_RGB_MATRIX, VAL_BRIGHTNESS))
        brightness = resp[3] if resp else 0

        resp = send_and_receive(build_msg(CMD_CUSTOM_GET_VALUE, CH_RGB_MATRIX, VAL_EFFECT))
        effect = resp[3] if resp else 0

        resp = send_and_receive(build_msg(CMD_CUSTOM_GET_VALUE, CH_RGB_MATRIX, VAL_EFFECT_SPEED))
        speed = resp[3] if resp else 0

        resp = send_and_receive(build_msg(CMD_CUSTOM_GET_VALUE, CH_RGB_MATRIX, VAL_COLOR))
        hue = resp[3] if resp else 0
        saturation = resp[4] if resp else 0

        return jsonify({
            "brightness": brightness,
            "effect": effect,
            "speed": speed,
            "hue": hue,
            "saturation": saturation,
        })
    except ConnectionError as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/brightness", methods=["POST"])
def set_brightness():
    value = max(0, min(255, int(request.json.get("value", 0))))
    try:
        send_only(build_msg(CMD_CUSTOM_SET_VALUE, CH_RGB_MATRIX, VAL_BRIGHTNESS, value))
        return jsonify({"brightness": value})
    except ConnectionError as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/effect", methods=["POST"])
def set_effect():
    value = max(0, min(255, int(request.json.get("value", 0))))
    try:
        send_only(build_msg(CMD_CUSTOM_SET_VALUE, CH_RGB_MATRIX, VAL_EFFECT, value))
        return jsonify({"effect": value})
    except ConnectionError as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/speed", methods=["POST"])
def set_speed():
    value = max(0, min(255, int(request.json.get("value", 0))))
    try:
        send_only(build_msg(CMD_CUSTOM_SET_VALUE, CH_RGB_MATRIX, VAL_EFFECT_SPEED, value))
        return jsonify({"speed": value})
    except ConnectionError as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/color", methods=["POST"])
def set_color():
    hue = max(0, min(255, int(request.json.get("hue", 0))))
    saturation = max(0, min(255, int(request.json.get("saturation", 255))))
    try:
        send_only(build_msg(CMD_CUSTOM_SET_VALUE, CH_RGB_MATRIX, VAL_COLOR, hue, saturation))
        return jsonify({"hue": hue, "saturation": saturation})
    except ConnectionError as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/presets")
def get_presets():
    return jsonify(load_presets())


@app.route("/api/presets/<int:num>", methods=["PUT"])
def update_preset(num):
    if num < 1 or num > 6:
        return jsonify({"error": "Preset must be 1-6"}), 400
    presets = load_presets()
    data = request.json
    presets[str(num)] = {
        "name": data.get("name", f"Preset {num}"),
        "mode": data.get("mode", "effect"),
        "effect": max(0, min(255, int(data.get("effect", 0)))),
        "brightness": max(0, min(255, int(data.get("brightness", 200)))),
        "speed": max(0, min(255, int(data.get("speed", 128)))),
        "hue": max(0, min(255, int(data.get("hue", 0)))),
        "saturation": max(0, min(255, int(data.get("saturation", 255)))),
        "keys": data.get("keys", {}),
    }
    save_presets(presets)
    return jsonify(presets[str(num)])


@app.route("/api/presets/<int:num>/apply", methods=["POST"])
def apply_preset_route(num):
    if num < 1 or num > 6:
        return jsonify({"error": "Preset must be 1-6"}), 400
    try:
        apply_preset(num)
        return jsonify({"status": "applied", "preset": num})
    except ConnectionError as e:
        return jsonify({"error": str(e)}), 503


if __name__ == "__main__":
    start_key_listener()
    app.run(host="0.0.0.0", port=5001, debug=True, use_reloader=False)
