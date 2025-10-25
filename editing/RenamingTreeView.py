# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import os

from gi.repository import Gtk, GObject
from senf import fsn2text, text2fsn

from quodlibet import _, config
from quodlibet.plugins.editing import RenameFilesPlugin
from quodlibet.util import print_d
from quodlibet.qltk import Icons
from quodlibet.qltk.views import TreeViewColumn
from quodlibet.qltk.renamefiles import RenameFiles
from quodlibet.qltk.properties import SongProperties


def find_ancestor_by_class(widget, target_class):
    """Recursively finds an ancestor widget of a specific class."""
    parent = widget.get_parent()
    while parent:
        if isinstance(parent, target_class):
            return parent
        parent = parent.get_parent()
    return None


def _case_insensitive_sort(model, iter1, iter2, user_data):
    """
    Custom Gtk.TreeModel sort function for case-insensitive string comparison.
    Sorts based on column 0 (the display name).
    """
    try:
        val1 = model.get_value(iter1, 0)
        val2 = model.get_value(iter2, 0)
    except Exception:
        return 0

    s1 = (val1 or "").lower()
    s2 = (val2 or "").lower()

    if s1 < s2:
        return -1
    elif s1 > s2:
        return 1
    else:
        return 0


class RenamingTreeView(Gtk.Box, RenameFilesPlugin):
    PLUGIN_ID = "RenamingTreeView"
    PLUGIN_NAME = _("Renaming Tree View")
    PLUGIN_DESC_MARKUP = _("A tree view for the renaming tab")
    PLUGIN_ICON = Icons.FOLDER

    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_LAST, None, ())}

    def __init__(self):
        super().__init__()
        self.rename_pane = None
        self.initialized = False
        self.connect("realize", self._on_realize)

    def _on_realize(self, widget):
        """Initializes the plugin once it's part of the widget tree."""
        if self.initialized:
            return

        self.rename_pane = find_ancestor_by_class(self, RenameFiles)

        if self.rename_pane:
            self.initialize_ui()
            self.initialized = True

    def initialize_ui(self):
        """Finds and modifies the RenameFiles UI to add the stack and tree view."""
        if hasattr(self.rename_pane, 'stack'):
            return

        self.rename_pane.stack = Gtk.Stack()
        self.rename_pane.stack.set_transition_type(
            Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        stack_switcher = Gtk.StackSwitcher()
        stack_switcher.set_stack(self.rename_pane.stack)

        top_hbox = self.rename_pane.get_children()[0]
        top_hbox.pack_start(stack_switcher, False, False, 0)
        stack_switcher.show()

        original_sw = self.rename_pane.get_children()[1]
        self.rename_pane.remove(original_sw)

        self.rename_pane.stack.add_named(original_sw, "list")
        self.rename_pane.stack.child_set_property(
            original_sw, "icon-name", "view-list-symbolic")

        self.fs_tstore = Gtk.TreeStore(str, str, object)

        self.fs_tstore.set_sort_func(0, _case_insensitive_sort, None)
        self.fs_tstore.set_sort_column_id(0, Gtk.SortType.ASCENDING)

        self.fs_view = Gtk.TreeView(model=self.fs_tstore)
        self.fs_view.set_headers_visible(False)
        self.fs_view.set_has_tooltip(True)
        self.__add_fs_tree_columns()
        self.fs_view.connect("query-tooltip", self._on_fs_view_query_tooltip)

        sw_tree = Gtk.ScrolledWindow()
        sw_tree.set_shadow_type(Gtk.ShadowType.IN)
        sw_tree.add(self.fs_view)
        sw_tree.show_all()

        self.rename_pane.stack.add_named(sw_tree, "tree")
        self.rename_pane.stack.child_set_property(
            sw_tree, "icon-name", "folder-visiting-symbolic")

        self.rename_pane.pack_start(self.rename_pane.stack, True, True, 0)
        self.rename_pane.reorder_child(self.rename_pane.stack, 1)
        self.rename_pane.stack.show()

        # Connect to the preview button's "clicked" signal.
        self.rename_pane.preview.connect("clicked", self._update_tree_view)

    def _update_tree_view(self, button):
        """
        Populates our tree view with data from the main list view model,
        which has just been updated by the original preview handler.
        """

        self.fs_tstore.clear()
        folder_iters = {}

        list_model = self.rename_pane.view.get_model()
        if len(list_model) == 0:
            return

        for row in list_model:
            entry = row[0]
            self.__add_to_fs_tree(entry, folder_iters)

        if len(list_model) <= 50:
            self.fs_view.expand_all()
        else:
            self.fs_tstore.foreach(self._selectively_expand)

    def _on_fs_view_query_tooltip(self, widget, x, y, keyboard_tip, tooltip):
        path_info = widget.get_path_at_pos(x, y)
        if not path_info:
            return False
        path, col, cell_x, cell_y = path_info
        entry = widget.get_model()[path][2]
        if entry:
            tooltip.set_text(entry.name)
            return True
        return False

    def _selectively_expand(self, model, path, iter):
        """
        Gtk.TreeStore.foreach() callback.
        Expands a row (iter) if it's a folder that contains other folders.
        Does not expand "leaf" directories (folders containing only files).
        """
        entry = model.get_value(iter, 2)
        if entry is not None:
            return False

        child_iter = model.iter_children(iter)
        is_parent_of_folder = False

        while child_iter:
            is_child_a_folder = model.get_value(child_iter, 2) is None
            if is_child_a_folder:
                is_parent_of_folder = True
                break
            child_iter = model.iter_next(child_iter)

        if is_parent_of_folder:
            self.fs_view.expand_row(path, open_all=False)

        return False

    def __add_fs_tree_columns(self):
        col = TreeViewColumn()
        cell_pixbuf = Gtk.CellRendererPixbuf()
        cell_text = Gtk.CellRendererText()
        col.pack_start(cell_pixbuf, False)
        col.pack_start(cell_text, True)
        col.add_attribute(cell_pixbuf, "icon-name", 1)
        col.add_attribute(cell_text, "text", 0)
        self.fs_view.append_column(col)

    def __add_to_fs_tree(self, entry, folder_iters):
        path = entry.new_name
        if not path:
            return

        parts = path.split(os.path.sep)
        if os.path.isabs(path) and parts and parts[0] == "":
            parts[0] = os.path.sep

        parent_iter = None
        current_path = ""

        for part in parts[:-1]:
            if not part:
                continue
            current_path = os.path.join(current_path, part) if part != os.path.sep else os.path.sep

            if current_path in folder_iters:
                parent_iter = folder_iters[current_path]
            else:
                icon_name = "folder" if os.path.isdir(text2fsn(current_path)) else "folder-new"
                display_name = part if current_path != os.path.sep else os.path.sep
                parent_iter = self.fs_tstore.append(
                    parent_iter, [display_name, icon_name, None])
                folder_iters[current_path] = parent_iter

        filename = parts[-1]
        self.fs_tstore.append(parent_iter, [filename, "audio-x-generic", entry])
