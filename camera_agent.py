"""노트북 카메라를 원격 Inventory 서버에 연결하는 작은 폴링 에이전트."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def capture_jpeg(camera_index: int) -> bytes:
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError(
            "OpenCV가 없습니다. python -m pip install -r requirements-camera-agent.txt 를 실행하세요."
        ) from error

    if sys.platform == "win32" and hasattr(cv2, "CAP_DSHOW"):
        camera = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    else:
        camera = cv2.VideoCapture(camera_index)

    try:
        if not camera.isOpened():
            raise RuntimeError(f"카메라 {camera_index}번을 열 수 없습니다.")

        frame = None
        for _ in range(10):
            success, candidate = camera.read()
            if success and candidate is not None:
                frame = candidate
            time.sleep(0.03)
        if frame is None:
            raise RuntimeError("카메라에서 사진을 가져오지 못했습니다.")

        parameters = []
        if hasattr(cv2, "IMWRITE_JPEG_QUALITY"):
            parameters = [cv2.IMWRITE_JPEG_QUALITY, 95]
        success, encoded = cv2.imencode(".jpg", frame, parameters)
        if not success:
            raise RuntimeError("촬영한 사진을 JPG로 변환하지 못했습니다.")
        return encoded.tobytes()
    finally:
        camera.release()


def call_server(
    url: str,
    token: str,
    method: str = "GET",
    data: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, bytes]:
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Inventory-Camera-Agent/1.0",
    }
    if content_type:
        headers["Content-Type"] = content_type
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=20) as response:
        return response.status, response.read()


def send_error(server: str, token: str, request_id: str, message: str) -> None:
    body = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
    call_server(
        f"{server}/gpt/camera-agent/result/{request_id}",
        token,
        method="POST",
        data=body,
        content_type="application/json",
    )


def run_agent(server: str, token: str, camera_index: int, interval: float, once: bool) -> None:
    server = server.rstrip("/")
    print(f"Inventory 카메라 에이전트 연결: {server} (카메라 {camera_index}번)")
    print("촬영 요청을 기다리는 중입니다. 종료하려면 Ctrl+C를 누르세요.")

    while True:
        try:
            status, body = call_server(
                f"{server}/gpt/camera-agent/request",
                token,
            )
            if status == 204:
                if once:
                    return
                time.sleep(interval)
                continue

            payload = json.loads(body.decode("utf-8"))
            request_id = str(payload["request_id"])
            print(f"촬영 요청 수신: {request_id}")

            try:
                image_data = capture_jpeg(camera_index)
                _, result_body = call_server(
                    f"{server}/gpt/camera-agent/result/{request_id}",
                    token,
                    method="POST",
                    data=image_data,
                    content_type="image/jpeg",
                )
                result = json.loads(result_body.decode("utf-8"))
                print(f"촬영 완료: image_id={result.get('image_id')}")
            except Exception as error:
                message = str(error) or type(error).__name__
                print(f"촬영 실패: {message}")
                try:
                    send_error(server, token, request_id, message)
                except Exception as report_error:
                    print(f"실패 결과 전송 오류: {report_error}")

            if once:
                return
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            print(f"서버 응답 오류 {error.code}: {detail}")
            if error.code in {401, 403}:
                raise SystemExit("CAMERA_AGENT_TOKEN을 확인하세요.") from error
            time.sleep(max(interval, 2.0))
        except (URLError, TimeoutError, json.JSONDecodeError, KeyError) as error:
            print(f"서버 연결 오류: {error}")
            time.sleep(max(interval, 2.0))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory 노트북 카메라 에이전트")
    parser.add_argument(
        "--server",
        default=os.environ.get("INVENTORY_SERVER_URL", ""),
        help="Inventory 서버 공개 주소 (예: https://example.trycloudflare.com)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("CAMERA_AGENT_TOKEN", ""),
        help="서버와 동일한 CAMERA_AGENT_TOKEN",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=int(os.environ.get("GPT_CAMERA_INDEX", "0")),
        help="노트북의 카메라/현미경 번호 (기본 0)",
    )
    parser.add_argument("--interval", type=float, default=0.5, help="요청 확인 간격(초)")
    parser.add_argument("--once", action="store_true", help="한 번 확인/촬영 후 종료")
    args = parser.parse_args()

    if not args.server:
        parser.error("--server 또는 INVENTORY_SERVER_URL이 필요합니다.")
    if not args.token:
        parser.error("--token 또는 CAMERA_AGENT_TOKEN이 필요합니다.")
    if args.interval < 0.1:
        parser.error("--interval은 0.1초 이상이어야 합니다.")
    return args


def main() -> None:
    args = parse_args()
    try:
        run_agent(args.server, args.token, args.camera, args.interval, args.once)
    except KeyboardInterrupt:
        print("\n카메라 에이전트를 종료했습니다.")


if __name__ == "__main__":
    main()
