import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

st.set_page_config(
    page_title="Fuel Risk Dashboard",
    layout="wide"
)

# =========================
# STYLE
# =========================

st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}
.main-title {
    font-size: 42px;
    font-weight: 800;
    color: #1f2937;
    margin-bottom: 0px;
}
.subtitle {
    font-size: 16px;
    color: #6b7280;
    margin-bottom: 25px;
}
.section-card {
    background-color: #f8fafc;
    padding: 18px 22px;
    border-radius: 18px;
    border: 1px solid #e5e7eb;
    margin-bottom: 20px;
}
.risk-box {
    background-color: #fff7ed;
    border-left: 6px solid #f97316;
    padding: 16px 20px;
    border-radius: 12px;
    margin-bottom: 18px;
}
.ai-box {
    background-color: #eef2ff;
    border-left: 6px solid #4f46e5;
    padding: 16px 20px;
    border-radius: 12px;
    margin-bottom: 18px;
    white-space: pre-line;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">Fuel, GPS və DUT Risk Dashboard</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Yanacaq sərfiyyatı, GPS motosaat/km, DUT sızma və risk analitikası</div>',
    unsafe_allow_html=True
)

# =========================
# DATA LOAD
# =========================

@st.cache_data
def load_excel(file_name):
    return pd.read_excel(file_name)

df_overuse_with_leak = load_excel("overuse_with_leak.xlsx")
df_decrease_10plus = load_excel("decrease_10_plus.xlsx")
df_analysis = load_excel("atlas_gps_analysis.xlsx")

# =========================
# HELPERS
# =========================

def get_date_col(df):
    if "fuel_datetime" in df.columns:
        return "fuel_datetime"
    if "datetime" in df.columns:
        return "datetime"
    if "first_leak_datetime" in df.columns:
        return "first_leak_datetime"
    return None


def get_plate_col(df):
    if "plate" in df.columns:
        return "plate"
    if "plate_clean" in df.columns:
        return "plate_clean"
    if "Grouping" in df.columns:
        return "Grouping"
    return None


def prepare_dates(df):
    for col in [
        "fuel_datetime",
        "next_fuel_datetime",
        "first_leak_datetime",
        "last_leak_datetime",
        "datetime"
    ]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def get_overuse_mask(data):
    mask = pd.Series(False, index=data.index)

    if "motohour_analysis" in data.columns:
        mask = mask | data["motohour_analysis"].astype(str).str.contains(
            "yüksək|limitindən yüksək|limitdən yüksək", case=False, na=False
        )

    if "km_analysis" in data.columns:
        mask = mask | data["km_analysis"].astype(str).str.contains(
            "yüksək|limitindən yüksək|limitdən yüksək", case=False, na=False
        )

    return mask


def build_attention_table(df, plate_col):
    if not plate_col or df.empty:
        return pd.DataFrame()

    temp = df.copy()

    temp["risk_score"] = 0

    if "total_leak_liters" in temp.columns:
        temp["risk_score"] += temp["total_leak_liters"].fillna(0) * 1.0

    if "leak_event_count" in temp.columns:
        temp["risk_score"] += temp["leak_event_count"].fillna(0) * 10

    if "actual_l_100km" in temp.columns:
        temp["risk_score"] += temp["actual_l_100km"].fillna(0) * 0.5

    if "actual_lph" in temp.columns:
        temp["risk_score"] += temp["actual_lph"].fillna(0) * 2

    if "motohour_analysis" in temp.columns or "km_analysis" in temp.columns:
        temp["overuse_flag"] = get_overuse_mask(temp).astype(int)
        temp["risk_score"] += temp["overuse_flag"] * 50

    agg_dict = {
        "risk_score": ("risk_score", "sum"),
        "record_count": (plate_col, "count")
    }

    if "total_leak_liters" in temp.columns:
        agg_dict["total_leak_liters"] = ("total_leak_liters", "sum")

    if "leak_event_count" in temp.columns:
        agg_dict["leak_event_count"] = ("leak_event_count", "sum")

    if "volume" in temp.columns:
        agg_dict["total_volume"] = ("volume", "sum")

    if "actual_l_100km" in temp.columns:
        agg_dict["max_l_100km"] = ("actual_l_100km", "max")

    if "actual_lph" in temp.columns:
        agg_dict["max_lph"] = ("actual_lph", "max")

    if "equipment_type" in temp.columns:
        agg_dict["equipment_type"] = ("equipment_type", "first")

    if "project" in temp.columns:
        agg_dict["project"] = ("project", "first")

    result = (
        temp.groupby(plate_col, as_index=False)
        .agg(**agg_dict)
        .sort_values("risk_score", ascending=False)
        .head(15)
    )

    return result


def generate_ai_summary(df, dataset_choice, plate_col):
    lines = []

    lines.append("📌 Ümumi baxış")
    lines.append(f"- Seçilmiş dataset: {dataset_choice}")
    lines.append(f"- Sətir sayı: {len(df)}")

    if plate_col:
        lines.append(f"- Unikal maşın sayı: {df[plate_col].nunique()}")

    if "volume" in df.columns:
        lines.append(f"- Ümumi yanacaq həcmi: {df['volume'].sum():,.2f} litr")

    if "total_leak_liters" in df.columns:
        lines.append(f"- Ümumi sızma/azalma həcmi: {df['total_leak_liters'].sum():,.2f} litr")

    elif "delta" in df.columns:
        lines.append(f"- Ümumi DUT azalma həcmi: {df['delta'].abs().sum():,.2f} litr")

    lines.append("")
    lines.append("⚠️ Risk analizi")

    if plate_col:
        attention = build_attention_table(df, plate_col)

        if not attention.empty:
            top = attention.iloc[0]
            lines.append(
                f"- Ən çox diqqət tələb edən maşın: {top[plate_col]} "
                f"(risk score: {top['risk_score']:.1f})"
            )

            if "total_leak_liters" in attention.columns:
                lines.append(
                    f"- Bu maşın üzrə sızma/azalma həcmi: "
                    f"{top.get('total_leak_liters', 0):,.2f} litr"
                )

    if "motohour_analysis" in df.columns or "km_analysis" in df.columns:
        overuse_count = int(get_overuse_mask(df).sum())
        lines.append(f"- Normadan artıq sərfiyyat görünən interval sayı: {overuse_count}")

    if "total_leak_liters" in df.columns and "leak_event_count" in df.columns:
        high_leak = df[df["total_leak_liters"] >= df["total_leak_liters"].quantile(0.75)]
        lines.append(f"- Yüksək sızma həcmi olan interval sayı: {len(high_leak)}")

    lines.append("")
    lines.append("📈 Trend müşahidəsi")

    date_col = get_date_col(df)
    leak_date_col = "first_leak_datetime" if "first_leak_datetime" in df.columns else date_col

    if leak_date_col and leak_date_col in df.columns:
        temp = df.copy()
        temp[leak_date_col] = pd.to_datetime(temp[leak_date_col], errors="coerce")
        temp = temp.dropna(subset=[leak_date_col])

        if "total_leak_liters" in temp.columns and not temp.empty:
            daily = (
                temp.assign(date=temp[leak_date_col].dt.date)
                .groupby("date")["total_leak_liters"]
                .sum()
                .sort_index()
            )

            if len(daily) >= 2:
                first_val = daily.iloc[0]
                last_val = daily.iloc[-1]

                if last_val > first_val:
                    trend = "artan"
                elif last_val < first_val:
                    trend = "azalan"
                else:
                    trend = "stabil"

                lines.append(f"- Seçilmiş aralıqda sızma trendi: {trend}")
                lines.append(f"- Maksimum gündəlik sızma: {daily.max():,.2f} litr")

        elif "delta" in temp.columns and not temp.empty:
            daily = (
                temp.assign(date=temp[leak_date_col].dt.date)
                .groupby("date")["delta"]
                .apply(lambda x: x.abs().sum())
                .sort_index()
            )

            if len(daily) >= 2:
                lines.append(f"- Maksimum gündəlik DUT azalma: {daily.max():,.2f} litr")

    lines.append("")
    lines.append("✅ Tövsiyə")

    lines.append("- Risk score-u yüksək olan maşınlar üzrə ayrıca yoxlama aparılsın.")
    lines.append("- Sızma hadisəsi ilə normadan artıq sərfiyyat eyni intervala düşürsə, həmin hal prioritet araşdırılsın.")
    lines.append("- Layihə və point üzrə təkrarlanan risklər ayrıca izlənilsin.")
    lines.append("- Çox yüksək L/100km və L/saat dəyərlərində sensor, km datası və faktiki iş rejimi ayrıca yoxlanılsın.")

    return "\n".join(lines)

# =========================
# SIDEBAR
# =========================

st.sidebar.header("Filterlər")

dataset_choice = st.sidebar.selectbox(
    "Dataset seç",
    [
        "Overuse + Leak",
        "Leak Events",
        "Atlas + GPS Analysis"
    ]
)

if dataset_choice == "Overuse + Leak":
    df = df_overuse_with_leak.copy()
    title = "Overuse + Leak: Normadan artıq sərfiyyat + sızma"
elif dataset_choice == "Leak Events":
    df = df_decrease_10plus.copy()
    title = "Leak Events: DUT sızma hadisələri"
else:
    df = df_analysis.copy()
    title = "Atlas + GPS Analysis: Yanacaq və normativ analizi"

df = prepare_dates(df)
date_col = get_date_col(df)
plate_col = get_plate_col(df)

# =========================
# FILTERS
# =========================

if date_col and df[date_col].notna().any():
    min_date = df[date_col].min().date()
    max_date = df[date_col].max().date()

    date_range = st.sidebar.date_input(
        "Tarix aralığı",
        [min_date, max_date]
    )

    if len(date_range) == 2:
        start_date, end_date = date_range
        df = df[
            (df[date_col].dt.date >= start_date) &
            (df[date_col].dt.date <= end_date)
        ]

if plate_col:
    selected_plates = st.sidebar.multiselect(
        "Maşın seç",
        sorted(df[plate_col].dropna().astype(str).unique())
    )

    if selected_plates:
        df = df[df[plate_col].astype(str).isin(selected_plates)]

if "equipment_type" in df.columns:
    selected_types = st.sidebar.multiselect(
        "Texnika tipi seç",
        sorted(df["equipment_type"].dropna().astype(str).unique())
    )

    if selected_types:
        df = df[df["equipment_type"].astype(str).isin(selected_types)]

if "project" in df.columns:
    selected_projects = st.sidebar.multiselect(
        "Layihə seç",
        sorted(df["project"].dropna().astype(str).unique())
    )

    if selected_projects:
        df = df[df["project"].astype(str).isin(selected_projects)]

if "point" in df.columns:
    selected_points = st.sidebar.multiselect(
        "Yanacaq məntəqəsi / point seç",
        sorted(df["point"].dropna().astype(str).unique())
    )

    if selected_points:
        df = df[df["point"].astype(str).isin(selected_points)]

# =========================
# HEADER
# =========================

st.markdown(f"### {title}")

# =========================
# KPI CARDS
# =========================

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Sətir sayı", len(df))

if plate_col:
    col2.metric("Maşın sayı", df[plate_col].nunique())
else:
    col2.metric("Maşın sayı", "-")

if "volume" in df.columns:
    col3.metric("Ümumi yanacaq", f"{df['volume'].sum():,.0f} L")
else:
    col3.metric("Ümumi yanacaq", "-")

if "total_leak_liters" in df.columns:
    col4.metric("Ümumi sızma", f"{df['total_leak_liters'].sum():,.0f} L")
elif "delta" in df.columns:
    col4.metric("Ümumi azalma", f"{df['delta'].abs().sum():,.0f} L")
else:
    col4.metric("Ümumi sızma", "-")

if "motohour_analysis" in df.columns or "km_analysis" in df.columns:
    col5.metric("Normadan artıq hallar", int(get_overuse_mask(df).sum()))
else:
    col5.metric("Normadan artıq hallar", "-")

st.divider()

# =========================
# TOP ATTENTION VEHICLES
# =========================

st.markdown("## Top diqqət edilməli maşınlar")

attention_table = build_attention_table(df, plate_col)

if not attention_table.empty:
    st.markdown(
        '<div class="risk-box">Bu siyahı sızma həcmi, sızma sayı, normadan artıq sərfiyyat və faktiki sərf dəyərlərinə əsasən hesablanır.</div>',
        unsafe_allow_html=True
    )

    st.dataframe(attention_table, width="stretch")

    fig = px.bar(
        attention_table,
        x=plate_col,
        y="risk_score",
        color="risk_score",
        title="Top risk score üzrə maşınlar"
    )
    st.plotly_chart(fig, width="stretch")
else:
    st.info("Bu dataset üçün top risk cədvəli formalaşdırmaq mümkün olmadı.")

st.divider()

# =========================
# AI SUMMARY
# =========================

st.markdown("## AI Summary")

if st.button("Risk, trend və məsləhət yarat"):
    summary_text = generate_ai_summary(df, dataset_choice, plate_col)
    st.markdown(f'<div class="ai-box">{summary_text}</div>', unsafe_allow_html=True)

st.divider()

# =========================
# DATA TABLE
# =========================

with st.expander("Dataset cədvəlini göstər", expanded=False):
    st.dataframe(df, width="stretch")

st.divider()

# =========================
# ANALYTICS
# =========================

leak_date_col = "first_leak_datetime" if "first_leak_datetime" in df.columns else date_col

# 1
if leak_date_col and "total_leak_liters" in df.columns:
    st.markdown("## 1. Tarix üzrə sızma miqdarları")

    daily_leak = (
        df.assign(date=df[leak_date_col].dt.date)
        .groupby("date", as_index=False)
        .agg(total_leak_liters=("total_leak_liters", "sum"))
        .sort_values("date")
    )

    fig = px.bar(
        daily_leak,
        x="date",
        y="total_leak_liters",
        title="Tarix üzrə sızma miqdarı"
    )
    st.plotly_chart(fig, width="stretch")
    st.dataframe(daily_leak, width="stretch")

elif date_col and "delta" in df.columns:
    st.markdown("## 1. Tarix üzrə DUT azalma miqdarları")

    temp = df.copy()
    temp["decrease_liters"] = temp["delta"].abs()

    daily_decrease = (
        temp.assign(date=temp[date_col].dt.date)
        .groupby("date", as_index=False)
        .agg(total_decrease_liters=("decrease_liters", "sum"))
        .sort_values("date")
    )

    fig = px.bar(
        daily_decrease,
        x="date",
        y="total_decrease_liters",
        title="Tarix üzrə DUT azalma miqdarı"
    )
    st.plotly_chart(fig, width="stretch")
    st.dataframe(daily_decrease, width="stretch")

# 2
if leak_date_col and plate_col and "total_leak_liters" in df.columns:
    st.markdown("## 2. Tarix üzrə sızma olan maşın sayı")

    daily_vehicle_count = (
        df.assign(date=df[leak_date_col].dt.date)
        .groupby("date", as_index=False)
        .agg(vehicle_count=(plate_col, "nunique"))
        .sort_values("date")
    )

    fig = px.line(
        daily_vehicle_count,
        x="date",
        y="vehicle_count",
        markers=True,
        title="Tarix üzrə sızma olan maşın sayı"
    )
    st.plotly_chart(fig, width="stretch")
    st.dataframe(daily_vehicle_count, width="stretch")

# 3
if plate_col and "total_leak_liters" in df.columns:
    st.markdown("## 3. Maşın üzrə toplam sızma litri və hadisə sayı")

    vehicle_leak = (
        df.groupby(plate_col, as_index=False)
        .agg(
            total_leak_liters=("total_leak_liters", "sum"),
            leak_event_count=("leak_event_count", "sum") if "leak_event_count" in df.columns else (plate_col, "count")
        )
        .sort_values("total_leak_liters", ascending=False)
    )

    fig = px.bar(
        vehicle_leak.head(20),
        x=plate_col,
        y="total_leak_liters",
        color="leak_event_count",
        title="Top maşınlar üzrə sızma litri"
    )
    st.plotly_chart(fig, width="stretch")
    st.dataframe(vehicle_leak, width="stretch")

elif plate_col and "delta" in df.columns:
    st.markdown("## 3. Maşın üzrə toplam DUT azalma")

    temp = df.copy()
    temp["decrease_liters"] = temp["delta"].abs()

    vehicle_decrease = (
        temp.groupby(plate_col, as_index=False)
        .agg(
            total_decrease_liters=("decrease_liters", "sum"),
            event_count=("delta", "count")
        )
        .sort_values("total_decrease_liters", ascending=False)
    )

    fig = px.bar(
        vehicle_decrease.head(20),
        x=plate_col,
        y="total_decrease_liters",
        color="event_count",
        title="Top maşınlar üzrə DUT azalma"
    )
    st.plotly_chart(fig, width="stretch")
    st.dataframe(vehicle_decrease, width="stretch")

# 4
if plate_col and ("motohour_analysis" in df.columns or "km_analysis" in df.columns):
    st.markdown("## 4. Maşın üzrə normadan artıq sərfiyyat sayı")

    risky_df = df[get_overuse_mask(df)].copy()

    risky_vehicle = (
        risky_df.groupby(plate_col, as_index=False)
        .size()
        .rename(columns={"size": "overuse_count"})
        .sort_values("overuse_count", ascending=False)
    )

    fig = px.bar(
        risky_vehicle.head(20),
        x=plate_col,
        y="overuse_count",
        title="Top maşınlar üzrə normadan artıq sərfiyyat sayı"
    )
    st.plotly_chart(fig, width="stretch")
    st.dataframe(risky_vehicle, width="stretch")

# 5
if "equipment_type" in df.columns and ("motohour_analysis" in df.columns or "km_analysis" in df.columns):
    st.markdown("## 5. Equipment type üzrə normadan artıq hallar")

    risky_equipment = (
        df[get_overuse_mask(df)]
        .groupby("equipment_type", as_index=False)
        .size()
        .rename(columns={"size": "risk_count"})
        .sort_values("risk_count", ascending=False)
    )

    fig = px.pie(
        risky_equipment,
        names="equipment_type",
        values="risk_count",
        title="Equipment type üzrə risk bölgüsü",
        hole=0.35
    )
    st.plotly_chart(fig, width="stretch")
    st.dataframe(risky_equipment, width="stretch")

# 6
if "actual_lph" in df.columns and "normal_lph" in df.columns:
    st.markdown("## 6. Motosaat üzrə actual_lph vs normal_lph")

    cols = [
        c for c in [
            plate_col,
            "equipment_type",
            "project",
            "point",
            "fuel_datetime",
            "volume",
            "work_hours_until_next_fuel",
            "actual_lph",
            "normal_lph",
            "heavy_lph",
            "motohour_analysis"
        ]
        if c in df.columns and c is not None
    ]

    compare_lph = df[cols].dropna(subset=["actual_lph"])

    if not compare_lph.empty:
        fig = px.scatter(
            compare_lph,
            x="normal_lph",
            y="actual_lph",
            color="motohour_analysis" if "motohour_analysis" in compare_lph.columns else None,
            hover_data=cols,
            title="Actual LPH vs Normal LPH"
        )
        st.plotly_chart(fig, width="stretch")

    st.dataframe(compare_lph.sort_values("actual_lph", ascending=False), width="stretch")

# 7
if "actual_l_100km" in df.columns and "flat_l_100km" in df.columns:
    st.markdown("## 7. Km üzrə actual_l_100km vs flat/mountain normativ")

    cols = [
        c for c in [
            plate_col,
            "equipment_type",
            "project",
            "point",
            "fuel_datetime",
            "volume",
            "mileage_until_next_fuel_km",
            "actual_l_100km",
            "flat_l_100km",
            "mountain_l_100km",
            "km_analysis"
        ]
        if c in df.columns and c is not None
    ]

    compare_km = df[cols].dropna(subset=["actual_l_100km"])

    if not compare_km.empty:
        fig = px.scatter(
            compare_km,
            x="flat_l_100km",
            y="actual_l_100km",
            color="km_analysis" if "km_analysis" in compare_km.columns else None,
            hover_data=cols,
            title="Actual L/100km vs Flat Norm"
        )
        st.plotly_chart(fig, width="stretch")

    st.dataframe(compare_km.sort_values("actual_l_100km", ascending=False), width="stretch")

# 8
if "total_leak_liters" in df.columns:
    st.markdown("## 8. Overuse + Leak eyni intervalda olan riskli hallar")

    risk_cols = [
        c for c in [
            "plate",
            "equipment_type",
            "project",
            "point",
            "fuel_datetime",
            "next_fuel_datetime",
            "volume",
            "work_hours_until_next_fuel",
            "mileage_until_next_fuel_km",
            "actual_lph",
            "actual_l_100km",
            "motohour_analysis",
            "km_analysis",
            "leak_event_count",
            "total_leak_liters",
            "first_leak_datetime",
            "last_leak_datetime"
        ]
        if c in df.columns
    ]

    risky_table = df[get_overuse_mask(df)].copy()

    if "total_leak_liters" in risky_table.columns:
        risky_table = risky_table.sort_values("total_leak_liters", ascending=False)

    st.dataframe(risky_table[risk_cols], width="stretch")

# Project pie
if "project" in df.columns:
    st.markdown("## Layihə üzrə risk bölgüsü")

    metric_choice = st.selectbox(
        "Project qrafiki üçün ölçü seç",
        [
            "Sətir sayı",
            "Unikal maşın sayı",
            "Ümumi sızma litri",
            "Normadan artıq hallar"
        ]
    )

    temp = df.copy()

    if metric_choice == "Unikal maşın sayı" and plate_col:
        project_summary = temp.groupby("project", as_index=False).agg(value=(plate_col, "nunique"))
        title = "Layihə üzrə unikal maşın sayı"
    elif metric_choice == "Ümumi sızma litri" and "total_leak_liters" in temp.columns:
        project_summary = temp.groupby("project", as_index=False).agg(value=("total_leak_liters", "sum"))
        title = "Layihə üzrə ümumi sızma litri"
    elif metric_choice == "Normadan artıq hallar":
        temp = temp[get_overuse_mask(temp)]
        project_summary = temp.groupby("project", as_index=False).size().rename(columns={"size": "value"})
        title = "Layihə üzrə normadan artıq hallar"
    else:
        project_summary = temp.groupby("project", as_index=False).size().rename(columns={"size": "value"})
        title = "Layihə üzrə sətir sayı"

    project_summary = project_summary.sort_values("value", ascending=False)

    fig = px.pie(
        project_summary,
        names="project",
        values="value",
        title=title,
        hole=0.35
    )
    st.plotly_chart(fig, width="stretch")
    st.dataframe(project_summary, width="stretch")

# Point pie
if "point" in df.columns:
    st.markdown("## Point üzrə risk bölgüsü")

    point_metric = st.selectbox(
        "Point qrafiki üçün ölçü seç",
        [
            "Sətir sayı",
            "Unikal maşın sayı",
            "Ümumi yanacaq litri",
            "Ümumi sızma litri",
            "Normadan artıq hallar"
        ]
    )

    temp = df.copy()

    if point_metric == "Unikal maşın sayı" and plate_col:
        point_summary = temp.groupby("point", as_index=False).agg(value=(plate_col, "nunique"))
        title = "Point üzrə unikal maşın sayı"
    elif point_metric == "Ümumi yanacaq litri" and "volume" in temp.columns:
        point_summary = temp.groupby("point", as_index=False).agg(value=("volume", "sum"))
        title = "Point üzrə ümumi yanacaq litri"
    elif point_metric == "Ümumi sızma litri" and "total_leak_liters" in temp.columns:
        point_summary = temp.groupby("point", as_index=False).agg(value=("total_leak_liters", "sum"))
        title = "Point üzrə ümumi sızma litri"
    elif point_metric == "Normadan artıq hallar":
        temp = temp[get_overuse_mask(temp)]
        point_summary = temp.groupby("point", as_index=False).size().rename(columns={"size": "value"})
        title = "Point üzrə normadan artıq hallar"
    else:
        point_summary = temp.groupby("point", as_index=False).size().rename(columns={"size": "value"})
        title = "Point üzrə sətir sayı"

    point_summary = point_summary.sort_values("value", ascending=False)

    fig = px.pie(
        point_summary,
        names="point",
        values="value",
        title=title,
        hole=0.35
    )
    st.plotly_chart(fig, width="stretch")
    st.dataframe(point_summary, width="stretch")