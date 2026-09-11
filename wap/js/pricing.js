const PRICE_FIELD_DEFS = [
    {
        key: "목표판매가",
        editId: "edit-target-price",
        label: "목표판매가"
    },
    {
        key: "최저판매가",
        editId: "edit-minimum-price",
        label: "최저판매가"
    },
    {
        key: "수리비",
        editId: "edit-repair-cost",
        label: "수리비"
    }
];


function pricingMoney(value) {

    return (
        Number(value || 0)
            .toLocaleString("ko-KR")
        + "원"
    );

}


function safePrice(value) {

    return Math.max(
        0,
        Math.floor(
            Number(value) || 0
        )
    );

}


/* =========================================================
   부품 수정 화면 가격 입력
========================================================= */

function addPricingFieldsToEditPage() {

    const statusGroup =
        document
            .getElementById(
                "edit-part-status"
            )
            ?.closest(
                ".form-group"
            );


    if (!statusGroup) {
        return;
    }


    let anchor = statusGroup;


    for (const def of PRICE_FIELD_DEFS) {

        if (
            document.getElementById(
                def.editId
            )
        ) {
            continue;
        }


        const group =
            document.createElement(
                "div"
            );

        group.className =
            "form-group";

        group.innerHTML = `
            <label for="${def.editId}">
                ${def.label}
            </label>

            <input
                id="${def.editId}"
                type="number"
                min="0"
                step="1"
                value="0"
            >
        `;


        anchor.after(
            group
        );

        anchor = group;

    }

}


/* =========================================================
   재고 표 가격 표시
========================================================= */

function addPricingColumnsToTable() {

    const headerRow =
        document.querySelector(
            "#parts-result-table thead tr"
        );


    if (
        !headerRow
        || headerRow.dataset.pricingReady === "1"
    ) {
        return;
    }


    const buyGroupHeader =
        headerRow.children[4];


    for (const def of PRICE_FIELD_DEFS) {

        const th =
            document.createElement(
                "th"
            );

        th.textContent =
            def.label;

        headerRow.insertBefore(
            th,
            buyGroupHeader
        );

    }


    headerRow.dataset.pricingReady =
        "1";

}


function addPricingCellsToRenderedRows() {

    document
        .querySelectorAll(
            "#parts-table tr"
        )
        .forEach(
            row => {

                if (
                    row.dataset.pricingReady
                    === "1"
                ) {
                    return;
                }


                const id =
                    Number(
                        row.children[0]
                            ?.textContent
                            ?.trim()
                    );


                const part =
                    cachedParts.find(
                        item =>
                            Number(item.id)
                            === id
                    );


                if (!part) {
                    return;
                }


                const buyGroupCell =
                    row.children[4];


                for (const def of PRICE_FIELD_DEFS) {

                    const td =
                        document.createElement(
                            "td"
                        );

                    td.textContent =
                        pricingMoney(
                            part[def.key]
                        );

                    row.insertBefore(
                        td,
                        buyGroupCell
                    );

                }


                row.dataset.pricingReady =
                    "1";

            }
        );

}


/* =========================================================
   부품 수정 가격 불러오기 / 저장
========================================================= */

function fillPartEditPrices(partId) {

    const part =
        cachedParts.find(
            item =>
                Number(item.id)
                === Number(partId)
        );


    if (!part) {
        return;
    }


    for (const def of PRICE_FIELD_DEFS) {

        const input =
            document.getElementById(
                def.editId
            );

        if (input) {

            input.value =
                safePrice(
                    part[def.key]
                );

        }

    }

}


function getPricePayloadFromPartEdit() {

    const result = {};


    for (const def of PRICE_FIELD_DEFS) {

        result[def.key] =
            safePrice(
                document.getElementById(
                    def.editId
                )?.value
            );

    }


    return result;

}


const originalRenderParts =
    window.renderParts;


if (
    typeof originalRenderParts
    === "function"
) {

    window.renderParts = function () {

        originalRenderParts();

        addPricingCellsToRenderedRows();

    };

}


const originalOpenPartEdit =
    window.openPartEdit;


if (
    typeof originalOpenPartEdit
    === "function"
) {

    window.openPartEdit = function (partId) {

        originalOpenPartEdit(
            partId
        );

        fillPartEditPrices(
            partId
        );

    };

}


async function pricingSavePart() {

    if (
        editingPartId === null
    ) {
        return;
    }


    const message =
        document.getElementById(
            "edit-part-message"
        );


    const name =
        document
            .getElementById(
                "edit-part-name"
            )
            .value
            .trim();


    if (!name) {

        message.textContent =
            "이름을 입력해주세요.";

        return;

    }


    const payload = {

        "이름": name,

        "종류": Number(
            document.getElementById(
                "edit-part-type"
            ).value
        ),

        "고장여부": Number(
            document.getElementById(
                "edit-part-status"
            ).value
        ),

        ...getPricePayloadFromPartEdit()

    };


    try {

        const response =
            await fetch(
                `/api/parts/${editingPartId}`,
                {
                    method: "PUT",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(
                            payload
                        )
                }
            );


        const result =
            await response.json();


        if (!response.ok) {

            message.textContent =
                result.detail
                || "수정 실패";

            return;

        }


        editingPartId = null;

        await loadParts();

        openPage(
            "inventory"
        );

    }

    catch (error) {

        console.error(error);

        message.textContent =
            "서버 연결 실패";

    }

}


/* =========================================================
   거래 수정 시에는 가격 수정 가능
========================================================= */

const originalAddTransactionPartRow =
    window.addTransactionPartRow;


if (
    typeof originalAddTransactionPartRow
    === "function"
) {

    window.addTransactionPartRow = function (
        part = null
    ) {

        originalAddTransactionPartRow(
            part
        );


        const list =
            document.getElementById(
                "edit-transaction-parts-list"
            );

        const row =
            list?.lastElementChild;


        if (!row) {
            return;
        }


        const removeButton =
            row.querySelector(
                ".remove-part-button"
            );


        for (const def of PRICE_FIELD_DEFS) {

            const input =
                document.createElement(
                    "input"
                );

            input.className =
                `edit-price-${def.editId}`;

            input.type = "number";
            input.min = "0";
            input.step = "1";
            input.placeholder =
                def.label;

            input.value =
                safePrice(
                    part?.[def.key]
                );


            row.insertBefore(
                input,
                removeButton
            );

        }


        row.style.gridTemplateColumns =
            "130px 130px minmax(180px,1fr) 120px 120px 110px 80px";

    };

}


const originalGetTransactionEditParts =
    window.getTransactionEditParts;


if (
    typeof originalGetTransactionEditParts
    === "function"
) {

    window.getTransactionEditParts = function () {

        const rows =
            document.querySelectorAll(
                "#edit-transaction-parts-list .part-input-row"
            );

        const result = [];


        for (const row of rows) {

            const name =
                row
                    .querySelector(
                        ".edit-transaction-part-name"
                    )
                    ?.value
                    .trim();


            if (!name) {
                continue;
            }


            const data = {

                "종류": Number(
                    row.querySelector(
                        ".edit-transaction-part-type"
                    )?.value
                ),

                "고장여부": Number(
                    row.querySelector(
                        ".edit-transaction-part-status"
                    )?.value
                ),

                "이름": name

            };


            for (const def of PRICE_FIELD_DEFS) {

                data[def.key] =
                    safePrice(
                        row.querySelector(
                            `.edit-price-${def.editId}`
                        )?.value
                    );

            }


            if (row.dataset.partId) {

                data.id =
                    Number(
                        row.dataset.partId
                    );

            }


            result.push(
                data
            );

        }


        return result;

    };

}


/* =========================================================
   이벤트 보완
========================================================= */

const savePartButton =
    document.getElementById(
        "save-part-button"
    );


if (savePartButton) {

    savePartButton.addEventListener(
        "click",
        event => {

            event.preventDefault();
            event.stopImmediatePropagation();

            pricingSavePart();

        },
        true
    );

}


const editAddPartButton =
    document.getElementById(
        "edit-add-part-button"
    );


if (editAddPartButton) {

    editAddPartButton.addEventListener(
        "click",
        event => {

            event.preventDefault();
            event.stopImmediatePropagation();

            window.addTransactionPartRow();

        },
        true
    );

}


/* =========================================================
   최초 적용
========================================================= */

addPricingFieldsToEditPage();
addPricingColumnsToTable();
addPricingCellsToRenderedRows();
