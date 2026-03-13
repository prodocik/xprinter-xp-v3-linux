#!/bin/bash
# Install dependencies for XPrinter Label GUI

set -e

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
    bluetooth

echo ""
echo "=== Установка Python зависимостей ==="
pip3 install --user -r requirements.txt

echo ""
echo "=== Готово! ==="
echo "Запуск: python3 main.py"
