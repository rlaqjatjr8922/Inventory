import json
import hashlib
import os
import re
from functools import wraps

import gpt_api
import tempfile

from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MEMORIES_FILE = DATA_DIR / "memories.json"
CATEGORIES_FILE = DATA_DIR / "memory_categories.json"
MEMORY_UPLOAD_DIR = DATA_DIR / "memory_uploads"

DEFAULT_CATEGORIES = [
    "고객",
    "글카",
    "친구",
    "배송",
    "기타"
]

ALLOWED_STATUS = {
    "진행중",
    "완료",
    "보류",
    "폐기"
}


def now_text():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def initialize():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    if not CATEGORIES_FILE.exists():
        save_json(CATEGORIES_FILE, DEFAULT_CATEGORIES)

    migrate_legacy_memories()


def load_json(path, default):
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

    return data


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    handle, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=path.parent
    )

    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def shared_write(operation):
    @wraps(operation)
    def locked(*args, **kwargs):
        with gpt_api._WRITE_LOCK:
            return operation(*args, **kwargs)
    return locked


def _projects():
    gpt_api._ensure_directories()
    return {
        str(int(path.stem)): gpt_api._load(int(path.stem))
        for path in gpt_api.GPT_DIR.glob("*.json")
        if path.stem.isdigit()
    }


def _next_project_id():
    ids = [int(key) for key in _projects()]
    # Never reuse IDs of deleted projects that were migrated from the old store.
    ids.extend(int(value) for value in _migration_map().values())
    return max(ids, default=0) + 1


def _migration_map():
    path = DATA_DIR / "memory_project_ids.json"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as file:
        return json.load(file)


@shared_write
def migrate_legacy_memories():
    if not MEMORIES_FILE.exists():
        return
    # Read strictly: malformed legacy data must never be silently discarded.
    with MEMORIES_FILE.open(encoding="utf-8") as file:
        legacy = json.load(file)
    if not isinstance(legacy, dict):
        raise ValueError("기존 메모 파일 형식이 잘못되었습니다.")
    mapping = _migration_map()
    projects = _projects()
    for key, original in legacy.items():
        if key in mapping:
            continue
        # Recover after a crash between the project write and the mapping write.
        recovered = next((pid for pid, item in projects.items()
                          if item.get("_legacy_memory_key") == key), None)
        if recovered is not None:
            mapping[key] = int(recovered)
            save_json(DATA_DIR / "memory_project_ids.json", mapping)
            continue
        data = json.loads(json.dumps(original))
        replacements = {}
        for attachment in data.get("첨부파일", []):
            old_id = str(attachment["아이디"])
            source = (DATA_DIR / attachment["파일경로"]).resolve()
            if not source.is_relative_to(MEMORY_UPLOAD_DIR.resolve()):
                raise ValueError("기존 메모 이미지 경로가 잘못되었습니다.")
            new_id, destination = gpt_api._save_image_bytes(
                source.read_bytes(), source.suffix.lower())
            replacements[old_id] = new_id
            attachment["아이디"] = new_id
            attachment["파일경로"] = "images/" + destination.name
        def rewrite(value):
            if isinstance(value, str):
                return re.sub(r"\[\[이미지:(\d+)\]\]",
                              lambda m: "[[이미지:" + str(replacements.get(m[1], m[1])) + "]]", value)
            if isinstance(value, list):
                return [rewrite(item) for item in value]
            if isinstance(value, dict):
                return {name: rewrite(item) for name, item in value.items()}
            return value
        data = rewrite(data)
        data["_legacy_memory_key"] = key
        project_id = _next_project_id()
        gpt_api._save(project_id, data)
        projects[str(project_id)] = data
        mapping[key] = project_id
        save_json(DATA_DIR / "memory_project_ids.json", mapping)
    # Original JSON and image files remain untouched as a migration backup.


def load_memories():
    with gpt_api._WRITE_LOCK:
        migrate_legacy_memories()
        return _projects()


def _resolve_key(memory_key):
    key = str(memory_key)
    if key.isdigit():
        return str(int(key))
    migrate_legacy_memories()
    mapped = _migration_map().get(key)
    if mapped is None:
        raise ValueError("메모를 찾을 수 없습니다.")
    return str(mapped)


def load_categories():
    categories = load_json(CATEGORIES_FILE, DEFAULT_CATEGORIES)

    if not isinstance(categories, list):
        return list(DEFAULT_CATEGORIES)

    result = []
    for value in categories:
        name = str(value).strip()
        if name and name not in result:
            result.append(name)

    for memory in load_memories().values():
        category = str(memory.get("상위태그", "")).strip()
        if category and category not in result:
            result.append(category)
    return result or list(DEFAULT_CATEGORIES)


def add_category(name):
    name = str(name or "").strip()

    if not name:
        raise ValueError("상위태그 이름을 입력해주세요.")

    if len(name) > 30:
        raise ValueError("상위태그는 30자 이하로 입력해주세요.")

    categories = load_categories()

    if name not in categories:
        categories.append(name)
        save_json(CATEGORIES_FILE, categories)

    return categories


def normalize_work_items(value):
    if value is None:
        return []

    if not isinstance(value, list):
        raise ValueError("작업내용 형식이 잘못되었습니다.")

    result = []

    for item in value:
        if not isinstance(item, dict):
            raise ValueError("작업내용 형식이 잘못되었습니다.")

        work_date = str(item.get("작업날짜", "")).strip()
        summary = str(item.get("요약", "")).strip()
        details = str(item.get("세부", "")).strip()

        if not any((summary, details)):
            continue

        if not work_date:
            raise ValueError("작업날짜를 입력해주세요.")

        result.append({
            "작업날짜": work_date,
            "요약": summary,
            "세부": details
        })

    return result


def normalize_memory(data, existing=None):
    if not isinstance(data, dict):
        raise ValueError("메모 형식이 잘못되었습니다.")

    title = str(data.get("제목", "")).strip()
    category = str(data.get("상위태그", "")).strip()
    status = str(data.get("상태", "진행중")).strip()

    if not title:
        raise ValueError("제목을 입력해주세요.")

    if not category:
        raise ValueError("상위태그를 선택해주세요.")

    if category not in load_categories():
        raise ValueError("등록되지 않은 상위태그입니다.")

    try:
        priority = int(data.get("우선도", 2))
    except (TypeError, ValueError):
        raise ValueError("우선도가 잘못되었습니다.")

    if priority not in range(1, 6):
        raise ValueError("우선도는 1부터 5까지 선택해주세요.")

    if status not in ALLOWED_STATUS:
        raise ValueError("상태가 잘못되었습니다.")

    existing = existing if isinstance(existing, dict) else {}
    created_at = existing.get("생성일시") or now_text()
    attachments = existing.get("첨부파일", [])

    return {
        **existing,
        "상위태그": category,
        "제목": title,
        "생성일시": created_at,
        "수정일시": now_text(),
        "우선도": priority,
        "상태": status,
        "작업내용": normalize_work_items(data.get("작업내용", [])),
        "최종결론": str(data.get("최종결론", "")).strip(),
        "첨부파일": attachments if isinstance(attachments, list) else []
    }


def serialize(memory_key, memory):
    attachments = list(memory.get("첨부파일", []))
    attached_ids = {int(item["아이디"]) for item in attachments}
    for value in re.findall(r"\[\[이미지:(\d+)\]\]", json.dumps(memory, ensure_ascii=False)):
        image_id = int(value)
        if image_id in attached_ids:
            continue
        try:
            path = gpt_api.get_image_path(image_id)
        except gpt_api.GPTAPIError:
            continue
        attachments.append({"아이디": image_id, "원본파일명": path.name,
                            "설명": "본문에서 참조한 이미지", "참조전용": True})
        attached_ids.add(image_id)
    return {
        "메모키": memory_key,
        **memory,
        "첨부파일": attachments,
        "버전": _version(memory),
    }


def _version(memory):
    content = {key: value for key, value in memory.items()
               if key not in {"수정일시", "첨부파일"}}
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


@shared_write
def create_memory(data):
    migrate_legacy_memories()
    normalized = normalize_memory(data)
    project_id = _next_project_id()
    gpt_api._save(project_id, normalized)
    return serialize(str(project_id), normalized)


def get_memory(memory_key):
    key = _resolve_key(memory_key)
    memory = load_memories().get(key)
    if memory is None:
        raise ValueError("메모를 찾을 수 없습니다.")
    return serialize(key, memory)


@shared_write
def update_memory(memory_key, data):
    key = _resolve_key(memory_key)
    existing = load_memories().get(key)
    if existing is None:
        raise ValueError("메모를 찾을 수 없습니다.")
    if data.get("버전") and data["버전"] != _version(existing):
        raise ValueError("플러그인 또는 다른 화면에서 메모가 변경되었습니다. 입력한 내용을 복사한 뒤 메모를 다시 열어주세요.")
    normalized = normalize_memory(data, existing)
    gpt_api._save(int(key), normalized)
    return serialize(key, normalized)


@shared_write
def update_memory_fields(memory_key, data):
    """Save only the five editor fields; never replace work or attachments."""
    existing = get_memory(memory_key)
    fields = ("상위태그", "제목", "우선도", "상태", "최종결론")
    changes = {key: data[key] for key in fields if key in data}
    return update_memory(memory_key, {**existing, **changes, "버전": data.get("버전")})


@shared_write
def change_work(memory_key, work_index, data, delete=False):
    existing = get_memory(memory_key)
    # Index addressing is safe only against the exact saved revision.
    if not data.get("버전") or data["버전"] != existing["버전"]:
        raise ValueError("다른 화면에서 메모가 변경되었습니다. 메모를 다시 열어주세요.")
    works = list(existing.get("작업내용", []))
    if work_index < 0 or work_index >= len(works):
        raise ValueError("작업내용을 찾을 수 없습니다.")
    if delete:
        del works[work_index]
    else:
        normalized = normalize_work_items([data])
        if not normalized:
            raise ValueError("요약 또는 상세 작업내용을 입력해주세요.")
        datetime.strptime(normalized[0]["작업날짜"], "%Y-%m-%d")
        works[work_index] = normalized[0]
    return update_memory(memory_key, {**existing, "작업내용": works})


@shared_write
def delete_memory(memory_key):
    key = _resolve_key(memory_key)
    memory = load_memories().get(key)
    if memory is None:
        raise ValueError("메모를 찾을 수 없습니다.")
    gpt_api._path(int(key)).unlink()
    # Images have global IDs and may be referenced by other projects.
    return memory


def searchable_text(memory):
    values = [
        memory.get("상위태그", ""),
        memory.get("제목", ""),
        memory.get("상태", ""),
        memory.get("최종결론", "")
    ]

    for item in memory.get("작업내용", []):
        if isinstance(item, dict):
            values.extend([
                item.get("작업날짜", ""),
                item.get("요약", ""),
                item.get("세부", "")
            ])

    for attachment in memory.get("첨부파일", []):
        if isinstance(attachment, dict):
            values.extend([
                attachment.get("원본파일명", ""),
                attachment.get("설명", "")
            ])

    return " ".join(str(value) for value in values).casefold()


def search_memories(query="", category="", status="", minimum_priority=0, limit=100):
    query = str(query or "").strip().casefold()
    terms = [term for term in query.split() if term]
    category = str(category or "").strip()
    status = str(status or "").strip()

    try:
        minimum_priority = int(minimum_priority or 0)
        limit = min(max(int(limit or 100), 1), 200)
    except (TypeError, ValueError):
        raise ValueError("검색 조건이 잘못되었습니다.")

    results = []

    for memory_key, memory in load_memories().items():
        if category and memory.get("상위태그") != category:
            continue

        if status and memory.get("상태") != status:
            continue

        if int(memory.get("우선도", 0) or 0) < minimum_priority:
            continue

        text = searchable_text(memory)
        if terms and not all(term in text for term in terms):
            continue

        results.append(serialize(memory_key, memory))

    results.sort(
        key=lambda item: (
            int(item.get("우선도", 0) or 0),
            item.get("수정일시", "")
        ),
        reverse=True
    )

    return results[:limit]


@shared_write
def add_attachment(memory_key, file_data, content_type, extension, original_name, description):
    key = _resolve_key(memory_key)
    memory = load_memories().get(key)
    if memory is None:
        raise ValueError("메모를 찾을 수 없습니다.")
    try:
        image_id, path = gpt_api._save_image_bytes(file_data, extension)
    except gpt_api.GPTAPIError as error:
        raise ValueError(error.detail) from error
    attachment = {
        "아이디": image_id,
        "종류": "이미지",
        "파일경로": "images/" + path.name,
        "원본파일명": str(original_name or path.name).strip()[:255],
        "설명": str(description or "").strip()[:500],
        "콘텐츠형식": content_type,
    }
    memory.setdefault("첨부파일", []).append(attachment)
    memory["수정일시"] = now_text()
    gpt_api._save(int(key), memory)
    return attachment


def get_attachment_path(memory_key, attachment_id):
    memory = get_memory(memory_key)
    attachment = next((item for item in memory.get("첨부파일", [])
                       if int(item.get("아이디", 0)) == int(attachment_id)), None)
    referenced = re.search(r"\[\[이미지:" + re.escape(str(attachment_id)) + r"\]\]",
                           json.dumps(memory, ensure_ascii=False))
    if attachment is None and not referenced:
        raise ValueError("첨부파일을 찾을 수 없습니다.")
    try:
        path = gpt_api.get_image_path(int(attachment_id))
    except gpt_api.GPTAPIError as error:
        raise ValueError(error.detail) from error
    return path, attachment or {
        "아이디": int(attachment_id),
        "콘텐츠형식": gpt_api.IMAGE_TYPES[path.suffix.lower()],
    }


@shared_write
def delete_attachment(memory_key, attachment_id):
    key = _resolve_key(memory_key)
    memory = load_memories().get(key)
    if memory is None:
        raise ValueError("메모를 찾을 수 없습니다.")
    attachments = memory.get("첨부파일", [])
    target = next((item for item in attachments
                   if int(item.get("아이디", 0)) == int(attachment_id)), None)
    if target is None:
        raise ValueError("첨부파일을 찾을 수 없습니다.")
    memory["첨부파일"] = [item for item in attachments if item is not target]
    memory["수정일시"] = now_text()
    gpt_api._save(int(key), memory)
    return target
