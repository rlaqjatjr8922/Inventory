# 심심PC 재고 관리 / 고객 판매 페이지

관리자는 기존 FastAPI 앱을 로컬에서 실행합니다. `app.py`의 uvicorn host는
`127.0.0.1`을 그대로 유지합니다.

고객 사이트: https://rlaqjatjr8922.github.io/Inventory/

관리자 화면의 **메모리** 메뉴에서 작업 기록을 저장하고 검색할 수 있습니다.
새 메모는 상위태그·제목·우선도·상태만 입력합니다. 기존 메모는 **메모 보기**에서
기본 정보와 최종결론을 하단 저장 버튼으로 저장하고, 입력 취소로 최근 저장값을 복원합니다.
날짜·요약으로 표시되는 작업 상자를 누르면 **세부내용 보기**가 열리며, 각 작업의
수정·저장·삭제는 메모 기본 정보 저장과 독립적으로 처리합니다. 작업을 저장해도
상단에 입력 중인 기본 정보 초안은 유지됩니다. 전체 메모 삭제에는 확인 절차가 있습니다.

검색 영역의 ON/OFF 토글은 ON=작업검색, OFF=이미지검색입니다.
이미지검색에서 image_id를 입력하고 Enter를 누르면 이미지와 저장된 모든 포인트를 표시합니다.
두 검색 모드 아래에 GPT가 마지막으로 호출한 이미지를 자동 표시합니다.
MCP/HTTP get_image·take_photo가 이미지를 성공적으로 반환할 때 최근 호출 ID가 저장되며,
메모리 탭이 보이는 동안 3초마다 확인합니다. 같은 이미지 재호출도 갱신됩니다.
관리자 이미지검색·작업 이미지 표시는 최근 GPT 호출 기록을 변경하지 않습니다.
최근 호출 ID는 SQLite의 image_tool_state에 보관되어 서버 재시작 후에도 유지됩니다.

상세 작업내용의 `{12:1}`, `{12:[1,2,3]}`는 해당 위치에 이미지 한 장과 지정한 포인트를
표시합니다. 서로 다른 이미지나 같은 이미지의 반복 참조도 본문 순서를 유지합니다.
기존 `[[이미지:12]]` 참조는 포인트 없는 이미지로 표시됩니다. 포인트를 클릭하면 주석을
확인할 수 있으며, 없는 이미지·포인트는 나머지 본문 표시를 방해하지 않습니다.
정규화 좌표에 맞춘 브라우저 오버레이이므로 화면 크기가 바뀌어도 위치가 유지되며
원본 이미지 파일에 점·숫자·글씨를 합성하지 않습니다.

관리자 API는 기본 정보 저장에 `PATCH /api/memories/{key}`, 개별 작업 저장/삭제에
`PUT`/`DELETE /api/memories/{key}/works/{index}`를 사용합니다. 작업 요청은 저장 버전을
검증하므로 오래된 목록의 번호로 다른 작업을 덮어쓰거나 삭제하지 않습니다.
이미지와 포인트는 관리자 인증이 적용되는 `GET /api/images/{image_id}`로 조회합니다.

검증: `python -m unittest discover -s tests -q` 및 `node tests/memory_ui.cjs`.
브라우저 테스트에는 Playwright와 Edge가 필요하며 테스트용 응답만 사용합니다.
다른 설치된 브라우저는 `PLAYWRIGHT_CHANNEL`로 선택할 수 있습니다.

메모 원본은 플러그인과 동일한 `data/gpt/{프로젝트ID}.json`, 상위태그는
`data/memory_categories.json`, 첨부 이미지는 공통 번호를 사용하는
`data/images/`에 저장됩니다. 사이트에서 만든 메모는 플러그인 검색에 나타나고,
플러그인의 작업 기록·수정은 사이트에서 다시 조회하면 표시됩니다.
모두 `.gitignore`의 `data/`
범위에 포함되므로 GitHub Pages나 공개 저장소에는 게시되지 않습니다.

기존 `data/memories.json`이 있으면 서버 시작 시 프로젝트 형식으로 한 번 옮기고,
메모별 이미지 번호와 본문의 참조도 공통 이미지 번호로 변환합니다.
원래 JSON과 `data/memory_uploads/` 파일은 백업으로 유지하며,
`data/memory_project_ids.json`에 이전 메모키와 프로젝트 ID 대응을 기록합니다.
메모·첨부 삭제 시 다른 프로젝트와 플러그인에서 참조할 수 있는 이미지 원본은 유지합니다.
편집 중 플러그인에서 내용이 바뀌면 사이트 저장을 거부해 새 기록이 지워지는 것을 방지합니다.

관리자 서버용 패키지를 처음 설치할 때는 다음 명령을 실행합니다.

```powershell
python -m pip install -r requirements.txt
```

## ChatGPT Inventory MCP

서버 PC에서 FastAPI를 실행하면 ChatGPT용 Streamable HTTP MCP가 `/mcp/`에
함께 열립니다. ChatGPT 플러그인에는 서버의 HTTPS 주소 뒤에 `/mcp/`를 붙여
연결합니다. OpenAPI 방식이 필요한 경우에는 `/gpt/openapi.json`을 가져오면 됩니다.
두 연결 방식 모두 외부에 공개하는 도구는 정확히 다음 8개입니다.

| 도구 | REST 경로 | 용도 |
| --- | --- | --- |
| `search_projects` | `GET /gpt/search` | `category`, `time`, `title`, `status`로 검색 |
| `get_project` | `GET /gpt/{id}` | 기본 일반보기, 꼭 필요할 때만 `detail=true` |
| `add_work` | `POST /gpt/{id}/work` | 오늘의 상세 작업 기록 저장 |
| `update_project` | `PATCH /gpt/{id}` | 제목·상태·우선도·최종결론·상위태그 수정 |
| `get_image` | `GET /gpt/image/{id}` | 이미지 자체, image ID, points 반환 |
| `take_photo` | `GET /gpt/camera` | 노트북 카메라 촬영 요청 후 이미지와 새 ID 반환 |
| `add_point` | `POST /gpt/image/{image_id}/points` | x, y, annotation 저장, 이미지별 point_id 자동 발급 |
| `update_point` | `PATCH /gpt/image/{image_id}/points/{point_id}` | 지정한 x, y, annotation만 수정 |

MCP 연결에서는 `get_image`와 `take_photo`가 `image_id` 텍스트와 네이티브
`type=image` 콘텐츠를 함께 반환합니다. HTTP 응답에는 `image_id`, `content`,
`content_items`가 포함되며 이미지 블록은 실제 형식에 맞는 `image/jpeg` 또는
`image/png` MIME 타입과 접두사 없는 순수 base64 데이터를 사용합니다.
두 도구는 공통 이미지 함수를 사용하고, 원본 파일은 유지한 채 응답 이미지의 긴 변을
최대 1600픽셀로 제한합니다. JPEG 품질은 85입니다.
이미지 ID는 대화에서 계속 `[[이미지:ID]]`로 참조할 수 있습니다.

### 이미지 단일 전달과 좌표 주석

기존 중복 원인은 네이티브 MCP 이미지 반환과 사진 위젯의 재업로드/자동 첨부가
동시에 실행된 것입니다. 이제 `get_image`와 `take_photo`는 네이티브 이미지 블록을
정확히 하나만 반환합니다. 이미지 데이터를 `_meta`에 복사하지 않으며, 도구의 사진
위젯 연결 및 위젯의 업로드/후속 메시지 기능을 제거했습니다. 별도 URL이나 파일 첨부로
같은 이미지를 재전송하지 않습니다. image_id와 points는 텍스트 및 구조화 메타데이터로 전달합니다.
HTTP 응답도 `content_items` 안에 이미지 블록 하나만 포함하고 `points`를 함께 반환합니다.

`points`는 `{image_id, point_id, x, y, annotation}` 목록이며 저장된 점이 없으면 `[]`입니다.
좌표는 0~1 범위이며 (0,0)은 좌측 상단, (1,1)은 우측 하단입니다.
`add_point`의 point_id는 이미지별로 1부터 서버가 발급하며 동시 요청도 트랜잭션으로 처리합니다.
`update_point`는 x/y만 또는 annotation만 수정할 수 있고 생략한 값은 유지합니다.
빈 annotation은 주석을 비우며, 수정할 값이 없는 요청은 거부합니다.
좌표·주석은 `data/inventory.sqlite3`의 단일 `image_points` 테이블에 저장됩니다.
DB와 테이블은 최초 사용 시 자동 생성되며 기존 원본 이미지에는 점이나 글씨를 합성하지 않습니다.

서버 재시작 후 연결된 클라이언트의 도구 목록을 새로 고침해야 새 도구가 표시됩니다.
네이티브 MCP 시각 입력을 지원하는 클라이언트가 필요합니다. 과거 일부 연결 경로에서
네이티브 이미지 인식 실패가 기록되어 있으므로 실제 사용하는 ChatGPT 연결에서도
저장 이미지 조회와 카메라 촬영 후 이미지 인식을 확인해야 합니다.

프로젝트는 `data/gpt/{프로젝트ID}.json`, GPT 이미지 원본은
`data/images/{이미지ID}.{확장자}`에 저장됩니다. 최근 이미지 조회 도구와
`GET /gpt/` 엔드포인트는 만들지 않습니다.

`add_work`는 같은 날짜에 기록이 없을 때만 바로 저장합니다. 이미 오늘 기록이 있으면
서버가 기존기록과 새기록을 반환하며 파일은 바꾸지 않습니다. GPT가 둘을 빠짐없이
합친 최종본을 만들어 `overwrite=true`로 다시 호출했을 때만 그 날짜 기록 전체를
교체합니다. 이미지 참조는 `[[이미지:ID]]` 형식을 사용합니다.

### 다른 PC의 서버와 노트북 카메라 연결

촬영 흐름은 `GPT → 서버 PC → 노트북 카메라 → 서버 PC → GPT`입니다. 서버 PC와
노트북에 동일한 임의의 긴 토큰을 설정해야 합니다. 서버 PC에서 FastAPI를 실행하는
PowerShell 창에 먼저 설정합니다.

```powershell
$env:CAMERA_AGENT_TOKEN = "직접-만든-긴-임의-문자열"
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

카메라 또는 USB 현미경이 연결된 노트북에서는 저장소를 받은 뒤 다음처럼 실행합니다.
`--server`에는 ChatGPT에서도 접근할 서버 PC의 HTTPS/Cloudflare Tunnel 주소를 넣습니다.

```powershell
python -m pip install -r requirements-camera-agent.txt
$env:CAMERA_AGENT_TOKEN = "서버-PC와-같은-문자열"
python camera_agent.py --server https://서버주소 --camera 0
```

내장 카메라가 0번이고 USB 현미경이 1번이면 `--camera 1`로 바꿉니다. 에이전트는
평소에는 촬영하지 않고 요청을 기다리며, `take_photo`가 호출됐을 때만 카메라를 열어
한 장을 촬영하고 서버에 업로드합니다. 기본 응답 제한은 45초이며 서버 PC에서
`CAMERA_REQUEST_TIMEOUT` 환경 변수로 5~120초 범위에서 변경할 수 있습니다.

GitHub Settings → Pages → Build and deployment에서
**Deploy from a branch**, **main**, **/docs**를 선택합니다.
고객 사이트는 GitHub가 정적 파일을 제공하므로 PC와 FastAPI가 꺼져 있어도 접속됩니다.
로컬 변경은 다음 게시 작업을 완료해야 반영됩니다.

## 기존 사용자: 최초 업데이트 전 반드시 백업

원본 `data/`와 Python 캐시는 공개 저장소에서 추적을 중단했습니다.
기존 체크아웃에서 pull하면 추적되던 원본 파일이 삭제될 수 있습니다.
**관리자 서버를 종료하고, data 폴더 전체를 저장소 밖에 복사한 뒤 pull하고 복원하세요.**
PowerShell에서 저장소 폴더를 연 후:

```powershell
$inventoryBackup = Join-Path (Split-Path -Parent (Get-Location).Path) ("Inventory-data-backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
Copy-Item -LiteralPath ./data -Destination $inventoryBackup -Recurse
git pull
New-Item -ItemType Directory -Path ./data -Force | Out-Null
Copy-Item -Path "$inventoryBackup/*" -Destination ./data -Recurse -Force
```

pull이 로컬 데이터 변경 충돌로 중단되면 백업을 확인하고 충돌부터 해결하세요.
reset --hard로 재고를 지우지 마세요. 복원 후 관리자 앱에서 재고를 확인합니다.
새로 복제한 저장소에는 실제 재고가 없습니다. 기존 PC의 data 백업을 복원하세요.

## 이후 재고 게시

관리자에서 재고 변경을 저장하고 저장소 폴더에서 실행합니다. Python 3.10 이상,
추가 패키지 설치 없이 실행됩니다.

```powershell
git pull
python publish_pages.py
git add docs
git commit -m "재고 업데이트"
git push
```

변환이 실패하면 commit/push하지 말고 오류를 해결하세요.
변경이 없으면 commit할 내용이 없다는 메시지가 나올 수 있습니다.

- 입력: 로컬 data/parts.json, data/uploads/
- 출력: docs/products.json, docs/uploads/, docs/.nojekyll
- 정상(고장여부 1)이면서 미판매이고 사진 파일이 있는 제품만 내보냅니다. 상태가 불명확하거나 사진이 없으면 제외합니다.
- 공개 JSON 필드는 이름 / 종류 / 목표판매가 / 이미지 / 재고번호뿐입니다.
- 매입가, 최저판매가, 수리비, 매입·판매그룹, 메모, 거래 원본은 내보내지 않습니다.
- 사진은 로컬 JPG/PNG/WEBP만 복사하며 공개 파일명은 해시로 바꿉니다.
  외부 주소와 localhost 이미지는 제외합니다. 사진 내용 자체에 내부 정보가 없도록 등록하세요.
- 게시할 때 이전 docs/uploads를 정리하여 판매·고장 제품의 사진도 제거합니다.
- 가격 미등록은 가격문의로 표시합니다. 사진 미등록·파일 누락·빈 사진 파일인 상품은 고객 목록에 표시하지 않습니다.
- 고객은 이름·종류·재고번호 검색, 종류 필터, 상품 상세, 당근 문의를 사용할 수 있습니다.
- 상세에는 중고·리퍼 안내와 1개월 환불 보증 안내가 있습니다.

## 기존 공개 이력 주의

data 원본은 이전 커밋에 이미 포함되어 있었습니다. 추적 중단과 .gitignore는
앞으로의 업로드를 막지만 **기존 Git 이력이나 이미 복사된 데이터까지 지우지는 않습니다.**
과거 노출까지 처리하려면 별도로 저장소 공개 범위와 Git 이력 정리를 검토해야 합니다.
이 변경은 기존 이력을 강제 재작성하지 않습니다.

## 검증

```powershell
python -m unittest discover -s tests -v
python -m http.server 8765 --bind 127.0.0.1 --directory docs
```

브라우저에서 http://127.0.0.1:8765/ 로 미리 볼 수 있습니다.
이 미리보기 서버는 기존 FastAPI 설정을 변경하지 않습니다.
