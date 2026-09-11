let pendingPartImageFile = null;


function ensurePartImageUi() {

    if (
        document.getElementById(
            "part-image-editor"
        )
    ) {
        return;
    }


    const readonlyInfo =
        document.querySelector(
            "#page-part-edit .readonly-info"
        );


    if (!readonlyInfo) {
        return;
    }


    const wrapper =
        document.createElement(
            "div"
        );

    wrapper.id =
        "part-image-editor";

    wrapper.innerHTML = `
        <style>
            #part-image-editor {
                margin: 0 0 20px;
            }

            #part-image-editor > label {
                display: block;
                margin-bottom: 8px;
                font-size: 14px;
                font-weight: 700;
            }

            .part-image-preview {
                display: flex;
                align-items: center;
                justify-content: center;
                width: 100%;
                min-height: 210px;
                overflow: hidden;
                border: 1px dashed #cbd5e1;
                border-radius: 12px;
                background: #f8fafc;
                color: #64748b;
                text-align: center;
            }

            .part-image-preview img {
                display: block;
                width: 100%;
                max-height: 360px;
                object-fit: contain;
                background: white;
            }

            .part-image-actions {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 8px;
                margin-top: 10px;
            }

            .part-image-actions button,
            .part-image-file-label {
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 44px;
                padding: 10px 12px;
                border: 0;
                border-radius: 9px;
                font-size: 14px;
                font-weight: 700;
                cursor: pointer;
            }

            .part-image-file-label {
                background: #e5e7eb;
                color: #111827;
            }

            #part-image-input {
                display: none;
            }

            #part-image-remove-button {
                grid-column: 1 / -1;
                background: #dc2626;
                color: white;
            }

            #part-image-message {
                min-height: 18px;
                margin: 8px 0 0;
                font-size: 13px;
                font-weight: 700;
            }

            @media (max-width: 700px) {
                .part-image-preview {
                    min-height: 180px;
                }

                .part-image-actions {
                    grid-template-columns: 1fr;
                }

                #part-image-remove-button {
                    grid-column: auto;
                }
            }
        </style>

        <label>상품 사진</label>

        <div
            id="part-image-preview"
            class="part-image-preview"
        >
            등록된 사진 없음
        </div>

        <div class="part-image-actions">
            <label
                for="part-image-input"
                class="part-image-file-label"
            >
                + 사진 선택
            </label>

            <input
                id="part-image-input"
                type="file"
                accept="image/jpeg,image/png,image/webp"
            >

            <button
                id="part-image-upload-button"
                type="button"
            >
                사진 저장
            </button>

            <button
                id="part-image-remove-button"
                type="button"
            >
                사진 삭제
            </button>
        </div>

        <p id="part-image-message"></p>
    `;


    readonlyInfo.before(
        wrapper
    );


    document
        .getElementById(
            "part-image-input"
        )
        .addEventListener(
            "change",
            previewSelectedPartImage
        );


    document
        .getElementById(
            "part-image-upload-button"
        )
        .addEventListener(
            "click",
            uploadSelectedPartImage
        );


    document
        .getElementById(
            "part-image-remove-button"
        )
        .addEventListener(
            "click",
            removePartImage
        );

}


function getEditingPart() {

    if (
        typeof editingPartId === "undefined"
        || editingPartId === null
    ) {
        return null;
    }


    return cachedParts.find(
        part =>
            Number(part.id)
            === Number(editingPartId)
    ) || null;

}


function showPartImage(imageUrl) {

    const preview =
        document.getElementById(
            "part-image-preview"
        );


    if (!preview) {
        return;
    }


    if (!imageUrl) {
        preview.innerHTML =
            "등록된 사진 없음";
        return;
    }


    const image =
        document.createElement(
            "img"
        );

    image.src = imageUrl;
    image.alt = "상품 사진";

    preview.innerHTML = "";
    preview.appendChild(image);

}


function loadEditingPartImage() {

    ensurePartImageUi();

    pendingPartImageFile = null;


    const input =
        document.getElementById(
            "part-image-input"
        );

    if (input) {
        input.value = "";
    }


    const message =
        document.getElementById(
            "part-image-message"
        );

    if (message) {
        message.textContent = "";
    }


    const part =
        getEditingPart();

    showPartImage(
        part?.["이미지"] || ""
    );

}


function previewSelectedPartImage(event) {

    const file =
        event.target.files?.[0];


    if (!file) {
        pendingPartImageFile = null;
        return;
    }


    if (
        ![
            "image/jpeg",
            "image/png",
            "image/webp"
        ].includes(file.type)
    ) {
        alert(
            "JPG, PNG, WEBP 이미지만 선택해주세요."
        );
        event.target.value = "";
        pendingPartImageFile = null;
        return;
    }


    if (
        file.size
        > 10 * 1024 * 1024
    ) {
        alert(
            "이미지는 10MB 이하만 등록할 수 있습니다."
        );
        event.target.value = "";
        pendingPartImageFile = null;
        return;
    }


    pendingPartImageFile = file;

    showPartImage(
        URL.createObjectURL(file)
    );


    document.getElementById(
        "part-image-message"
    ).textContent =
        "사진을 선택했습니다. 사진 저장을 눌러주세요.";

}


async function uploadSelectedPartImage() {

    const message =
        document.getElementById(
            "part-image-message"
        );


    if (
        typeof editingPartId === "undefined"
        || editingPartId === null
    ) {
        message.textContent =
            "수정 중인 부품이 없습니다.";
        return;
    }


    if (!pendingPartImageFile) {
        message.textContent =
            "먼저 사진을 선택해주세요.";
        return;
    }


    message.textContent =
        "사진 저장 중...";


    try {

        const response =
            await fetch(
                `/api/parts/${editingPartId}/image`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            pendingPartImageFile.type
                    },
                    body:
                        pendingPartImageFile
                }
            );


        const result =
            await response.json();


        if (!response.ok) {
            message.textContent =
                result.detail
                || "사진 저장 실패";
            return;
        }


        pendingPartImageFile = null;

        await loadParts();

        const part =
            getEditingPart();

        showPartImage(
            part?.["이미지"]
            || result.image
        );

        message.textContent =
            "사진 저장 완료";

    }
    catch (error) {

        console.error(error);

        message.textContent =
            "서버 연결 실패";

    }

}


async function removePartImage() {

    const message =
        document.getElementById(
            "part-image-message"
        );


    if (
        typeof editingPartId === "undefined"
        || editingPartId === null
    ) {
        return;
    }


    const part =
        getEditingPart();


    if (!part?.["이미지"]) {
        message.textContent =
            "삭제할 사진이 없습니다.";
        return;
    }


    if (
        !confirm(
            "등록된 상품 사진을 삭제할까요?"
        )
    ) {
        return;
    }


    try {

        const response =
            await fetch(
                `/api/parts/${editingPartId}/image`,
                {
                    method: "DELETE"
                }
            );


        const result =
            await response.json();


        if (!response.ok) {
            message.textContent =
                result.detail
                || "사진 삭제 실패";
            return;
        }


        pendingPartImageFile = null;

        await loadParts();

        showPartImage("");

        message.textContent =
            "사진을 삭제했습니다.";

    }
    catch (error) {

        console.error(error);

        message.textContent =
            "서버 연결 실패";

    }

}


ensurePartImageUi();


const imageOriginalOpenPartEdit =
    window.openPartEdit;


if (
    typeof imageOriginalOpenPartEdit
    === "function"
) {

    window.openPartEdit = function (
        partId
    ) {

        imageOriginalOpenPartEdit(
            partId
        );

        loadEditingPartImage();

    };

}
