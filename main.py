import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, timedelta

# ------------------------------------------------------------
# 기본 설정
# ------------------------------------------------------------
st.set_page_config(
    page_title="서울 기온 랭킹",
    page_icon="🌡️",
    layout="centered",
)

CSV_PATH = "seoul.csv"


# ------------------------------------------------------------
# 데이터 로드
# ------------------------------------------------------------
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    df["날짜"] = df["날짜"].astype(str).str.strip()
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"])
    df = df.sort_values("날짜").reset_index(drop=True)
    df["연도"] = df["날짜"].dt.year
    return df


df = load_data(CSV_PATH)
min_date = df["날짜"].min().date()
max_date = df["날짜"].max().date()


# ------------------------------------------------------------
# 스타일
# ------------------------------------------------------------
st.markdown(
    """
    <style>
    .big-title {
        font-size: 2rem;
        font-weight: 800;
        margin-bottom: 0rem;
    }
    .sub-title {
        color: #888;
        margin-bottom: 1.5rem;
    }
    .rank-card {
        background: linear-gradient(135deg, #ff9966 0%, #ff5e62 100%);
        border-radius: 20px;
        padding: 28px 24px;
        text-align: center;
        color: white;
        box-shadow: 0 8px 20px rgba(255, 94, 98, 0.25);
        margin-bottom: 1.2rem;
    }
    .rank-card.cold {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        box-shadow: 0 8px 20px rgba(79, 172, 254, 0.25);
    }
    .rank-number {
        font-size: 3rem;
        font-weight: 900;
        line-height: 1.1;
    }
    .rank-label {
        font-size: 1.05rem;
        opacity: 0.95;
        margin-top: 4px;
    }
    .metric-box {
        background: #f7f7f9;
        border-radius: 14px;
        padding: 16px;
        text-align: center;
    }
    .metric-box .v {
        font-size: 1.6rem;
        font-weight: 700;
    }
    .metric-box .l {
        color: #888;
        font-size: 0.85rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="big-title">🌡️ 서울, 이 기간은 역대 몇 위였을까?</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sub-title">서울 기상 관측 데이터 ({min_date.year}년 ~ {max_date.year}년) 기반</div>',
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# 기간(달력) 선택
# ------------------------------------------------------------
default_start = date(max_date.year - 1 if max_date.month < 8 else max_date.year, 7, 20)
default_end = default_start + timedelta(days=10)
if default_start < min_date:
    default_start = min_date
if default_end > max_date:
    default_end = max_date

date_range = st.date_input(
    "궁금한 기간을 선택하세요 (시작일 ~ 종료일)",
    value=(default_start, default_end),
    min_value=min_date,
    max_value=max_date,
)

if not isinstance(date_range, tuple) or len(date_range) != 2:
    st.info("달력에서 시작일과 종료일을 모두 선택해주세요.")
    st.stop()

start_date, end_date = date_range
if start_date > end_date:
    st.error("시작일이 종료일보다 늦을 수 없어요. 다시 선택해주세요.")
    st.stop()

period_len = (end_date - start_date).days  # 0 = 하루
n_days = period_len + 1


# ------------------------------------------------------------
# 연도별 동일 기간(월/일 기준) 평균기온 계산
# ------------------------------------------------------------
def year_period_window(year: int, start: date, length_days: int):
    """해당 연도에서 start와 같은 월/일에서 시작하는 기간의 (시작일, 종료일)을 반환"""
    month, day = start.month, start.day
    if month == 2 and day == 29:
        # 윤년이 아니면 2/28로 보정
        try:
            s = date(year, 2, 29)
        except ValueError:
            s = date(year, 2, 28)
    else:
        try:
            s = date(year, month, day)
        except ValueError:
            s = date(year, month, day - 1)
    e = s + timedelta(days=length_days)
    return s, e


@st.cache_data
def compute_period_stats(_df: pd.DataFrame, start: date, length_days: int, n_expected: int):
    years = sorted(_df["연도"].unique())
    rows = []
    for y in years:
        s, e = year_period_window(y, start, length_days)
        s_ts, e_ts = pd.Timestamp(s), pd.Timestamp(e)
        mask = (_df["날짜"] >= s_ts) & (_df["날짜"] <= e_ts)
        sub = _df.loc[mask, "평균기온"].dropna()
        # 결측이 너무 많으면(90% 미만 확보) 비교에서 제외
        if len(sub) < max(1, int(n_expected * 0.9)):
            continue
        rows.append(
            {
                "연도": y,
                "시작일": s,
                "종료일": e,
                "평균기온": round(sub.mean(), 2),
                "일수": len(sub),
            }
        )
    return pd.DataFrame(rows)


stats = compute_period_stats(df, start_date, period_len, n_days)

if stats.empty or start_date.year not in stats["연도"].values:
    st.warning("선택한 기간에 대한 비교 가능한 과거 데이터가 부족합니다. 다른 기간을 선택해보세요.")
    st.stop()

target_row = stats[stats["연도"] == start_date.year].iloc[0]
target_temp = target_row["평균기온"]

total_n = len(stats)
hot_rank = int((stats["평균기온"] > target_temp).sum()) + 1  # 더운 순위 (1위 = 가장 더움)
cold_rank = int((stats["평균기온"] < target_temp).sum()) + 1  # 추운 순위 (1위 = 가장 추움)
percentile = round((1 - (hot_rank - 1) / total_n) * 100, 1)


# ------------------------------------------------------------
# 결과 카드
# ------------------------------------------------------------
md_label = f"{start_date.month}/{start_date.day} ~ {end_date.month}/{end_date.day}"

col1, col2 = st.columns(2)
with col1:
    st.markdown(
        f"""
        <div class="rank-card">
            <div class="rank-number">{hot_rank}위</div>
            <div class="rank-label">역대 가장 더운 순위<br>(총 {total_n}개 연도 중)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        f"""
        <div class="rank-card cold">
            <div class="rank-number">{cold_rank}위</div>
            <div class="rank-label">역대 가장 추운 순위<br>(총 {total_n}개 연도 중)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

m1, m2, m3 = st.columns(3)
with m1:
    st.markdown(
        f'<div class="metric-box"><div class="v">{target_temp}°C</div>'
        f'<div class="l">{start_date.year}년 {md_label} 평균기온</div></div>',
        unsafe_allow_html=True,
    )
with m2:
    st.markdown(
        f'<div class="metric-box"><div class="v">상위 {percentile}%</div>'
        f'<div class="l">더운 기록 기준 백분위</div></div>',
        unsafe_allow_html=True,
    )
with m3:
    hottest_year = stats.loc[stats["평균기온"].idxmax(), "연도"]
    st.markdown(
        f'<div class="metric-box"><div class="v">{int(hottest_year)}년</div>'
        f'<div class="l">역대 1위 더웠던 해</div></div>',
        unsafe_allow_html=True,
    )

st.write("")


# ------------------------------------------------------------
# 전체 연도 분포 차트
# ------------------------------------------------------------
st.subheader(f"📊 역대 {md_label} 기간 평균기온 분포")

chart_df = stats.copy()
chart_df["구분"] = chart_df["연도"].apply(
    lambda y: "선택한 연도" if y == start_date.year else "그 외 연도"
)

base_chart = (
    alt.Chart(chart_df)
    .mark_bar()
    .encode(
        x=alt.X("연도:O", title="연도", sort=None),
        y=alt.Y("평균기온:Q", title="평균기온 (°C)"),
        color=alt.Color(
            "구분:N",
            scale=alt.Scale(domain=["선택한 연도", "그 외 연도"], range=["#ff5e62", "#c9c9d1"]),
            legend=alt.Legend(title=None),
        ),
        tooltip=[
            alt.Tooltip("연도:O", title="연도"),
            alt.Tooltip("평균기온:Q", title="평균기온(°C)"),
        ],
    )
    .properties(height=340)
)

st.altair_chart(base_chart, use_container_width=True)

with st.expander("🏆 역대 더운 순위 TOP 10 보기"):
    top10 = stats.sort_values("평균기온", ascending=False).head(10).reset_index(drop=True)
    top10.index = top10.index + 1
    st.dataframe(
        top10[["연도", "평균기온"]].rename(columns={"연도": "연도", "평균기온": "평균기온(°C)"}),
        use_container_width=True,
    )

with st.expander("❄️ 역대 추운 순위 TOP 10 보기"):
    bottom10 = stats.sort_values("평균기온", ascending=True).head(10).reset_index(drop=True)
    bottom10.index = bottom10.index + 1
    st.dataframe(
        bottom10[["연도", "평균기온"]].rename(columns={"연도": "연도", "평균기온": "평균기온(°C)"}),
        use_container_width=True,
    )

st.caption(
    "※ 선택한 기간과 동일한 월/일 구간을 매년 기준으로 비교했습니다. "
    "결측치가 많은 연도는 비교에서 제외될 수 있습니다."
)
