let memoryCategories = [];
let memoryItems = [];
let editingMemoryKey = null;
let savedMemory = null;
let activeWorkIndex = null;
let workVersion = null;
let mutationBusy = false;
const imageRenderGenerations = new WeakMap();

function memoryElement(id) {
    return document.getElementById(id);
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


function basicValues() {
    return {
        "상위태그": memoryElement("memory-category").value,
        "제목": memoryElement("memory-title").value.trim(),
        "우선도": Number(memoryElement("memory-priority").value),
        "상태": memoryElement("memory-status").value,
        "최종결론": memoryElement("memory-conclusion").value.trim()
    };
}

function fillBasic(item) {
    memoryElement("memory-category").value = item["상위태그"] || memoryCategories[0] || "";
    memoryElement("memory-title").value = item["제목"] || "";
    memoryElement("memory-priority").value = String(item["우선도"] || 2);
    memoryElement("memory-status").value = item["상태"] || "진행중";
    memoryElement("memory-conclusion").value = item["최종결론"] || "";
}

function resetMemoryEditor() {
    editingMemoryKey = null;
    savedMemory = null;
    fillBasic({});
    memoryElement("memory-editor-title").textContent = "새 메모";
    memoryElement("memory-saved-sections").hidden = true;
    memoryElement("delete-memory-button").classList.add("hidden");
    memoryElement("reset-memory-button").textContent = "입력 초기화";
    showMemoryMessage("");
    renderMemoryList();
}

function renderWorkList() {
    const list = memoryElement("memory-work-list");
    list.replaceChildren();
    const works = savedMemory?.["작업내용"] || [];
    if (!works.length) {
        const empty = document.createElement("p");
        empty.className = "memory-empty";
        empty.textContent = "저장된 작업내용이 없습니다.";
        list.append(empty);
    }
    works.forEach((work, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "memory-work-link";
        button.textContent = `${work["작업날짜"]} : ${work["요약"] || "요약 없음"}`;
        button.addEventListener("click", () => openWork(index));
        list.append(button);
    });
}

function openMemory(item) {
    if (!memoryCategories.includes(item["상위태그"])) {
        memoryCategories.push(item["상위태그"]);
        fillMemoryCategorySelects();
    }
    editingMemoryKey = item["메모키"];
    savedMemory = structuredClone(item);
    fillBasic(savedMemory);
    memoryElement("memory-editor-title").textContent = "메모 보기";
    memoryElement("memory-saved-sections").hidden = false;
    memoryElement("delete-memory-button").classList.remove("hidden");
    memoryElement("reset-memory-button").textContent = "입력 취소";
    renderWorkList();
    renderMemoryList();
    showMemoryMessage("");
}

async function memoryRequest(url, method, data) {
    const response = await fetch(url, {
        method, headers: {"Content-Type": "application/json"},
        ...(data === undefined ? {} : {body: JSON.stringify(data)})
    });
    if (!response.ok) throw new Error(await memoryErrorMessage(response, "요청을 처리하지 못했습니다."));
    return response.json();
}

function rememberSaved(item) {
    savedMemory = structuredClone(item);
    const index = memoryItems.findIndex(row => row["메모키"] === item["메모키"]);
    if (index < 0) memoryItems.unshift(item);
    else memoryItems[index] = item;
    renderMemoryList();
    renderWorkList();
}

async function saveMemory() {
    const editing = editingMemoryKey !== null;
    const data = basicValues();
    if (!editing) delete data["최종결론"];
    else data["버전"] = savedMemory["버전"];
    const saved = await memoryRequest(editing ? `/api/memories/${editingMemoryKey}` : "/api/memories",
        editing ? "PATCH" : "POST", data);
    rememberSaved(saved);
    openMemory(saved);
    showMemoryMessage("저장했습니다.");
}

async function deleteMemory() {
    if (!editingMemoryKey || !window.confirm("현재 메모 전체와 모든 작업내용을 삭제할까요? 이미지 원본은 보관됩니다.")) return;
    await memoryRequest(`/api/memories/${editingMemoryKey}`, "DELETE");
    memoryItems = memoryItems.filter(item => item["메모키"] !== editingMemoryKey);
    resetMemoryEditor();
    showMemoryMessage("메모를 삭제했습니다.");
}

function setWorkEditing(editing) {
    memoryElement("memory-work-view").hidden = editing;
    memoryElement("memory-work-edit").hidden = !editing;
    memoryElement("edit-memory-work").hidden = editing;
    memoryElement("cancel-memory-work").hidden = !editing;
    memoryElement("save-memory-work").hidden = !editing;
}

function showWork() {
    const work = savedMemory["작업내용"][activeWorkIndex];
    memoryElement("work-view-date").textContent = work["작업날짜"];
    memoryElement("work-view-summary").textContent = work["요약"];
    memoryElement("work-date").value = work["작업날짜"];
    memoryElement("work-summary").value = work["요약"];
    memoryElement("work-details").value = work["세부"];
    memoryElement("memory-work-message").textContent = "";
    setWorkEditing(false);
    renderWorkContent(work["세부"] || "");
}

function openWork(index) {
    activeWorkIndex = index;
    workVersion = savedMemory["버전"];
    showWork();
    memoryElement("memory-work-dialog").showModal();
}

async function changeWork(remove = false) {
    if (remove && !window.confirm("이 작업내용만 삭제할까요? 메모의 다른 작업내용은 유지됩니다.")) return;
    const data = {"버전": workVersion};
    if (!remove) Object.assign(data, {
        "작업날짜": memoryElement("work-date").value,
        "요약": memoryElement("work-summary").value,
        "세부": memoryElement("work-details").value
    });
    const saved = await memoryRequest(`/api/memories/${editingMemoryKey}/works/${activeWorkIndex}`,
        remove ? "DELETE" : "PUT", data);
    // Update the saved baseline, but leave unsaved basic fields in their inputs.
    rememberSaved(saved);
    workVersion = saved["버전"];
    if (remove) memoryElement("memory-work-dialog").close();
    else {
        showWork();
        memoryElement("memory-work-message").textContent = "작업내용을 저장했습니다.";
    }
}

function parseWorkContent(text) {
    const expression = /\{(\d+):\s*(\d+|\[\s*\d+(?:\s*,\s*\d+)*\s*\])\s*\}|\[\[이미지:(\d+)\]\]/g;
    const tokens = [];
    let position = 0;
    for (const match of text.matchAll(expression)) {
        if (match.index > position) tokens.push({text: text.slice(position, match.index)});
        tokens.push({imageId: Number(match[1] || match[3]),
            pointIds: match[2] ? [...new Set((match[2].match(/\d+/g) || []).map(Number))] : []});
        position = match.index + match[0].length;
    }
    if (position < text.length) tokens.push({text: text.slice(position)});
    return tokens;
}

async function renderWorkContent(text, container = memoryElement("work-view-content"), tokens = parseWorkContent(text)) {
    const generation = (imageRenderGenerations.get(container) || 0) + 1;
    imageRenderGenerations.set(container, generation);
    container.replaceChildren();
    const requests = new Map();
    const jobs = [];
    for (const token of tokens) {
        if (token.text !== undefined) {
            const paragraph = document.createElement("div");
            paragraph.className = "memory-work-text";
            paragraph.textContent = token.text;
            container.append(paragraph);
            continue;
        }
        const figure = document.createElement("figure");
        figure.className = "memory-point-figure";
        const caption = document.createElement("figcaption");
        caption.textContent = `이미지 ${token.imageId} 불러오는 중…`;
        figure.append(caption);
        container.append(figure);
        if (!requests.has(token.imageId)) requests.set(token.imageId,
            fetch(`/api/images/${token.imageId}`).then(async response => {
                if (!response.ok) throw new Error("이미지를 찾거나 불러올 수 없습니다.");
                return response.json();
            }));
        jobs.push((async () => {
            try {
                const result = await requests.get(token.imageId);
                if (generation !== imageRenderGenerations.get(container)) return;
                const block = result.content_items.find(item => item.type === "image");
                if (!block || !["image/jpeg", "image/png"].includes(block.mimeType)) throw new Error("이미지 형식 오류");
                const stage = document.createElement("div");
                stage.className = "memory-point-stage";
                const img = document.createElement("img");
                img.alt = `이미지 ${token.imageId}`;
                img.src = `data:${block.mimeType};base64,${block.data}`;
                img.addEventListener("error", () => {
                    stage.hidden = true;
                    caption.textContent = `이미지 ${token.imageId} 표시 실패`;
                });
                stage.append(img);
                const note = document.createElement("p");
                note.className = "memory-point-note";
                note.setAttribute("role", "status");
                note.hidden = true;
                const available = new Set();
                for (const point of result.points || []) {
                    if (!(token.allPoints || token.pointIds.includes(point.point_id)) || !Number.isFinite(point.x) || !Number.isFinite(point.y)) continue;
                    available.add(point.point_id);
                    const marker = document.createElement("button");
                    marker.type = "button";
                    marker.className = "memory-point-marker";
                    marker.style.left = `${point.x * 100}%`;
                    marker.style.top = `${point.y * 100}%`;
                    marker.style.setProperty("--shift-x", point.x < .05 ? "0%" : point.x > .95 ? "-100%" : "-50%");
                    marker.style.setProperty("--shift-y", point.y < .05 ? "0%" : point.y > .95 ? "-100%" : "-50%");
                    marker.textContent = `● ${point.point_id}`;
                    marker.setAttribute("aria-label", `포인트 ${point.point_id}: ${point.annotation || "주석 없음"}`);
                    marker.title = point.annotation || "주석 없음";
                    marker.addEventListener("click", () => {
                        note.textContent = `${point.point_id}: ${point.annotation || "주석 없음"}`;
                        note.hidden = false;
                    });
                    stage.append(marker);
                }
                const missing = token.pointIds.filter(id => !available.has(id));
                caption.textContent = `이미지 ${token.imageId}` + (missing.length ? ` · 없는 포인트: ${missing.join(", ")}` : "");
                figure.prepend(stage);
                figure.append(note);
            } catch (error) {
                if (generation === imageRenderGenerations.get(container)) caption.textContent = `이미지 ${token.imageId}: ${error.message}`;
            }
        })());
    }
    await Promise.all(jobs);
}

function bindMemoryAction(id, action, work = false) {
    memoryElement(id).addEventListener("click", async () => {
        if (mutationBusy) return;
        mutationBusy = true;
        const controls = [...document.querySelectorAll(".memory-editor-panel input, .memory-editor-panel select, .memory-editor-panel textarea, .memory-editor-panel button, .memory-list button, #new-memory-button, #memory-work-dialog button, #memory-work-dialog input, #memory-work-dialog textarea")];
        controls.forEach(control => control.disabled = true);
        try { await action(); }
        catch (error) {
            if (work) memoryElement("memory-work-message").textContent = error.message;
            else showMemoryMessage(error.message || "요청 실패", true);
        } finally {
            mutationBusy = false;
            controls.forEach(control => control.disabled = false);
        }
    });
}

memoryElement("new-memory-button").addEventListener("click", resetMemoryEditor);
memoryElement("reset-memory-button").addEventListener("click", () => {
    if (savedMemory) { fillBasic(savedMemory); showMemoryMessage("저장된 값으로 되돌렸습니다."); }
    else resetMemoryEditor();
});
bindMemoryAction("save-memory-button", saveMemory);
bindMemoryAction("delete-memory-button", deleteMemory);
bindMemoryAction("save-memory-work", () => changeWork(), true);
bindMemoryAction("delete-memory-work", () => changeWork(true), true);
memoryElement("edit-memory-work").addEventListener("click", () => setWorkEditing(true));
memoryElement("cancel-memory-work").addEventListener("click", showWork);
memoryElement("close-memory-work").addEventListener("click", () => memoryElement("memory-work-dialog").close());
memoryElement("memory-work-dialog").addEventListener("cancel", event => { if (mutationBusy) event.preventDefault(); });
for (const [id, event] of [["memory-search", "input"], ["memory-category-filter", "change"], ["memory-status-filter", "change"], ["memory-priority-filter", "change"]]) {
    memoryElement(id).addEventListener(event, () => loadMemories().catch(error => showMemoryMessage(error.message, true)));
}
(async () => {
    try { await loadMemoryCategories(); resetMemoryEditor(); await loadMemories(); }
    catch (error) { showMemoryMessage(error.message || "메모 초기화 실패", true); }
})();


function displaySearchImage(imageId, target) {
    return renderWorkContent("", memoryElement(target), [{imageId, pointIds: [], allPoints: true}]);
}

memoryElement("memory-search-mode").addEventListener("change", event => {
    const workSearch = event.target.checked;
    memoryElement("memory-search-mode-label").textContent = workSearch ? "ON · 작업검색" : "OFF · 이미지검색";
    memoryElement("memory-work-search").hidden = !workSearch;
    memoryElement("memory-image-search").hidden = workSearch;
    if (!workSearch) memoryElement("memory-image-id").focus();
});

memoryElement("memory-image-search-form").addEventListener("submit", event => {
    event.preventDefault();
    const raw = memoryElement("memory-image-id").value.trim();
    const id = Number(raw);
    if (!/^\d+$/.test(raw) || !Number.isSafeInteger(id) || id < 1) {
        memoryElement("memory-image-search-message").textContent = "올바른 image_id를 입력해주세요.";
        return;
    }
    memoryElement("memory-image-search-message").textContent = "";
    void displaySearchImage(id, "memory-image-search-result");
});

let latestImageRevision = null;
let latestImagePolling = false;
async function refreshLatestImage() {
    if (latestImagePolling || document.hidden) return;
    latestImagePolling = true;
    try {
        const response = await fetch("/api/memory/latest-image", {cache: "no-store"});
        if (!response.ok) throw new Error("최근 호출 이미지를 확인하지 못했습니다. 자동으로 다시 확인합니다.");
        const latest = await response.json();
        memoryElement("memory-latest-message").textContent = latest.image_id === null
            ? "아직 GPT가 호출한 이미지가 없습니다." : `image_id: ${latest.image_id}`;
        if (latest.revision !== latestImageRevision) {
            latestImageRevision = latest.revision;
            if (latest.image_id !== null) await displaySearchImage(latest.image_id, "memory-latest-result");
            else memoryElement("memory-latest-result").replaceChildren();
        }
    } catch (error) {
        memoryElement("memory-latest-message").textContent = error.message;
    } finally { latestImagePolling = false; }
}
void refreshLatestImage();
setInterval(() => {
    if (memoryElement("page-memory").classList.contains("active")) void refreshLatestImage();
}, 3000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) void refreshLatestImage(); });
