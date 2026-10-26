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

- [x] 2단계: zip(CP949 파일명 복원)/cbz(하위폴더, __MACOSX 제외)/7z(임시캐시 + 7-Zip 실행파일 폴백)/tar.*/rar,
      확장자 오인 자동 판별, 암호 감지, 미리 읽기. 테스트 23개 통과
  - RAR 압축 해제 도구: tools/UnRAR.exe → 7z.exe → Windows 내장 tar.exe 순. 릴리스에는 7z.exe+7z.dll 동봉 예정(6단계)

- [x] 3단계: 경계 안내(prompt/auto/stop), Enter 확인, Esc 취소, 4초 만료, 이전 파일은 마지막 페이지부터,
      빈 폴더 건너뛰기, 상위 폴더 열면 첫 하위 책 열기, Ctrl+←/→·[ ] 단축키. 테스트 34개 통과
  - 화면 확인 중 발견/수정: 안내 토스트 줄바꿈 어색함, 썸네일 정렬 들쭉날쭉

- [x] 4단계: 책갈피(경로+페이지명+크기+지문), 옮김/이름변경/폴더 이동 재탐색, 라이브러리 폴더 탐색,
      이름만 같은 후보는 확인 질문, 못 찾으면 직접 지정, 찾으면 경로 자동 수정·저장, 이어보기(재시작 후 유지),
      최근 파일. 테스트 47개 통과

- [x] 5단계: 두 페이지(표지 단독, 가로 이미지 단독), RTL(배치·클릭 방향), 맞춤 4종+확대, 썸네일, 정보 표시,
      전체 화면, 설정 대화상자(일반/보기/책갈피 폴더/단축키), 단축키 중복 검사, Qt 한국어 번역,
      실행 진입점 --smoke-test. 테스트 59개 통과 + 대화상자 화면 확인

- [x] 6단계: 아이콘, ellview.spec(onedir, 불필요 Qt 모듈 제외), scripts/build.py(버전 리소스, 7-Zip 동봉, zip),
      GitHub Actions(ci.yml: Windows+Ubuntu 테스트 / release.yml: 태그 → 테스트 → exe 빌드 → exe 실행 확인 → 릴리스),
      README/CHANGELOG/LICENSE, 업데이트 확인. 리눅스에서 실제 빌드 + 빌드된 실행 파일로 압축 4종 열기 확인
  - 자체 점검 중 수정: 좌우 클릭 0.5초 지연 제거, 큰 GIF 애니메이션 판별 시 전체 스캔 제거
  - 성능: 300프레임 GIF 열기 0.01초, 140MP JPEG 축소 디코딩 2.8초. 테스트 65개 통과

## 다음에 이어서 할 것
- 7단계: 사용자 PC(Desktop\Python\AI\Ellview)로 복사 후 해시 비교, GitHub 업로드 안내
