"""Supabase 로그인과 분류 결과 저장."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st
from supabase import Client, create_client

TABLE_NAME = "classified_work"

SCHEMA_HELP = """
Supabase 대시보드 → SQL Editor에서 `schema.sql` 내용을 실행해 주세요.
인증(Authentication)에서 Email 가입을 켜 두고,
테스트할 때는 Confirm email을 끄면 가입 직후 바로 로그인됩니다.
""".strip()


def schema_sql() -> str:
    return Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")


def _settings() -> tuple[str, str]:
    url = ""
    key = ""
    try:
        url = str(st.secrets["supabase"]["url"])
        key = str(st.secrets["supabase"]["anon_key"])
    except Exception:
        pass
    url = url or os.environ.get("SUPABASE_URL", "")
    key = key or os.environ.get("SUPABASE_ANON_KEY", "")
    return url.strip(), key.strip()


def create_supabase_client() -> Client | None:
    url, key = _settings()
    if not url or not key:
        return None
    client = create_client(url, key)
    tokens = st.session_state.get("sb_session")
    if tokens:
        client.auth.set_session(tokens["access_token"], tokens["refresh_token"])
    return client


def current_user() -> dict[str, str] | None:
    return st.session_state.get("sb_user")


def _store_session(session: Any, user: Any) -> None:
    st.session_state["sb_session"] = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
    }
    st.session_state["sb_user"] = {
        "id": user.id,
        "email": user.email or "",
    }


def sign_up(email: str, password: str) -> str:
    client = create_supabase_client()
    if client is None:
        return "Supabase 설정이 없습니다."
    response = client.auth.sign_up({"email": email, "password": password})
    if response.session and response.user:
        _store_session(response.session, response.user)
        return "가입과 로그인이 완료되었습니다."
    return "가입되었습니다. 이메일 확인 후 로그인해 주세요."


def sign_in(email: str, password: str) -> str:
    client = create_supabase_client()
    if client is None:
        return "Supabase 설정이 없습니다."
    response = client.auth.sign_in_with_password(
        {"email": email, "password": password}
    )
    if not response.session or not response.user:
        return "로그인에 실패했습니다."
    _store_session(response.session, response.user)
    return "로그인되었습니다."


def sign_out() -> None:
    client = create_supabase_client()
    if client is not None:
        try:
            client.auth.sign_out()
        except Exception:
            pass
    st.session_state.pop("sb_session", None)
    st.session_state.pop("sb_user", None)


def classified_to_payload(result: dict, raw_text: str, months: list[int]) -> dict:
    tables = {}
    for month in months:
        df = result["tables"][month]
        tables[str(month)] = df.reset_index(drop=True).to_dict("records")
    return {
        "title_count": result["title_count"],
        "raw_text": raw_text,
        "unclassified_items": result["unclassified_items"],
        "tables": tables,
    }


def payload_to_classified(
    payload: dict,
    months: list[int],
    dataframe_from_rows,
) -> dict:
    tables = {}
    saved = payload.get("tables") or {}
    for month in months:
        rows = saved.get(str(month), [])
        tables[month] = dataframe_from_rows(rows)
    return {
        "tables": tables,
        "unclassified_items": payload.get("unclassified_items") or [],
        "title_count": int(payload.get("title_count") or 0),
    }


def save_classified_work(
    result: dict,
    raw_text: str,
    academic_year: int,
    months: list[int],
) -> None:
    user = current_user()
    client = create_supabase_client()
    if user is None or client is None:
        raise RuntimeError("로그인이 필요합니다.")
    payload = classified_to_payload(result, raw_text, months)
    row = {
        "user_id": user["id"],
        "academic_year": academic_year,
        "title_count": result["title_count"],
        "raw_text": raw_text,
        "payload": payload,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    client.table(TABLE_NAME).upsert(row, on_conflict="user_id,academic_year").execute()


def load_classified_work(
    academic_year: int,
    months: list[int],
    dataframe_from_rows,
) -> dict | None:
    user = current_user()
    client = create_supabase_client()
    if user is None or client is None:
        return None
    response = (
        client.table(TABLE_NAME)
        .select("payload, raw_text, title_count")
        .eq("user_id", user["id"])
        .eq("academic_year", academic_year)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        return None
    row = rows[0]
    payload = row.get("payload") or {}
    classified = payload_to_classified(payload, months, dataframe_from_rows)
    if not classified["title_count"]:
        classified["title_count"] = int(row.get("title_count") or 0)
    return {
        "classified": classified,
        "raw_text": row.get("raw_text") or payload.get("raw_text") or "",
    }


def try_save(result: dict, raw_text: str, academic_year: int, months: list[int]) -> str | None:
    if current_user() is None:
        return None
    try:
        save_classified_work(result, raw_text, academic_year, months)
        return "클라우드에 저장했습니다."
    except Exception as exc:
        return f"저장에 실패했습니다: {exc}"
