import re
from re import Pattern
from typing import Any, Generator, Tuple, Union

from sublime import View
from sublime_api import view_cached_substr as substr  # pyright: ignore

CHUNKSIZE = 10_000

def buffer_slice(
    v: View, forward: bool, default_yield_border: bool = False
) -> Generator[Union[None, Tuple[int, int]], Tuple[Any, int, Pattern], None]:
    vid = v.id()

    first = 0
    last = v.size()

    if default_yield_border:
        default_yield = (last, last) if forward else (first, first)
    else:
        default_yield = None

    *_, index, pattern = yield default_yield
    unfolded = []
    for fold_start, fold_end in v.folded_regions():
        unfolded.append((first, fold_start))
        first = fold_end
    unfolded.append((first, last))

    regions = []
    pt = -1
    for a, b in unfolded:
        while pt < b:
            pt = min((index if index > a else last), b, v.line(a + CHUNKSIZE).b)
            regions.append((a, pt))
            a = pt

    buffers = {}
    if forward:
        while True:
            while index >= last:
                *_, index, new_pattern = yield default_yield
            _s, _e = next((_s, _e) for _s, _e in regions if index < _e)
            offset = max(index - _s, 0)
            piece = buffers.setdefault(_s, substr(vid, _s, _e))
            for m in re.finditer(pattern, piece[offset:]):
                mstart = _s + offset + m.start()
                mend = _s + offset + m.end()
                *_, index, new_pattern = yield (mstart, mend)
                if index != mend or new_pattern != pattern:  # new region
                    pattern = new_pattern
                    break
            else:
                index = _e + 1
    else:
        regions = regions[::-1]
        while True:
            while index <= 0:
                *_, index, new_pattern = yield default_yield
            _e, _s = next((_s, _e) for _s, _e in regions if index > _s)
            offset = max(_s - index, 0)
            piece = buffers.setdefault(_s, substr(vid, _s, _e)[::-1])
            for m in re.finditer(pattern, piece[offset:]):
                mstart = _s - offset - m.start()
                mend = _s - offset - m.end()
                *_, index, new_pattern = yield (mstart, mend)
                if index != mend or new_pattern != pattern:  # new region
                    pattern = new_pattern
                    break
            else:
                index = _e - 1
