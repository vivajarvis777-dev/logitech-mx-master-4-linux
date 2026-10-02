# Draft Issue / Feature Request for Solaar

**Target Repo:** `pwr-Solaar/Solaar`  
**Title:** Support for Logitech MX Master 4 (`046D:B042`): Haptic Engine (`0x19B0`) & Split Thumb Controls (`0x1B04`)

---

### Description

Hello Solaar team,

I have been using and reverse-engineering the **Logitech MX Master 4** (BLE/Bolt, USB ID `046D:B042`) under Linux. I wanted to share the verified HID++ feature specifications and hardware behaviors to help integrate native support into Solaar.

#### 1. Device Identifiers
- **Model:** Logitech MX Master 4
- **Vendor/Product ID:** `046D:B042`
- **Protocol:** HID++ 4.5

#### 2. Haptic Feedback Engine (`0x19B0`)
The MX Master 4 introduces a physical piezoelectric haptic feedback motor located under the thumb rest pad.
- **Feature ID:** `0x19B0` (located at index `0x0B` over BLE).
- **Haptic Trigger Function:** `0x4E`.
- **Packet Format (Long Report 0x11):**
  ```
  11 FF <feature_index> 4E <waveform_id> 00 00 [13 zero bytes]
  ```
- **Observed Waveforms (`waveform_id`):**
  - `0x01`: Sharp, crisp mechanical click/tick.
  - `0x02`: Subtle soft confirmation click (default).
  - `0x03`–`0x0E`: Double clicks, ramps, and pulse variations.

#### 3. Thumb Control Differentiation (`0x1B04`)
Unlike previous MX Master revisions, the thumb area features two distinct controls:
1. `0x01A0` (Haptic Wing Pad): Bottom thumb pressure rest. Sends HID++ event `0x01A0` on press.
2. `0x00C3` (Gesture Button): Physical button situated slightly above the thumb rest pad. Sends HID++ event `0x00C3`.

Currently, under generic handlers, both actions can clash with window manager gestures. In our standalone daemon implementation, we route `0x01A0` to trigger `0x19B0` haptic feedback plus window operations, while `0x00C3` can be mapped independently.

#### 4. Reference Implementation & Testing
We have created a standalone Python daemon with CLI testing tools (`--test-haptic`, raw HID++ read/write):
https://github.com/vivajarvis777-dev/logitech-mx-master-4-linux

Happy to test any PRs or descriptors on real hardware!
