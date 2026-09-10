const PRICE_FIELD_DEFS = [
    {
        key: "목표판매가",
        className: "part-target-price",
        editId: "edit-target-price",
        label: "목표판매가"
    },
    {
        key: "최저판매가",
        className: "part-minimum-price",
        editId: "edit-minimum-price",
        label: "최저판매가"
    },
    {
        key: "수리비",
        className: "part-repair-cost",
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


function addPricingFieldsToBuyRow(row) {

    if (!row || row.dataset.pricingReady === "1") {
        return;
    }


    row.dataset.pricingReady = "1";


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
            def.className;

        input.type = "number";
        input.min = "0";
        input.step = "1";
        input.value = "0";
        input.placeholder = def.label;


        row.insertBefore(
            input,
            removeButton
        );

    }


    row.style.gridTemplateColumns =
        "130px 130px minmax(180px,1fr) 80px 120px 120px 110px 80px";

}


function enhanceExistingBuyRows() {

    document
        .querySelectorAll(
            "#new-parts-list .part-input-row"
        )
        .forEach(
            addPricingFieldsToBuyRow
        );

}


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


    headerRow.dataset.pricingReady = "1";


    const cells =
        headerRow.querySelectorAll(
            "th"
        );


    const buyGroupHeader =
        cells[4];


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

}


const originalAddNewPartRow =
    window.addNewPartRow;


if (typeof originalAddNewPartRow === "function") {

    window.addNewPartRow = function () {

        originalAddNewPartRow();

        enhanceExistingBuyRows();

    };

}


const originalGetNewParts =
    window.getNewParts;


if (typeof originalGetNewParts === "function") {

    window.getNewParts = function () {

        const rows =
            document.querySelectorAll(
                "#new-parts-list .part-input-row"
            );

        const parts = [];


        for (const row of rows) {

            const type =
                Number(
                    row.querySelector(
                        ".part-type"
                    ).value
                );

            const status =
                Number(
                    row.querySelector(
                        ".part-status"
                    ).value
                );

            const name =
                row.querySelector(
                    ".part-name"
                ).value.trim();

            const quantity =
                Math.max(
                    1,
                    Math.floor(
                        Number(
                            row.querySelector(
                                ".part-quantity"
                            )?.value
                        ) || 1
                    )
                );


            if (!name) {
                continue;
            }


            const priceData = {};


            for (const def of PRICE_FIELD_DEFS) {

                priceData[def.key] =
                    Math.max(
                        0,
                        Math.floor(
                            Number(
                                row.querySelector(
                                    `.${def.className}`
                                )?.value
                            ) || 0
                        )
                    );

            }


            for (
                let index = 0;
                index < quantity;
                index++
            ) {

                parts.push({
                    "종류": type,
                    "고장여부": status,
                    "이름": name,
                    ...priceData
                });

            }

        }


        return parts;

    };

}


const originalRenderParts =
    window.renderParts;


if (typeof originalRenderParts === "function") {

    window.renderParts = function () {

        originalRenderParts();


        const rows =
            document.querySelectorAll(
                "#parts-table tr"
            );


        rows.forEach(
            row => {

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

            }
        );

    };

}


const originalOpenPartEdit =
    window.openPartEdit;


if (typeof originalOpenPartEdit === "function") {

    window.openPartEdit = function (partId) {

        originalOpenPartEdit(
            partId
        );


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
                    Number(
                        part[def.key]
                        || 0
                    );
            }

        }

    };

}


const originalSavePart =
    window.savePart;


if (typeof originalSavePart === "function") {

    window.savePart = async function () {

        if (
            editingPartId === null
        ) {
            return;
        }


        const name =
            document
                .getElementById(
                    "edit-part-name"
                )
                .value
                .trim();

        const type =
            Number(
                document.getElementById(
                    "edit-part-type"
                ).value
            );

        const status =
            Number(
                document.getElementById(
                    "edit-part-status"
                ).value
            );

        const message =
            document.getElementById(
                "edit-part-message"
            );


        if (!name) {
            message.textContent =
                "이름을 입력해주세요.";
            return;
        }


        const payload = {
            "이름": name,
            "종류": type,
            "고장여부": status
        };


        for (const def of PRICE_FIELD_DEFS) {

            payload[def.key] =
                Math.max(
                    0,
                    Math.floor(
                        Number(
                            document.getElementById(
                                def.editId
                            )?.value
                        ) || 0
                    )
                );

        }


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

    };

}


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
                `edit-${def.className}`;

            input.type = "number";
            input.min = "0";
            input.step = "1";
            input.placeholder = def.label;
            input.value =
                Number(
                    part?.[def.key]
                    || 0
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
                    .value
                    .trim();


            if (!name) {
                continue;
            }


            const data = {
                "종류": Number(
                    row.querySelector(
                        ".edit-transaction-part-type"
                    ).value
                ),
                "고장여부": Number(
                    row.querySelector(
                        ".edit-transaction-part-status"
                    ).value
                ),
                "이름": name
            };


            for (const def of PRICE_FIELD_DEFS) {

                data[def.key] =
                    Math.max(
                        0,
                        Math.floor(
                            Number(
                                row.querySelector(
                                    `.edit-${def.className}`
                                )?.value
                            ) || 0
                        )
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


addPricingFieldsToEditPage();
addPricingColumnsToTable();
enhanceExistingBuyRows();


if (
    typeof renderParts
    === "function"
) {
    renderParts();
}
