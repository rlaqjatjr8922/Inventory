import json
import os
import shutil
import tempfile
import uuid

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

    if not MEMORIES_FILE.exists():
        save_json(MEMORIES_FILE, {})

    if not CATEGORIES_FILE.exists():
        save_json(CATEGORIES_FILE, DEFAULT_CATEGORIES)


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


def load_memories():
    data = load_json(MEMORIES_FILE, {})
    return data if isinstance(data, dict) else {}


def load_categories():
    categories = load_json(CATEGORIES_FILE, DEFAULT_CATEGORIES)

    if not isinstance(categories, list):
        return list(DEFAULT_CATEGORIES)

    result = []
    for value in categories:
        name = str(value).strip()
        if name and name not in result:
            result.append(name)

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
        outcome = str(item.get("결과", "")).strip()

        if not any((summary, details, outcome)):
            continue

        if not work_date:
            raise ValueError("작업날짜를 입력해주세요.")

        result.append({
            "작업날짜": work_date,
            "요약": summary,
            "세부": details,
            "결과": outcome
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
    return {
        "메모키": memory_key,
        **memory
    }


def create_memory(data):
    memories = load_memories()
    memory_key = uuid.uuid4().hex
    memories[memory_key] = normalize_memory(data)
    save_json(MEMORIES_FILE, memories)
    return serialize(memory_key, memories[memory_key])


def get_memory(memory_key):
    memory = load_memories().get(memory_key)
    if memory is None:
        raise ValueError("메모를 찾을 수 없습니다.")
    return serialize(memory_key, memory)


def update_memory(memory_key, data):
    memories = load_memories()
    existing = memories.get(memory_key)

    if existing is None:
        raise ValueError("메모를 찾을 수 없습니다.")

    memories[memory_key] = normalize_memory(data, existing)
    save_json(MEMORIES_FILE, memories)
    return serialize(memory_key, memories[memory_key])


def delete_memory(memory_key):
    memories = load_memories()

    if memory_key not in memories:
        raise ValueError("메모를 찾을 수 없습니다.")

    deleted = memories.pop(memory_key)
    save_json(MEMORIES_FILE, memories)

    upload_directory = MEMORY_UPLOAD_DIR / memory_key
    if upload_directory.exists():
        shutil.rmtree(upload_directory)

    return deleted


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
                item.get("세부", ""),
                item.get("결과", "")
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


def add_attachment(memory_key, file_data, content_type, extension, original_name, description):
    memories = load_memories()
    memory = memories.get(memory_key)

    if memory is None:
        raise ValueError("메모를 찾을 수 없습니다.")

    attachments = memory.setdefault("첨부파일", [])
    existing_ids = [
        int(item.get("아이디", 0) or 0)
        for item in attachments
        if isinstance(item, dict)
    ]
    attachment_id = max(existing_ids, default=0) + 1

    upload_directory = MEMORY_UPLOAD_DIR / memory_key
    upload_directory.mkdir(parents=True, exist_ok=True)
    filename = f"{attachment_id}{extension}"
    file_path = upload_directory / filename
    file_path.write_bytes(file_data)

    attachment = {
        "아이디": attachment_id,
        "종류": "이미지",
        "파일경로": f"memory_uploads/{memory_key}/{filename}",
        "원본파일명": str(original_name or filename).strip()[:255],
        "설명": str(description or "").strip()[:500],
        "콘텐츠형식": content_type
    }

    attachments.append(attachment)
    memory["수정일시"] = now_text()
    save_json(MEMORIES_FILE, memories)
    return attachment


def get_attachment_path(memory_key, attachment_id):
    memory = load_memories().get(memory_key)

    if memory is None:
        raise ValueError("메모를 찾을 수 없습니다.")

    for attachment in memory.get("첨부파일", []):
        if int(attachment.get("아이디", 0)) == int(attachment_id):
            relative_path = Path(str(attachment.get("파일경로", "")))
            expected_prefix = Path("memory_uploads") / memory_key

            if relative_path.parent != expected_prefix:
                raise ValueError("첨부파일 경로가 잘못되었습니다.")

            path = DATA_DIR / relative_path
            if not path.is_file():
                raise ValueError("첨부파일을 찾을 수 없습니다.")

            return path, attachment

    raise ValueError("첨부파일을 찾을 수 없습니다.")


def delete_attachment(memory_key, attachment_id):
    memories = load_memories()
    memory = memories.get(memory_key)

    if memory is None:
        raise ValueError("메모를 찾을 수 없습니다.")

    attachments = memory.get("첨부파일", [])
    target = next(
        (
            item for item in attachments
            if int(item.get("아이디", 0)) == int(attachment_id)
        ),
        None
    )

    if target is None:
        raise ValueError("첨부파일을 찾을 수 없습니다.")

    try:
        path, _ = get_attachment_path(memory_key, attachment_id)
        path.unlink(missing_ok=True)
    except ValueError:
        pass

    memory["첨부파일"] = [item for item in attachments if item is not target]
    memory["수정일시"] = now_text()
    save_json(MEMORIES_FILE, memories)
    return target
