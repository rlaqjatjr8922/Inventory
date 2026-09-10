from pathlib import Path

from fastapi import (
    FastAPI,
    HTTPException
)

from fastapi.responses import (
    FileResponse
)

from fastapi.staticfiles import (
    StaticFiles
)

import database
import pricing_backend


BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
)


WAP_DIR = (
    BASE_DIR / "wap"
)

CSS_DIR = (
    WAP_DIR / "css"
)

JS_DIR = (
    WAP_DIR / "js"
)


app = FastAPI()


database.initialize()
pricing_backend.install(database)


app.mount(
    "/css",
    StaticFiles(
        directory=CSS_DIR
    ),
    name="css"
)


app.mount(
    "/js",
    StaticFiles(
        directory=JS_DIR
    ),
    name="js"
)


@app.get("/")
def main_page():

    return FileResponse(
        WAP_DIR / "main.htm"
    )


# =========================
# 부품
# =========================

@app.get("/api/parts")
def get_parts():

    return database.load_parts()


@app.put("/api/parts/{part_id}")
def update_part(
    part_id: int,
    data: dict
):

    try:

        return database.update_part(
            part_id,
            data
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


@app.delete("/api/parts/{part_id}")
def delete_part(
    part_id: int
):

    try:

        deleted = database.delete_part(
            part_id
        )

        return {
            "success": True,
            "deleted": deleted
        }

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


# =========================
# 거래
# =========================

@app.get("/api/transactions")
def get_transactions():

    return database.load_transactions()


@app.post("/api/transactions")
def add_transaction(
    data: dict
):

    try:

        transaction_type = data.get(
            "구분"
        )

        if transaction_type == 1:

            return database.add_purchase(
                data
            )

        if transaction_type == 2:

            return database.add_sale(
                data
            )

        raise ValueError(
            "구분은 매입 또는 판매여야 합니다."
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


@app.put("/api/transactions/{transaction_id}")
def update_transaction(
    transaction_id: int,
    data: dict
):

    try:

        return database.update_transaction(
            transaction_id,
            data
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


@app.delete("/api/transactions/{transaction_id}")
def delete_transaction(
    transaction_id: int
):

    try:

        deleted = database.delete_transaction(
            transaction_id
        )

        return {
            "success": True,
            "deleted": deleted
        }

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
