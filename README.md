# Keychron Q11 RGB Controller

A web interface for controlling RGB lighting on the Keychron Q11 split mechanical keyboard. Communicates directly with the keyboard over USB HID using the VIA protocol, with custom QMK firmware for per-key RGB control.

## Features

- **Live RGB Control** -- change effects, color, brightness, and speed from your browser
- **25 Built-in Effects** -- cycle all, rainbow, typing heatmap, digital rain, reactive modes, and more
- **Per-Key RGB** -- set individual key colors using an interactive visual keyboard layout (requires custom firmware)
- **6 Presets** -- save and recall lighting configurations, triggered from the web UI or via Fn+1 through Fn+6 hotkeys
- **Hotkey Listener** -- background daemon detects Fn+1-6 keypresses and applies presets instantly
- **Caps Lock Indicator** -- caps lock key turns white when active, in all modes (effect and per-key)
- **Split Keyboard Support** -- custom firmware syncs per-key RGB data to both halves via QMK split transport

## Architecture

```
Browser  <-->  Flask API  <-->  /dev/hidraw  <-->  Keychron Q11 (left half)
                  |                                       |
             presets.json                           TRRS cable
                  |                                       |
           evdev key listener (Fn+1-6)             Right half (slave)
```

The app talks to the keyboard over the raw HID interface (USB usage page `0xFF60`) using 32-byte VIA protocol messages. No drivers or VIA desktop app needed.

For per-key RGB, the custom firmware adds a "direct mode" where the host sends individual LED colors over HID. The left half (master) receives the data and syncs the right half's colors over the split transport in 9-LED chunks per frame (~100ms for full right-half sync).

## Requirements

- Linux (uses `/dev/hidraw` and `evdev`)
- Python 3.10+
- Keychron Q11 ANSI Encoder (VID `0x3434`, PID `0x01E0`)
- `dfu-util` for flashing custom firmware

## Installation

### 1. System dependencies

```bash
sudo apt install python3.12-venv dfu-util
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

### 4. Flash custom firmware (required for per-key RGB)

The Q11 is a split keyboard -- **both halves must be flashed separately** with the same firmware binary.

#### Left half (master)

1. Unplug the keyboard.
2. Hold the **Esc** key while plugging the USB-C cable into the **left half**. It enters DFU bootloader mode.
3. Flash:
   ```bash
   sudo dfu-util -a 0 -d 0483:DF11 -s 0x08000000:leave -D firmware/keychron_q11_ansi_encoder_custom.bin
   ```
4. The left half reboots automatically.

#### Right half (slave)

1. Unplug the USB-C cable **and** the TRRS bridging cable from the right half.
2. Locate the small reset hole/button on the right PCB (near the right space bar switch area -- you may need to remove keycaps to access it).
3. Press and hold the **reset button**, then plug the USB-C cable into the **right half**. It enters DFU bootloader mode.
4. Flash with the same command:
   ```bash
   sudo dfu-util -a 0 -d 0483:DF11 -s 0x08000000:leave -D firmware/keychron_q11_ansi_encoder_custom.bin
   ```
5. The right half reboots. Reconnect normally: USB-C to left half, TRRS cable between halves.

### 5. Remap Fn+1-6 hotkeys

The custom firmware includes Fn+1-6 mapped to F13-F18 in the keymap. If you're using stock firmware without flashing, run the remap script instead:

```bash
source venv/bin/activate
python remap_fn_fix.py
```

This remaps layer 3 (Fn overlay) number keys 1-6 to F13-F18 and saves to EEPROM. Normal typing is not affected.

### 6. Run

#### Option A: Run as a systemd service (recommended)

This starts the controller automatically on boot:

```bash
sudo cp keychron-controller.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now keychron-controller
```

Useful commands:

```bash
sudo systemctl status keychron-controller   # check status
sudo journalctl -u keychron-controller -f   # watch logs
sudo systemctl restart keychron-controller   # restart
```

#### Option B: Run manually

```bash
source venv/bin/activate
python app.py
```

To also enable Fn+1-6 hotkeys (requires access to `/dev/input`), run with sudo:

```bash
sudo venv/bin/python3 app.py
```

Open **http://localhost:5001** in your browser. The port can be changed with the `PORT` environment variable.

## Usage

### Effect Mode

Select an effect from the dropdown, adjust hue, saturation, brightness, and speed with the sliders. Changes apply to the keyboard in real time.

Available effects include: Solid Color, Breathing, Cycle All, Cycle Left Right, Rainbow Beacon, Typing Heatmap, Digital Rain, Solid Reactive, Multisplash, and many more.

### Per-Key Mode

Switch to "Per Key" mode to see a visual representation of the Q11 split layout (89 keys).

- **Click** a key to select/deselect it
- **Click and drag** across keys to paint them with the current color
- Use the **R/G/B sliders** to pick a color
- **Paint Selected** -- apply the current color to all selected keys
- **Paint All** -- apply the current color to every key
- **Select All** -- select all keys
- **Deselect All** -- clear the selection
- **Clear All** -- remove all per-key colors and reset

Per-key RGB requires the custom firmware. Without it, effect mode still works fully.

### Presets

There are 6 preset slots, each mapped to Fn+1 through Fn+6:

- **Apply**: click a preset button in the web UI, or press Fn+1-6 on the keyboard
- **Save**: configure your desired settings (effect or per-key), enter a name, and click "Save to Fn+X"
- Presets can store either an effect configuration (effect, color, brightness, speed) or a full per-key color layout
- Presets are saved to `presets.json` and persist across restarts

### Caps Lock Indicator

When caps lock is active, the caps lock key (LED index 23) turns white regardless of the current RGB mode. This works in both effect mode and per-key direct mode.

## Custom Firmware Details

### What the firmware adds

The custom QMK firmware extends the default Keychron Q11 keymap with:

- **Direct mode** (`0x12`): switches the keyboard into per-LED control mode. Normal effects are overridden by the host-set colors.
- **Set single LED** (`0x10`): `[0x10, led_index, R, G, B]`
- **Set LED batch** (`0x11`): `[0x11, start_index, count, R,G,B, ...]` (up to 9 LEDs per message)
- **Set all LEDs** (`0x13`): `[0x13, R, G, B]`
- **Split sync**: right-half LED data is synced from master to slave via QMK's split transaction RPC (9 LEDs per frame, ~100ms for full sync)
- **Caps lock indicator**: white override on LED 23 in all modes
- **Fn+1-6 = F13-F18**: baked into the MAC_FN and WIN_FN layers
- All standard VIA commands and keyboard functionality continue to work normally

### HID Protocol

All per-key commands use the raw HID interface (usage page `0xFF60`, 32-byte messages). Commands 0x10-0x13 are intercepted by `via_command_kb()` before VIA processing. All other commands pass through to VIA normally.

### Building from source

```bash
sudo apt install gcc-arm-none-eabi dfu-util
pip install qmk
qmk setup -H qmk_firmware
cp -r firmware/qmk_keymap qmk_firmware/keyboards/keychron/q11/ansi_encoder/keymaps/custom
qmk compile -kb keychron/q11/ansi_encoder -km custom
```

The compiled binary will be at `qmk_firmware/keychron_q11_ansi_encoder_custom.bin`.

## LED Index Map

The Q11 has **89 addressable LEDs** (no knob LEDs in the RGB matrix).

### Left half (indices 0-41)

| Row | Keys (index) |
|-----|-------------|
| F-row | Esc(0), F1(1), F2(2), F3(3), F4(4), F5(5), F6(6) |
| Number | M1(7), \`(8), 1(9), 2(10), 3(11), 4(12), 5(13), 6(14) |
| QWERTY | M2(15), Tab(16), Q(17), W(18), E(19), R(20), T(21) |
| Home | M3(22), Caps(23), A(24), S(25), D(26), F(27), G(28) |
| Shift | M4(29), LShift(30), Z(31), X(32), C(33), V(34), B(35) |
| Bottom | M5(36), LCtrl(37), Win(38), Alt(39), Fn(40), Space(41) |

### Right half (indices 42-88)

| Row | Keys (index) |
|-----|-------------|
| F-row | F7(42), F8(43), F9(44), F10(45), F11(46), F12(47), Ins(48), Del(49) |
| Number | 7(50), 8(51), 9(52), 0(53), -(54), =(55), Bksp(56), PgUp(57) |
| QWERTY | Y(58), U(59), I(60), O(61), P(62), [(63), ](64), \\(65), PgDn(66) |
| Home | H(67), J(68), K(69), L(70), ;(71), '(72), Enter(73), Home(74) |
| Shift | N(75), M(76), ,(77), .(78), /(79), RShift(80), Up(81) |
| Bottom | Space(82), Alt(83), Fn(84), Ctrl(85), Left(86), Down(87), Right(88) |

## File Structure

```
app.py                          Flask backend + HID communication + key listener
static/index.html               Web UI (effect controls, visual keyboard, presets)
requirements.txt                Python dependencies (flask, evdev)
keychron-controller.service     systemd unit file for auto-start on boot
99-keychron.rules               udev rule for non-root HID access
presets.json                    Saved presets (auto-generated at runtime)
remap_fn_fix.py         Remap Fn+1-6 to F13-F18 (for stock firmware)
detect_keys.py          Utility: detect keypresses on all Keychron input devices
probe_layers.py         Utility: read keymap layers to find Fn layer
test_leds.py            Utility: light up LEDs one at a time to verify index mapping
firmware/
  keychron_q11_ansi_encoder_custom.bin   Pre-built firmware binary
  qmk_keymap/                           QMK keymap source
    keymap.c                            Keymap with per-LED HID handler + split sync
    config.h                            Split transaction config
    rules.mk                            Build flags (VIA + RAW_HID)
```

## Troubleshooting

### Keyboard not found
- Check the keyboard is plugged in: `lsusb | grep 3434`
- Check the udev rule is installed: `ls -la /dev/hidraw* | grep rw`
- Unplug and replug the keyboard after installing the udev rule

### Per-key mode doesn't work
- Make sure you've flashed the custom firmware on **both halves**
- The right half takes ~100ms to fully sync -- colors appear in chunks

### Fn+1-6 hotkeys don't trigger presets
- The app must be run with `sudo` for evdev access to `/dev/input`
- If using stock firmware, run `python remap_fn_fix.py` to remap the Fn layer
- Verify with `sudo python detect_keys.py` -- press Fn+1, should show KEY_F13

### Entering DFU bootloader mode
- **Left half**: unplug, hold Esc, plug in USB-C
- **Right half**: unplug both USB-C and TRRS cables, press the PCB reset button (near right space bar), plug in USB-C
- Verify with: `lsusb | grep 0483`

## License

GPL-2.0 (follows QMK firmware licensing)
