#!/bin/bash
# Launch Chrome without CPDB delay
# GTK_USE_PORTAL=0 makes GTK apps use direct CUPS dialog instead of xdg-desktop-portal + CPDB
export GTK_USE_PORTAL=0
exec /usr/bin/google-chrome-stable "$@"
