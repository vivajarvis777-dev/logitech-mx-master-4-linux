# Logitech MX Master 4 on Linux

Comprehensive driver and daemon for the **Logitech MX Master 4** on Linux (Bluetooth Low Energy & Bolt), featuring native **Haptic Feedback (HID++ 0x19B0)**, programmable thumb controls, gesture management, and resolved Bluetooth/Wi-Fi coexistence issues.

---

## Highlights

- **Haptic Engine Support (`0x19B0`):** Full hardware vibration support on the thumb rest pad (sharp ticks, subtle confirmation clicks, custom waveforms).
- **Dual Thumb Controls Separation:** Distinguishes between the bottom rubber thumb rest (`0x01A0`) and the upper gesture button (`0x00C3`).
- **X11 / Wayland Friendly:** Prevents desktop environment conflicts (e.g. Cinnamon/GNOME treating extra mouse buttons as window minimize actions) via direct raw HID++ interception and pointer button isolation.
- **Wi-Fi & Bluetooth Coexistence Guide:** Practical hardware and network fixes for 2.4 GHz interference issues.
- **Lightweight Systemd Service:** Native `systemd --user` background daemon with auto-reconnection and minimal resource usage (pure Python 3, zero heavy external dependencies).

---

## Hardware & Protocol Specifications

- **Device Name:** Logitech MX Master 4
- **Vendor / Product ID:** `046D:B042`
- **Protocol:** HID++ 4.5 / HID++ 2.0 over Bluetooth Low Energy / Bolt
- **Interface:** `/dev/hidrawX` (auto-detected)

### HID++ Features Uncovered

| Feature ID | Name | Index (BLE) | Description |
| :--- | :--- | :--- | :--- |
| `0x19B0` | **Haptic Feedback** | `0x0B` | Triggers piezoelectric vibration waveforms |
| `0x1B04` | **Reprogrammable Controls V4** | `0x09` | Reports thumb pad pressure and gesture clicks |
| `0x2150` | **Thumb Wheel** | `0x07` | Horizontal scroll wheel events and diversion |
| `0x2201` | **Adjustable DPI** | `0x06` | Optical sensor resolution |

### Haptic Waveform Presets (`0x19B0` Function `0x4E`)

Trigger packet format (HID++ Long Report `0x11`):
```text
11 FF [feature_index] 4E [waveform_id] 00 00 [13 zero bytes]
```

| Waveform ID | Haptic Feel | Recommended Use |
| :--- | :--- | :--- |
| `0x01` | Sharp Tick | Scroll notch simulation / crisp trigger |
| `0x02` | Subtle Click | Primary confirmation (e.g., thumb rest press) |
| `0x03` - `0x06` | Medium to Heavy Pulses | Warning or mode switch feedback |
| `0x07` - `0x0E` | Double-ticks & Rhythmic Clicks | Multi-step gesture acknowledgments |

---

## Architecture & Default Controls

```
               ┌────────────────────────┐
               │ Logitech MX Master 4   │
               └───────────┬────────────┘
                           │ HID++ Raw Packets (/dev/hidrawX)
                           ▼
               ┌────────────────────────┐
               │      mx4-daemon        │
               └───┬────────────────┬───┘
                   │                │
     0x01A0 (Pad)  │                │  0x00C3 (Upper Button)
                   ▼                ▼
       ┌──────────────────────┐   ┌──────────────────────┐
       │ Haptic Click (WF 2)  │   │ Screenshot Tool      │
       │ + Toggle Desktop     │   │ (Zenity / GUI Menu)  │
       └──────────────────────┘   └──────────────────────┘
```

1. **Thumb Rest / Wing Panel (`0x01A0`):**
   - Triggers physical haptic vibration (`waveform=2`).
   - Toggles desktop (minimizes/restores all windows via `wmctrl`).
2. **Upper Gesture Button (`0x00C3`):**
   - Launches interactive screenshot menu (Area / Window / Screen) with direct clipboard copy and notification.
3. **Thumb Wheel (`0x2150`):**
   - Configured via Solaar diversion with displacement threshold `14` for discrete one-by-one browser tab switching (`Ctrl+Tab` / `Ctrl+Shift+Tab`).

---

## System Fixes & Troubleshooting

### 1. Bluetooth 2.4 GHz & Wi-Fi Interference
**Symptom:** Wi-Fi speed drops drastically (from 300+ Mbps down to 0.5–2 Mbps) whenever the mouse is moving.  
**Cause:** The 2.4 GHz Bluetooth carrier overlaps with 2.4 GHz Wi-Fi channels (especially Wi-Fi Channel 9 / 2452 MHz).  
**Solution:** Lock your Linux machine's Wi-Fi connection to the 5 GHz band (e.g. Channel 48, 5240 MHz):
```bash
# Identify your 5 GHz BSSID:
nmcli dev wifi list

# Lock your connection to the 5 GHz BSSID:
nmcli con modify "<Connection-Name>" 802-11-wireless.bssid <5GHz-BSSID>
nmcli con up "<Connection-Name>"
```

### 2. X11 Duplicate Window Minimize Actions
**Symptom:** Pressing the upper gesture button causes window manager gestures in Cinnamon/GNOME.  
**Solution:** The daemon automatically masks pointer buttons 10 and 11 via `xinput set-button-map`, routing events cleanly through raw HID++ reports without X11 desktop interference.

### 3. Solaar Keyboard Layout Divert Bug
**Symptom:** Emulated keystrokes fail when non-Latin keyboard layouts (e.g., Ukrainian) are active.  
**Solution:** Handled out-of-band by `mx4-daemon` using direct IPC / system commands instead of simulated X11 key presses.

---

## Installation

### Prerequisites

On Debian / Ubuntu / Linux Mint:
```bash
sudo apt update
sudo apt install python3 wmctrl xinput zenity gnome-screenshot
```
*(On Arch Linux: `sudo pacman -S python wmctrl xorg-xinput zenity gnome-screenshot`)*

### Quick Install

Clone this repository and run the installer:
```bash
git clone https://github.com/vivajarvis777-dev/logitech-mx-master-4-linux.git
cd logitech-mx-master-4-linux
./install.sh
```

The installer will:
1. Copy the executable daemon to `~/.local/bin/mx4-daemon`.
2. Install the screenshot menu utility to `~/.local/bin/mx4-screenshot-menu`.
3. Generate `~/.config/mx4/config.ini`.
4. Enable and start the user systemd service (`mx4-daemon.service`).

### Non-Root Device Access (udev)

To grant your unprivileged user access to `/dev/hidraw*` without sudo:
```bash
sudo cp udev/99-logitech-mx4.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```
Ensure your user belongs to the `plugdev` group:
```bash
sudo usermod -aG plugdev $USER
```

---

## Configuration

Edit `~/.config/mx4/config.ini` to customize button behaviors, debounce time, and haptic waveforms:

```ini
[daemon]
debounce_sec = 0.40
disable_x11_extra_buttons = true

[haptic]
default_waveform = 2

[wing_panel]
# Trigger haptic pulse (0 = disabled, 1..14 = presets)
haptic_waveform = 2
# Action can be 'toggle_desktop', 'none', or any shell command:
action = toggle_desktop

[gesture_button]
haptic_waveform = 0
action = /usr/local/bin/mx4-screenshot-menu
```

Restart the service after editing:
```bash
systemctl --user restart mx4-daemon.service
```

---

## CLI Utility Commands

You can use `mx4-daemon` directly from the terminal for testing:

```bash
# Detect connected MX Master 4 devices:
mx4-daemon --list-devices

# Test haptic vibration pulse (1 = sharp, 2 = subtle):
mx4-daemon --test-haptic 2

# Run in debug mode:
mx4-daemon --debug
```

---

## Uninstallation

To remove the daemon and service:
```bash
./uninstall.sh
```

---

## Contributing

Contributions, bug reports, and pull requests are welcome! If you discover additional HID++ features on the MX Master 4, feel free to open an issue or pull request.

## License

This project is licensed under the [MIT License](LICENSE).
