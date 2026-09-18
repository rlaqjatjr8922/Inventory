from pathlib import Path
from datetime import datetime
import json
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

router = APIRouter(prefix="/gpt", tags=["gpt"])

BASE_DIR = Path(__file__).resolve().parent
GPT_DIR = BASE_DIR / "data" / "gpt"
IMAGE_DIR = BASE_DIR / "data" / "images"
GPT_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def _path(project_id: int) -> Path:
    return GPT_DIR / f"{project_id}.json"


def _load(project_id: int) -> dict:
    path = _path(project_id)
    if not path.exists():
        raise HTTPException(404, "프로젝트를 찾을 수 없습니다.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(500, "프로젝트 JSON을 읽을 수 없습니다.")


def _save(project_id: int, data: dict):
    _path(project_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now().astimezone().date().isoformat()


def _summary(text: str) -> str:
    # TODO: 이 함수만 나중에 로컬 AI 호출로 교체.
    clean = re.sub(r"\[\[이미지:\d+\]\]", "", text)
    clean = " ".join(clean.split())
    return clean[:120]


@router.get("/search")
def search_projects(
    category: str = "",
    time: str = "",
    title: str = "",
    status: str = "",
):
    result = {}
    today = datetime.now().astimezone().date()

    for path in GPT_DIR.glob("*.json"):
        if not path.stem.isdigit():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        if category and str(data.get("상위태그", "")) != category:
            continue
        if title and title.lower() not in str(data.get("제목", "")).lower():
            continue
        if status and str(data.get("상태", "")) != status:
            continue

        if time:
            raw = str(data.get("수정일시", data.get("생성일시", "")))
            try:
                d = datetime.fromisoformat(raw).date()
            except Exception:
                continue
            if time in ("today", "오늘") and d != today:
                continue
            if time in ("week", "이번주") and (today - d).days not in range(0, 7):
                continue
            if time in ("month", "이번달") and (d.year, d.month) != (today.year, today.month):
                continue

        result[str(data.get("제목", path.stem))] = int(path.stem)

    return result


@router.get("/image/{image_id}")
def get_image(image_id: int):
    matches = [
        p for p in IMAGE_DIR.glob(f"{image_id}.*")
        if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]
    if not matches:
        raise HTTPException(404, "이미지를 찾을 수 없습니다.")
    return FileResponse(matches[0])


@router.get("/{project_id}")
def get_project(project_id: int):
    data = _load(project_id)
    works = {}
    for item in data.get("작업내용", []):
        date = str(item.get("작업날짜", ""))
        summary = str(item.get("요약", ""))
        if date:
            works[date] = summary
    return {
        "제목": data.get("제목", ""),
        "작업내용": works,
    }


@router.post("/{project_id}/work")
async def add_work(project_id: int, request: Request):
    data = _load(project_id)

    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        body = await request.json()
        detail = str(body.get("세부", body.get("내용", ""))).strip()
    else:
        detail = (await request.body()).decode("utf-8").strip()

    if not detail:
        raise HTTPException(400, "작업내용이 비어 있습니다.")

    today = _today()
    works = data.setdefault("작업내용", [])
    target = next((x for x in works if x.get("작업날짜") == today), None)

    if target is None:
        target = {"작업날짜": today, "요약": "", "세부": detail}
        works.append(target)
    else:
        old = str(target.get("세부", "")).strip()
        target["세부"] = f"{old}\n{detail}".strip()

    target["요약"] = _summary(target["세부"])
    data["수정일시"] = _now()
    _save(project_id, data)
    return {"success": True}


@router.patch("/{project_id}")
async def update_project(project_id: int, request: Request):
    data = _load(project_id)
    changes = await request.json()

    allowed = {"상위태그", "제목", "우선도", "상태", "최종결론"}
    for key, value in changes.items():
        if key in allowed:
            data[key] = value

    data["수정일시"] = _now()
    _save(project_id, data)
    return {"success": True}
