import time
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

import sublime
from sublime import Region, View

# navigate paragraphs
interesting_regions: Dict[int, Dict[str, Tuple[int]]] = {}
timeouts: Dict[int, float] = {}

# sneak
matches: List[Region] = []


def maybe_rebuild(view: View):
    if view.element() is not None:
        return
    global timeouts
    timeouts[view.buffer_id()] = time.time()
    sublime.set_timeout(lambda: build_or_rebuild_ws_for_buffer(view, False), 2000)


def build_or_rebuild_ws_for_buffer(view: View, now: bool):
    if view is None:
        return
    global timeouts
    buf_id = view.buffer_id()
    if now or (time.time() - timeouts.get(buf_id, 0) >= 2):
        global interesting_regions
        interesting_regions[buf_id] = {}
        try:
            whitespaces: List[Region] = view.find_all(r"\n[\t ]*\n[\t ]*\S")
            size = view.size() + 1
            (
                interesting_regions[buf_id]["first"],
                interesting_regions[buf_id]["last"],
            ) = zip(
                *[(-2, -1)]
                + [(first, last - 1) for first, last in whitespaces]
                + [(size, size)]
            )
        except ValueError:
            pass
        timeouts[view.buffer_id()] = time.time()


def get_regions(view: View, part: str, now: bool = False):
    global interesting_regions

    if now:
        build_or_rebuild_ws_for_buffer(view, now=True)
        myregs: Tuple[int] = interesting_regions[view.buffer_id()][part]
        return myregs

    try:
        myregs: Tuple[int] = interesting_regions[view.buffer_id()][part]
    except KeyError:
        build_or_rebuild_ws_for_buffer(view, now=True)
        myregs: Tuple[int] = interesting_regions[view.buffer_id()][part]
    return myregs
