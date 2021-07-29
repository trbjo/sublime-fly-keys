import sublime
import sublime_plugin
from subprocess import check_output, Popen
from collections import OrderedDict
import os


class PromptGitCommand(sublime_plugin.WindowCommand):
    last_selected = 0

    def is_enabled(self):
        view = self.window.active_view()
        if view:
            scope = view.scope_name(view.sel()[0].begin()).split(' ')[0]
            if scope == 'text.git.commit':
                return True
        return False

    def run(self):
        git_actions_pretty = [
        '1: Commit, Rebase and Push',
        '2: Commit and Push',
        '3: Commit only'
        ]

        self.window.show_quick_panel(
            git_actions_pretty,
            self.transform,
            selected_index=self.last_selected)

    def transform(self, i):
        print(i)
        if i == -1:
            return
        self.last_selected = i

        sublime.active_window().run_command('save')
        sublime.active_window().run_command('close')

        if i >= 2:
            return

        pwd = self.window.active_view().file_name().rsplit('/', 1)[0]
        if i == 0:
            Popen(['git', '-C', pwd, 'pull', '--rebase'], shell=False).wait()

        Popen(['git', '-C', pwd, 'push'], shell=False)




class GitResetHead(sublime_plugin.WindowCommand):
    def run(self, edit=None):
        self.run_command(['git', 'reset', 'HEAD', self.get_file_name()])



class GitCommitNewCommand(sublime_plugin.WindowCommand):
    global git_dirs
    global non_git_dirs
    git_dirs = []
    non_git_dirs = []

    def run(self):
        pwd = self.window.active_view().file_name().rsplit('/', 1)[0]
        try:
            Popen(['git', '-C', pwd, 'commit', '-v'])
        except:
            sublime.status_message('Nothing to commit')
        # if sp.returncode != 0:
        #     output = sp.communicate()[0]
        #     last_line = output.strip().rsplit('\n', 1)[-1].capitalize()
        #     print(output)
        #     sublime.status_message(last_line)


    def is_enabled(self):
        pwd = self.window.active_view().file_name().rsplit('/', 1)[0]
        if pwd is None:
            return False

        for repo in git_dirs:
            if repo in pwd:
                return True
        for directory in non_git_dirs:
            if directory in pwd:
                return False

        result = self.is_git_dir(pwd)
        if result:
            git_dirs.append(result)
            return True
        else:
            non_git_dirs.append(pwd)
            return False


    def is_git_dir(self, pwd) -> str:
        while pwd:
            if os.path.exists(os.path.join(pwd, '.git')):
                return pwd
            parent = os.path.realpath(os.path.join(pwd, os.path.pardir))
            if parent == pwd:
                # /.. == /
                return ''
            pwd = parent
