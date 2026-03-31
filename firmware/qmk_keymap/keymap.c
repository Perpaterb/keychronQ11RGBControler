/* Custom Keychron Q11 keymap with VIA + per-key RGB HID control.
 * Adds a "direct mode" where the host can set individual LED colors
 * via raw HID commands 0x10-0x13.
 */
#include QMK_KEYBOARD_H
#include "raw_hid.h"

enum layers {
    MAC_BASE,
    MAC_FN,
    WIN_BASE,
    WIN_FN,
};

#define KC_TASK LGUI(KC_TAB)
#define KC_FLXP LGUI(KC_E)

// --- Per-key RGB ---
#define LED_COUNT 89
#define HID_CMD_SET_LED       0x10  // [0x10, index, R, G, B]
#define HID_CMD_SET_LED_BATCH 0x11  // [0x11, start, count, R,G,B, R,G,B, ...]
#define HID_CMD_DIRECT_MODE   0x12  // [0x12, enable(0/1)]
#define HID_CMD_SET_ALL_LEDS  0x13  // [0x13, R, G, B]

static uint8_t led_buffer[LED_COUNT][3];
static bool direct_mode = false;

// Hook into VIA's command processing. Return true = we handled it.
bool via_command_kb(uint8_t *data, uint8_t length) {
    uint8_t cmd = data[0];

    switch (cmd) {
        case HID_CMD_DIRECT_MODE:
            direct_mode = data[1] ? true : false;
            if (direct_mode) {
                memset(led_buffer, 0, sizeof(led_buffer));
            }
            raw_hid_send(data, length);
            return true;

        case HID_CMD_SET_LED: {
            uint8_t idx = data[1];
            if (idx < LED_COUNT) {
                led_buffer[idx][0] = data[2];
                led_buffer[idx][1] = data[3];
                led_buffer[idx][2] = data[4];
            }
            raw_hid_send(data, length);
            return true;
        }

        case HID_CMD_SET_LED_BATCH: {
            uint8_t start = data[1];
            uint8_t count = data[2];
            // Max 9 LEDs per message: (32 - 3) / 3 = 9
            for (uint8_t i = 0; i < count && (start + i) < LED_COUNT; i++) {
                uint8_t off = 3 + (i * 3);
                if (off + 2 < length) {
                    led_buffer[start + i][0] = data[off];
                    led_buffer[start + i][1] = data[off + 1];
                    led_buffer[start + i][2] = data[off + 2];
                }
            }
            raw_hid_send(data, length);
            return true;
        }

        case HID_CMD_SET_ALL_LEDS: {
            uint8_t r = data[1], g = data[2], b = data[3];
            for (uint8_t i = 0; i < LED_COUNT; i++) {
                led_buffer[i][0] = r;
                led_buffer[i][1] = g;
                led_buffer[i][2] = b;
            }
            raw_hid_send(data, length);
            return true;
        }

        default:
            return false; // Let VIA handle it
    }
}

// Override LED colors when in direct mode
bool rgb_matrix_indicators_advanced_user(uint8_t led_min, uint8_t led_max) {
    if (!direct_mode) {
        return false;
    }
    for (uint8_t i = led_min; i < led_max; i++) {
        if (i < LED_COUNT) {
            rgb_matrix_set_color(i, led_buffer[i][0], led_buffer[i][1], led_buffer[i][2]);
        }
    }
    return false;
}

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [MAC_BASE] = LAYOUT_91_ansi(
        KC_MUTE,  KC_ESC,   KC_BRID,  KC_BRIU,  KC_MCTL,  KC_LPAD,  RM_VALD,   RM_VALU,  KC_MPRV,  KC_MPLY,  KC_MNXT,  KC_MUTE,  KC_VOLD,    KC_VOLU,  KC_INS,   KC_DEL,   KC_MUTE,
        _______,  KC_GRV,   KC_1,     KC_2,     KC_3,     KC_4,     KC_5,      KC_6,     KC_7,     KC_8,     KC_9,     KC_0,     KC_MINS,    KC_EQL,   KC_BSPC,            KC_PGUP,
        _______,  KC_TAB,   KC_Q,     KC_W,     KC_E,     KC_R,     KC_T,      KC_Y,     KC_U,     KC_I,     KC_O,     KC_P,     KC_LBRC,    KC_RBRC,  KC_BSLS,            KC_PGDN,
        _______,  KC_CAPS,  KC_A,     KC_S,     KC_D,     KC_F,     KC_G,      KC_H,     KC_J,     KC_K,     KC_L,     KC_SCLN,  KC_QUOT,              KC_ENT,             KC_HOME,
        _______,  KC_LSFT,            KC_Z,     KC_X,     KC_C,     KC_V,      KC_B,     KC_N,     KC_M,     KC_COMM,  KC_DOT,   KC_SLSH,              KC_RSFT,  KC_UP,
        _______,  KC_LCTL,  KC_LOPT,  KC_LCMD,  MO(MAC_FN),         KC_SPC,                        KC_SPC,             KC_RCMD,  MO(MAC_FN), KC_RCTL,  KC_LEFT,  KC_DOWN,  KC_RGHT),

    [MAC_FN] = LAYOUT_91_ansi(
        RM_TOGG,  _______,  KC_F1,    KC_F2,    KC_F3,    KC_F4,    KC_F5,     KC_F6,    KC_F7,    KC_F8,    KC_F9,    KC_F10,   KC_F11,     KC_F12,   _______,  _______,  RM_TOGG,
        _______,  _______,  KC_F13,   KC_F14,   KC_F15,   KC_F16,   KC_F17,    KC_F18,   _______,  _______,  _______,  _______,  _______,    _______,  _______,            _______,
        _______,  RM_TOGG,  RM_NEXT,  RM_VALU,  RM_HUEU,  RM_SATU,  RM_SPDU,   _______,  _______,  _______,  _______,  _______,  _______,    _______,  _______,            _______,
        _______,  _______,  RM_PREV,  RM_VALD,  RM_HUED,  RM_SATD,  RM_SPDD,   _______,  _______,  _______,  _______,  _______,  _______,              _______,            _______,
        _______,  _______,            _______,  _______,  _______,  _______,   _______,  NK_TOGG,  _______,  _______,  _______,  _______,              _______,  _______,
        _______,  _______,  _______,  _______,  _______,            _______,                       _______,            _______,  _______,    _______,  _______,  _______,  _______),

    [WIN_BASE] = LAYOUT_91_ansi(
        KC_MUTE,  KC_ESC,   KC_F1,    KC_F2,    KC_F3,    KC_F4,    KC_F5,     KC_F6,    KC_F7,    KC_F8,    KC_F9,    KC_F10,   KC_F11,     KC_F12,   KC_INS,   KC_DEL,   KC_MUTE,
        _______,  KC_GRV,   KC_1,     KC_2,     KC_3,     KC_4,     KC_5,      KC_6,     KC_7,     KC_8,     KC_9,     KC_0,     KC_MINS,    KC_EQL,   KC_BSPC,            KC_PGUP,
        _______,  KC_TAB,   KC_Q,     KC_W,     KC_E,     KC_R,     KC_T,      KC_Y,     KC_U,     KC_I,     KC_O,     KC_P,     KC_LBRC,    KC_RBRC,  KC_BSLS,            KC_PGDN,
        _______,  KC_CAPS,  KC_A,     KC_S,     KC_D,     KC_F,     KC_G,      KC_H,     KC_J,     KC_K,     KC_L,     KC_SCLN,  KC_QUOT,              KC_ENT,             KC_HOME,
        _______,  KC_LSFT,            KC_Z,     KC_X,     KC_C,     KC_V,      KC_B,     KC_N,     KC_M,     KC_COMM,  KC_DOT,   KC_SLSH,              KC_RSFT,  KC_UP,
        _______,  KC_LCTL,  KC_LWIN,  KC_LALT,  MO(WIN_FN),         KC_SPC,                        KC_SPC,             KC_RALT,  MO(WIN_FN), KC_RCTL,  KC_LEFT,  KC_DOWN,  KC_RGHT),

    [WIN_FN] = LAYOUT_91_ansi(
        RM_TOGG,  _______,  KC_BRID,  KC_BRIU,  KC_TASK,  KC_FLXP,  RM_VALD,   RM_VALU,  KC_MPRV,  KC_MPLY,  KC_MNXT,  KC_MUTE,  KC_VOLD,    KC_VOLU,  _______,  _______,  RM_TOGG,
        _______,  _______,  KC_F13,   KC_F14,   KC_F15,   KC_F16,   KC_F17,    KC_F18,   _______,  _______,  _______,  _______,  _______,    _______,  _______,            _______,
        _______,  RM_TOGG,  RM_NEXT,  RM_VALU,  RM_HUEU,  RM_SATU,  RM_SPDU,   _______,  _______,  _______,  _______,  _______,  _______,    _______,  _______,            _______,
        _______,  _______,  RM_PREV,  RM_VALD,  RM_HUED,  RM_SATD,  RM_SPDD,   _______,  _______,  _______,  _______,  _______,  _______,              _______,            _______,
        _______,  _______,            _______,  _______,  _______,  _______,   _______,  NK_TOGG,  _______,  _______,  _______,  _______,              _______,  _______,
        _______,  _______,  _______,  _______,  _______,            _______,                       _______,            _______,  _______,    _______,  _______,  _______,  _______),
};

#if defined(ENCODER_MAP_ENABLE)
const uint16_t PROGMEM encoder_map[][NUM_ENCODERS][NUM_DIRECTIONS] = {
    [MAC_BASE] = { ENCODER_CCW_CW(KC_VOLD, KC_VOLU), ENCODER_CCW_CW(KC_VOLD, KC_VOLU) },
    [MAC_FN]   = { ENCODER_CCW_CW(RM_VALD, RM_VALU), ENCODER_CCW_CW(RM_VALD, RM_VALU) },
    [WIN_BASE] = { ENCODER_CCW_CW(KC_VOLD, KC_VOLU), ENCODER_CCW_CW(KC_VOLD, KC_VOLU) },
    [WIN_FN]   = { ENCODER_CCW_CW(RM_VALD, RM_VALU), ENCODER_CCW_CW(RM_VALD, RM_VALU) }
};
#endif
