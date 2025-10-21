# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

from gi.repository import Gtk, GObject

from quodlibet import _, config
from quodlibet.plugins.editing import RenameFilesPlugin
from quodlibet.util import print_d
from quodlibet.qltk import Icons


class RenamingPathPrune(Gtk.Box, RenameFilesPlugin):
    PLUGIN_ID = "RenamingPathPrune"
    PLUGIN_NAME = _("Renaming Path Prune")
    PLUGIN_DESC_MARKUP = _(
        "For path components containing multiple values (tags separated by commas) "
        "while renaming files, this plugin intelligently selects a single value "
        "based on defined preference and avoidance rules."
    )
    PLUGIN_ICON = Icons.EDIT_FIND_REPLACE

    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_LAST, None, ())}
    active = True

    @classmethod
    def PluginPreferences(cls, window):
        grid = Gtk.Grid()
        grid.set_border_width(6)
        grid.set_row_spacing(6)
        grid.set_column_spacing(12)

        def connect_config_entry(entry, key):
            def on_changed(e):
                config.set("plugins", key, e.get_text())
            entry.connect("changed", on_changed)

        # Preferred values
        label_priority = Gtk.Label(
            label=_("Preferred values (comma-separated):"))
        label_priority.set_halign(Gtk.Align.START)
        grid.attach(label_priority, 0, 0, 1, 1)

        priority_entry = Gtk.Entry()
        priority_entry.set_hexpand(True)
        priority_words = config.get(
            "plugins", "pathprune_priority_words", "")
        priority_entry.set_text(priority_words)
        grid.attach(priority_entry, 1, 0, 1, 1)
        connect_config_entry(priority_entry, "pathprune_priority_words")

        # Avoided values
        label_avoid = Gtk.Label(
            label=_("Avoided values (comma-separated):"))
        label_avoid.set_halign(Gtk.Align.START)
        grid.attach(label_avoid, 0, 1, 1, 1)

        avoid_entry = Gtk.Entry()
        avoid_entry.set_hexpand(True)
        avoid_words = config.get("plugins", "pathprune_avoid_words", "")
        avoid_entry.set_text(avoid_words)
        grid.attach(avoid_entry, 1, 1, 1, 1)
        connect_config_entry(avoid_entry, "pathprune_avoid_words")

        explanation_markup = _(
            "<b>Note on Operation:</b> The plugin processes path components "
            "(folders) by splitting them at the comma (','). "
            "This is effective for multi-valued tags like &lt;genre&gt; or "
            "&lt;grouping&gt;, but <b>should be avoided</b> for tags that may "
            "legitimately contain commas (e.g., certain album titles).\n\n"
            "To limit the plugin's impact, you can specify in the renaming panel "
            "the number of path components (folders) to process:\n"
            "if the number is positive, the first <i>[N]</i> folders are processed,\n"
            "if the number is negative, the last <i>[N]</i> folders are protected,\n"
            "If the number is zero or left empty, the plugin only acts on folders "
            "that appear before a double delimiter (//) in your rename pattern.\n"
            "E.g.: <b>&lt;genre&gt;/&lt;grouping&gt;//&lt;artist&gt;/&lt;year&gt; "
            "- &lt;album&gt;</b>"
        )
        explanation_label = Gtk.Label(
            label=explanation_markup,
            use_markup=True,
            wrap=True,
            xalign=0,
            justify=Gtk.Justification.LEFT
        )
        explanation_label.set_halign(Gtk.Align.START)
        grid.attach(explanation_label, 0, 2, 2, 1)

        return grid

    def __init__(self):
        super().__init__()
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_spacing(6)

        max_folders_str = config.get("plugins", "pathprune_maxfolders", "2")
        self._maxfolders_entry = Gtk.Entry()
        self._maxfolders_entry.set_text(max_folders_str)
        self._maxfolders_entry.set_width_chars(3)

        self.pack_start(Gtk.Label(label=_("In the first ")), False, False, 0)
        self.pack_start(self._maxfolders_entry, False, False, 0)
        self.pack_start(
            Gtk.Label(label=_(" path components, automatically select a single value from multi-valued tags.")),
            False, False, 0)

        self._maxfolders_entry.connect("changed", self._on_maxfolders_changed)

    def _on_maxfolders_changed(self, entry):
        config.set("plugins", "pathprune_maxfolders", entry.get_text())
        self.emit("changed")

    def _get_words_from_config(self, key):
        words_str = config.get("plugins", key, "")
        return [w.strip().lower() for w in words_str.split(',') if w.strip()]

    def _get_best_value(self, part, priority_words, avoid_words):
        values = [v.strip() for v in part.split(',')]
        if len(values) <= 1:
            return part

        for p_word in priority_words:
            for value in values:
                if p_word == value.lower():
                    return value

        found_value = None
        for value in values:
            if value.lower() not in avoid_words:
                found_value = value
                break

        return found_value if found_value is not None else values[0]

    def filter_list(self, songs, paths):
        max_folders_str = self._maxfolders_entry.get_text()

        try:
            max_folders = int(max_folders_str)
        except ValueError:
            print_d(f"PathPrune: Invalid number '{max_folders_str}', doing nothing.")
            return paths

        priority_words = self._get_words_from_config("pathprune_priority_words")
        avoid_words = self._get_words_from_config("pathprune_avoid_words")

        new_paths = []
        for path in paths:
            if "//" in path:
                pre, post = path.split('//', 1)
                pre_parts = pre.split('/')
                new_pre_parts = []
                for part in pre_parts:
                    new_pre_parts.append(self._get_best_value(
                        part, priority_words, avoid_words))
                processed_pre = "/".join(new_pre_parts)
                new_paths.append(processed_pre + "/" + post)
                continue

            if max_folders == 0:
                new_paths.append(path)
                continue

            parts = path.split("/")
            new_parts = []

            is_absolute = path.startswith('/')
            limit = 0
            if max_folders > 0:
                limit = max_folders + 1 if is_absolute else max_folders
            else:
                limit = len(parts) - 1 + max_folders

            for i, part in enumerate(parts):
                if i < limit and i < len(parts) - 1:
                    best_value = self._get_best_value(
                        part, priority_words, avoid_words)
                    new_parts.append(best_value)
                else:
                    new_parts.append(part)

            new_path = "/".join(new_parts)
            new_paths.append(new_path)

        return new_paths
