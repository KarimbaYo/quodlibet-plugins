
import operator

from gi.repository import Gtk

from quodlibet import _
from quodlibet import app
from quodlibet.plugins import PluginConfig
from quodlibet.plugins.events import EventPlugin
from quodlibet.browsers.paned.main import PanedBrowser
from quodlibet.browsers.paned.pane import Pane
from quodlibet.browsers.paned.models import PaneModel, AllEntry
from quodlibet.qltk import Icons, print_d
from quodlibet.qltk.x import ToggleButton

plugin_config = PluginConfig("conjunction")
defaults = plugin_config.defaults
defaults.set("state", "||")

def conjunction_plugin_get_selected_songs(pane, sort=False):
	"""Modified method of __get_selected_songs"""
	model, paths = pane.get_selection().get_selected_rows()

	# Determine if the current pane is the last column in the browser.
	is_last_pane = False
	try:
		if hasattr(app.browser, "_panes") and app.browser._panes:
			if pane is app.browser._panes[-1]:
				is_last_pane = True
	except Exception:
		pass

	if (plugin_config.get("state") == "&") and not is_last_pane:
		songs = model.get_songs_conjunction(paths)
	else:
		songs = model.get_songs(paths)

	if sort:
		return sorted(songs, key=operator.attrgetter("sort_key"))
	return songs

def conjunction_plugin_get_songs(model, paths):
	"""Get all songs for the given paths with conjunction"""

	s = set()
	if not paths:
		return s

	constraining_entries = []
	for path in paths:
		entry = model[path][0]
		if not isinstance(entry, AllEntry):
			constraining_entries.append(entry)

	if not constraining_entries:
		for entry in model.itervalues():
			s.update(entry.songs)
		return s

	s = set(constraining_entries[0].songs)
	for entry in constraining_entries[1:]:
		if not s:
			return set()
		s.intersection_update(entry.songs)

	return s

class Conjunction(EventPlugin):
	PLUGIN_ID = 'conjunction'
	PLUGIN_NAME = "Conjonction"
	PLUGIN_DESC = "Filters paned browser multi-selections using conjunction (logical AND). Ideal for multi-tagged songs."
	PLUGIN_ICON = Icons.EDIT
	PLUGIN_VERSION = "0.1"

	def enabled(self):
		self.keep_original_get_songs_method = Pane._Pane__get_selected_songs
		Pane._Pane__get_selected_songs = conjunction_plugin_get_selected_songs
		PaneModel.get_songs_conjunction = conjunction_plugin_get_songs

		state = plugin_config.get("state")
		self.toggle_button = ToggleButton(label=state)
		if state == "&":
			self.toggle_button.set_active(True)
		self.toggle_button.connect("toggled", self._conjunction_changed)
		self.toggle_button.set_tooltip_text(_("Toggle conjunction mode for multi-selections"))
		app.browser._sb_box.pack_start(self.toggle_button, False, True, 0)
		sb_box_length = len(app.browser._sb_box.get_children())
		app.browser._sb_box.reorder_child(self.toggle_button, sb_box_length-2)
		self.toggle_button.show();

	def disabled(self):
		self.toggle_button.destroy()
		self.toggle_button = None
		Pane._Pane__get_selected_songs = self.keep_original_get_songs_method
		del PaneModel.get_songs_conjunction
		pass

	def _conjunction_changed(self, button):
		state = "&" if plugin_config.get("state") == "||" else "||"
		button.set_label(state)
		plugin_config.set("state", state)
