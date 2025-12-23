# Copyright 2025 Yoann Guerin
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

from gi.repository import Gtk, GLib, Gdk

from quodlibet import _
from quodlibet import app
from quodlibet import config
from quodlibet.plugins.events import EventPlugin
from quodlibet.qltk import Icons, Button


class FadeOut(EventPlugin):
    """
    Fade-Out: A plugin to fade out the current song over a configurable duration
    and then stop, pause, or quit.
    """

    PLUGIN_ID = "Fadeout"
    PLUGIN_NAME = "Fade-out"
    PLUGIN_DESC = _("Fades out music and stops/pauses/quits.")
    PLUGIN_ICON = Icons.AUDIO_VOLUME_MUTED

    # Config keys
    _CONF_DURATION = "fadeout_duration"
    _CONF_ACTION = "fadeout_action"
    _CONF_SHORTCUT = "fadeout_shortcut"

    # Action constants
    ACTION_STOP = "stop"
    ACTION_PAUSE = "pause"
    ACTION_QUIT = "quit"

    # Defaults
    DEFAULT_DURATION = 5.0
    DEFAULT_ACTION = ACTION_PAUSE
    DEFAULT_SHORTCUT = "<Primary><Shift>f"

    # Internal state
    _merge_id = None
    _action_group = None
    _original_volume = 1.0
    _timer_id = None
    _timer_interval_ms = 50

    def enabled(self):
        """Called when the plugin is enabled."""
        if app.window is None:
            return
        self._inject_menu_item()

    def disabled(self):
        """Called when the plugin is disabled."""
        self._cancel_fade()
        self._remove_menu_item()

    def _inject_menu_item(self):
        """Injects the 'Stop with Fade-out' action into the UI."""
        self._remove_menu_item()

        ui_manager = app.window.ui
        self._action_group = Gtk.ActionGroup(name="FadeOutActions")

        action = Gtk.Action(
            name="FadeOutAction",
            label=_("Stop with _fade-out"),
            tooltip=_("Fade out and stop/pause/quit"),
            icon_name=Icons.AUDIO_VOLUME_MUTED
        )
        action.connect("activate", self._initiate_fade_out)

        shortcut = self._get_config_shortcut()

        if not shortcut:
            shortcut = self.DEFAULT_SHORTCUT

        self._action_group.add_action_with_accel(action, shortcut)
        ui_manager.insert_action_group(self._action_group, -1)

        ui_def = """
        <ui>
          <menubar name='Menu'>
            <menu action='Control'>
              <menuitem action='FadeOutAction' always-show-image='true'/>
            </menu>
          </menubar>
        </ui>
        """
        self._merge_id = ui_manager.add_ui_from_string(ui_def)
        ui_manager.ensure_update()

    def _remove_menu_item(self):
        if app.window and app.window.ui:
            ui_manager = app.window.ui
            if self._merge_id:
                ui_manager.remove_ui(self._merge_id)
                self._merge_id = None
            if self._action_group:
                ui_manager.remove_action_group(self._action_group)
                self._action_group = None
            ui_manager.ensure_update()

    def _get_config_duration(self):
        try:
            return float(config.get("plugins", self._CONF_DURATION))
        except (ValueError, Exception):
            return self.DEFAULT_DURATION

    def _get_config_action(self):
        try:
            val = config.get("plugins", self._CONF_ACTION)
            if val in [self.ACTION_STOP, self.ACTION_PAUSE, self.ACTION_QUIT]:
                return val
        except Exception:
            pass
        return self.DEFAULT_ACTION

    def _get_config_shortcut(self):
        return config.get("plugins", self._CONF_SHORTCUT, self.DEFAULT_SHORTCUT)

    def _initiate_fade_out(self, action):
        """Starts the fading process if music is playing."""
        if app.player.paused or app.player.song is None:
            return

        self._cancel_fade()
        self._original_volume = app.player.volume
        duration = self._get_config_duration()

        if duration <= 0:
            self._finalize_stop()
            return

        total_steps = (duration * 1000) / self._timer_interval_ms
        self._volume_step = self._original_volume / max(1, total_steps)

        self._timer_id = GLib.timeout_add(
            self._timer_interval_ms,
            self._fade_step
        )

    def _fade_step(self):
        if app.player.paused:
            self._restore_volume()
            return False

        new_volume = app.player.volume - self._volume_step

        if new_volume <= 0:
            self._finalize_stop()
            return False
        else:
            app.player.volume = new_volume
            return True

    def _finalize_stop(self):
        """Performs the requested action at the end of the fade."""
        # Set volume to zero for the final cut
        app.player.volume = 0
        action = self._get_config_action()

        if action == self.ACTION_QUIT:
            # Quit
            if app.window:
                app.window.destroy()
            else:
                import sys
                sys.exit(0)
        elif action == self.ACTION_STOP:
            # Stop
            app.player.paused = True
            self._restore_volume()
            app.player.stop()
        else:
            # Pause
            app.player.paused = True
            self._restore_volume()

        self._timer_id = None

    def _restore_volume(self):
        app.player.volume = self._original_volume

    def _cancel_fade(self):
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
            if app.player.volume < self._original_volume:
                self._restore_volume()

    def PluginPreferences(self, parent):
        """Builds the GUI for plugin settings."""
        table = Gtk.Table(n_rows=4, n_columns=2)
        table.set_row_spacings(6)
        table.set_col_spacings(12)
        table.set_border_width(6)

        lbl_duration = Gtk.Label(label=_("Fade-out duration (seconds):"))
        lbl_duration.set_alignment(0.0, 0.5)

        adj = Gtk.Adjustment(
            value=self._get_config_duration(),
            lower=0.0, upper=30.0,
            step_increment=0.5,
            page_increment=1.0
        )
        scale = Gtk.HScale(adjustment=adj)
        scale.set_digits(1)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        scale.set_size_request(200, -1)
        scale.connect("value-changed", self._on_duration_changed)

        table.attach(lbl_duration, 0, 1, 0, 1, xoptions=Gtk.AttachOptions.FILL)
        table.attach(scale, 1, 2, 0, 1)

        lbl_action = Gtk.Label(label=_("Action after fade:"))
        lbl_action.set_alignment(0.0, 0.5)

        store = Gtk.ListStore(str, str)
        store.append([self.ACTION_PAUSE, _("Pause (Keep position)")])
        store.append([self.ACTION_STOP, _("Stop (Reset to start)")])
        store.append([self.ACTION_QUIT, _("Quit Quod Libet")])

        combo = Gtk.ComboBox.new_with_model(store)
        renderer_text = Gtk.CellRendererText()
        combo.pack_start(renderer_text, True)
        combo.add_attribute(renderer_text, "text", 1)

        current_action = self._get_config_action()
        for idx, row in enumerate(store):
            if row[0] == current_action:
                combo.set_active(idx)
                break

        combo.connect("changed", self._on_action_changed)

        table.attach(lbl_action, 0, 1, 1, 2, xoptions=Gtk.AttachOptions.FILL)
        table.attach(combo, 1, 2, 1, 2)

        lbl_shortcut = Gtk.Label(label=_("Shortcut (Click to set):"))
        lbl_shortcut.set_alignment(0.0, 0.5)

        hbox_shortcut = Gtk.HBox(spacing=6)

        self.entry_shortcut = Gtk.Entry()
        self.entry_shortcut.set_text(self._get_config_shortcut())
        self.entry_shortcut.set_editable(False)
        self.entry_shortcut.set_tooltip_text(_("Click here and press the desired key combination"))
        self.entry_shortcut.connect("key-press-event", self._on_shortcut_keypress)

        btn_reset = Gtk.Button()
        btn_reset.add(
            Gtk.Image.new_from_icon_name(Icons.DOCUMENT_REVERT, Gtk.IconSize.MENU)
        )
        btn_reset.set_tooltip_text(_("Reset to default shortcut"))
        btn_reset.connect("clicked", self._on_reset_shortcut)

        hbox_shortcut.pack_start(self.entry_shortcut, True, True, 0)
        hbox_shortcut.pack_start(btn_reset, False, False, 0)

        table.attach(lbl_shortcut, 0, 1, 2, 3, xoptions=Gtk.AttachOptions.FILL)
        table.attach(hbox_shortcut, 1, 2, 2, 3)

        lbl_warning = Gtk.Label(label=_("<i>Note: Restart Quod Libet to fully apply shortcut changes.</i>"))
        lbl_warning.set_use_markup(True)
        lbl_warning.set_alignment(0.0, 0.5)
        lbl_warning.set_sensitive(False)

        table.attach(lbl_warning, 0, 2, 3, 4, xoptions=Gtk.AttachOptions.FILL, yoptions=Gtk.AttachOptions.SHRINK)

        return table

    def _on_duration_changed(self, scale):
        val = scale.get_value()
        config.set("plugins", self._CONF_DURATION, str(val))

    def _on_action_changed(self, combo):
        iter = combo.get_active_iter()
        if iter is not None:
            model = combo.get_model()
            action_id = model[iter][0]
            config.set("plugins", self._CONF_ACTION, action_id)

    def _on_shortcut_keypress(self, widget, event):
        """Captures the keystroke and converts it to a GTK accelerator string."""
        if event.keyval in [Gdk.KEY_Control_L, Gdk.KEY_Control_R,
                            Gdk.KEY_Shift_L, Gdk.KEY_Shift_R,
                            Gdk.KEY_Alt_L, Gdk.KEY_Alt_R,
                            Gdk.KEY_Meta_L, Gdk.KEY_Meta_R,
                            Gdk.KEY_Super_L, Gdk.KEY_Super_R]:
            return False

        modifiers = event.state & Gtk.accelerator_get_default_mod_mask()
        accel_string = Gtk.accelerator_name(event.keyval, modifiers)

        if accel_string:
            widget.set_text(accel_string)
            config.set("plugins", self._CONF_SHORTCUT, accel_string)
            self._inject_menu_item()

        return True

    def _on_reset_shortcut(self, btn):
        """Resets the shortcut to the default value."""
        default = self.DEFAULT_SHORTCUT
        self.entry_shortcut.set_text(default)
        config.set("plugins", self._CONF_SHORTCUT, default)
        self._inject_menu_item()
