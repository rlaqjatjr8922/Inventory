from __future__ import annotations

from typing import Annotated, Any, Callable, TypeVar

from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

import gpt_api


ResultT = TypeVar("ResultT")


inventory_mcp = MCPServer(
    name="simsimpc-inventory",
    title="심심PC Inventory",
    description="심심PC 수리 프로젝트 기록과 카메라 이미지를 다루는 MCP 서버",
    instructions=(
        "프로젝트는 먼저 search_projects로 찾고 get_project는 detail=false인 일반보기를 우선 사용하세요. "
        "사용자가 상세 내용을 요구하거나 실제 상세 기록이 꼭 필요할 때만 detail=true를 사용하세요. "
        "add_work에는 현재 대화에서 확인된 내용을 요약하지 말고 최대한 자세히 기록하며 추측하지 마세요. "
        "같은 날짜 기록이 반환되면 기존 기록과 새 기록을 빠짐없이 합쳐 overwrite=true로 다시 보내세요. "
        "이미지는 [[이미지:ID]]로 언급하고 get_image와 take_photo 결과의 image ID를 이미지와 함께 유지하세요. "
        "take_photo는 서버 PC를 거쳐 노트북의 camera_agent.py에 촬영을 요청합니다."
    ),
    version="1.0.0",
)


def _run(operation: Callable[[], ResultT]) -> ResultT:
    try:
        return operation()
    except gpt_api.GPTAPIError as error:
        raise ToolError(error.detail) from error


@inventory_mcp.tool(name="search_projects", structured_output=False)
def search_projects(
    category: Annotated[str, Field(description="상위태그 완전일치 필터. 필요 없으면 빈 문자열")] = "",
    time: Annotated[
        str,
        Field(description="수정일 필터: today/오늘, week/이번주, month/이번달, YYYY-MM-DD 또는 빈 문자열"),
    ] = "",
    title: Annotated[str, Field(description="제목 부분검색. 필요 없으면 빈 문자열")] = "",
    status: Annotated[str, Field(description="상태 완전일치 필터. 필요 없으면 빈 문자열")] = "",
) -> Any:
    """category, time, title, status 조건만 사용해 프로젝트를 검색합니다."""

    return _run(lambda: gpt_api.search_projects_data(category, time, title, status))


@inventory_mcp.tool(name="get_project", structured_output=False)
def get_project(
    project_id: Annotated[int, Field(description="search_projects가 반환한 프로젝트 ID")],
    detail: Annotated[
        bool,
        Field(
            description=(
                "기본값 false를 우선 사용. 사용자가 상세 내용을 요구하거나 실제 상세 기록이 "
                "꼭 필요한 경우에만 true"
            )
        ),
    ] = False,
) -> Any:
    """프로젝트를 조회합니다. 일반보기(detail=false)를 우선해 토큰 사용량을 줄입니다."""

    return _run(lambda: gpt_api.get_project_data(project_id, detail))


@inventory_mcp.tool(name="add_work", structured_output=False)
def add_work(
    project_id: Annotated[int, Field(description="작업을 저장할 프로젝트 ID")],
    content: Annotated[
        str,
        Field(
            description=(
                "현재 대화에서 확인된 상세 작업 전체. 증상, 측정 위치/측정값, 테스트 방법, 장비, "
                "교체/탈거 부품, 수리 과정, 작업 전후 변화, 실패한 시도, 테스트 결과와 판단 근거를 "
                "요약하지 말고 최대한 자세히 기록. 추측 금지. 이미지 언급은 [[이미지:ID]] 형식"
            )
        ),
    ],
    overwrite: Annotated[
        bool,
        Field(
            description=(
                "같은 날짜의 기존기록과 새기록을 직접 합친 최종본을 다시 보낼 때만 true. "
                "true이면 오늘 기록 전체를 이 요청으로 교체"
            )
        ),
    ] = False,
    summary: Annotated[str, Field(description="날짜별 짧은 요약. 비우면 서버가 자동 생성")] = "",
    result: Annotated[str, Field(description="확인된 작업 결과. 확인되지 않은 내용은 쓰지 않음")] = "",
) -> Any:
    """오늘 작업을 상세히 저장합니다.

    같은 날짜 기록이 이미 있으면 첫 호출은 저장하지 않고 기존기록과 새기록을 반환합니다.
    두 기록을 빠짐없이 합친 최종 content를 만든 뒤 overwrite=true로 다시 호출해야 합니다.
    """

    return _run(
        lambda: gpt_api.add_work_data(
            project_id,
            content,
            overwrite,
            summary,
            result,
        )
    )


@inventory_mcp.tool(name="update_project", structured_output=False)
def update_project(
    project_id: Annotated[int, Field(description="수정할 프로젝트 ID")],
    title: Annotated[str | None, Field(description="새 제목")] = None,
    status: Annotated[str | None, Field(description="새 상태: 진행중, 완료, 보류, 폐기")] = None,
    priority: Annotated[int | None, Field(ge=1, le=5, description="새 우선도(1~5)")] = None,
    final_conclusion: Annotated[str | None, Field(description="새 최종결론. 빈 문자열이면 결론 삭제")] = None,
    category: Annotated[str | None, Field(description="새 상위태그")] = None,
) -> Any:
    """제목, 상태, 우선도, 최종결론, 상위태그 중 지정한 값만 수정합니다."""

    changes = {
        key: value
        for key, value in {
            "제목": title,
            "상태": status,
            "우선도": priority,
            "최종결론": final_conclusion,
            "상위태그": category,
        }.items()
        if value is not None
    }
    return _run(lambda: gpt_api.update_project_data(project_id, changes))


@inventory_mcp.tool(name="get_image", structured_output=False)
def get_image(
    image_id: Annotated[int, Field(description="가져올 저장 이미지 ID")],
) -> list[Any]:
    """저장된 이미지 자체와 그 image ID를 함께 반환합니다."""

    path = _run(lambda: gpt_api.get_image_path(image_id))
    return [f"image_id: {image_id}", Image(path=path)]


@inventory_mcp.tool(name="take_photo", structured_output=False)
def take_photo() -> list[Any]:
    """노트북 카메라 에이전트로 촬영하고 이미지 자체와 새 image ID를 함께 반환합니다."""

    image_id, path = _run(gpt_api.take_photo_data)
    return [f"image_id: {image_id}", Image(path=path)]


mcp_http_app = inventory_mcp.streamable_http_app(
    streamable_http_path="/",
    json_response=True,
    stateless_http=True,
    host="0.0.0.0",
)
