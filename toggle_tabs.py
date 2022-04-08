import sublime_plugin

class HideTabsCommand(sublime_plugin.WindowCommand):
    def run(self):
        if self.window.num_groups() == 1:
            self.window.set_tabs_visible(False)

class ShowTabsCommand(sublime_plugin.WindowCommand):
    def run(self):
        if self.window.num_groups() > 1:
            self.window.set_tabs_visible(True)

