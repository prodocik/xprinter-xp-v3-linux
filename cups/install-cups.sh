#!/bin/bash
# Install Xprinter V3 as a CUPS printer.
#
# Usage:
#   sudo ./install-cups.sh bluetooth AA:BB:CC:DD:EE:FF
#   sudo ./install-cups.sh usb /dev/usb/lp0
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
    echo "  sudo $0 bluetooth AA:BB:CC:DD:EE:FF    — подключение по Bluetooth"
    echo "  sudo $0 usb [/dev/usb/lp0]             — подключение по USB"
    echo "  sudo $0 wifi 192.168.1.100              — подключение по WiFi"
    echo ""
    echo "Удаление:"
    echo "  sudo $0 remove                          — удалить принтер из системы"
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

MODE="$1"

case "$MODE" in
    remove)
        echo "=== Удаление принтера $PRINTER_NAME ==="
        lpadmin -x "$PRINTER_NAME" 2>/dev/null || true
        rm -f "$FILTER_DIR/xprinter-tspl"
        rm -f "$PPD_DIR/xprinter-v3.ppd"
        echo "Готово!"
        exit 0
        ;;
    bluetooth)
        if [ $# -lt 2 ]; then
            echo "Ошибка: укажите Bluetooth адрес"
            show_usage
            exit 1
        fi
        BT_ADDR="$2"
        # Create rfcomm binding
        RFCOMM_DEV="/dev/rfcomm0"
        echo "=== Настройка Bluetooth RFCOMM ==="
        rfcomm release 0 2>/dev/null || true
        rfcomm bind 0 "$BT_ADDR" 1
        DEVICE_URI="serial:$RFCOMM_DEV?baud=9600"
        echo "Bluetooth: $BT_ADDR → $RFCOMM_DEV"

        # Add rfcomm bind to startup
        SYSTEMD_FILE="/etc/systemd/system/xprinter-rfcomm.service"
        cat > "$SYSTEMD_FILE" << EOSVC
[Unit]
Description=Xprinter V3 Bluetooth RFCOMM bind
After=bluetooth.target

[Service]
Type=oneshot
ExecStart=/usr/bin/rfcomm bind 0 $BT_ADDR 1
ExecStop=/usr/bin/rfcomm release 0
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOSVC
        systemctl daemon-reload
        systemctl enable xprinter-rfcomm.service
        echo "Автозапуск rfcomm настроен"
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
