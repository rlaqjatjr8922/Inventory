from __future__ import annotations

import json
import hmac
import os
import re
import tempfile
import threading
import time
import uuid

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, Response
from PIL import UnidentifiedImageError
from image_content import image_response
from pydantic import BaseModel, ConfigDict, Field, model_validator


router = APIRouter(prefix="/gpt", tags=["gpt"])

BASE_DIR = Path(__file__).resolve().parent
GPT_DIR = BASE_DIR / "data" / "gpt"
IMAGE_DIR = BASE_DIR / "data" / "images"

IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
ALLOWED_STATUS = {"진행중", "완료", "보류", "폐기"}
TOOL_NAMES = {
    "search_projects",
    "get_project",
    "add_work",
    "update_project",
    "get_image",
    "take_photo",
}

_WRITE_LOCK = threading.RLock()
_CAMERA_LOCK = threading.RLock()


@dataclass
class CameraRequest:
    request_id: str
    created_at: float
    event: threading.Event = field(default_factory=threading.Event)
    claimed_at: float | None = None
    image_id: int | None = None
    image_path: Path | None = None
    error: str = ""


_CAMERA_REQUESTS: dict[str, CameraRequest] = {}


class GPTAPIError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class WorkPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(
        ...,
        description=(
            "요약하지 않은 상세 작업 기록. 증상, 측정 위치와 값, 테스트 방법과 장비, "
            "교체·탈거 부품, 과정, 전후 변화, 실패한 시도, 결과와 판단 근거를 "
            "현재 대화에서 확인된 범위 안에서 최대한 자세히 적습니다. "
            "이미지는 [[이미지:ID]] 형식으로 적습니다."
        ),
    )
    overwrite: bool = Field(
        False,
        description=(
            "같은 날짜의 기존 기록과 새 내용을 직접 합친 최종본을 다시 보낼 때만 true. "
            "true이면 그 날짜 기록을 이 요청 내용으로 교체합니다."
        ),
    )
    summary: str = Field("", description="날짜별 짧은 요약. 비우면 서버가 자동 생성합니다.")
    result: str = Field("", description="확인된 작업 결과. 확인되지 않은 내용은 쓰지 않습니다.")

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_names(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        result = dict(value)
        aliases = {
            "세부": "content",
            "내용": "content",
            "덮어쓰기": "overwrite",
            "요약": "summary",
            "결과": "result",
        }
        for old, new in aliases.items():
            if new not in result and old in result:
                result[new] = result.pop(old)
        return result


class ProjectUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str | None = Field(None, description="새 상위태그")
    title: str | None = Field(None, description="새 프로젝트 제목")
    priority: int | None = Field(None, ge=1, le=5, description="새 우선도(1~5)")
    status: str | None = Field(None, description="새 상태: 진행중, 완료, 보류, 폐기")
    final_conclusion: str | None = Field(None, description="새 최종결론")

    @model_validator(mode="before")
    @classmethod
    def accept_korean_names(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        result = dict(value)
        aliases = {
            "상위태그": "category",
            "제목": "title",
            "우선도": "priority",
            "상태": "status",
            "최종결론": "final_conclusion",
        }
        for old, new in aliases.items():
            if new not in result and old in result:
                result[new] = result.pop(old)
        return result

    def changes(self) -> dict[str, Any]:
        names = {
            "category": "상위태그",
            "title": "제목",
            "priority": "우선도",
            "status": "상태",
            "final_conclusion": "최종결론",
        }
        supplied = self.model_dump(exclude_unset=True)
        return {names[key]: value for key, value in supplied.items()}


def _ensure_directories() -> None:
    GPT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def _path(project_id: int) -> Path:
    return GPT_DIR / f"{project_id}.json"


def _load(project_id: int) -> dict[str, Any]:
    path = _path(project_id)
    if not path.is_file():
        raise GPTAPIError(404, "프로젝트를 찾을 수 없습니다.")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GPTAPIError(500, "프로젝트 JSON을 읽을 수 없습니다.") from error

    if not isinstance(data, dict):
        raise GPTAPIError(500, "프로젝트 JSON 형식이 잘못되었습니다.")
    return data


def _save(project_id: int, data: dict[str, Any]) -> None:
    _ensure_directories()
    destination = _path(project_id)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f"{project_id}.",
        suffix=".tmp",
        dir=GPT_DIR,
    )

    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now().astimezone().date().isoformat()


def _summary(text: str) -> str:
    clean = re.sub(r"\[\[이미지:\d+\]\]", "", text)
    clean = " ".join(clean.split())
    return clean[:120]


def _as_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None


def _matches_time(data: dict[str, Any], value: str, today: date) -> bool:
    value = value.strip().casefold()
    if not value or value in {"all", "전체"}:
        return True

    changed = _as_date(data.get("수정일시", data.get("생성일시", "")))
    if changed is None:
        return False

    if value in {"today", "오늘"}:
        return changed == today
    if value in {"week", "this_week", "이번주"}:
        return 0 <= (today - changed).days < 7
    if value in {"month", "this_month", "이번달"}:
        return (changed.year, changed.month) == (today.year, today.month)

    requested = _as_date(value)
    if requested is None:
        raise GPTAPIError(
            400,
            "time은 today/오늘, week/이번주, month/이번달 또는 YYYY-MM-DD만 사용할 수 있습니다.",
        )
    return changed == requested


def search_projects_data(
    category: str = "",
    time: str = "",
    title: str = "",
    status: str = "",
) -> dict[str, list[dict[str, Any]]]:
    _ensure_directories()
    today = datetime.now().astimezone().date()
    matches: list[tuple[str, dict[str, Any]]] = []

    for path in GPT_DIR.glob("*.json"):
        if not path.stem.isdigit():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue

        if category and str(data.get("상위태그", "")) != category:
            continue
        if title and title.casefold() not in str(data.get("제목", "")).casefold():
            continue
        if status and str(data.get("상태", "")) != status:
            continue
        if not _matches_time(data, time, today):
            continue

        matches.append((str(data.get("수정일시", data.get("생성일시", ""))), {
            "아이디": int(path.stem),
            "제목": str(data.get("제목", path.stem)),
        }))

    matches.sort(key=lambda item: (item[0], item[1]["아이디"]), reverse=True)
    return {"검색결과": [item for _, item in matches]}


def get_project_data(project_id: int, detail: bool = False) -> dict[str, Any]:
    data = _load(project_id)
    if detail:
        return {"아이디": project_id, **data}

    works: dict[str, str] = {}
    raw_works = data.get("작업내용", [])
    if isinstance(raw_works, list):
        for item in raw_works:
            if not isinstance(item, dict):
                continue
            work_date = str(item.get("작업날짜", "")).strip()
            if work_date:
                works[work_date] = str(item.get("요약", ""))

    return {
        "아이디": project_id,
        "제목": data.get("제목", ""),
        "작업내용": works,
    }


def add_work_data(
    project_id: int,
    content: str,
    overwrite: bool = False,
    summary: str = "",
    result: str = "",
) -> dict[str, Any]:
    content = str(content or "").strip()
    summary = str(summary or "").strip()
    result = str(result or "").strip()
    if not content:
        raise GPTAPIError(400, "작업내용이 비어 있습니다.")

    today = _today()
    new_record = {
        "작업날짜": today,
        "요약": summary or _summary(content),
        "세부": content,
        "결과": result,
    }

    with _WRITE_LOCK:
        data = _load(project_id)
        works = data.setdefault("작업내용", [])
        if not isinstance(works, list):
            raise GPTAPIError(500, "프로젝트 작업내용 형식이 잘못되었습니다.")

        target = next(
            (
                item
                for item in works
                if isinstance(item, dict) and str(item.get("작업날짜", "")) == today
            ),
            None,
        )

        if target is not None and not overwrite:
            return {
                "저장됨": False,
                "병합필요": True,
                "안내": (
                    "오늘 기록이 이미 있습니다. 기존기록과 새기록을 빠짐없이 합친 최종본을 "
                    "만든 뒤 overwrite=true로 add_work를 다시 호출하세요. "
                    "두 번째 호출의 내용이 오늘 기록 전체를 덮어씁니다."
                ),
                "기존기록": dict(target),
                "새기록": new_record,
            }

        action = "created"
        if target is None:
            works.append(new_record)
        else:
            target.clear()
            target.update(new_record)
            action = "overwritten"

        data["수정일시"] = _now()
        _save(project_id, data)

    return {
        "저장됨": True,
        "병합필요": False,
        "처리": action,
        "프로젝트아이디": project_id,
        "저장기록": new_record,
    }


def update_project_data(project_id: int, changes: dict[str, Any]) -> dict[str, Any]:
    if not changes:
        raise GPTAPIError(400, "수정할 항목이 없습니다.")

    allowed = {"상위태그", "제목", "우선도", "상태", "최종결론"}
    unknown = set(changes) - allowed
    if unknown:
        raise GPTAPIError(400, f"수정할 수 없는 항목입니다: {', '.join(sorted(unknown))}")

    normalized = dict(changes)
    for key in ("상위태그", "제목"):
        if key in normalized:
            normalized[key] = str(normalized[key] or "").strip()
            if not normalized[key]:
                raise GPTAPIError(400, f"{key}은(는) 비울 수 없습니다.")

    if "최종결론" in normalized:
        normalized["최종결론"] = str(normalized["최종결론"] or "").strip()

    if "우선도" in normalized:
        try:
            priority = int(normalized["우선도"])
        except (TypeError, ValueError) as error:
            raise GPTAPIError(400, "우선도는 1부터 5까지의 숫자여야 합니다.") from error
        if priority not in range(1, 6):
            raise GPTAPIError(400, "우선도는 1부터 5까지의 숫자여야 합니다.")
        normalized["우선도"] = priority

    if "상태" in normalized:
        normalized["상태"] = str(normalized["상태"] or "").strip()
        if normalized["상태"] not in ALLOWED_STATUS:
            raise GPTAPIError(400, "상태는 진행중, 완료, 보류, 폐기 중 하나여야 합니다.")

    with _WRITE_LOCK:
        data = _load(project_id)
        data.update(normalized)
        data["수정일시"] = _now()
        _save(project_id, data)

    return {
        "수정됨": True,
        "프로젝트아이디": project_id,
        "변경내용": normalized,
    }


def get_image_path(image_id: int) -> Path:
    _ensure_directories()
    for candidate in sorted(IMAGE_DIR.glob(f"{image_id}.*")):
        if (
            candidate.is_file()
            and candidate.stem == str(image_id)
            and candidate.suffix.lower() in IMAGE_TYPES
        ):
            return candidate
    raise GPTAPIError(404, "이미지를 찾을 수 없습니다.")


def _next_image_id() -> int:
    ids = [
        int(path.stem)
        for path in IMAGE_DIR.iterdir()
        if path.is_file() and path.stem.isdigit() and path.suffix.lower() in IMAGE_TYPES
    ]
    return max(ids, default=0) + 1


def _save_image_bytes(image_data: bytes, extension: str) -> tuple[int, Path]:
    if not image_data:
        raise GPTAPIError(400, "업로드된 이미지가 비어 있습니다.")
    if len(image_data) > 10 * 1024 * 1024:
        raise GPTAPIError(400, "이미지는 10MB 이하만 업로드할 수 있습니다.")
    if extension not in IMAGE_TYPES:
        raise GPTAPIError(400, "JPG, PNG, WEBP 이미지만 업로드할 수 있습니다.")

    with _WRITE_LOCK:
        _ensure_directories()
        image_id = _next_image_id()
        destination = IMAGE_DIR / f"{image_id}{extension}"
        handle, temporary_name = tempfile.mkstemp(
            prefix=f"{image_id}.",
            suffix=".tmp",
            dir=IMAGE_DIR,
        )
        try:
            with os.fdopen(handle, "wb") as file:
                file.write(image_data)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_name, destination)
        except Exception:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise
    return image_id, destination


def _camera_agent_token() -> str:
    return os.environ.get("CAMERA_AGENT_TOKEN", "").strip()


def _camera_timeout() -> float:
    try:
        timeout = float(os.environ.get("CAMERA_REQUEST_TIMEOUT", "45"))
    except ValueError as error:
        raise GPTAPIError(500, "CAMERA_REQUEST_TIMEOUT은 숫자여야 합니다.") from error
    return min(max(timeout, 5.0), 120.0)


def claim_camera_request() -> dict[str, str] | None:
    now = time.monotonic()
    retry_after = 15.0
    with _CAMERA_LOCK:
        pending = sorted(_CAMERA_REQUESTS.values(), key=lambda item: item.created_at)
        for camera_request in pending:
            if camera_request.event.is_set():
                continue
            if (
                camera_request.claimed_at is None
                or now - camera_request.claimed_at >= retry_after
            ):
                camera_request.claimed_at = now
                return {"request_id": camera_request.request_id}
    return None


def complete_camera_request(
    request_id: str,
    image_data: bytes,
    extension: str = ".jpg",
) -> tuple[int, Path]:
    with _CAMERA_LOCK:
        camera_request = _CAMERA_REQUESTS.get(request_id)
        if camera_request is None:
            raise GPTAPIError(404, "촬영 요청을 찾을 수 없거나 시간이 만료되었습니다.")
        if camera_request.event.is_set():
            raise GPTAPIError(409, "이미 처리된 촬영 요청입니다.")

        image_id, image_path = _save_image_bytes(image_data, extension)
        camera_request.image_id = image_id
        camera_request.image_path = image_path
        camera_request.event.set()
        return image_id, image_path


def fail_camera_request(request_id: str, message: str) -> None:
    with _CAMERA_LOCK:
        camera_request = _CAMERA_REQUESTS.get(request_id)
        if camera_request is None:
            raise GPTAPIError(404, "촬영 요청을 찾을 수 없거나 시간이 만료되었습니다.")
        if camera_request.event.is_set():
            raise GPTAPIError(409, "이미 처리된 촬영 요청입니다.")
        camera_request.error = str(message or "노트북 촬영에 실패했습니다.").strip()[:500]
        camera_request.event.set()


def take_photo_data() -> tuple[int, Path]:
    if not _camera_agent_token():
        raise GPTAPIError(
            503,
            "CAMERA_AGENT_TOKEN이 설정되지 않았습니다. 서버 PC와 노트북 카메라 에이전트에 같은 토큰을 설정하세요.",
        )

    timeout = _camera_timeout()
    camera_request = CameraRequest(
        request_id=uuid.uuid4().hex,
        created_at=time.monotonic(),
    )
    with _CAMERA_LOCK:
        _CAMERA_REQUESTS[camera_request.request_id] = camera_request

    completed = camera_request.event.wait(timeout)
    with _CAMERA_LOCK:
        completed = completed or camera_request.event.is_set()
        _CAMERA_REQUESTS.pop(camera_request.request_id, None)

    if not completed:
        raise GPTAPIError(
            504,
            "노트북 카메라 에이전트의 촬영 응답 시간이 초과되었습니다. camera_agent.py 실행 상태를 확인하세요.",
        )
    if camera_request.error:
        raise GPTAPIError(503, f"노트북 카메라 촬영 실패: {camera_request.error}")
    if camera_request.image_id is None or camera_request.image_path is None:
        raise GPTAPIError(500, "촬영 결과에 이미지 ID 또는 파일이 없습니다.")
    return camera_request.image_id, camera_request.image_path


def _image_response(image_id: int, path: Path) -> dict:
    try:
        return image_response(image_id, path)
    except (OSError, UnidentifiedImageError, ValueError) as error:
        raise GPTAPIError(422, "이미지 파일을 읽거나 변환할 수 없습니다.") from error


def _http_error(error: GPTAPIError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.detail)


def _authorize_camera_agent(request: Request) -> None:
    expected = _camera_agent_token()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="서버에 CAMERA_AGENT_TOKEN이 설정되지 않았습니다.",
        )

    authorization = request.headers.get("authorization", "")
    supplied = request.headers.get("x-camera-agent-token", "")
    if authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="카메라 에이전트 토큰이 올바르지 않습니다.")


@router.get(
    "/search",
    operation_id="search_projects",
    summary="프로젝트 검색",
    description="category, time, title, status 조건만 사용해 프로젝트를 검색합니다.",
)
def search_projects(
    category: str = "",
    time: str = "",
    title: str = "",
    status: str = "",
):
    try:
        return search_projects_data(category, time, title, status)
    except GPTAPIError as error:
        raise _http_error(error) from error


@router.get(
    "/image/{image_id}",
    operation_id="get_image",
    summary="저장된 이미지 가져오기",
    description="image_id와 실제 이미지 블록을 content_items로 함께 반환합니다.",
)
def get_image(image_id: int):
    try:
        path = get_image_path(image_id)
        return _image_response(image_id, path)
    except GPTAPIError as error:
        raise _http_error(error) from error


@router.get(
    "/camera",
    operation_id="take_photo",
    summary="카메라 또는 현미경으로 촬영",
    description="노트북 카메라로 촬영하고 새 image_id와 실제 이미지 블록을 content_items로 반환합니다.",
)
def take_photo():
    try:
        image_id, path = take_photo_data()
        return _image_response(image_id, path)
    except GPTAPIError as error:
        raise _http_error(error) from error


@router.get("/camera-agent/request", include_in_schema=False)
def camera_agent_request(request: Request):
    _authorize_camera_agent(request)
    pending = claim_camera_request()
    if pending is None:
        return Response(status_code=204)
    return pending


@router.post("/camera-agent/result/{request_id}", include_in_schema=False)
async def camera_agent_result(request_id: str, request: Request):
    _authorize_camera_agent(request)
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()

    try:
        if content_type == "application/json":
            payload = await request.json()
            if not isinstance(payload, dict) or not str(payload.get("error", "")).strip():
                raise GPTAPIError(400, "오류 결과에는 error 메시지가 필요합니다.")
            fail_camera_request(request_id, str(payload["error"]))
            return {"success": False, "request_id": request_id}

        extensions = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }
        extension = extensions.get(content_type)
        if extension is None:
            raise GPTAPIError(400, "JPG, PNG, WEBP 이미지 결과만 받을 수 있습니다.")
        image_id, _ = complete_camera_request(
            request_id,
            await request.body(),
            extension,
        )
        return {
            "success": True,
            "request_id": request_id,
            "image_id": image_id,
        }
    except GPTAPIError as error:
        raise _http_error(error) from error


@router.get("/openapi.json", include_in_schema=False)
def gpt_openapi(request: Request):
    routes = [
        route
        for route in router.routes
        if getattr(route, "operation_id", None) in TOOL_NAMES
    ]
    schema = get_openapi(
        title="Inventory GPT API",
        version="1.0.0",
        description="심심PC Inventory의 ChatGPT용 6개 도구입니다.",
        routes=routes,
    )
    schema["servers"] = [{"url": str(request.base_url).rstrip("/")}]
    return JSONResponse(schema)


@router.get(
    "/{project_id}",
    operation_id="get_project",
    summary="프로젝트 작업기록 확인",
    description=(
        "기본은 토큰을 적게 쓰는 일반보기입니다. detail=true는 사용자가 상세 내용을 요구하거나 "
        "실제 상세 기록이 꼭 필요한 경우에만 사용합니다."
    ),
)
def get_project(project_id: int, detail: bool = False):
    try:
        return get_project_data(project_id, detail)
    except GPTAPIError as error:
        raise _http_error(error) from error


@router.post(
    "/{project_id}/work",
    operation_id="add_work",
    summary="오늘 작업기록 저장",
    description=(
        "작업내용을 요약하지 말고 현재 대화에서 확인된 내용을 최대한 자세히 기록합니다. "
        "같은 날짜의 기록이 있으면 첫 호출은 저장하지 않고 기존값을 반환합니다. GPT가 기존값과 "
        "새 내용을 합친 최종본을 만든 뒤 overwrite=true로 다시 호출하면 그 날짜 값을 교체합니다."
    ),
)
def add_work(
    project_id: int,
    payload: Annotated[WorkPayload | str, Body(description="상세 작업 기록")],
):
    if isinstance(payload, str):
        values = WorkPayload(content=payload)
    else:
        values = payload
    try:
        return add_work_data(
            project_id,
            values.content,
            values.overwrite,
            values.summary,
            values.result,
        )
    except GPTAPIError as error:
        raise _http_error(error) from error


@router.patch(
    "/{project_id}",
    operation_id="update_project",
    summary="프로젝트 정보 수정",
    description="제목, 상태, 우선도, 최종결론, 상위태그 중 전달한 항목만 수정합니다.",
)
def update_project(project_id: int, payload: ProjectUpdatePayload):
    try:
        return update_project_data(project_id, payload.changes())
    except GPTAPIError as error:
        raise _http_error(error) from error


_ensure_directories()
