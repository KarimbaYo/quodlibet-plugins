import operator

from gi.repository import Gtk, GdkPixbuf, Gio

from quodlibet import _
from quodlibet import app
from quodlibet.plugins import PluginConfig
from quodlibet.plugins.events import EventPlugin
from quodlibet.browsers.paned.main import PanedBrowser
from quodlibet.browsers.paned.pane import Pane
from quodlibet.browsers.paned.models import PaneModel, AllEntry
from quodlibet.qltk import Icons, print_d

ICON_AND = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
	<path fill="currentColor" d="M15.7,4.5c-1.1,0-2.2,0.3-3.2,0.7c-0.1,0.1-0.3,0.1-0.4,0.1s-0.3,0-0.4-0.1c-1-0.5-2.1-0.7-3.2-0.7C4.4,4.5,1,7.9,1,12
	s3.4,7.5,7.5,7.5c1.1,0,2.2-0.3,3.2-0.7c0.1-0.1,0.3-0.1,0.4-0.1s0.3,0,0.4,0.1c1,0.5,2.1,0.7,3.2,0.7c4.1,0,7.5-3.4,7.5-7.5
	S19.8,4.5,15.7,4.5z M12.6,16.6c-0.2,0.1-0.4,0.2-0.6,0.2s-0.4-0.1-0.6-0.2c-1.6-1.3-2.6-2.9-2.6-4.6s0.9-3.3,2.6-4.6
	c0.2-0.1,0.4-0.2,0.6-0.2s0.4,0.1,0.6,0.2c1.6,1.3,2.6,2.9,2.6,4.6C15.2,13.7,14.3,15.3,12.6,16.6z"/>
</svg>
"""

ICON_OR = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
	<path fill="currentColor" d="M15.7,4.5c-1.1,0-2.2,0.3-3.2,0.7c-0.1,0.1-0.3,0.1-0.4,0.1s-0.3,0-0.4-0.1c-1-0.5-2.1-0.7-3.2-0.7c-4.1,0-7.5,3.4-7.5,7.5
	s3.4,7.5,7.5,7.5c1.1,0,2.2-0.3,3.2-0.7c0.1-0.1,0.3-0.1,0.4-0.1s0.3,0,0.4,0.1c1,0.5,2.1,0.7,3.2,0.7c4.1,0,7.5-3.4,7.5-7.5
	S19.8,4.5,15.7,4.5z M9.3,16.3c0.2,0.2,0.2,0.5,0.1,0.7s-0.3,0.4-0.6,0.4c-0.2,0-0.4,0-0.6,0c-3,0-5.5-2.5-5.5-5.5
	c0-3,2.5-5.5,5.5-5.5c0.2,0,0.4,0,0.6,0c0.3,0,0.5,0.2,0.6,0.4c0.1,0.2,0.1,0.5-0.1,0.7C8.3,9,7.8,10.5,7.8,12
	C7.8,13.5,8.3,15,9.3,16.3z M12.7,15.8c-0.2,0.2-0.5,0.3-0.7,0.3s-0.5-0.1-0.7-0.3c-1.1-1.1-1.7-2.4-1.7-3.8c0-1.4,0.6-2.7,1.7-3.8
	C11.5,8,11.7,7.9,12,7.9s0.5,0.1,0.7,0.3c1.1,1.1,1.7,2.4,1.7,3.8C14.4,13.4,13.8,14.7,12.7,15.8z M15.7,17.5c-0.2,0-0.4,0-0.6,0
	c-0.3,0-0.5-0.2-0.6-0.4s-0.1-0.5,0.1-0.7c1-1.3,1.5-2.8,1.5-4.3c0-1.5-0.5-3-1.5-4.3c-0.2-0.2-0.2-0.5-0.1-0.7
	c0.1-0.2,0.3-0.4,0.6-0.4c0.2,0,0.4,0,0.6,0c3,0,5.5,2.5,5.5,5.5C21.2,15,18.7,17.5,15.7,17.5z"/>
</svg>
"""

plugin_config = PluginConfig("conjunction")
defaults = plugin_config.defaults
defaults.set("state", "||")

def get_pixbuf_from_svg(svg_str, size=24):
	"""Converts an SVG string to a GdkPixbuf"""
	try:
		input_stream = Gio.MemoryInputStream.new_from_data(svg_str.encode("utf-8"), None)
		return GdkPixbuf.Pixbuf.new_from_stream_at_scale(input_stream, size, size, True, None)
	except Exception as e:
		print_d(f"Conjunction Plugin: Error parsing SVG: {e}")
		return None

class ConjunctionButton(Gtk.ToggleButton):
	"""A specific ToggleButton that handles its own SVG icons and states"""

	def __init__(self, initial_state_is_and):
		super().__init__()

		style_context = self.get_style_context()
		style_context.add_class("conjunction-switch")

		css = """
		.conjunction-switch:checked {
			background-color: transparent;
		}
		.conjunction-switch:hover {
			background-color: @theme_selected_bg_color;
			color: @theme_selected_fg_color;
		}
		"""
		provider = Gtk.CssProvider()
		provider.load_from_data(css.encode("utf-8"))
		style_context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

		self.pixbuf_and = get_pixbuf_from_svg(ICON_AND)
		self.pixbuf_or = get_pixbuf_from_svg(ICON_OR)

		self.set_tooltip_text(_("Toggle conjunction mode for multi-selections"))
		self.set_always_show_image(True)

		self.set_active(initial_state_is_and)
		self.update_icon()

		self.connect("toggled", self._on_internal_toggle)

	def _on_internal_toggle(self, widget):
		self.update_icon()

	def update_icon(self):
		is_and = self.get_active()
		pixbuf = self.pixbuf_and if is_and else self.pixbuf_or

		if pixbuf:
			self.set_image(Gtk.Image.new_from_pixbuf(pixbuf))
		else:
			self.set_label("&" if is_and else "||")

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

    is_and_mode = plugin_config.get("state") == "&"

    # Apply conjunction (AND) only if enabled AND we are NOT in the last column.
    if is_and_mode and not is_last_pane:
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
    PLUGIN_DESC = "Filters paned browser multi-selections using conjunction (logical AND)."
    PLUGIN_ICON = Icons.EDIT
    PLUGIN_VERSION = "0.5"

    def enabled(self):
        # Monkey-patching
        self.keep_original_get_songs_method = Pane._Pane__get_selected_songs
        Pane._Pane__get_selected_songs = conjunction_plugin_get_selected_songs
        PaneModel.get_songs_conjunction = conjunction_plugin_get_songs

        # UI Initialization
        current_state = plugin_config.get("state")
        self.button = ConjunctionButton(initial_state_is_and=(current_state == "&"))

        # Connect to main plugin logic
        self.button.connect("toggled", self._on_button_toggled)

        # Inject into Search Bar
        if hasattr(app.browser, "_sb_box"):
            app.browser._sb_box.pack_start(self.button, False, True, 0)
            sb_box_length = len(app.browser._sb_box.get_children())
            app.browser._sb_box.reorder_child(self.button, sb_box_length - 2)
            self.button.show()

    def disabled(self):
        if hasattr(self, 'button') and self.button:
            self.button.destroy()
            self.button = None

        Pane._Pane__get_selected_songs = self.keep_original_get_songs_method
        if hasattr(PaneModel, "get_songs_conjunction"):
            del PaneModel.get_songs_conjunction

    def _on_button_toggled(self, button):
        """Handle the state change and save config"""
        new_state = "&" if button.get_active() else "||"
        plugin_config.set("state", new_state)
