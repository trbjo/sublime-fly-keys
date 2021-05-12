import sublime
import sublime_plugin
import subprocess

class SaveAndCloseGitCommitCommand(sublime_plugin.WindowCommand):
    def run(self):
        sublime.active_window().run_command('save')
        sublime.active_window().run_command('close')
        subprocess.Popen(['swaymsg', '[app_id="^PopUp$"]', 'scratchpad', 'show,', 'fullscreen', 'disable,', 'move', 'position', 'center,', 'resize', 'set', 'width', '100ppt', 'height', '100ppt,', 'resize', 'grow', 'width', '2px,', 'resize', 'shrink', 'up', '1100px,', 'resize', 'grow', 'up', '340px,', 'move', 'down', '1px']).wait()
        subprocess.Popen(['/usr/bin/pkill', 'zsh', '--signal=USR1']).wait()
