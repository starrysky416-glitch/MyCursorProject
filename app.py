"""교사 월별 업무 정돈 웹 앱 — Streamlit 뼈대."""

from __future__ import annotations

import re
from datetime import date

import pandas as pd
import streamlit as st

# 학년도: 3월 ~ 다음 해 2월
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

# 공문 제목에 자주 등장하는 표현 → 해당 월 (예시 규칙)
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


def academic_year_start(today: date | None = None) -> int:
    """오늘 기준 학년도 시작 연도(3월 시작)를 반환한다."""
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
    """제목에 '3월', '03월', '3.15' 같은 날짜가 있으면 그 월을 쓴다."""
    found: list[int] = []
    for match in re.finditer(r"(?<!\d)(1[0-2]|0?[1-9])\s*월", title):
        month = int(match.group(1))
        if month in ACADEMIC_MONTHS and month not in found:
            found.append(month)
    for match in re.finditer(r"(?<!\d)(1[0-2]|0?[1-9])[./-](0?[1-9]|[12]\d|3[01])", title):
        month = int(match.group(1))
        if month in ACADEMIC_MONTHS and month not in found:
            found.append(month)
    return found


def classify_title(title: str) -> list[int]:
    """공문 제목을 학년도 월 목록으로 매핑한다. 매칭이 없으면 빈 리스트."""
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
    """제목을 짧은 할 일 문구로 바꾼다(예시)."""
    cleaned = re.sub(r"\s+", " ", title).strip()
    if len(cleaned) > 48:
        cleaned = cleaned[:45] + "…"
    return f"공문 확인 및 후속 조치: {cleaned}"


def build_month_tables(titles: list[str]) -> tuple[dict[int, pd.DataFrame], list[str]]:
    rows_by_month: dict[int, list[dict[str, str]]] = {m: [] for m in ACADEMIC_MONTHS}
    unclassified: list[str] = []

    for title in titles:
        months = classify_title(title)
        if not months:
            unclassified.append(title)
            continue
        for month in months:
            rows_by_month[month].append(
                {
                    "할 일": title_to_todo(title),
                    "공문 제목": title,
                    "분류 근거": "제목 키워드/날짜",
                    "상태": "대기",
                }
            )

    tables: dict[int, pd.DataFrame] = {}
    columns = ["할 일", "공문 제목", "분류 근거", "상태"]
    for month in ACADEMIC_MONTHS:
        df = pd.DataFrame(rows_by_month[month], columns=columns)
        if not df.empty:
            df.index = range(1, len(df) + 1)
            df.index.name = "번호"
        tables[month] = df

    return tables, unclassified


def render_empty_table() -> None:
    empty = pd.DataFrame(
        columns=["할 일", "공문 제목", "분류 근거", "상태"],
    )
    st.dataframe(empty, use_container_width=True, hide_index=True)
    st.caption("이 달에 분류된 할 일이 없습니다.")


def main() -> None:
    st.set_page_config(page_title="교사 월별 업무 정돈", layout="wide")
    st.title("교사 월별 업무 정돈")
    st.write(
        "공문 제목을 붙여넣은 뒤 **월별 업무로 분류하기**를 누르면 "
        "3월부터 다음 해 2월까지 탭으로 나누어 할 일 표를 보여 줍니다. "
        "아래 분류는 제목 키워드·날짜를 쓰는 **예시 로직**입니다."
    )

    raw_text = st.text_area(
        "공문 제목 (한 줄에 하나씩 붙여넣기)",
        value=SAMPLE_TITLES,
        height=220,
        placeholder="공문 제목을 줄바꿈으로 구분해 붙여넣으세요.",
    )

    classify_clicked = st.button("월별 업무로 분류하기", type="primary")

    if classify_clicked:
        titles = split_titles(raw_text)
        if not titles:
            st.warning("분류할 공문 제목이 없습니다. 텍스트를 입력해 주세요.")
            st.session_state.pop("classified", None)
        else:
            tables, unclassified = build_month_tables(titles)
            st.session_state["classified"] = {
                "tables": tables,
                "unclassified": unclassified,
                "title_count": len(titles),
            }

    result = st.session_state.get("classified")
    if not result:
        st.info("제목을 입력하고 버튼을 누르면 월별 탭이 생성됩니다.")
        return

    year_start = academic_year_start()
    st.success(
        f"공문 제목 {result['title_count']}건을 "
        f"{year_start}학년도(3월~{year_start + 1}년 2월) 기준으로 분류했습니다."
    )

    unclassified: list[str] = result["unclassified"]
    if unclassified:
        with st.expander(f"월을 특정하지 못한 제목 {len(unclassified)}건", expanded=True):
            st.write("날짜나 월 관련 키워드가 없어 탭에 넣지 못했습니다.")
            st.dataframe(
                pd.DataFrame({"공문 제목": unclassified}),
                use_container_width=True,
                hide_index=True,
            )

    tables: dict[int, pd.DataFrame] = result["tables"]
    tab_labels = [month_tab_label(m, year_start) for m in ACADEMIC_MONTHS]
    tabs = st.tabs(tab_labels)

    for month, tab in zip(ACADEMIC_MONTHS, tabs):
        with tab:
            df = tables[month]
            st.subheader(f"{month_tab_label(month, year_start)} 할 일")
            if df.empty:
                render_empty_table()
            else:
                st.dataframe(df, use_container_width=True)


if __name__ == "__main__":
    main()
