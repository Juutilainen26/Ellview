"""두 페이지 보기에서 어떤 페이지를 함께 보여줄지 계산 (Qt와 무관해서 단독 테스트 가능)."""
from __future__ import annotations

from typing import Callable


def spread_at(index: int, count: int, two_page: bool, cover_single: bool,
              is_wide: Callable[[int], bool]) -> list[int]:
    if count <= 0:
        return []
    index = max(0, min(index, count - 1))
    if not two_page:
        return [index]
    if cover_single and index == 0:
        return [0]
    if index >= count - 1 or is_wide(index) or is_wide(index + 1):
        return [index]
    return [index, index + 1]


def prev_start(index: int, count: int, two_page: bool, cover_single: bool,
               is_wide: Callable[[int], bool]) -> int | None:
    """index에서 시작하는 화면의 바로 앞 화면이 시작하는 페이지."""
    if index <= 0:
        return None
    if two_page and index - 2 >= 0:
        s = spread_at(index - 2, count, two_page, cover_single, is_wide)
        if s == [index - 2, index - 1]:
            return index - 2
    return index - 1


def last_start(count: int, two_page: bool, cover_single: bool, is_wide: Callable[[int], bool]) -> int:
    """마지막 화면의 시작 페이지."""
    if count <= 0:
        return 0
    last = count - 1
    if two_page and last - 1 >= 0:
        s = spread_at(last - 1, count, two_page, cover_single, is_wide)
        if s == [last - 1, last]:
            return last - 1
    return last
