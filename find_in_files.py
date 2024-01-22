import re
from os import getenv, path
from typing import Counter, Dict, List, Optional, Tuple

import sublime
import sublime_plugin
from sublime import NewFileFlags, View, active_window, set_clipboard  # pyright: ignore
from sublime_api import view_cached_substr as view_substr  # pyright: ignore
from sublime_api import view_selection_add_point as add_point  # pyright: ignore
from sublime_api import view_selection_add_region as add_region  # pyright: ignore
from sublime_api import view_set_viewport_position as set_vp  # pyright: ignore
from sublime_plugin import TextCommand, WindowCommand

VIEWPORT_MARGIN = 2
HOME: str = getenv("HOME")  # pyright: ignore


class CopyInFindInFilesCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        v: View = self.view
        sel = v.sel()
        line = v.line(sel[0])
        line_content = v.substr(line)

        if not line_content.startswith(" "):
            set_clipboard(line_content[:-1])
        elif line_match := re.match(r"^\s+\d+", line_content):
            offset = line_match.end() + 2
            set_clipboard(line_content[offset:])


class FindInFilesListener(sublime_plugin.EventListener):
    def on_activated(self, view: View):
        if view.element() == "find_in_files:output" or view.name() == "Find Results":
            views = active_window().views()
            v_n_s = {str(v.id()): [tuple(reg) for reg in v.sel()] for v in views}
            vps = {str(v.id()): v.viewport_position() for v in views}
            active_window().settings().set(key="ViewsBeforeSearch", value=v_n_s)
            active_window().settings().set(key="viewport_positions", value=vps)


def restore_views(restore_groups: bool):
    w = sublime.active_window()
    views: Dict[str, List[List[int]]] = w.settings().get(
        "ViewsBeforeSearch", {}
    )  # pyright: ignore

    viewport_pos: Dict[str, Tuple[float, float]] = w.settings().get(
        "viewport_positions", {}
    )  # pyright: ignore

    active_group: int = w.settings().get("active_group", 0)


    if restore_groups:
        prev_groups =w.settings().get("groups_before_search", {})
        length = len(prev_groups.keys()) - 1

        for i in range(length):
            w.run_command("new_pane", args={"move": False})
        for groupnum, groupviews, in prev_groups.items():
            if (transient := w.transient_view_in_group(int(groupnum))) is not None:
                if str(transient.id()) not in views.keys():
                    transient.close()

            for ts in w.sheets():
                if (thisView:=ts.view()) is None:
                    continue

                if thisView.name() == "Find Results":
                    thisView.close()
                    continue

                if groupnum == '0':
                    continue

                if str(thisView.id()) in groupviews:
                    w.move_sheets_to_group([ts],int(groupnum))

    prior_vs: List[int] = w.settings().get("views_before_search", [])
    for v in w.views():
        v.sel().clear()
        [add_region(v.id(), reg[0], reg[1], 0.0) for reg in views[str(v.id())]]
        if v.id() in prior_vs:
            w.focus_view(v)

    for v in w.views():
        set_vp(v.id(), viewport_pos[str(v.id())], False)

    w.focus_group(active_group)
    w.run_command("hide_panel")


class CloseFindBufferCommand(WindowCommand):
    def run(self):
        view = self.window.active_view()
        if view is None:
            return

        restore_views(view.name()=="Find Results")


class CloseTransientViewCommand(WindowCommand):
    def run(self):
        view = self.window.active_view()
        if view is None:
            return
        restore_views(view.name()=="Find Results")


class OpenFindResultsCommand(WindowCommand):
    def run(self, panel):
        w = self.window
        own_tab = False
        vs = []

        gbs = {}
        for num in range(w.num_groups()):
            thisgroup = []
            for thisview in w.views_in_group(num):
                thisgroup.append(str(thisview.id()))
            gbs[str(num)] = thisgroup

        active_window().settings().set(key="groups_before_search", value=gbs)

        if (v := w.active_view()) is not None and v.name() == "Find Results":
            own_tab = True



        for num in range(w.num_groups()):
            if (v := w.active_view_in_group(num)) is not None:
                vs.append(v.id())
        w.settings().set(key="views_before_search", value=vs)
        w.settings().set(key="active_group", value=w.active_group())


        if own_tab:
            for num in range(w.num_groups()):
                w.run_command("close_pane")
            w.run_command("new_pane")

        if panel == "find_results" and not own_tab:
            w.run_command("show_panel", {"panel": f"output.{panel}"})

        if view := w.find_output_panel(panel):
            view.set_read_only(True)
            view.settings().set("command_mode", True)
            view.settings().set("block_caret", True)
            s = view.sel()
            if len(s) == 0:
                view.sel().add(0)
            w.focus_view(view)


class GotoSearchResultCommand(TextCommand):
    def run(self, _, new_tab=False) -> None:
        if (view := self.view) is None:
            return
        if (window := view.window()) is None:
            return

        own_buffer = view.name() == "Find Results"
        files = files_with_loc(view, own_buffer)
        restore_views(own_buffer)

        params = sublime.ENCODED_POSITION
        if new_tab:
            params += NewFileFlags.FORCE_CLONE

        for filewithloc in files:
            window.open_file(fname=filewithloc, flags=params)  # pyright: ignore

        if new_tab:
            window.run_command("new_pane")


def files_with_loc(view: sublime.View, full_buffer: bool) -> List[str]:
    names = []
    for reg in view.sel():
        line_no = get_line_no(view, reg)
        file_name, target_line = get_file(view, reg)
        if file_name is None or target_line is None:
            continue

        if line_no is not None:
            col = max(1, view.rowcol(reg.b)[1] - 6)
            file_loc = f"{file_name}:{line_no}:{col}"
        else:
            file_loc = f"{file_name}:1:1"
        names.append(file_loc)
        if full_buffer:
            continue

        target_tp = view.text_to_layout(target_line.a)[1]
        cursor_tp = view.text_to_layout(reg.b)[1]
        padding = view.line_height()
        if cursor_tp + padding - target_tp < view.viewport_extent()[1]:
            target_viewpoint = (0.0, target_tp - VIEWPORT_MARGIN)
            view.set_viewport_position(target_viewpoint)
    return names


class OutputPanelNavigateCommand(TextCommand):
    def run(self, _, show="next_line") -> None:
        if (view := self.view) is None:
            return
        if (window := view.window()) is None:
            return

        params = sublime.ENCODED_POSITION
        params += NewFileFlags.TRANSIENT

        carets = []
        for reg in view.sel():
            if (new_caret := self.get_next_pos(reg, show)) == -1:
                return
            carets.append(new_caret)

        view.sel().clear()
        vid = view.id()
        for caret in carets:
            add_point(vid, caret)
            view.show(caret)

        own_buffer = view.name() == "Find Results"
        group = 0 if own_buffer else -1
        files = files_with_loc(view, own_buffer)
        for filewithloc in files:
            window.open_file(
                fname=filewithloc, flags=params, group=group
            )  # pyright: ignore

    def get_next_pos(self, reg: sublime.Region, show: Optional[str]) -> int:
        v = self.view
        if show == "prev_line":
            line = v.line(v.line(reg.b - 1).a)
            while line.begin() > 1:
                if line.empty() or re.match(r"^(\S.+):$", v.substr(line)):
                    line = v.line(line.a - 1)
                    continue
                return line.a
        elif show == "next_line":
            line = v.line(v.line(reg.b + 1).b + 1)
            while line.end() + 1 < v.size():
                if line.empty() or re.match(r"^(\S.+):$", v.substr(line)):
                    line = v.line(line.b + 1)
                    continue
                return line.a
        elif show == "next_paragraph":
            if (match := v.find(r"\n\n.+:\n", reg.b).a) != -1:
                return match + 2
        elif show == "prev_paragraph":
            buffer = view_substr(v.id(), 0, reg.b)[::-1]
            if match := re.search(r"\n:.+\S\n\n", buffer):
                return reg.b - match.end() + 2

        return -1


def get_line_no(view: sublime.View, region: sublime.Region):
    line_text = view.substr(view.line(region))
    match = re.match(r"\s*(\d+):.+", line_text)
    if match:
        return match.group(1)
    return None


def get_file(view: sublime.View, region: sublime.Region):
    line = view.line(region)
    if line.empty() or line.b + 1 == view.size() or line.a == 1:
        return None, None
    while line.begin() > 1:
        line_text = view.substr(line)
        match = re.match(r"^(\S.+):$", line_text)
        if match:
            normalized_path = match.group(1).replace("~", HOME)
            if path.exists(normalized_path):
                return normalized_path, line
        line = view.line(line.begin() - 1)
    return None, None
