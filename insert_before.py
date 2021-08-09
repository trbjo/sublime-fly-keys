import sublime
import sublime_plugin
import subprocess

class InsertBeforeCommand(sublime_plugin.WindowCommand):
    def run(self):
        hej = sublime.active_window().active_view()
        hej.run_command("move", args={"by": "characters", "forward": False, "extend":False})
        hej.run_command("move", args={"by": "characters", "forward": False, "extend":False})
        hej.settings().set(key="block_caret", value=False)

class InsertAfterCommand(sublime_plugin.WindowCommand):
    def run(self):
        hej = sublime.active_window().active_view()
        hej.run_command("move", args={"by": "characters", "forward": True, "extend":False})
        hej.run_command("move", args={"by": "characters", "forward": True, "extend":False})
        hej.settings().set(key="block_caret", value=False)


