import re
from os import getenv, path
from typing import Dict, List, Optional, Tuple

import sublime
import sublime_plugin
from sublime import NewFileFlags, Region, Sheet, View, active_window  # pyright: ignore
from sublime_api import view_cached_substr as view_substr  # pyright: ignore
from sublime_api import view_selection_add_point as add_point  # pyright: ignore
from sublime_api import view_selection_add_region as add_region  # pyright: ignore
from sublime_api import view_set_viewport_position as set_vp  # pyright: ignore
from sublime_api import view_show_point as show_point  # pyright: ignore
from sublime_api import (
    window_active_sheet_in_group as active_sheet_grp,  # pyright: ignore
)
from sublime_api import window_move_sheets_to_group as mv_shts_grp  # pyright: ignore
from sublime_api import window_num_groups as win_num_grp  # pyright: ignore
from sublime_api import window_sheets_in_group as sheets_in_group  # pyright: ignore
from sublime_api import window_views  # pyright: ignore
from sublime_plugin import TextCommand, WindowCommand

from .cut_copy_paste import setClipboard

VIEWPORT_MARGIN = 2
HOME: str = getenv("HOME")  # pyright: ignore


def issearch(v: Optional[View]) -> bool:
    if v is None:
        return False
    return v.name() == "Find Results"


class CopyInFindInFilesCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        v: View = self.view
        sel = v.sel()
        line = v.line(sel[0])
        line_content = v.substr(line)

        if not line_content.startswith(" "):
            setClipboard(line_content[:-1])
        elif line_match := re.match(r"^\s+\d+", line_content):
            offset = line_match.end() + 2
            setClipboard(line_content[offset:])


def restore_views(new_views):
    w = sublime.active_window()
    wid = w.id()
    views: Dict[str, List[List[int]]] = w.settings().get(
        "ViewsBeforeSearch", {}
    )  # pyright: ignore

    if (layout := w.settings().get("layout", None)) is not None:
        w.set_layout(layout)

    prevFocused: Dict[str, int] = w.settings().get("prior_sheets", {})
    settings = w.settings().get("groups_before_search", {})
    for groupnum, groupviews in settings.items():
        mv_shts_grp(wid, groupviews, int(groupnum), -1, False)
        prvFocused = prevFocused[groupnum]
        mv_shts_grp(wid, [prvFocused], int(groupnum), -1, True)

    viewport_pos: Dict[str, Tuple[float, float]] = w.settings().get(
        "wiewp_pos", {}
    )  # pyright: ignore

    new_view_ids = [v.id() for v in new_views]
    for vid in window_views(wid, False):
        if vid in new_view_ids:
            continue

        thisview = sublime.View(vid)
        if (key := str(vid)) not in views.keys():
            thisview.close()
            continue

        thisview.sel().clear()
        [add_region(thisview.id(), reg[0], reg[1], 0.0) for reg in views[key]]
        set_vp(thisview.id(), viewport_pos[key], False)


class CloseFindInFilesCommand(WindowCommand):
    def run(self):
        w = self.window
        view = w.active_view()
        if view is None:
            return
        if issearch(view):
            view.close()
        elif (panel := w.active_panel()) == "output.find_results":
            w.run_command("hide_panel", {"panel": panel})

        restore_views([])
        w.focus_group(w.settings().get("active_group", 0))


class RegisterViewsCommand(WindowCommand):
    def run(self):
        w = self.window
        wid = w.id()
        shts: Dict[str, int] = {
            str(num): active_sheet_grp(wid, num) for num in range(win_num_grp(wid))
        }
        w.settings().set(key="prior_sheets", value=shts)

        views = [v for v in active_window().views() if not issearch(v)]
        v_n_s = {str(v.id()): [tuple(reg) for reg in v.sel()] for v in views}
        vps = {str(v.id()): v.viewport_position() for v in views}
        active_window().settings().set(key="ViewsBeforeSearch", value=v_n_s)
        active_window().settings().set(key="wiewp_pos", value=vps)
        gbs: Dict[str, List[int]] = {}
        for num in range(w.num_groups()):
            sheet_ids = []
            for s in w.sheets_in_group(num):
                if issearch(s.view()):
                    continue
                if s.id() in shts.values():
                    continue
                sheet_ids.append(s.id())
            gbs[str(num)] = sheet_ids

        w.settings().set(key="groups_before_search", value=gbs)
        w.settings().set(key="active_group", value=w.active_group())

        w.settings().set("layout", w.layout())


class OpenFindResultsCommand(WindowCommand):
    def run(self, panel):
        w = self.window
        wid = w.id()
        v = w.active_view()
        own_tab = issearch(v)

        # layout = {"cells": [[0, 0, 1, 1]], "cols": [0.0, 1.0], "rows": [0.0, 1.0]}
        if own_tab:
            sheet: Sheet = v.sheet()  # pyright: ignore
            sid = sheet.sheet_id

            w.set_layout(
                {
                    "cells": [[0, 0, 1, 1], [1, 0, 2, 1]],
                    "cols": [0.0, 0.5, 1.0],
                    "rows": [0.0, 1.0],
                }
            )

            for i in range(1, w.num_groups()):
                sheet_ids = [s for s in sheets_in_group(wid, i) if s != sid]
                mv_shts_grp(wid, sheet_ids, 0, -1, False)
            mv_shts_grp(wid, [sid], 1, -1, True)
            return

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
        if (w := view.window()) is None:
            return

        params = sublime.ENCODED_POSITION
        if new_tab:
            params += NewFileFlags.FORCE_CLONE
        files = files_with_loc(view, issearch(view))

        if issearch(view):
            view.close()
        elif (panel := w.active_panel()) == "output.find_results":
            w.run_command("hide_panel", {"panel": panel})

        views = [w.open_file(fname=v, flags=params) for v in files]
        restore_views(views)

        if new_tab:
            w.run_command("new_pane")

        for new_view in views:
            regions = list(new_view.sel()) or [Region(0, 0)]
            w.focus_view(new_view)
            show_point(new_view.id(), regions[0].b, True, False, False)


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

        for filewithloc in files_with_loc(view, issearch(view)):
            window.open_file(
                fname=filewithloc, flags=params, group=0
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
