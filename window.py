"""Main application window."""

import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, Gdk, GdkPixbuf, GLib, Gio

from label_sizes import LABEL_SIZES, DEFAULT_SIZE
from pdf_renderer import PDFDocument, prepare_label_image, pil_to_gdk_pixbuf
from printer_connection import ConnectionManager, USBConnection, BluetoothConnection
from tspl import build_label_job
from preferences import Preferences


class XPrinterWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs, default_width=900, default_height=650)
        self.set_title("XPrinter Label")

        self._pdf = None
        self._current_page = 0
        self._prefs = Preferences()
        self._conn_mgr = ConnectionManager()

        self._build_ui()
        self._setup_drop_target()
        self._setup_shortcuts()

    def _build_ui(self):
        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        main_box.append(header)

        # Open button
        open_btn = Gtk.Button(icon_name="document-open-symbolic", tooltip_text="Открыть PDF")
        open_btn.connect("clicked", self._on_open_clicked)
        header.pack_start(open_btn)

        # Print button in header
        print_btn = Gtk.Button(icon_name="printer-symbolic", tooltip_text="Печать (Ctrl+P)")
        print_btn.add_css_class("suggested-action")
        print_btn.connect("clicked", self._on_print_clicked)
        header.pack_end(print_btn)

        # Settings button
        settings_btn = Gtk.Button(icon_name="emblem-system-symbolic", tooltip_text="Настройки")
        settings_btn.connect("clicked", self._on_settings_clicked)
        header.pack_end(settings_btn)

        # Content: sidebar + preview
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(180)
        paned.set_vexpand(True)
        main_box.append(paned)

        # Sidebar — page thumbnails
        sidebar_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        sidebar_scroll.set_size_request(180, -1)
        self._thumb_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._thumb_box.set_margin_start(4)
        self._thumb_box.set_margin_end(4)
        self._thumb_box.set_margin_top(4)
        self._thumb_box.set_margin_bottom(4)
        sidebar_scroll.set_child(self._thumb_box)
        paned.set_start_child(sidebar_scroll)

        # Preview area
        preview_scroll = Gtk.ScrolledWindow()
        self._preview_image = Gtk.Picture()
        self._preview_image.set_can_shrink(True)
        self._preview_image.set_content_fit(Gtk.ContentFit.CONTAIN)
        self._preview_image.set_hexpand(True)
        self._preview_image.set_vexpand(True)

        # Placeholder
        self._placeholder = Adw.StatusPage(
            icon_name="document-open-symbolic",
            title="Откройте PDF файл",
            description="Перетащите файл сюда или нажмите кнопку открытия",
        )
        self._preview_stack = Gtk.Stack()
        self._preview_stack.add_named(self._placeholder, "placeholder")
        preview_scroll.set_child(self._preview_image)
        self._preview_stack.add_named(preview_scroll, "preview")
        self._preview_stack.set_visible_child_name("placeholder")
        paned.set_end_child(self._preview_stack)

        # Bottom bar
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        bottom.set_margin_start(12)
        bottom.set_margin_end(12)
        bottom.set_margin_top(8)
        bottom.set_margin_bottom(8)
        main_box.append(bottom)

        # Label size dropdown
        bottom.append(Gtk.Label(label="Размер:"))
        self._size_dropdown = Gtk.DropDown.new_from_strings(list(LABEL_SIZES.keys()) + ["Свой размер"])
        # Set default
        size_names = list(LABEL_SIZES.keys())
        if self._prefs["label_size"] in size_names:
            self._size_dropdown.set_selected(size_names.index(self._prefs["label_size"]))
        self._size_dropdown.connect("notify::selected", self._on_size_changed)
        bottom.append(self._size_dropdown)

        # Copies spinner
        bottom.append(Gtk.Label(label="Копии:"))
        self._copies_spin = Gtk.SpinButton.new_with_range(1, 100, 1)
        self._copies_spin.set_value(self._prefs["copies"])
        bottom.append(self._copies_spin)

        # Connection type
        bottom.append(Gtk.Label(label="Подключение:"))
        self._conn_dropdown = Gtk.DropDown.new_from_strings(["USB", "Bluetooth", "WiFi"])
        conn_types = ["USB", "Bluetooth", "WiFi"]
        if self._prefs["connection_type"] in conn_types:
            self._conn_dropdown.set_selected(conn_types.index(self._prefs["connection_type"]))
        bottom.append(self._conn_dropdown)

        # Connect button
        self._connect_btn = Gtk.Button(label="Подключить")
        self._connect_btn.connect("clicked", self._on_connect_clicked)
        bottom.append(self._connect_btn)

        # Status indicator
        self._status_label = Gtk.Label(label="Не подключён")
        self._status_label.add_css_class("dim-label")
        self._status_label.set_hexpand(True)
        self._status_label.set_halign(Gtk.Align.END)
        bottom.append(self._status_label)

    def _setup_drop_target(self):
        drop = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        self.add_controller(drop)

    def _setup_shortcuts(self):
        ctrl = Gtk.ShortcutController.new()
        ctrl.set_scope(Gtk.ShortcutScope.MANAGED)
        self.add_controller(ctrl)

        # Ctrl+O — open
        ctrl.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>o"),
            Gtk.CallbackAction.new(lambda *_: self._on_open_clicked(None)),
        ))
        # Ctrl+P — print
        ctrl.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>p"),
            Gtk.CallbackAction.new(lambda *_: self._on_print_clicked(None)),
        ))

    def _on_drop(self, target, value, x, y):
        if isinstance(value, Gio.File):
            path = value.get_path()
            if path and path.lower().endswith(".pdf"):
                self.open_pdf(path)
                return True
        return False

    def open_pdf(self, path):
        if self._pdf:
            self._pdf.close()
        try:
            self._pdf = PDFDocument(path)
        except Exception as e:
            self._show_error(f"Не удалось открыть PDF: {e}")
            return

        self._current_page = 0
        self._load_thumbnails()
        self._show_preview(0)
        self._preview_stack.set_visible_child_name("preview")
        self.set_title(f"XPrinter Label — {path.split('/')[-1]}")

    def _load_thumbnails(self):
        # Clear existing
        while child := self._thumb_box.get_first_child():
            self._thumb_box.remove(child)

        for i in range(self._pdf.page_count):
            thumb_img = self._pdf.render_thumbnail(i, max_size=150)
            pixbuf = pil_to_gdk_pixbuf(thumb_img)
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)

            btn = Gtk.Button()
            btn.add_css_class("flat")
            pic = Gtk.Picture.new_for_paintable(texture)
            pic.set_size_request(150, -1)
            pic.set_can_shrink(True)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.append(pic)
            box.append(Gtk.Label(label=f"Стр. {i + 1}"))
            btn.set_child(box)

            page_num = i
            btn.connect("clicked", lambda b, p=page_num: self._show_preview(p))
            self._thumb_box.append(btn)

    def _show_preview(self, page_num):
        self._current_page = page_num
        img = self._pdf.render_preview(page_num)
        pixbuf = pil_to_gdk_pixbuf(img)
        texture = Gdk.Texture.new_for_pixbuf(pixbuf)
        self._preview_image.set_paintable(texture)

    def _get_selected_size(self):
        idx = self._size_dropdown.get_selected()
        names = list(LABEL_SIZES.keys())
        if idx < len(names):
            return LABEL_SIZES[names[idx]]
        return (58, 40)  # fallback

    def _on_size_changed(self, dropdown, pspec):
        idx = dropdown.get_selected()
        names = list(LABEL_SIZES.keys())
        if idx < len(names):
            self._prefs["label_size"] = names[idx]
            self._prefs.save()

    def _on_open_clicked(self, btn):
        dialog = Gtk.FileDialog()
        pdf_filter = Gtk.FileFilter()
        pdf_filter.set_name("PDF файлы")
        pdf_filter.add_mime_type("application/pdf")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(pdf_filter)
        dialog.set_filters(filters)
        dialog.open(self, None, self._on_file_chosen)

    def _on_file_chosen(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.open_pdf(file.get_path())
        except GLib.Error:
            pass  # user cancelled

    def _on_connect_clicked(self, btn):
        idx = self._conn_dropdown.get_selected()
        conn_type = ["USB", "Bluetooth", "WiFi"][idx]
        self._prefs["connection_type"] = conn_type
        self._prefs.save()

        if self._conn_mgr.is_connected():
            self._conn_mgr.disconnect()
            self._status_label.set_label("Отключён")
            self._connect_btn.set_label("Подключить")
            return

        try:
            if conn_type == "USB":
                ports = USBConnection.find_ports()
                if not ports:
                    self._show_error("USB-принтер не найден. Подключите принтер.")
                    return
                self._conn_mgr.create_connection("USB", port=ports[0])

            elif conn_type == "Bluetooth":
                addr = self._prefs["bt_address"]
                if not addr:
                    self._show_bt_dialog()
                    return
                self._conn_mgr.create_connection("Bluetooth", address=addr)

            elif conn_type == "WiFi":
                host = self._prefs["wifi_host"]
                if not host:
                    self._show_wifi_dialog()
                    return
                self._conn_mgr.create_connection("WiFi", host=host, port=self._prefs["wifi_port"])

            self._conn_mgr.connect()
            self._status_label.set_label(f"Подключён: {self._conn_mgr.connection.display_name}")
            self._connect_btn.set_label("Отключить")

        except Exception as e:
            self._show_error(f"Ошибка подключения: {e}")

    def _on_print_clicked(self, btn):
        if not self._pdf:
            self._show_error("Сначала откройте PDF файл")
            return
        if not self._conn_mgr.is_connected():
            self._show_error("Сначала подключите принтер")
            return

        w_mm, h_mm = self._get_selected_size()
        copies = int(self._copies_spin.get_value())
        density = self._prefs["density"]
        speed = self._prefs["speed"]
        gap_mm = self._prefs["gap_mm"]

        self._status_label.set_label("Печать...")

        def do_print():
            try:
                img = self._pdf.render_page(self._current_page, dpi=203)
                mono = prepare_label_image(img, w_mm, h_mm)
                data = build_label_job(mono, w_mm, h_mm, copies=copies,
                                       density=density, speed=speed, gap_mm=gap_mm)
                self._conn_mgr.send(data)
                GLib.idle_add(self._status_label.set_label, "Напечатано!")
            except Exception as e:
                GLib.idle_add(self._show_error, f"Ошибка печати: {e}")
                GLib.idle_add(self._status_label.set_label, "Ошибка")

        thread = threading.Thread(target=do_print, daemon=True)
        thread.start()

    def _on_settings_clicked(self, btn):
        dialog = Adw.PreferencesDialog()
        page = Adw.PreferencesPage()
        dialog.add(page)

        # Printer settings group
        group = Adw.PreferencesGroup(title="Настройки печати")
        page.add(group)

        # Density
        density_row = Adw.SpinRow.new_with_range(0, 15, 1)
        density_row.set_title("Плотность (0–15)")
        density_row.set_value(self._prefs["density"])
        density_row.connect("notify::value", lambda r, _: self._prefs.__setitem__("density", int(r.get_value())))
        group.add(density_row)

        # Speed
        speed_row = Adw.SpinRow.new_with_range(1, 5, 1)
        speed_row.set_title("Скорость (1–5)")
        speed_row.set_value(self._prefs["speed"])
        speed_row.connect("notify::value", lambda r, _: self._prefs.__setitem__("speed", int(r.get_value())))
        group.add(speed_row)

        # Gap
        gap_row = Adw.SpinRow.new_with_range(0, 10, 1)
        gap_row.set_title("Зазор между этикетками (мм)")
        gap_row.set_value(self._prefs["gap_mm"])
        gap_row.connect("notify::value", lambda r, _: self._prefs.__setitem__("gap_mm", int(r.get_value())))
        group.add(gap_row)

        # Connection group
        conn_group = Adw.PreferencesGroup(title="Подключение")
        page.add(conn_group)

        bt_row = Adw.EntryRow(title="Bluetooth адрес")
        bt_row.set_text(self._prefs["bt_address"])
        bt_row.connect("changed", lambda r: self._prefs.__setitem__("bt_address", r.get_text()))
        conn_group.add(bt_row)

        wifi_row = Adw.EntryRow(title="WiFi IP адрес")
        wifi_row.set_text(self._prefs["wifi_host"])
        wifi_row.connect("changed", lambda r: self._prefs.__setitem__("wifi_host", r.get_text()))
        conn_group.add(wifi_row)

        dialog.connect("closed", lambda d: self._prefs.save())
        dialog.present(self)

    def _show_bt_dialog(self):
        dialog = Adw.AlertDialog(
            heading="Bluetooth",
            body="Укажите Bluetooth адрес принтера в настройках (⚙)",
        )
        dialog.add_response("ok", "OK")
        dialog.present(self)

    def _show_wifi_dialog(self):
        dialog = Adw.AlertDialog(
            heading="WiFi",
            body="Укажите IP адрес принтера в настройках (⚙)",
        )
        dialog.add_response("ok", "OK")
        dialog.present(self)

    def _show_error(self, message):
        dialog = Adw.AlertDialog(heading="Ошибка", body=message)
        dialog.add_response("ok", "OK")
        dialog.present(self)
