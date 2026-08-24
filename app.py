"""교사 월별 업무 정돈 웹 앱 — Streamlit 뼈대."""

from __future__ import annotations

import re
import uuid
from datetime import date

import pandas as pd
import streamlit as st

import db

ACADEMIC_MONTHS = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2]

MONTH_LABELS = {
    3: "3월",
    4: "4월",
    5: "5월",
    6: "6월",
    7: "7월",
    8: "8월",
    9: "9월",
    10: "10월",
    11: "11월",
    12: "12월",
    1: "1월",
    2: "2월",
}

KEYWORD_TO_MONTHS: dict[str, list[int]] = {
    "입학": [3],
    "개학": [3, 8],
    "신학기": [3],
    "학급편성": [3],
    "오리엔테이션": [3],
    "식목": [4],
    "과학의 달": [4],
    "중간고사": [4, 10],
    "어린이": [5],
    "어버이": [5],
    "스승": [5],
    "현장학습": [5, 6],
    "체험학습": [5, 6, 9],
    "기말고사": [6, 11],
    "여름방학": [7],
    "방학식": [7, 12],
    "2학기": [8],
    "개학식": [3, 8],
    "추석": [9],
    "운동회": [10],
    "축제": [10],
    "개교": [10],
    "수능": [11],
    "성적": [12, 1],
    "겨울방학": [12],
    "졸업": [2],
    "종업": [2],
    "전출": [2, 3],
    "전입": [2, 3],
    "생활기록": [1, 2],
    "생기부": [1, 2],
}

SAMPLE_TITLES = """\
○○초 2026학년도 학급편성 및 입학식 운영 계획
4월 과학의 달 행사 추진 안내
어린이날·어버이날 관련 가정통신문 발송 협조
1학기 기말고사 시행 계획
여름방학 중 방과후학교 운영 안내
2학기 개학 준비 및 교과서 배부 계획
추석 연휴 교무실 당직 편성
운동회 및 학교축제 추진 계획
대학수학능력시험 당일 등교 조정 안내
겨울방학식 및 성적 통지표 배부
생활기록부 마감 일정 안내
졸업식·종업식 운영 계획
""".strip()

TABLE_COLUMNS = ["할 일", "공문 제목", "분류 근거", "상태"]
UNCLASSIFIED_MONTH_LABEL = "미분류"
USER_ASSIGN_REASON = "사용자 지정"


def academic_year_start(today: date | None = None) -> int:
    today = today or date.today()
    return today.year if today.month >= 3 else today.year - 1


def month_tab_label(month: int, year_start: int) -> str:
    year = year_start if month >= 3 else year_start + 1
    return f"{year}년 {MONTH_LABELS[month]}"


def split_titles(raw: str) -> list[str]:
    lines: list[str] = []
    for chunk in re.split(r"[\n\r;]+", raw):
        title = chunk.strip(" \t-•·*")
        if title:
            lines.append(title)
    return lines


def months_from_explicit_date(title: str) -> list[int]:
    found: list[int] = []
    for match in re.finditer(r"(?<!\d)(1[0-2]|0?[1-9])\s*월", title):
        month = int(match.group(1))
        if month in ACADEMIC_MONTHS and month not in found:
            found.append(month)
    for match in re.finditer(
        r"(?<!\d)(1[0-2]|0?[1-9])[./-](0?[1-9]|[12]\d|3[01])", title
    ):
        month = int(match.group(1))
        if month in ACADEMIC_MONTHS and month not in found:
            found.append(month)
    return found


def classify_title(title: str) -> list[int]:
    months = months_from_explicit_date(title)
    if months:
        return months

    matched: list[int] = []
    for keyword, target_months in KEYWORD_TO_MONTHS.items():
        if keyword in title:
            for month in target_months:
                if month not in matched:
                    matched.append(month)
    return matched


def title_to_todo(title: str) -> str:
    cleaned = re.sub(r"\s+", " ", title).strip()
    if len(cleaned) > 48:
        cleaned = cleaned[:45] + "…"
    return f"공문 확인 및 후속 조치: {cleaned}"


def todo_row(title: str, reason: str) -> dict[str, str]:
    return {
        "할 일": title_to_todo(title),
        "공문 제목": title,
        "분류 근거": reason,
        "상태": "대기",
    }


def dataframe_from_rows(rows: list[dict[str, str]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=TABLE_COLUMNS)
    if not df.empty:
        df.index = range(1, len(df) + 1)
        df.index.name = "번호"
    return df


def month_choice_labels() -> list[str]:
    return [MONTH_LABELS[month] for month in ACADEMIC_MONTHS]


def months_from_choice_labels(labels: list[str] | None) -> list[int]:
    reverse = {label: month for month, label in MONTH_LABELS.items()}
    months: list[int] = []
    for label in labels or []:
        month = reverse.get(label)
        if month is not None and month not in months:
            months.append(month)
    return months


def append_title_to_months(
    tables: dict[int, pd.DataFrame],
    title: str,
    months: list[int],
    reason: str,
) -> dict[int, pd.DataFrame]:
    updated = dict(tables)
    for month in months:
        existing = updated[month].reset_index(drop=True)
        rows = existing.to_dict("records") + [todo_row(title, reason)]
        updated[month] = dataframe_from_rows(rows)
    return updated


def build_month_tables(
    titles: list[str],
) -> tuple[dict[int, pd.DataFrame], list[str]]:
    rows_by_month: dict[int, list[dict[str, str]]] = {m: [] for m in ACADEMIC_MONTHS}
    unclassified: list[str] = []

    for title in titles:
        months = classify_title(title)
        if not months:
            unclassified.append(title)
            continue
        for month in months:
            rows_by_month[month].append(todo_row(title, "제목 키워드/날짜"))

    tables = {
        month: dataframe_from_rows(rows_by_month[month]) for month in ACADEMIC_MONTHS
    }
    return tables, unclassified


def new_unclassified_items(titles: list[str]) -> list[dict[str, str]]:
    return [{"id": str(uuid.uuid4()), "title": title} for title in titles]


def unclassified_titles(items: list[dict[str, str]]) -> list[str]:
    return [item["title"] for item in items]


def unclassified_table(titles: list[str]) -> pd.DataFrame:
    return dataframe_from_rows([todo_row(title, "월 미특정") for title in titles])


def combined_download_table(
    tables: dict[int, pd.DataFrame],
    unclassified: list[str],
    year_start: int,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for month in ACADEMIC_MONTHS:
        df = tables[month]
        if df.empty:
            continue
        part = df.reset_index(drop=True).copy()
        part.insert(0, "분류된 월", month_tab_label(month, year_start))
        frames.append(part)
    if unclassified:
        part = unclassified_table(unclassified)
        part.insert(0, "분류된 월", UNCLASSIFIED_MONTH_LABEL)
        frames.append(part)
    columns = ["분류된 월", *TABLE_COLUMNS]
    if not frames:
        return pd.DataFrame(columns=columns)
    return pd.concat(frames, ignore_index=True)[columns]


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def render_empty_table() -> None:
    empty = pd.DataFrame(columns=TABLE_COLUMNS)
    st.dataframe(empty, use_container_width=True, hide_index=True)
    st.caption("이 달에 분류된 할 일이 없습니다.")


def apply_manual_month_choices(
    tables: dict[int, pd.DataFrame],
    items: list[dict[str, str]],
) -> tuple[dict[int, pd.DataFrame], list[dict[str, str]], int]:
    remaining: list[dict[str, str]] = []
    moved = 0
    updated = tables
    for item in items:
        months = months_from_choice_labels(
            st.session_state.get(f"manual_months_{item['id']}")
        )
        if not months:
            remaining.append(item)
            continue
        updated = append_title_to_months(
            updated, item["title"], months, USER_ASSIGN_REASON
        )
        moved += 1
    return updated, remaining, moved


def render_unclassified_editor(result: dict) -> None:
    items: list[dict[str, str]] = result["unclassified_items"]
    if not items:
        return

    with st.expander(
        f"월을 특정하지 못한 제목 {len(items)}건 — 직접 분류",
        expanded=True,
    ):
        st.write(
            "자동으로 달을 찾지 못한 공문입니다. 각 제목에 해당 월을 고른 뒤 "
            "**선택한 달로 보내기**를 누르세요. 여러 달을 함께 고를 수 있습니다."
        )
        options = month_choice_labels()
        with st.form("manual_classify"):
            for item in items:
                st.markdown(f"**{item['title']}**")
                st.multiselect(
                    f"{item['title']} 보낼 월",
                    options=options,
                    key=f"manual_months_{item['id']}",
                    placeholder="달을 선택하세요",
                    label_visibility="collapsed",
                )
            submitted = st.form_submit_button(
                "선택한 달로 보내기",
                type="primary",
                icon=":material/send:",
            )
        if submitted:
            tables, remaining, moved = apply_manual_month_choices(
                result["tables"], items
            )
            result["tables"] = tables
            result["unclassified_items"] = remaining
            st.session_state["classified"] = result
            if moved:
                st.session_state["manual_flash"] = (
                    f"{moved}건을 선택한 달 탭으로 보냈습니다."
                )
                persist_classified(result)
            else:
                st.session_state["manual_flash_warn"] = (
                    "달을 고른 제목이 없습니다. 월을 선택한 뒤 다시 눌러 주세요."
                )
            st.rerun()


def persist_classified(result: dict) -> None:
    message = db.try_save(
        result,
        st.session_state.get("raw_text", ""),
        academic_year_start(),
        ACADEMIC_MONTHS,
    )
    if message:
        st.session_state["save_flash"] = message


def restore_saved_work() -> None:
    saved = db.load_classified_work(
        academic_year_start(),
        ACADEMIC_MONTHS,
        dataframe_from_rows,
    )
    if not saved:
        st.session_state["save_flash"] = (
            "저장된 업무가 없습니다. 분류하면 자동으로 저장됩니다."
        )
        return
    st.session_state["classified"] = saved["classified"]
    if saved["raw_text"]:
        st.session_state["raw_text"] = saved["raw_text"]
    st.session_state["save_flash"] = "저장해 둔 업무 목록을 불러왔습니다."


def render_auth_sidebar() -> None:
    with st.sidebar:
        st.subheader("계정")
        user = db.current_user()
        if user:
            st.write(f"{user['email']} 으로 로그인됨")
            st.caption(
                "분류 결과는 클라우드에 저장되어, 다음에 로그인하면 다시 불러옵니다."
            )
            if st.button("로그아웃", width="stretch"):
                db.sign_out()
                st.rerun()
            if st.button("지금 저장", type="primary", width="stretch"):
                result = st.session_state.get("classified")
                if not result:
                    st.warning("저장할 분류 결과가 없습니다.")
                else:
                    persist_classified(result)
                    st.rerun()
            return

        st.write("이메일로 가입하거나 로그인한 뒤, 분류한 업무를 저장할 수 있습니다.")
        mode = st.radio("계정 작업", ["로그인", "회원가입"], horizontal=True)
        with st.form("auth_form"):
            email = st.text_input("이메일")
            password = st.text_input("비밀번호", type="password")
            submitted = st.form_submit_button(mode, width="stretch")
        if submitted:
            email = email.strip()
            if not email or not password:
                st.warning("이메일과 비밀번호를 입력해 주세요.")
                return
            if len(password) < 6:
                st.warning("비밀번호는 6자 이상이어야 합니다.")
                return
            try:
                if mode == "회원가입":
                    message = db.sign_up(email, password)
                else:
                    message = db.sign_in(email, password)
            except Exception as exc:
                st.error(str(exc))
                return
            if db.current_user():
                restore_saved_work()
                st.session_state["auth_flash"] = message
                st.rerun()
            else:
                st.info(message)
        with st.expander("저장 테이블이 없다면"):
            st.write(db.SCHEMA_HELP)
            st.code(db.schema_sql(), language="sql")


def main() -> None:
    st.set_page_config(
        page_title="교사 월별 업무 정돈",
        page_icon=":material/calendar_month:",
        layout="wide",
    )
    if "raw_text" not in st.session_state:
        st.session_state.raw_text = SAMPLE_TITLES

    render_auth_sidebar()

    st.title(":material/calendar_month: 교사 월별 업무 정돈")
    st.write(
        "공문 제목을 붙여넣은 뒤 **월별 업무로 분류하기**를 누르면 "
        "3월부터 다음 해 2월까지 탭으로 나누어 할 일 표를 보여 줍니다. "
        "달을 자동으로 못 찾은 제목은 직접 월을 지정할 수 있습니다. "
        "로그인하면 분류 결과가 저장되어 다음에 다시 불러올 수 있습니다."
    )
    if auth_flash := st.session_state.pop("auth_flash", None):
        st.success(auth_flash)
    if save_flash := st.session_state.pop("save_flash", None):
        if "실패" in save_flash:
            st.error(save_flash)
            with st.expander("저장용 테이블 만들기"):
                st.write(db.SCHEMA_HELP)
                st.code(db.schema_sql(), language="sql")
        else:
            st.info(save_flash)
    if db.current_user() is None:
        st.info("왼쪽에서 로그인하면 분류한 업무가 사라지지 않습니다.")

    raw_text = st.text_area(
        "공문 제목 (한 줄에 하나씩 붙여넣기)",
        height=220,
        placeholder="공문 제목을 줄바꿈으로 구분해 붙여넣으세요.",
        key="raw_text",
    )

    classify_clicked = st.button("월별 업무로 분류하기", type="primary")

    if classify_clicked:
        titles = split_titles(raw_text)
        if not titles:
            st.warning("분류할 공문 제목이 없습니다. 텍스트를 입력해 주세요.")
            st.session_state.pop("classified", None)
        else:
            tables, unclassified = build_month_tables(titles)
            result = {
                "tables": tables,
                "unclassified_items": new_unclassified_items(unclassified),
                "title_count": len(titles),
            }
            st.session_state["classified"] = result
            persist_classified(result)

    result = st.session_state.get("classified")
    if not result:
        st.info("제목을 입력하고 버튼을 누르면 월별 탭이 생성됩니다.")
        return

    if "unclassified_items" not in result and "unclassified" in result:
        result["unclassified_items"] = new_unclassified_items(result["unclassified"])
        st.session_state["classified"] = result

    year_start = academic_year_start()
    st.success(
        f"공문 제목 {result['title_count']}건을 "
        f"{year_start}학년도(3월~{year_start + 1}년 2월) 기준으로 분류했습니다."
    )

    if flash := st.session_state.pop("manual_flash", None):
        st.success(flash)
    if warn := st.session_state.pop("manual_flash_warn", None):
        st.warning(warn)

    render_unclassified_editor(result)

    tables: dict[int, pd.DataFrame] = result["tables"]
    leftover = unclassified_titles(result["unclassified_items"])
    combined = combined_download_table(tables, leftover, year_start)

    st.divider()
    with st.container(border=True):
        st.subheader(":material/download: 전체 데이터 한 번에 다운로드")
        st.write(
            "3월부터 다음 해 2월까지 할 일과 아직 분류하지 않은 공문을 한 CSV로 받습니다. "
            "엑셀에서 **분류된 월** 열로 해당 달을 구분할 수 있습니다."
        )
        st.download_button(
            label="전체 데이터 한 번에 다운로드",
            data=dataframe_to_csv_bytes(combined),
            file_name=f"교사_월별업무_전체_{year_start}학년도.csv",
            mime="text/csv",
            type="primary",
            icon=":material/download:",
            width="stretch",
        )
        st.caption(f"총 {len(combined)}행 (월별 할 일 + 미분류)")

    tab_labels = [month_tab_label(month, year_start) for month in ACADEMIC_MONTHS]
    tabs = st.tabs(tab_labels)

    for month, tab in zip(ACADEMIC_MONTHS, tabs):
        with tab:
            df = tables[month]
            label = month_tab_label(month, year_start)
            st.subheader(f"{label} 할 일")
            month_csv = df.reset_index(drop=True) if not df.empty else df
            st.download_button(
                label=f"{MONTH_LABELS[month]} CSV 다운로드",
                data=dataframe_to_csv_bytes(month_csv),
                file_name=f"교사_월별업무_{year_start}학년도_{MONTH_LABELS[month]}.csv",
                mime="text/csv",
                icon=":material/download:",
                key=f"download_month_{month}",
            )
            if df.empty:
                render_empty_table()
            else:
                st.dataframe(df, use_container_width=True)


if __name__ == "__main__":
    main()
