class ViewTabs(sublime_plugin.EventListener):

    def on_activated_async(self, view):
            if len(sublime.active_window().views()) > 1:
                sublime.active_window().set_tabs_visible(True)

    def on_deactivated_async(self, view):
            if len(sublime.active_window().views()) == 1:
                sublime.active_window().set_tabs_visible(False)
