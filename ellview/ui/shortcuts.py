"""동작(액션) 목록과 기본 단축키.

새 기능을 추가할 땐 여기에 (id, 메뉴 이름, 기본 단축키)를 한 줄 추가하고
MainWindow에 같은 이름의 `act_<id>` 메서드를 만들면 메뉴·단축키 설정 화면에 자동으로 나타납니다.
"""
from __future__ import annotations

# (id, 표시 이름, 기본 단축키 목록, 분류)
ACTIONS: list[tuple[str, str, list[str], str]] = [
    ("open_file", "파일 열기", ["Ctrl+O"], "파일"),
    ("open_folder", "폴더 열기", ["Ctrl+Shift+O"], "파일"),
    ("reload", "다시 읽기", ["F5"], "파일"),
    ("open_location", "파일 위치 열기", ["Ctrl+E"], "파일"),
    ("close_book", "닫기", ["Ctrl+W"], "파일"),
    ("quit", "종료", ["Ctrl+Q"], "파일"),

    ("next_page", "다음 페이지", ["Right", "PgDown", "Space"], "이동"),
    ("prev_page", "이전 페이지", ["Left", "PgUp", "Backspace"], "이동"),
    ("scroll_down", "아래로 스크롤 / 다음", ["Down"], "이동"),
    ("scroll_up", "위로 스크롤 / 이전", ["Up"], "이동"),
    ("first_page", "첫 페이지", ["Home"], "이동"),
    ("last_page", "마지막 페이지", ["End"], "이동"),
    ("next_single", "한 장만 앞으로", ["Shift+Right"], "이동"),
    ("prev_single", "한 장만 뒤로", ["Shift+Left"], "이동"),
    ("next_book", "다음 파일(폴더/압축)", ["Ctrl+Right", "]"], "이동"),
    ("prev_book", "이전 파일(폴더/압축)", ["Ctrl+Left", "["], "이동"),
    ("confirm", "안내 확인(다음 파일로 이동)", ["Return", "Enter"], "이동"),
    ("goto_page", "페이지로 이동...", ["Ctrl+G"], "이동"),

    ("fit_window", "창에 맞춤", ["Ctrl+1"], "보기"),
    ("fit_width", "가로 맞춤", ["Ctrl+2"], "보기"),
    ("fit_height", "세로 맞춤", ["Ctrl+3"], "보기"),
    ("fit_original", "원본 크기", ["Ctrl+4", "Ctrl+0"], "보기"),
    ("zoom_in", "확대", ["Ctrl+=", "+", "Ctrl++"], "보기"),
    ("zoom_out", "축소", ["Ctrl+-", "-"], "보기"),
    ("toggle_upscale", "작은 이미지 확대", [], "보기"),
    ("toggle_two_page", "두 페이지 보기", ["D"], "보기"),
    ("toggle_rtl", "오른쪽→왼쪽 읽기(만화)", ["M"], "보기"),
    ("toggle_cover", "두 페이지: 첫 장 단독", [], "보기"),
    ("toggle_fullscreen", "전체 화면", ["F11", "Alt+Return"], "보기"),
    ("escape", "전체 화면 해제 / 안내 닫기 / 슬라이드쇼 정지", ["Esc"], "보기"),
    ("toggle_thumbnails", "썸네일 목록", ["T"], "보기"),
    ("toggle_statusbar", "상태 표시줄", ["Ctrl+Shift+S"], "보기"),
    ("toggle_info", "이미지 정보 표시", ["I"], "보기"),
    ("toggle_animation", "애니메이션 일시정지", ["P"], "보기"),
    ("rotate_right", "오른쪽으로 회전", ["Ctrl+R"], "보기"),
    ("rotate_left", "왼쪽으로 회전", ["Ctrl+Shift+R"], "보기"),
    ("flip_h", "좌우 반전", ["H"], "보기"),
    ("reset_orientation", "회전/반전 초기화", [], "보기"),
    ("toggle_slideshow", "슬라이드쇼 시작/정지", ["S"], "보기"),

    ("copy_image", "이미지 복사", ["Ctrl+C"], "편집"),
    ("copy_path", "경로 복사", ["Ctrl+Shift+C"], "편집"),

    ("add_bookmark", "책갈피 추가", ["Ctrl+D"], "책갈피"),
    ("show_bookmarks", "책갈피 목록", ["Ctrl+B"], "책갈피"),

    ("settings", "설정...", ["Ctrl+,"], "도구"),
    ("check_update", "업데이트 확인", [], "도구"),
    ("shortcut_help", "단축키 목록", ["F1"], "도구"),
    ("about", "Ellview 정보", [], "도구"),
]

ACTION_IDS = [a[0] for a in ACTIONS]


def keys_for(action_id: str, overrides: dict) -> list[str]:
    if action_id in overrides and isinstance(overrides[action_id], list):
        return overrides[action_id]
    for a in ACTIONS:
        if a[0] == action_id:
            return list(a[2])
    return []
