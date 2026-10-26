# Ellview 작업 체크포인트

## 처음 계획
| 단계 | 내용 |
|---|---|
| 0 | 프로젝트 구조, git, CHECKPOINT |
| 1 | 이미지 뷰어 코어 (열기/이동/확대/대용량/GIF) |
| 2 | 압축파일 지원 + 미리 읽기 |
| 3 | 파일 경계 이동 안내 + 단축키 |
| 4 | 책갈피(재탐색) + 이어보기 + 최근 파일 |
| 5 | 보기 모드, 썸네일, 두 페이지(RTL), 설정/단축키 편집, 다크 테마, 정보 표시 |
| 6 | PyInstaller + GitHub Actions + 업데이트 알림 |
| 7 | 최종 검증 + 사용자 PC로 복사 후 비교 |

## 진행 상황
- [x] 0단계: 폴더 구조, requirements, .gitignore, config.py(설정/포터블 모드), formats.py, archives.py, books.py, loader.py 초안

## 다음에 이어서 할 것
- 1단계: ui/viewer.py, ui/animation.py, ui/main_window.py, app.py 작성 후 오프스크린 GUI 테스트
