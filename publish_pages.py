from pathlib import Path
import json
import shutil

BASE_DIR = Path(__file__).resolve().parent
PARTS_FILE = BASE_DIR / "data" / "parts.json"
SOURCE_UPLOAD_DIR = BASE_DIR / "data" / "uploads"
DOCS_DIR = BASE_DIR / "docs"
DOCS_UPLOAD_DIR = DOCS_DIR / "uploads"
PUBLIC_DATA_FILE = DOCS_DIR / "products.json"


def load_parts():
    if not PARTS_FILE.exists():
        return []

    with PARTS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def safe_int(value, default=0):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def publish():
    parts = load_parts()

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    if DOCS_UPLOAD_DIR.exists():
        shutil.rmtree(DOCS_UPLOAD_DIR)

    DOCS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    public_parts = []

    for part in parts:
        if part.get("판매그룹"):
            continue

        if safe_int(part.get("고장여부"), 3) != 1:
            continue

        image = str(part.get("이미지", "") or "").strip()
        public_image = ""

        if image.startswith("/uploads/"):
            filename = Path(image.removeprefix("/uploads/")).name
            source = SOURCE_UPLOAD_DIR / filename

            if source.exists() and source.is_file():
                target = DOCS_UPLOAD_DIR / filename
                shutil.copy2(source, target)
                public_image = f"uploads/{filename}"
        elif image.startswith("http://") or image.startswith("https://"):
            public_image = image

        public_parts.append({
            "id": part.get("id"),
            "이름": part.get("이름", ""),
            "종류": part.get("종류"),
            "상태": "정상",
            "판매가": safe_int(part.get("목표판매가"), 0),
            "이미지": public_image
        })

    with PUBLIC_DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            public_parts,
            file,
            ensure_ascii=False,
            indent=2
        )
        file.write("\n")

    print(f"GitHub Pages 공개 재고 {len(public_parts)}개 생성 완료")
    print(f"파일: {PUBLIC_DATA_FILE}")
    print("이제 git add / commit / push 하면 고객 사이트에 반영됩니다.")


if __name__ == "__main__":
    publish()
