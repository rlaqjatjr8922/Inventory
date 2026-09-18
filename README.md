# 심심PC 재고 관리 / 고객 판매 페이지

관리자는 기존 FastAPI 앱을 로컬에서 실행합니다. `app.py`의 uvicorn host는
`127.0.0.1`을 그대로 유지합니다.

고객 사이트: https://rlaqjatjr8922.github.io/Inventory/

관리자 화면의 **메모리** 메뉴에서는 고객·글카·친구·배송·기타 상위태그로
작업 기록을 저장하고 검색할 수 있습니다. 상위태그는 직접 추가할 수 있으며,
날짜별 요약·세부내용·결과와 최종결론, 우선도, 상태를 기록합니다. 메모 이미지는
본문에서 `[[이미지:번호]]` 형식으로 참조합니다.

메모 원본은 `data/memories.json`, 상위태그는 `data/memory_categories.json`,
첨부 이미지는 `data/memory_uploads/`에 저장됩니다. 모두 `.gitignore`의 `data/`
범위에 포함되므로 GitHub Pages나 공개 저장소에는 게시되지 않습니다.

관리자 서버용 패키지를 처음 설치할 때는 다음 명령을 실행합니다.

```powershell
python -m pip install -r requirements.txt
```

## ChatGPT Inventory MCP

서버 PC에서 FastAPI를 실행하면 ChatGPT용 Streamable HTTP MCP가 `/mcp/`에
함께 열립니다. ChatGPT 플러그인에는 서버의 HTTPS 주소 뒤에 `/mcp/`를 붙여
연결합니다. OpenAPI 방식이 필요한 경우에는 `/gpt/openapi.json`을 가져오면 됩니다.
두 연결 방식 모두 외부에 공개하는 도구는 정확히 다음 6개입니다.

| 도구 | REST 경로 | 용도 |
| --- | --- | --- |
| `search_projects` | `GET /gpt/search` | `category`, `time`, `title`, `status`로 검색 |
| `get_project` | `GET /gpt/{id}` | 기본 일반보기, 꼭 필요할 때만 `detail=true` |
| `add_work` | `POST /gpt/{id}/work` | 오늘의 상세 작업 기록 저장 |
| `update_project` | `PATCH /gpt/{id}` | 제목·상태·우선도·최종결론·상위태그 수정 |
| `get_image` | `GET /gpt/image/{id}` | 이미지 자체와 image ID 반환 |
| `take_photo` | `GET /gpt/camera` | 노트북 카메라 촬영 요청 후 이미지와 새 ID 반환 |

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
