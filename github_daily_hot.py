#!/usr/bin/env python3
"""Send a daily GitHub breakout-repository digest to a Feishu bot."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

GITHUB_SEARCH_API = "https://api.github.com/search/repositories"
DEFAULT_DAYS = 7
DEFAULT_LIMIT = 10
SHANGHAI = ZoneInfo("Asia/Shanghai")


class WorkflowError(RuntimeError):
    """An expected workflow failure with a safe, user-facing message."""


def configure_console_encoding() -> None:
    """Keep Chinese text and emoji readable in Windows action/debug logs."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def compact_text(value: object, limit: int = 180) -> str:
    text = " ".join(str(value or "暂无简介").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def build_search_url(now: datetime, days: int, limit: int) -> str:
    cutoff = (now.astimezone(timezone.utc) - timedelta(days=days)).date().isoformat()
    query = f"created:>={cutoff} fork:false archived:false is:public stars:>=5"
    params = urlencode(
        {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": max(1, min(limit, 30)),
        }
    )
    return f"{GITHUB_SEARCH_API}?{params}"


def fetch_hot_repositories(
    github_token: str | None,
    now: datetime,
    days: int = DEFAULT_DAYS,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "github-daily-hot-feishu",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    request = Request(build_search_url(now, days, limit), headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise WorkflowError(f"GitHub API 请求失败（HTTP {exc.code}）：{detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise WorkflowError(f"无法连接 GitHub API：{exc}") from exc

    items = payload.get("items")
    if not isinstance(items, list):
        raise WorkflowError("GitHub API 返回了无法识别的数据格式")
    return [item for item in items if isinstance(item, dict)][:limit]


def format_repo(repo: dict[str, Any], rank: int) -> str:
    name = compact_text(repo.get("full_name"), 80)
    url = str(repo.get("html_url") or "https://github.com")
    description = compact_text(repo.get("description"))
    language = compact_text(repo.get("language") or "未标注", 30)
    stars = int(repo.get("stargazers_count") or 0)
    forks = int(repo.get("forks_count") or 0)
    return (
        f"**{rank}. [{name}]({url})**\n"
        f"{description}\n"
        f"`{language}`  ⭐ {stars:,}  🍴 {forks:,}"
    )


def build_feishu_card(
    repositories: Iterable[dict[str, Any]], now: datetime, days: int
) -> dict[str, Any]:
    repos = list(repositories)
    local_date = now.astimezone(SHANGHAI).strftime("%Y-%m-%d")
    title = f"GitHub 每日热点 · {local_date}"

    if repos:
        sections = [format_repo(repo, rank) for rank, repo in enumerate(repos, start=1)]
        body = "\n\n---\n\n".join(sections)
    else:
        body = "今天没有找到符合条件的新锐仓库，请稍后再试。"

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "blue",
                "title": {"tag": "plain_text", "content": title},
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": (
                        f"关键词：`github`\n\n"
                        f"近 **{days} 天**新建仓库按 Star 总数排序；每天固定时间刷新。\n\n{body}"
                    ),
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": "数据来源：GitHub Search API；Star 为当前累计值。",
                        }
                    ],
                },
            ],
        },
    }


def add_feishu_signature(payload: dict[str, Any], secret: str, timestamp: int) -> None:
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(string_to_sign, digestmod=hashlib.sha256).digest()
    payload["timestamp"] = str(timestamp)
    payload["sign"] = base64.b64encode(digest).decode("ascii")


def response_is_success(payload: dict[str, Any]) -> bool:
    return payload.get("code") == 0 or payload.get("StatusCode") == 0


def send_to_feishu(
    webhook_url: str,
    payload: dict[str, Any],
    signing_secret: str | None = None,
) -> None:
    outgoing = json.loads(json.dumps(payload, ensure_ascii=False))
    if signing_secret:
        add_feishu_signature(outgoing, signing_secret, int(time.time()))

    request = Request(
        webhook_url,
        data=json.dumps(outgoing, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise WorkflowError(f"飞书 Webhook 请求失败（HTTP {exc.code}）：{detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise WorkflowError(f"无法连接飞书 Webhook：{exc}") from exc

    if not isinstance(result, dict) or not response_is_success(result):
        safe_result = compact_text(result, 300)
        raise WorkflowError(f"飞书拒绝了消息：{safe_result}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print card JSON only")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args(argv)
    if not 1 <= args.days <= 30:
        parser.error("--days must be between 1 and 30")
    if not 1 <= args.limit <= 20:
        parser.error("--limit must be between 1 and 20")
    return args


def main(argv: list[str] | None = None) -> int:
    configure_console_encoding()
    args = parse_args(argv)
    now = datetime.now(timezone.utc)
    try:
        repositories = fetch_hot_repositories(
            os.getenv("GITHUB_TOKEN"), now, days=args.days, limit=args.limit
        )
        payload = build_feishu_card(repositories, now, days=args.days)
        if args.dry_run:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        webhook_url = os.getenv("FEISHU_WEBHOOK_URL", "").strip()
        if not webhook_url:
            raise WorkflowError("缺少 GitHub Secret：FEISHU_WEBHOOK_URL")
        send_to_feishu(
            webhook_url,
            payload,
            signing_secret=os.getenv("FEISHU_SIGNING_SECRET") or None,
        )
        print(f"已向飞书发送 {len(repositories)} 个 GitHub 热点仓库。")
        return 0
    except WorkflowError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

