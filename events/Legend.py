# Copyright 2025 Yoann Guerin
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

from gi.repository import Gtk

from quodlibet import app
from quodlibet.plugins import PluginConfig, ConfProp
from quodlibet.plugins.events import EventPlugin
from quodlibet.qltk import Icons
from quodlibet.qltk.entry import UndoEntry

class Config:
    """Configuration handler for the plugin."""
    _config = PluginConfig(__name__)
    DEFAULT_CONTENT = "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
    legend_content = ConfProp(_config, "legend_content", DEFAULT_CONTENT)

CONFIG = Config()

class Legend(EventPlugin):
    PLUGIN_ID = 'legend'
    PLUGIN_NAME = "Legend"
    PLUGIN_DESC = "Adds a custom legend to the status bar."
    PLUGIN_ICON = Icons.EDIT
    PLUGIN_VERSION = "0.2"

    container = None
    label = None

    def enabled(self):
        """
        Called when the plugin is enabled.
        Injects the legend label into the status bar container.
        """
        try:
            self.statusbar = app.window.statusbar
            self.container = self.statusbar.get_parent()
        except AttributeError:
            print("Legend Plugin: Could not locate the status bar hierarchy.")
            return

        self.label = Gtk.Label()
        self.label.set_markup(CONFIG.legend_content)
        self.label.set_name("LegendPluginLabel")

        self.container.pack_start(self.label, False, False, 10)
        try:
            self.container.reorder_child(self.label, 1)
        except Exception:
            pass

        self.label.show_all()

    def disabled(self):
        """
        Called when the plugin is disabled.
        Clean up the widget to avoid UI clutter.
        """
        if self.label:
            self.label.destroy()
            self.label = None
        self.container = None

    @classmethod
    def PluginPreferences(cls, parent):
        """
        Generates the settings widget in the plugin window.
        """
        def changed(entry):
            text_content = entry.get_text()
            CONFIG.legend_content = text_content

            if hasattr(app, 'window') and app.window and hasattr(app.window, 'statusbar'):
                try:
                    statusbar_container = app.window.statusbar.get_parent()
                    for child in statusbar_container.get_children():
                        if child.get_name() == "LegendPluginLabel":
                            child.set_markup(text_content)
                            break
                except Exception:
                    pass

        vbox = Gtk.VBox(spacing=6)

        def create_legend_content_ui():
            hbox = Gtk.HBox(spacing=6)
            hbox.set_border_width(6)

            label = Gtk.Label(label="Legend content:")
            hbox.pack_start(label, False, True, 0)

            entry = UndoEntry()
            if CONFIG.legend_content:
                entry.set_text(CONFIG.legend_content)

            entry.connect('changed', changed)

            hbox.pack_start(entry, True, True, 0)
            return hbox

        vbox.pack_start(create_legend_content_ui(), True, True, 0)

        return vbox
