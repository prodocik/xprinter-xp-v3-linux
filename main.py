#!/usr/bin/env python3
"""XPrinter Label GUI — entry point."""

import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio

from window import XPrinterWindow


class XPrinterApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.github.xprinter-label-gui",
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = XPrinterWindow(application=self)
        win.present()

    def do_open(self, files, n_files, hint):
        self.do_activate()
        win = self.props.active_window
        if files:
            win.open_pdf(files[0].get_path())


def main():
    app = XPrinterApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
