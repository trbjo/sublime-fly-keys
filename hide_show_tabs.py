import sublime
import sublime_plugin

class SetTabsTrueCommand(sublime_plugin.WindowCommand):
    def run(self):
        sublime.active_window().set_tabs_visible(True)

class SetTabsFalseCommand(sublime_plugin.WindowCommand):
    def run(self):
        groups = self.window.num_groups()
        if groups == 1:
            sublime.active_window().set_tabs_visible(False)

