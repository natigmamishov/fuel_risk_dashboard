import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="Fuel Risk Dashboard",
    layout="wide"
)

st.title("Fuel, GPS və DUT Risk Dashboard")


@st.cache_data
def load_excel(file_name):
    return pd.read_excel(file_name)


df_overuse_with_leak = load_excel("overuse_with_leak.xlsx")
df_decrease_10plus = load_excel("decrease_10_plus.xlsx")
df_analysis = load_excel("atlas_gps_analysis.xlsx")


def generate_data_summary(df, dataset_choice, plate_col=None):
    lines = []

    lines.append(f"Seçilmiş dataset: {dataset_choice}")
    lines.append(f"Ümumi sətir sayı: {len(df)}")

    if plate_col and plate_col in df.columns:
        lines.append(f"Unikal maşın sayı: {df[plate_col].nunique()}")

    if "volume" in df.columns:
        lines.append(f"Ümumi yanacaq miqdarı: {df['volume'].sum():,.2f} litr")

    if "total_leak_liters" in df.columns:
        lines.append(f"Ümumi sızma miqdarı: {df['total_leak_liters'].sum():,.2f} litr")

    if "leak_event_count" in df.columns:
        lines.append(f"Ümumi sızma hadisəsi: {df['leak_event_count'].sum():,.0f}")

    if "actual_l_100km" in df.columns and plate_col:
        temp = df.dropna(subset=["actual_l_100km"])
        if not temp.empty:
            max_row = temp.sort_values("actual_l_100km", ascending=False).iloc[0]
            lines.append(
                f"Ən yüksək km sərfi: {max_row[plate_col]} - "
                f"{max_row['actual_l_100km']:.2f} L/100km"
            )

    if "actual_lph" in df.columns and plate_col:
        temp = df.dropna(subset=["actual_lph"])
        if not temp.empty:
            max_row = temp.sort_values("actual_lph", ascending=False).iloc[0]
            lines.append(
                f"Ən yüksək motosaat sərfi: {max_row[plate_col]} - "
                f"{max_row['actual_lph']:.2f} L/saat"
            )

    if "total_leak_liters" in df.columns and plate_col:
        top_leak = (
            df.groupby(plate_col)["total_leak_liters"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )

        lines.append("Ən çox sızma görünən maşınlar:")
        for plate, val in top_leak.items():
            lines.append(f"- {plate}: {val:.2f} litr")

    if "project" in df.columns and "total_leak_liters" in df.columns:
        top_project = (
            df.groupby("project")["total_leak_liters"]
            .sum()
            .sort_values(ascending=False)
            .head(1)
        )

        if not top_project.empty:
            lines.append(
                f"Ən yüksək sızma miqdarı olan layihə: "
                f"{top_project.index[0]} ({top_project.iloc[0]:.2f} litr)"
            )

    if "project" in df.columns and plate_col:
        top_project_vehicle = (
            df.groupby("project")[plate_col]
            .nunique()
            .sort_values(ascending=False)
            .head(1)
        )

        if not top_project_vehicle.empty:
            lines.append(
                f"Ən çox maşın görünən layihə: "
                f"{top_project_vehicle.index[0]} ({top_project_vehicle.iloc[0]} maşın)"
            )

    lines.append(
        "Yekun fikir: Bu nəticələr normadan artıq sərfiyyat və sızma hallarının "
        "eyni intervalda düşdüyü riskli halları prioritetləşdirmək üçün istifadə oluna bilər."
    )

    return "\n".join(lines)


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

st.subheader(title)

date_col = None

if "fuel_datetime" in df.columns:
    date_col = "fuel_datetime"
elif "datetime" in df.columns:
    date_col = "datetime"
elif "first_leak_datetime" in df.columns:
    date_col = "first_leak_datetime"

for col in [
    "fuel_datetime",
    "next_fuel_datetime",
    "first_leak_datetime",
    "last_leak_datetime",
    "datetime"
]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

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

plate_col = None

if "plate" in df.columns:
    plate_col = "plate"
elif "plate_clean" in df.columns:
    plate_col = "plate_clean"
elif "Grouping" in df.columns:
    plate_col = "Grouping"

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


col1, col2, col3, col4 = st.columns(4)

col1.metric("Sətir sayı", len(df))

if plate_col:
    col2.metric("Maşın sayı", df[plate_col].nunique())
else:
    col2.metric("Maşın sayı", "-")

if "volume" in df.columns:
    col3.metric("Ümumi yanacaq, litr", round(df["volume"].sum(), 2))
else:
    col3.metric("Ümumi yanacaq, litr", "-")

if "total_leak_liters" in df.columns:
    col4.metric("Ümumi sızma, litr", round(df["total_leak_liters"].sum(), 2))
elif "delta" in df.columns:
    col4.metric("Ümumi azalma, litr", round(df["delta"].abs().sum(), 2))
else:
    col4.metric("Ümumi sızma, litr", "-")

st.divider()

st.subheader("AI Summary")

if st.button("Summary yarat"):
    summary_text = generate_data_summary(df, dataset_choice, plate_col)
    st.text_area("Avtomatik analiz", summary_text, height=320)

st.divider()

st.subheader("Dataset cədvəli")
st.dataframe(df, width="stretch")

st.divider()


def get_overuse_mask(data):
    mask = pd.Series(False, index=data.index)

    if "motohour_analysis" in data.columns:
        mask = mask | data["motohour_analysis"].astype(str).str.contains(
            "yüksək|limitindən yüksək", case=False, na=False
        )

    if "km_analysis" in data.columns:
        mask = mask | data["km_analysis"].astype(str).str.contains(
            "yüksək|limitdən yüksək", case=False, na=False
        )

    return mask


leak_date_col = "first_leak_datetime" if "first_leak_datetime" in df.columns else date_col

if leak_date_col and "total_leak_liters" in df.columns:
    st.subheader("1. Tarix üzrə sızma miqdarları")

    daily_leak = (
        df.assign(date=df[leak_date_col].dt.date)
        .groupby("date", as_index=False)
        .agg(total_leak_liters=("total_leak_liters", "sum"))
        .sort_values("date")
    )

    st.bar_chart(daily_leak.set_index("date")["total_leak_liters"])
    st.dataframe(daily_leak, width="stretch")

elif date_col and "delta" in df.columns:
    st.subheader("1. Tarix üzrə sızma / azalma miqdarları")

    df_tmp = df.copy()
    df_tmp["decrease_liters"] = df_tmp["delta"].abs()

    daily_leak = (
        df_tmp.assign(date=df_tmp[date_col].dt.date)
        .groupby("date", as_index=False)
        .agg(total_decrease_liters=("decrease_liters", "sum"))
        .sort_values("date")
    )

    st.bar_chart(daily_leak.set_index("date")["total_decrease_liters"])
    st.dataframe(daily_leak, width="stretch")


if leak_date_col and plate_col and "total_leak_liters" in df.columns:
    st.subheader("2. Tarix üzrə sızma olan maşın sayı")

    daily_vehicle_count = (
        df.assign(date=df[leak_date_col].dt.date)
        .groupby("date", as_index=False)
        .agg(vehicle_count=(plate_col, "nunique"))
        .sort_values("date")
    )

    st.bar_chart(daily_vehicle_count.set_index("date")["vehicle_count"])
    st.dataframe(daily_vehicle_count, width="stretch")

elif date_col and plate_col and "delta" in df.columns:
    st.subheader("2. Tarix üzrə sızma / azalma olan maşın sayı")

    daily_vehicle_count = (
        df.assign(date=df[date_col].dt.date)
        .groupby("date", as_index=False)
        .agg(vehicle_count=(plate_col, "nunique"))
        .sort_values("date")
    )

    st.bar_chart(daily_vehicle_count.set_index("date")["vehicle_count"])
    st.dataframe(daily_vehicle_count, width="stretch")


if plate_col and "total_leak_liters" in df.columns:
    st.subheader("3. Maşın üzrə toplam sızma litri və hadisə sayı")

    vehicle_leak = (
        df.groupby(plate_col, as_index=False)
        .agg(
            total_leak_liters=("total_leak_liters", "sum"),
            leak_event_count=("leak_event_count", "sum") if "leak_event_count" in df.columns else (plate_col, "count")
        )
        .sort_values("total_leak_liters", ascending=False)
    )

    st.bar_chart(vehicle_leak.set_index(plate_col)["total_leak_liters"])
    st.dataframe(vehicle_leak, width="stretch")

elif plate_col and "delta" in df.columns:
    st.subheader("3. Maşın üzrə toplam sızma / azalma litri və hadisə sayı")

    df_tmp = df.copy()
    df_tmp["decrease_liters"] = df_tmp["delta"].abs()

    vehicle_leak = (
        df_tmp.groupby(plate_col, as_index=False)
        .agg(
            total_decrease_liters=("decrease_liters", "sum"),
            leak_event_count=("delta", "count")
        )
        .sort_values("total_decrease_liters", ascending=False)
    )

    st.bar_chart(vehicle_leak.set_index(plate_col)["total_decrease_liters"])
    st.dataframe(vehicle_leak, width="stretch")


if plate_col and ("motohour_analysis" in df.columns or "km_analysis" in df.columns):
    st.subheader("4. Maşın üzrə normadan artıq sərfiyyat sayı")

    risky_df = df[get_overuse_mask(df)].copy()

    risky_vehicle = (
        risky_df.groupby(plate_col, as_index=False)
        .size()
        .rename(columns={"size": "overuse_count"})
        .sort_values("overuse_count", ascending=False)
    )

    st.bar_chart(risky_vehicle.set_index(plate_col)["overuse_count"])
    st.dataframe(risky_vehicle, width="stretch")


if "equipment_type" in df.columns and ("motohour_analysis" in df.columns or "km_analysis" in df.columns):
    st.subheader("5. Equipment type üzrə normadan artıq hallar")

    risky_equipment = (
        df[get_overuse_mask(df)]
        .groupby("equipment_type", as_index=False)
        .size()
        .rename(columns={"size": "risk_count"})
        .sort_values("risk_count", ascending=False)
    )

    st.bar_chart(risky_equipment.set_index("equipment_type")["risk_count"])
    st.dataframe(risky_equipment, width="stretch")


if "actual_lph" in df.columns and "normal_lph" in df.columns:
    st.subheader("6. Motosaat üzrə actual_lph vs normal_lph")

    compare_lph_cols = [
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

    compare_lph = df[compare_lph_cols].dropna(subset=["actual_lph"])
    st.dataframe(compare_lph.sort_values("actual_lph", ascending=False), width="stretch")


if "actual_l_100km" in df.columns and "flat_l_100km" in df.columns:
    st.subheader("7. Km üzrə actual_l_100km vs flat/mountain normativ")

    compare_km_cols = [
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

    compare_km = df[compare_km_cols].dropna(subset=["actual_l_100km"])
    st.dataframe(compare_km.sort_values("actual_l_100km", ascending=False), width="stretch")


if "total_leak_liters" in df.columns:
    st.subheader("8. Overuse + Leak eyni intervalda olan riskli hallar")

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


if "project" in df.columns:
    st.subheader("9. Layihə üzrə bölgü")

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

    if metric_choice == "Sətir sayı":
        project_summary = temp.groupby("project", as_index=False).size().rename(columns={"size": "value"})
        title = "Project üzrə sətir sayı"

    elif metric_choice == "Unikal maşın sayı" and plate_col:
        project_summary = temp.groupby("project", as_index=False).agg(value=(plate_col, "nunique"))
        title = "Project üzrə unikal maşın sayı"

    elif metric_choice == "Ümumi sızma litri" and "total_leak_liters" in temp.columns:
        project_summary = temp.groupby("project", as_index=False).agg(value=("total_leak_liters", "sum"))
        title = "Project üzrə ümumi sızma litri"

    elif metric_choice == "Normadan artıq hallar":
        temp = temp[get_overuse_mask(temp)]
        project_summary = temp.groupby("project", as_index=False).size().rename(columns={"size": "value"})
        title = "Project üzrə normadan artıq hallar"

    else:
        project_summary = temp.groupby("project", as_index=False).size().rename(columns={"size": "value"})
        title = "Project üzrə bölgü"

    project_summary = project_summary.sort_values("value", ascending=False)

    fig = px.pie(project_summary, names="project", values="value", title=title, hole=0.35)
    st.plotly_chart(fig, width="stretch")
    st.dataframe(project_summary, width="stretch")


if "point" in df.columns:
    st.subheader("10. Point üzrə bölgü")

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

    if point_metric == "Sətir sayı":
        point_summary = temp.groupby("point", as_index=False).size().rename(columns={"size": "value"})
        title = "Point üzrə sətir sayı"

    elif point_metric == "Unikal maşın sayı" and plate_col:
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
        title = "Point üzrə bölgü"

    point_summary = point_summary.sort_values("value", ascending=False)

    fig = px.pie(point_summary, names="point", values="value", title=title, hole=0.35)
    st.plotly_chart(fig, width="stretch")
    st.dataframe(point_summary, width="stretch")


if date_col and "project" in df.columns and plate_col:
    st.subheader("11. Tarix və layihə üzrə maşın sayı")

    temp = df.copy()
    temp["date"] = temp[date_col].dt.date

    project_daily = (
        temp.groupby(["date", "project"], as_index=False)
        .agg(vehicle_count=(plate_col, "nunique"))
        .sort_values(["date", "vehicle_count"], ascending=[True, False])
    )

    st.dataframe(project_daily, width="stretch")

    fig = px.bar(
        project_daily,
        x="date",
        y="vehicle_count",
        color="project",
        title="Tarix üzrə layihələrdə maşın sayı",
        barmode="stack"
    )

    st.plotly_chart(fig, width="stretch")