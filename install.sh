#!/bin/bash
# Install dependencies for XPrinter Label GUI

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Установка системных зависимостей ==="
sudo apt-get update
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-4.0 \
    gir1.2-adw-1 \
    libgirepository-1.0-dev \
    libbluetooth-dev \
    bluetooth \
    bluez \
    rfcomm \
    cups

echo ""
echo "=== Настройка прав доступа ==="
# Добавить пользователя в группу dialout для доступа к /dev/rfcomm*
if ! groups "$USER" | grep -q '\bdialout\b'; then
    sudo usermod -aG dialout "$USER"
    echo "Пользователь $USER добавлен в группу dialout"
    NEED_RELOGIN=1
else
    echo "Пользователь $USER уже в группе dialout"
fi

# Добавить пользователя в группу lpadmin для управления CUPS
if ! groups "$USER" | grep -q '\blpadmin\b'; then
    sudo usermod -aG lpadmin "$USER"
    echo "Пользователь $USER добавлен в группу lpadmin"
    NEED_RELOGIN=1
else
    echo "Пользователь $USER уже в группе lpadmin"
fi

echo ""
echo "=== Установка Python зависимостей ==="
pip3 install --user -r requirements.txt

echo ""
echo "=== Готово! ==="
echo "Запуск: python3 main.py"
echo ""

if [ "${NEED_RELOGIN:-0}" = "1" ]; then
    echo "⚠ ВАЖНО: Перелогиньтесь, чтобы права на группы применились."
    echo "  Или выполните: newgrp dialout"
fi
