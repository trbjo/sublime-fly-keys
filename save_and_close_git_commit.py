import sublime
import sublime_plugin
import subprocess

class SaveAndCloseGitCommitCommand(sublime_plugin.WindowCommand):
    def run(self):
        sublime.active_window().run_command('save')
        sublime.active_window().run_command('close')
        subprocess.Popen([ 'swaymsg', '[app_id="^PopUp$"]', 'scratchpad', 'show,', 'fullscreen', 'disable,', 'move', 'position', 'center,', 'resize', 'set', 'width', '1502px', 'height', '1002px,', 'resize', 'shrink', 'up', '650px']).wait()
