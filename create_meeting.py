"""Zoom Server-to-Server OAuth で会議を作成し、ID・パスワード・参加リンクを返す。"""

import argparse
import os
import secrets
import string
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

TOKEN_URL = "https://zoom.us/oauth/token"
API_BASE = "https://api.zoom.us/v2"
PASSWORD_CHARS = string.ascii_letters + string.digits
ENV_PATH = Path(__file__).resolve().parent / ".env"


class ZoomError(Exception):
    """Zoom API または設定のエラー。"""


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ZoomError(f"環境変数 {name} が未設定です。.env を確認してください。")
    return value


def zoom_error_message(response: requests.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text or f"HTTP {response.status_code}"
    message = body.get("message") or body.get("reason") or body
    code = body.get("code") or body.get("error")
    if code:
        return f"{code}: {message}"
    return str(message)


def get_access_token(account_id: str, client_id: str, client_secret: str) -> str:
    """Account ID / Client ID / Client Secret からアクセストークンを取得する。"""
    response = requests.post(
        TOKEN_URL,
        auth=(client_id, client_secret),
        data={
            "grant_type": "account_credentials",
            "account_id": account_id,
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise ZoomError(
            "アクセストークンの取得に失敗しました。\n"
            f"{zoom_error_message(response)}\n"
            "Account ID・Client ID・Client Secret と、アプリが Activate 済みかを確認してください。"
        )

    token = response.json().get("access_token")
    if not token:
        raise ZoomError("レスポンスに access_token がありません。")
    return token


def get_host_email(token: str, host_email: str) -> str:
    """ホストのメールアドレスを返す。未指定ならアカウント内の先頭ユーザーを使う。"""
    if host_email:
        return host_email

    response = requests.get(
        f"{API_BASE}/users",
        headers={"Authorization": f"Bearer {token}"},
        params={"status": "active", "page_size": 30},
        timeout=30,
    )
    if response.status_code != 200:
        raise ZoomError(
            "ホストユーザーの取得に失敗しました。\n"
            f"{zoom_error_message(response)}\n"
            ".env の ZOOM_HOST_EMAIL に、自分の Zoom ログインメールを設定してください。"
        )

    users = response.json().get("users") or []
    if not users:
        raise ZoomError("アクティブな Zoom ユーザーが見つかりません。ZOOM_HOST_EMAIL を設定してください。")
    return users[0]["email"]


def create_meeting(
    token: str,
    host_email: str,
    topic: str,
    start_time: datetime,
    duration: int,
    timezone: str,
    password: str,
) -> dict:
    """指定ユーザーをホストにしてスケジュール会議を作成する。"""
    user_path = quote(host_email, safe="")
    payload = {
        "topic": topic,
        "type": 2,
        "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration": duration,
        "timezone": timezone,
        "password": password,
        "settings": {
            "host_video": True,
            "participant_video": True,
            "join_before_host": False,
            "waiting_room": True,
            "mute_upon_entry": True,
            "use_pmi": False,
        },
    }
    response = requests.post(
        f"{API_BASE}/users/{user_path}/meetings",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if response.status_code != 201:
        raise ZoomError(
            "会議の作成に失敗しました。\n"
            f"{zoom_error_message(response)}\n"
            "アプリに meeting:write:meeting:admin（または meeting:write:admin）スコープがあるか確認してください。"
        )
    return response.json()


def format_meeting_id(meeting_id: int | str) -> str:
    digits = str(meeting_id)
    if len(digits) == 11:
        return f"{digits[:3]} {digits[3:7]} {digits[7:]}"
    if len(digits) == 10:
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    return digits


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Zoom 会議を作成します。")
    parser.add_argument("--topic", default="APIで作成した会議", help="会議のタイトル")
    parser.add_argument("--duration", type=int, default=60, help="会議の長さ（分）")
    parser.add_argument(
        "--start",
        help="開始日時（例: 2026-10-05T10:00）。省略時は1時間後",
    )
    parser.add_argument("--timezone", default="Asia/Tokyo", help="タイムゾーン")
    return parser.parse_args()


def create_zoom_meeting(
    topic: str = "APIで作成した会議",
    duration: int = 60,
    start: str | None = None,
    timezone: str = "Asia/Tokyo",
) -> dict:
    """会議を1件作成し、画面表示とコピーに使う情報だけを返す。"""
    load_dotenv(ENV_PATH)

    account_id = require_env("ZOOM_ACCOUNT_ID")
    client_id = require_env("ZOOM_CLIENT_ID")
    client_secret = require_env("ZOOM_CLIENT_SECRET")
    host_email = os.getenv("ZOOM_HOST_EMAIL", "").strip()

    tz = ZoneInfo(timezone)
    if start:
        start_time = datetime.fromisoformat(start)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=tz)
    else:
        start_time = datetime.now(tz) + timedelta(hours=1)
        start_time = start_time.replace(minute=0, second=0, microsecond=0)

    password = "".join(secrets.choice(PASSWORD_CHARS) for _ in range(8))
    token = get_access_token(account_id, client_id, client_secret)
    host_email = get_host_email(token, host_email)
    meeting = create_meeting(
        token=token,
        host_email=host_email,
        topic=topic,
        start_time=start_time,
        duration=duration,
        timezone=timezone,
        password=password,
    )

    return {
        "topic": meeting.get("topic") or topic,
        "host_email": meeting.get("host_email") or host_email,
        "start_time": start_time.strftime("%Y-%m-%d %H:%M"),
        "timezone": timezone,
        "duration": meeting.get("duration") or duration,
        "meeting_id": format_meeting_id(meeting.get("id")),
        "password": meeting.get("password") or password,
        "join_url": meeting.get("join_url") or "",
    }


def main() -> None:
    from meeting_ui import run

    run()


if __name__ == "__main__":
    main()
