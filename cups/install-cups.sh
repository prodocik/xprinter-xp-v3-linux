#!/bin/bash
# Install Xprinter V3 as a CUPS printer.
#
# Usage:
#   sudo ./install-cups.sh bluetooth              — автопоиск принтера
#   sudo ./install-cups.sh bluetooth AA:BB:CC:DD:EE:FF
#   sudo ./install-cups.sh usb [/dev/usb/lp0]
#   sudo ./install-cups.sh wifi 192.168.1.100
#
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FILTER_SRC="$SCRIPT_DIR/xprinter-tspl"
PPD_SRC="$SCRIPT_DIR/xprinter-v3.ppd"

# Detect CUPS filter/ppd directories
if [ -d /usr/lib/cups/filter ]; then
    FILTER_DIR="/usr/lib/cups/filter"
elif [ -d /usr/libexec/cups/filter ]; then
    FILTER_DIR="/usr/libexec/cups/filter"
else
    echo "Ошибка: не найдена директория фильтров CUPS"
    exit 1
fi

PPD_DIR="/usr/share/cups/model"
PRINTER_NAME="XprinterV3"

show_usage() {
    echo "Использование:"
    echo "  sudo $0 bluetooth                       — автопоиск Bluetooth принтера"
    echo "  sudo $0 bluetooth AA:BB:CC:DD:EE:FF    — подключение по Bluetooth (вручную)"
    echo "  sudo $0 usb [/dev/usb/lp0]             — подключение по USB"
    echo "  sudo $0 wifi 192.168.1.100              — подключение по WiFi"
    echo ""
    echo "Удаление:"
    echo "  sudo $0 remove                          — удалить принтер из системы"
}

find_bt_printer() {
    echo "=== Поиск Bluetooth принтеров ==="
    echo "Убедитесь, что принтер включён..."
    echo ""

    # First check already paired devices
    PAIRED=$(bluetoothctl devices 2>/dev/null | grep -iE "xp|xprinter|printer|label" || true)
    if [ -n "$PAIRED" ]; then
        echo "Найдены спаренные устройства:"
        echo "$PAIRED"
        echo ""
        # Extract first match
        BT_FOUND=$(echo "$PAIRED" | head -1 | awk '{print $2}')
        BT_NAME=$(echo "$PAIRED" | head -1 | cut -d' ' -f3-)
        echo "→ Выбран: $BT_NAME ($BT_FOUND)"
        return 0
    fi

    # Scan for new devices
    echo "Спаренные принтеры не найдены. Сканирование (10 сек)..."
    # Power on and start scan
    bluetoothctl power on >/dev/null 2>&1 || true
    bluetoothctl --timeout 10 scan on >/dev/null 2>&1 &
    SCAN_PID=$!
    sleep 10
    kill $SCAN_PID 2>/dev/null || true
    wait $SCAN_PID 2>/dev/null || true

    # Check all discovered devices
    ALL_DEVICES=$(bluetoothctl devices 2>/dev/null)
    FOUND=$(echo "$ALL_DEVICES" | grep -iE "xp|xprinter|printer|label" || true)

    if [ -n "$FOUND" ]; then
        echo ""
        echo "Найдены принтеры:"
        echo "$FOUND"
        echo ""
        BT_FOUND=$(echo "$FOUND" | head -1 | awk '{print $2}')
        BT_NAME=$(echo "$FOUND" | head -1 | cut -d' ' -f3-)
        echo "→ Выбран: $BT_NAME ($BT_FOUND)"
        return 0
    fi

    # Nothing found by name — show all devices and let user pick
    if [ -n "$ALL_DEVICES" ]; then
        echo ""
        echo "Принтер не найден автоматически. Все обнаруженные устройства:"
        echo ""
        IDX=0
        while IFS= read -r line; do
            ADDR=$(echo "$line" | awk '{print $2}')
            NAME=$(echo "$line" | cut -d' ' -f3-)
            echo "  [$IDX] $NAME ($ADDR)"
            IDX=$((IDX + 1))
        done <<< "$ALL_DEVICES"
        echo ""
        read -p "Введите номер устройства (или Enter для отмены): " CHOICE
        if [ -n "$CHOICE" ]; then
            SELECTED=$(echo "$ALL_DEVICES" | sed -n "$((CHOICE + 1))p")
            if [ -n "$SELECTED" ]; then
                BT_FOUND=$(echo "$SELECTED" | awk '{print $2}')
                BT_NAME=$(echo "$SELECTED" | cut -d' ' -f3-)
                echo "→ Выбран: $BT_NAME ($BT_FOUND)"
                return 0
            fi
        fi
    fi

    echo ""
    echo "Принтер не найден. Убедитесь что:"
    echo "  1. Принтер включён"
    echo "  2. Bluetooth на компьютере включён"
    echo "  3. Принтер в режиме обнаружения"
    echo ""
    echo "Или укажите адрес вручную:"
    echo "  sudo $0 bluetooth AA:BB:CC:DD:EE:FF"
    BT_FOUND=""
    return 1
}

if [ $# -lt 1 ]; then
    show_usage
    exit 1
fi

# Ensure running as root
if [ "$(id -u)" -ne 0 ]; then
    echo "Ошибка: запустите с sudo"
    exit 1
fi

# Determine the real user (even under sudo)
REAL_USER="${SUDO_USER:-$USER}"

MODE="$1"

case "$MODE" in
    remove)
        echo "=== Удаление принтера $PRINTER_NAME ==="
        lpadmin -x "$PRINTER_NAME" 2>/dev/null || true
        rm -f "$FILTER_DIR/xprinter-tspl"
        rm -f "$PPD_DIR/xprinter-v3.ppd"
        systemctl disable xprinter-rfcomm.service 2>/dev/null || true
        rm -f /etc/systemd/system/xprinter-rfcomm.service
        systemctl daemon-reload 2>/dev/null || true
        echo "Готово!"
        exit 0
        ;;
    bluetooth)
        if [ $# -ge 2 ]; then
            BT_ADDR="$2"
        else
            # Автопоиск
            BT_FOUND=""
            BT_NAME=""
            find_bt_printer
            if [ -z "$BT_FOUND" ]; then
                exit 1
            fi
            BT_ADDR="$BT_FOUND"
        fi

        echo "=== Настройка Bluetooth ==="

        # Ensure Bluetooth is powered on
        bluetoothctl power on 2>/dev/null || true

        # Pair if not already paired
        PAIRED=$(bluetoothctl info "$BT_ADDR" 2>/dev/null | grep "Paired: yes" || true)
        if [ -z "$PAIRED" ]; then
            echo "Сопряжение с $BT_ADDR..."
            bluetoothctl pair "$BT_ADDR" 2>/dev/null || true
            sleep 2
        fi

        # Trust the device
        bluetoothctl trust "$BT_ADDR" 2>/dev/null || true

        # Use CUPS bluetooth:// backend (avoids AppArmor blocking serial)
        BT_ADDR_NOCOLON=$(echo "$BT_ADDR" | tr -d ':')
        DEVICE_URI="xprinter-bt://$BT_ADDR_NOCOLON"
        echo "Bluetooth: $BT_ADDR → $DEVICE_URI"
        ;;
    usb)
        USB_PORT="${2:-/dev/usb/lp0}"
        if [ ! -e "$USB_PORT" ]; then
            echo "Предупреждение: $USB_PORT не найден. Подключите принтер по USB."
        fi
        DEVICE_URI="usb://$USB_PORT"
        # Try serial if /dev/ttyUSB*
        if [[ "$USB_PORT" == /dev/tty* ]]; then
            DEVICE_URI="serial:$USB_PORT?baud=9600"
        fi
        echo "USB: $USB_PORT"
        ;;
    wifi)
        if [ $# -lt 2 ]; then
            echo "Ошибка: укажите IP адрес принтера"
            show_usage
            exit 1
        fi
        IP_ADDR="$2"
        PORT="${3:-9100}"
        DEVICE_URI="socket://$IP_ADDR:$PORT"
        echo "WiFi: $IP_ADDR:$PORT"
        ;;
    *)
        show_usage
        exit 1
        ;;
esac

echo ""
echo "=== Установка системных зависимостей ==="
apt-get install -y cups python3 python3-pip 2>/dev/null || true
pip3 install PyMuPDF Pillow 2>/dev/null || pip3 install --break-system-packages PyMuPDF Pillow 2>/dev/null || true

echo ""
echo "=== Установка CUPS фильтра ==="
install -m 755 "$FILTER_SRC" "$FILTER_DIR/xprinter-tspl"
install -m 644 "$PPD_SRC" "$PPD_DIR/xprinter-v3.ppd"

echo ""
echo "=== Регистрация принтера в CUPS ==="
# Remove old instance if exists
lpadmin -x "$PRINTER_NAME" 2>/dev/null || true

lpadmin -p "$PRINTER_NAME" \
    -v "$DEVICE_URI" \
    -P "$PPD_DIR/xprinter-v3.ppd" \
    -D "Xprinter V3 Thermal Label Printer" \
    -L "Thermal Label Printer" \
    -E

# Set default options
lpadmin -p "$PRINTER_NAME" \
    -o XprinterDensity=8 \
    -o XprinterSpeed=3 \
    -o XprinterGap=2 \
    -o PageSize=w164h113

echo ""
echo "=== Готово! ==="
echo ""
echo "Принтер '$PRINTER_NAME' установлен."
echo "URI: $DEVICE_URI"
echo ""
echo "Теперь вы можете печатать из любого приложения:"
echo "  1. Ctrl+P → выберите '$PRINTER_NAME'"
echo "  2. В настройках принтера выберите размер этикетки"
echo "  3. Нажмите 'Печать'"
echo ""
echo "Или из командной строки:"
echo "  lp -d $PRINTER_NAME -o PageSize=w164h113 file.pdf"
echo ""
echo "Размеры этикеток:"
echo "  w57h28   = 20×10 мм"
echo "  w85h57   = 30×20 мм"
echo "  w113h57  = 40×20 мм"
echo "  w113h85  = 40×30 мм"
echo "  w164h85  = 58×30 мм"
echo "  w164h113 = 58×40 мм (по умолчанию)"
echo "  w170h113 = 60×40 мм"
echo "  w227h142 = 80×50 мм"
echo "  w227h170 = 80×60 мм"
echo "  w283h170 = 100×60 мм"
echo "  w283h198 = 100×70 мм"
echo "  w283h425 = 100×150 мм"
echo "  w340h213 = 120×75 мм"
