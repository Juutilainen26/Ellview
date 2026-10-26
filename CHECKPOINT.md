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

- [x] 1단계: viewer.py(맞춤/확대/끌기/클릭·휠 이동), animation.py(GIF·WebP=QMovie 스트리밍, APNG=Pillow),
      main_window.py, app.py, 대용량 축소 디코딩, EXIF 회전. 테스트 14개 통과 + 스크린샷 확인
  - 발견/수정: Qt TIFF 플러그인이 Pillow libtiff와 충돌해 크래시 → TIFF는 Pillow로만 디코딩

## 다음에 이어서 할 것
- 2단계: 압축 백엔드 테스트(zip cp949, cbz 하위폴더, 7z, tar.gz, rar), 비밀번호, 미리 읽기 확인
