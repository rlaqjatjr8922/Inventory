import json

from datetime import date
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"

PARTS_FILE = DATA_DIR / "parts.json"

TRANSACTIONS_FILE = DATA_DIR / "transactions.json"


def initialize():

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    if not PARTS_FILE.exists():

        save_json(
            PARTS_FILE,
            []
        )

    if not TRANSACTIONS_FILE.exists():

        save_json(
            TRANSACTIONS_FILE,
            []
        )


def load_json(path):

    try:

        with path.open(
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except (
        FileNotFoundError,
        json.JSONDecodeError
    ):

        return []


def save_json(path, data):

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )


def get_next_id(items):

    ids = []

    for item in items:

        try:

            ids.append(
                int(item["id"])
            )

        except (
            KeyError,
            TypeError,
            ValueError
        ):

            pass

    if not ids:
        return 1

    return max(ids) + 1


def load_parts():

    return load_json(
        PARTS_FILE
    )


def load_transactions():

    return load_json(
        TRANSACTIONS_FILE
    )


# =========================
# 매입
# =========================

def add_purchase(data):

    if data.get("구분") != 1:

        raise ValueError(
            "매입 거래가 아닙니다."
        )


    amount = data.get("금액")


    if not isinstance(amount, int):

        raise ValueError(
            "금액은 숫자여야 합니다."
        )


    if amount <= 0:

        raise ValueError(
            "금액은 0원보다 커야 합니다."
        )


    related_parts = data.get(
        "관련부품",
        []
    )


    if not isinstance(
        related_parts,
        list
    ):

        raise ValueError(
            "관련부품 형식이 잘못되었습니다."
        )


    parts = load_parts()

    transactions = (
        load_transactions()
    )


    transaction_id = (
        get_next_id(
            transactions
        )
    )


    transaction_group = (
        f"b{transaction_id}"
    )


    next_part_id = (
        get_next_id(parts)
    )


    created_ids = []


    for input_part in related_parts:

        if not isinstance(
            input_part,
            dict
        ):

            raise ValueError(
                "부품 형식이 잘못되었습니다."
            )


        name = str(
            input_part.get(
                "이름",
                ""
            )
        ).strip()


        if not name:

            raise ValueError(
                "부품 이름이 없습니다."
            )


        part_type = input_part.get(
            "종류"
        )


        status = input_part.get(
            "고장여부"
        )


        if part_type not in range(
            1,
            12
        ):

            raise ValueError(
                "부품 종류가 잘못되었습니다."
            )


        if status not in (
            1,
            2,
            3
        ):

            raise ValueError(
                "고장여부가 잘못되었습니다."
            )


        new_part = {
            "id": next_part_id,

            "매입그룹":
                transaction_group,

            "판매그룹":
                "",

            "종류":
                part_type,

            "고장여부":
                status,

            "이름":
                name
        }


        parts.append(
            new_part
        )


        created_ids.append(
            next_part_id
        )


        next_part_id += 1


    transaction = {
        "id":
            transaction_id,

        "구분":
            1,

        "거래그룹":
            transaction_group,

        "금액":
            amount,

        "날짜":
            date.today().isoformat(),

        "메모":
            str(
                data.get(
                    "메모",
                    ""
                )
            ),

        "관련부품":
            created_ids
    }


    transactions.append(
        transaction
    )


    save_json(
        PARTS_FILE,
        parts
    )


    save_json(
        TRANSACTIONS_FILE,
        transactions
    )


    return transaction


# =========================
# 판매
# =========================

def add_sale(data):

    amount = data.get("금액")


    if not isinstance(amount, int):

        raise ValueError(
            "금액은 숫자여야 합니다."
        )


    if amount <= 0:

        raise ValueError(
            "금액은 0원보다 커야 합니다."
        )


    selected_ids = data.get(
        "관련부품",
        []
    )


    if not isinstance(
        selected_ids,
        list
    ):

        raise ValueError(
            "관련부품 형식이 잘못되었습니다."
        )


    selected_ids = [
        int(part_id)
        for part_id
        in selected_ids
    ]


    if not selected_ids:

        raise ValueError(
            "판매할 부품이 없습니다."
        )


    parts = load_parts()

    transactions = (
        load_transactions()
    )


    transaction_id = (
        get_next_id(
            transactions
        )
    )


    transaction_group = (
        f"s{transaction_id}"
    )


    found_ids = []


    for part in parts:

        part_id = int(
            part["id"]
        )


        if part_id not in selected_ids:
            continue


        if part.get(
            "판매그룹"
        ):

            raise ValueError(
                f"{part_id}번 부품은 "
                "이미 판매되었습니다."
            )


        part["판매그룹"] = (
            transaction_group
        )


        found_ids.append(
            part_id
        )


    missing = (
        set(selected_ids)
        - set(found_ids)
    )


    if missing:

        raise ValueError(
            "존재하지 않는 부품 ID: "
            + ", ".join(
                str(item)
                for item
                in sorted(missing)
            )
        )


    transaction = {
        "id":
            transaction_id,

        "구분":
            2,

        "거래그룹":
            transaction_group,

        "금액":
            amount,

        "날짜":
            date.today().isoformat(),

        "메모":
            str(
                data.get(
                    "메모",
                    ""
                )
            ),

        "관련부품":
            selected_ids
    }


    transactions.append(
        transaction
    )


    save_json(
        PARTS_FILE,
        parts
    )


    save_json(
        TRANSACTIONS_FILE,
        transactions
    )


    return transaction


# =========================
# 부품 수정
# =========================

def update_part(
    part_id,
    data
):

    parts = load_parts()


    target = None


    for part in parts:

        if int(
            part["id"]
        ) == int(part_id):

            target = part

            break


    if target is None:

        raise ValueError(
            "부품을 찾을 수 없습니다."
        )


    name = str(
        data.get(
            "이름",
            ""
        )
    ).strip()


    if not name:

        raise ValueError(
            "부품 이름을 입력해주세요."
        )


    part_type = data.get(
        "종류"
    )


    status = data.get(
        "고장여부"
    )


    if part_type not in range(
        1,
        12
    ):

        raise ValueError(
            "부품 종류가 잘못되었습니다."
        )


    if status not in (
        1,
        2,
        3
    ):

        raise ValueError(
            "고장여부가 잘못되었습니다."
        )


    target["이름"] = name

    target["종류"] = (
        part_type
    )

    target["고장여부"] = (
        status
    )


    save_json(
        PARTS_FILE,
        parts
    )


    return target


# =========================
# 부품 삭제
# =========================

def delete_part(part_id):

    parts = load_parts()

    transactions = (
        load_transactions()
    )


    target = None


    for part in parts:

        if int(
            part["id"]
        ) == int(part_id):

            target = part

            break


    if target is None:

        raise ValueError(
            "부품을 찾을 수 없습니다."
        )


    parts = [
        part
        for part
        in parts
        if int(
            part["id"]
        ) != int(part_id)
    ]


    # 거래 관련부품에서도 제거
    for transaction in transactions:

        related = transaction.get(
            "관련부품",
            []
        )


        if not isinstance(
            related,
            list
        ):

            continue


        transaction["관련부품"] = [
            related_id
            for related_id
            in related
            if int(related_id)
            != int(part_id)
        ]


    save_json(
        PARTS_FILE,
        parts
    )


    save_json(
        TRANSACTIONS_FILE,
        transactions
    )


    return target