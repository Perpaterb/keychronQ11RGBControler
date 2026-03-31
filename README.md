# Keychron Q11 RGB Controller

A web interface for controlling RGB lighting on the Keychron Q11 split mechanical keyboard. Communicates directly with the keyboard over USB HID using the VIA protocol.

## Features

- **Live RGB Control** -- change effects, color, brightness, and speed from your browser
- **25 Built-in Effects** -- cycle all, rainbow, typing heatmap, digital rain, reactive modes, and more
- **Per-Key RGB** -- set individual key colors using a visual keyboard layout (requires custom firmware)
- **6 Presets** -- save and recall lighting configurations, triggered from the web UI or via Fn+1 through Fn+6 hotkeys
- **Hotkey Listener** -- background daemon detects Fn+1-6 keypresses and applies presets instantly

## Architecture

```
Browser  <-->  Flask API  <-->  /dev/hidraw  <-->  Keychron Q11
                  |
             presets.json
                  |
           evdev key listener (Fn+1-6)
```

The app talks to the keyboard over the raw HID interface (USB usage page `0xFF60`) using 32-byte VIA protocol messages. No drivers or VIA desktop app needed.

## Requirements

- Linux (uses `/dev/hidraw` and `evdev`)
- Python 3.10+
- Keychron Q11 ANSI Encoder (VID `0x3434`, PID `0x01E0`)

## Installation

### 1. System dependencies

```bash
sudo apt install python3.12-venv
```

### 2. Clone and set up

```bash
git clone https://github.com/Perpaterb/keychronQ11RGBControler.git
cd keychronQ11RGBControler
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. udev rule (allows non-root HID access)

```bash
sudo cp 99-keychron.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

You may need to unplug and replug the keyboard after this.

### 4. Run

```bash
source venv/bin/activate
python app.py
```

Open **http://localhost:5001** in your browser.

To also enable Fn+1-6 hotkeys (requires access to `/dev/input`), run with sudo:

```bash
sudo venv/bin/python3 app.py
```

## Usage

### Effect Mode

Select an effect from the dropdown, adjust hue, saturation, brightness, and speed with the sliders. Changes apply to the keyboard in real time.

### Per-Key Mode (requires custom firmware)

Switch to "Per Key" mode to see a visual representation of the Q11 layout. Click individual keys to select them, pick a color, and click "Paint Selected". You can also click-drag across keys to paint as you go.

Per-key RGB requires flashing the custom QMK firmware included in this repo (see below).

### Presets

- **Apply**: click any preset button (Fn+1 through Fn+6) to apply it
- **Save**: configure your desired settings, type a name, and click "Save to Fn+X"
- **Hotkeys**: when running with sudo, pressing Fn+1-6 on the keyboard applies the corresponding preset

## Custom Firmware (Per-Key RGB)

Stock Keychron firmware only supports global RGB settings via HID. The custom firmware adds per-key LED control by hooking into QMK's VIA command processing.

### What the firmware adds

- **Direct mode** (`0x12`): switches the keyboard into per-LED control mode
- **Set single LED** (`0x10`): `[0x10, led_index, R, G, B]`
- **Set LED batch** (`0x11`): `[0x11, start_index, count, R,G,B, ...]` (up to 9 LEDs per message)
- **Set all LEDs** (`0x13`): `[0x13, R, G, B]`
- All standard VIA commands continue to work normally

### Flashing

The pre-built firmware binary is at `firmware/keychron_q11_ansi_encoder_custom.bin`. The QMK keymap source is at `firmware/qmk_keymap/`.

1. **Enter bootloader mode**: unplug the keyboard, hold the Esc key, plug it back in. The keyboard should appear as a DFU device.

2. **Flash**:
   ```bash
   sudo dfu-util -a 0 -d 0483:DF11 -s 0x08000000:leave -D firmware/keychron_q11_ansi_encoder_custom.bin
   ```

3. The keyboard will reboot with the new firmware. All normal keyboard functionality is preserved.

### Building from source

```bash
sudo apt install gcc-arm-none-eabi dfu-util
pip install qmk
qmk setup -H qmk_firmware
cp -r firmware/qmk_keymap qmk_firmware/keyboards/keychron/q11/ansi_encoder/keymaps/custom
qmk compile -kb keychron/q11/ansi_encoder -km custom
```

## Fn+1-6 Hotkey Setup

The Fn+1-6 keys need to be remapped to F13-F18 on the keyboard's Fn layer so Linux can detect them. Run the included remap script:

```bash
source venv/bin/activate
python remap_fn_fix.py
```

This remaps layer 3 (Fn overlay) number keys 1-6 to F13-F18 and saves to EEPROM. Normal typing is not affected. If you flash the custom firmware, this remapping is already included in the keymap.

## File Structure

```
app.py                  Flask backend + HID communication + key listener
static/index.html       Web UI (effect controls, visual keyboard, presets)
requirements.txt        Python dependencies (flask, evdev)
99-keychron.rules       udev rule for non-root HID access
presets.json            Saved presets (auto-generated)
remap_fn_fix.py         Remap Fn+1-6 to F13-F18 on keyboard
firmware/
  keychron_q11_ansi_encoder_custom.bin   Pre-built firmware binary
  qmk_keymap/                           QMK keymap source
    keymap.c                            Keymap with per-LED HID handler
    rules.mk                           Build flags (VIA + RAW_HID)
```

## LED Index Map

The Q11 has 89 LEDs. Indices 0-41 are the left half, 42-88 are the right half. The visual keyboard in the web UI maps to these indices directly. See `firmware/qmk_keymap/keymap.c` and `ansi_encoder.c` in the QMK source for the full mapping.

## License

GPL-2.0 (follows QMK firmware licensing)
