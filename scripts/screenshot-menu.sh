#!/usr/bin/env bash
# Screenshot menu utility for Logitech MX Master 4 button action
# Supports Zenity GUI chooser or CLI arguments: area | window | screen

set -euo pipefail

mode="${1:-}"

# Show Zenity chooser if no argument was passed
if [[ -z "$mode" ]]; then
    if command -v zenity >/dev/null 2>&1; then
        mode="$({
            printf '%s\n' \
                'area'   'Select rectangular screen region' \
                'window' 'Capture active window' \
                'screen' 'Capture entire desktop'
        } | zenity --list \
            --title='Screenshot Menu' \
            --text='Select capture mode to copy to clipboard:' \
            --column='Mode' \
            --column='Description' \
            --print-column=1 \
            --width=450 \
            --height=260 2>/dev/null || true)"
    else
        # Default to interactive area if zenity is not installed
        mode="area"
    fi
fi

[[ -z "$mode" ]] && exit 0

capture_to_clipboard() {
    local target="$1"

    if command -v gnome-screenshot >/dev/null 2>&1; then
        case "$target" in
            area)   gnome-screenshot --area --clipboard ;;
            window) gnome-screenshot --window --clipboard --delay=1 ;;
            screen) gnome-screenshot --clipboard ;;
        esac
    elif command -v maim >/dev/null 2>&1 && command -v xclip >/dev/null 2>&1; then
        case "$target" in
            area)   maim -s | xclip -selection clipboard -t image/png ;;
            window) maim -i "$(xdotool getactivewindow)" | xclip -selection clipboard -t image/png ;;
            screen) maim | xclip -selection clipboard -t image/png ;;
        esac
    elif command -v spectacle >/dev/null 2>&1; then
        case "$target" in
            area)   spectacle -b -r -c ;;
            window) spectacle -b -a -c ;;
            screen) spectacle -b -f -c ;;
        esac
    else
        echo "Error: No supported screenshot tool found (gnome-screenshot, maim+xclip, or spectacle)." >&2
        exit 1
    fi
}

capture_to_clipboard "$mode"

if command -v notify-send >/dev/null 2>&1; then
    notify-send \
        --app-name='Screenshot' \
        --icon=camera-photo-symbolic \
        'Screenshot copied' \
        'Image is in your clipboard. Paste with Ctrl+V.' 2>/dev/null || true
fi

exit 0
