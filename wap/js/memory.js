const MEMORY_PRIORITY_NAMES = {
    1: "낮음",
    2: "보통",
    3: "높음",
    4: "매우높음",
    5: "고정"
};

let memoryCategories = [];
let memoryItems = [];
let editingMemoryKey = null;
let editingMemoryAttachments = [];


function memoryElement(id) {
    return document.getElementById(id);
}


function memoryToday() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}


async function memoryErrorMessage(response, fallback) {
    try {
        const data = await response.json();
        return data.detail || fallback;
    }
    catch (error) {
        return fallback;
    }
}


function showMemoryMessage(message, isError = false) {
    const element = memoryElement("memory-message");
    element.textContent = message;
    element.style.color = isError ? "#b91c1c" : "#047857";
}


function fillMemoryCategorySelects() {
    const editor = memoryElement("memory-category");
    const filter = memoryElement("memory-category-filter");
    const selectedEditor = editor.value;
    const selectedFilter = filter.value;

    editor.innerHTML = "";
    filter.innerHTML = '<option value="">상위태그 전체</option>';

    for (const category of memoryCategories) {
        const editorOption = document.createElement("option");
        editorOption.value = category;
        editorOption.textContent = category;
        editor.appendChild(editorOption);

        const filterOption = document.createElement("option");
        filterOption.value = category;
        filterOption.textContent = category;
        filter.appendChild(filterOption);
    }

    if (memoryCategories.includes(selectedEditor)) {
        editor.value = selectedEditor;
    }

    if (memoryCategories.includes(selectedFilter)) {
        filter.value = selectedFilter;
    }
}


async function loadMemoryCategories() {
    const response = await fetch("/api/memory/categories");
    if (!response.ok) {
        throw new Error("상위태그를 불러오지 못했습니다.");
    }

    memoryCategories = await response.json();
    fillMemoryCategorySelects();
}


function createMemoryWorkRow(item = {}) {
    const row = document.createElement("div");
    row.className = "memory-work-card";

    const header = document.createElement("div");
    header.className = "memory-work-header";

    const dateInput = document.createElement("input");
    dateInput.className = "memory-work-date";
    dateInput.type = "date";
    dateInput.value = item["작업날짜"] || memoryToday();

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "danger-button small-button";
    removeButton.textContent = "작업 삭제";
    removeButton.addEventListener("click", () => row.remove());

    header.append(dateInput, removeButton);

    const summaryInput = document.createElement("input");
    summaryInput.className = "memory-work-summary";
    summaryInput.type = "text";
    summaryInput.placeholder = "요약";
    summaryInput.value = item["요약"] || "";

    const detailsInput = document.createElement("textarea");
    detailsInput.className = "memory-work-details";
    detailsInput.rows = 5;
    detailsInput.placeholder = "세부 작업내용 · 이미지 참조 예: [[이미지:1]]";
    detailsInput.value = item["세부"] || "";

    const outcomeInput = document.createElement("input");
    outcomeInput.className = "memory-work-outcome";
    outcomeInput.type = "text";
    outcomeInput.placeholder = "결과";
    outcomeInput.value = item["결과"] || "";

    row.append(header, summaryInput, detailsInput, outcomeInput);
    memoryElement("memory-work-list").appendChild(row);
}


function collectMemoryWorkItems() {
    return Array.from(
        document.querySelectorAll(".memory-work-card")
    ).map(row => ({
        "작업날짜": row.querySelector(".memory-work-date").value,
        "요약": row.querySelector(".memory-work-summary").value.trim(),
        "세부": row.querySelector(".memory-work-details").value.trim(),
        "결과": row.querySelector(".memory-work-outcome").value.trim()
    }));
}


function collectMemoryData() {
    return {
        "상위태그": memoryElement("memory-category").value,
        "제목": memoryElement("memory-title").value.trim(),
        "우선도": Number(memoryElement("memory-priority").value),
        "상태": memoryElement("memory-status").value,
        "작업내용": collectMemoryWorkItems(),
        "최종결론": memoryElement("memory-conclusion").value.trim()
    };
}


function resetMemoryEditor() {
    editingMemoryKey = null;
    editingMemoryAttachments = [];
    memoryElement("memory-editor-title").textContent = "새 메모";
    memoryElement("memory-title").value = "";
    memoryElement("memory-priority").value = "2";
    memoryElement("memory-status").value = "진행중";
    memoryElement("memory-conclusion").value = "";
    memoryElement("memory-work-list").innerHTML = "";
    memoryElement("memory-attachment-list").innerHTML = "";
    memoryElement("memory-meta").textContent = "";
    memoryElement("delete-memory-button").classList.add("hidden");
    memoryElement("memory-upload-help").textContent =
        "새 메모는 먼저 저장한 뒤 이미지를 추가할 수 있습니다.";
    memoryElement("memory-image-file").value = "";
    memoryElement("memory-image-description").value = "";
    showMemoryMessage("");
    createMemoryWorkRow();
}


function formatMemoryDate(value) {
    if (!value) {
        return "";
    }
    return String(value).replace("T", " ").slice(0, 16);
}


function renderMemoryList() {
    const list = memoryElement("memory-list");
    list.innerHTML = "";
    memoryElement("memory-result-count").textContent =
        `검색 결과 ${memoryItems.length}개`;

    if (!memoryItems.length) {
        const empty = document.createElement("p");
        empty.className = "memory-empty";
        empty.textContent = "조건에 맞는 메모가 없습니다.";
        list.appendChild(empty);
        return;
    }

    for (const item of memoryItems) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "memory-list-card";
        if (item["메모키"] === editingMemoryKey) {
            button.classList.add("active");
        }

        const top = document.createElement("span");
        top.className = "memory-list-top";

        const category = document.createElement("strong");
        category.textContent = item["상위태그"];

        const priority = document.createElement("span");
        priority.textContent =
            `우선도 ${item["우선도"]} · ${item["상태"]}`;

        top.append(category, priority);

        const title = document.createElement("span");
        title.className = "memory-list-title";
        title.textContent = item["제목"];

        const bottom = document.createElement("span");
        bottom.className = "memory-list-bottom";
        bottom.textContent =
            `수정 ${formatMemoryDate(item["수정일시"])} · 작업 ${(item["작업내용"] || []).length}개`;

        button.append(top, title, bottom);
        button.addEventListener("click", () => openMemory(item));
        list.appendChild(button);
    }
}


function renderMemoryAttachments() {
    const list = memoryElement("memory-attachment-list");
    list.innerHTML = "";

    for (const attachment of editingMemoryAttachments) {
        const card = document.createElement("div");
        card.className = "memory-attachment-card";

        const image = document.createElement("img");
        image.alt = attachment["설명"] || attachment["원본파일명"] || "첨부 이미지";
        image.loading = "lazy";
        image.src =
            `/api/memories/${editingMemoryKey}/attachments/${attachment["아이디"]}`;

        const info = document.createElement("div");
        info.className = "memory-attachment-info";

        const reference = document.createElement("code");
        reference.textContent = `[[이미지:${attachment["아이디"]}]]`;

        const description = document.createElement("span");
        description.textContent =
            attachment["설명"] || attachment["원본파일명"] || "설명 없음";

        const actions = document.createElement("div");
        actions.className = "memory-attachment-actions";

        const copyButton = document.createElement("button");
        copyButton.type = "button";
        copyButton.className = "secondary-button small-button";
        copyButton.textContent = "참조 복사";
        copyButton.addEventListener("click", async () => {
            const text = `[[이미지:${attachment["아이디"]}]]`;
            try {
                await navigator.clipboard.writeText(text);
                showMemoryMessage(`${text} 복사 완료`);
            }
            catch (error) {
                showMemoryMessage(`복사할 참조: ${text}`);
            }
        });

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "danger-button small-button";
        deleteButton.textContent = "삭제";
        deleteButton.addEventListener("click", () =>
            deleteMemoryAttachment(attachment["아이디"])
        );

        actions.append(copyButton, deleteButton);
        info.append(reference, description, actions);
        card.append(image, info);
        list.appendChild(card);
    }
}


function openMemory(item) {
    editingMemoryKey = item["메모키"];
    editingMemoryAttachments = item["첨부파일"] || [];
    memoryElement("memory-editor-title").textContent = "메모 수정";
    memoryElement("memory-category").value = item["상위태그"];
    memoryElement("memory-title").value = item["제목"];
    memoryElement("memory-priority").value = String(item["우선도"]);
    memoryElement("memory-status").value = item["상태"];
    memoryElement("memory-conclusion").value = item["최종결론"] || "";
    memoryElement("memory-work-list").innerHTML = "";

    const workItems = item["작업내용"] || [];
    if (workItems.length) {
        workItems.forEach(createMemoryWorkRow);
    }
    else {
        createMemoryWorkRow();
    }

    memoryElement("delete-memory-button").classList.remove("hidden");
    memoryElement("memory-upload-help").textContent =
        "JPG·PNG·WEBP, 이미지당 최대 10MB";
    memoryElement("memory-meta").textContent =
        `생성 ${formatMemoryDate(item["생성일시"])} · 수정 ${formatMemoryDate(item["수정일시"])}`;
    showMemoryMessage("");
    renderMemoryAttachments();
    renderMemoryList();

    if (window.innerWidth <= 900) {
        memoryElement("memory-editor-title").scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }
}


async function loadMemories() {
    const params = new URLSearchParams();
    const query = memoryElement("memory-search").value.trim();
    const category = memoryElement("memory-category-filter").value;
    const status = memoryElement("memory-status-filter").value;
    const minimumPriority = memoryElement("memory-priority-filter").value;

    if (query) params.set("검색어", query);
    if (category) params.set("상위태그", category);
    if (status) params.set("상태", status);
    if (minimumPriority !== "0") params.set("최소우선도", minimumPriority);

    const response = await fetch(`/api/memories?${params.toString()}`);
    if (!response.ok) {
        throw new Error(await memoryErrorMessage(response, "메모 검색 실패"));
    }

    memoryItems = await response.json();
    renderMemoryList();
}


async function saveMemory() {
    const data = collectMemoryData();
    const isEditing = Boolean(editingMemoryKey);
    const url = isEditing
        ? `/api/memories/${editingMemoryKey}`
        : "/api/memories";

    const response = await fetch(url, {
        method: isEditing ? "PUT" : "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(data)
    });

    if (!response.ok) {
        showMemoryMessage(
            await memoryErrorMessage(response, "저장 실패"),
            true
        );
        return;
    }

    const saved = await response.json();
    editingMemoryKey = saved["메모키"];
    editingMemoryAttachments = saved["첨부파일"] || [];
    await loadMemories();
    openMemory(saved);
    showMemoryMessage(isEditing ? "수정했습니다." : "저장했습니다. 이제 이미지를 추가할 수 있습니다.");
}


async function deleteMemory() {
    if (!editingMemoryKey) return;
    if (!window.confirm("이 메모와 첨부 이미지를 모두 삭제할까요?")) return;

    const response = await fetch(`/api/memories/${editingMemoryKey}`, {
        method: "DELETE"
    });

    if (!response.ok) {
        showMemoryMessage(
            await memoryErrorMessage(response, "삭제 실패"),
            true
        );
        return;
    }

    resetMemoryEditor();
    await loadMemories();
    showMemoryMessage("메모를 삭제했습니다.");
}


async function uploadMemoryImage() {
    if (!editingMemoryKey) {
        showMemoryMessage("메모를 먼저 저장해주세요.", true);
        return;
    }

    const file = memoryElement("memory-image-file").files[0];
    if (!file) {
        showMemoryMessage("추가할 이미지를 선택해주세요.", true);
        return;
    }

    const description = memoryElement("memory-image-description").value.trim();
    const response = await fetch(
        `/api/memories/${editingMemoryKey}/attachments`,
        {
            method: "POST",
            headers: {
                "Content-Type": file.type,
                "X-File-Name": encodeURIComponent(file.name),
                "X-File-Description": encodeURIComponent(description)
            },
            body: file
        }
    );

    if (!response.ok) {
        showMemoryMessage(
            await memoryErrorMessage(response, "이미지 추가 실패"),
            true
        );
        return;
    }

    const attachment = await response.json();
    memoryElement("memory-image-file").value = "";
    memoryElement("memory-image-description").value = "";
    const refreshedResponse = await fetch(`/api/memories/${editingMemoryKey}`);
    const refreshed = await refreshedResponse.json();
    editingMemoryAttachments = refreshed["첨부파일"] || [];
    renderMemoryAttachments();
    await loadMemories();
    showMemoryMessage(`[[이미지:${attachment["아이디"]}]] 추가 완료`);
}


async function deleteMemoryAttachment(attachmentId) {
    if (!window.confirm("이 이미지를 삭제할까요?")) return;

    const response = await fetch(
        `/api/memories/${editingMemoryKey}/attachments/${attachmentId}`,
        {method: "DELETE"}
    );

    if (!response.ok) {
        showMemoryMessage(
            await memoryErrorMessage(response, "이미지 삭제 실패"),
            true
        );
        return;
    }

    editingMemoryAttachments = editingMemoryAttachments.filter(
        item => Number(item["아이디"]) !== Number(attachmentId)
    );
    renderMemoryAttachments();
    await loadMemories();
    showMemoryMessage("이미지를 삭제했습니다. 본문의 참조도 확인해주세요.");
}


async function addMemoryCategory() {
    const name = window.prompt("추가할 상위태그 이름");
    if (name === null) return;

    const response = await fetch("/api/memory/categories", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({"이름": name})
    });

    if (!response.ok) {
        showMemoryMessage(
            await memoryErrorMessage(response, "상위태그 추가 실패"),
            true
        );
        return;
    }

    memoryCategories = await response.json();
    fillMemoryCategorySelects();
    memoryElement("memory-category").value = name.trim();
    showMemoryMessage("상위태그를 추가했습니다.");
}


async function initializeMemoryPage() {
    try {
        await loadMemoryCategories();
        resetMemoryEditor();
        await loadMemories();
    }
    catch (error) {
        console.error(error);
        showMemoryMessage(error.message || "메모리 초기화 실패", true);
    }
}


memoryElement("new-memory-button").addEventListener("click", resetMemoryEditor);
memoryElement("reset-memory-button").addEventListener("click", resetMemoryEditor);
memoryElement("add-memory-work-button").addEventListener("click", () => createMemoryWorkRow());
memoryElement("add-memory-category-button").addEventListener("click", addMemoryCategory);
memoryElement("save-memory-button").addEventListener("click", saveMemory);
memoryElement("delete-memory-button").addEventListener("click", deleteMemory);
memoryElement("upload-memory-image-button").addEventListener("click", uploadMemoryImage);

memoryElement("memory-search").addEventListener("input", loadMemories);
memoryElement("memory-category-filter").addEventListener("change", loadMemories);
memoryElement("memory-status-filter").addEventListener("change", loadMemories);
memoryElement("memory-priority-filter").addEventListener("change", loadMemories);

initializeMemoryPage();
