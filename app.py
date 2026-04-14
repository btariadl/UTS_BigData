import os
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="UTS Big Data - Dashboard", layout="wide")

st.title("Dashboard Kunjungan Puskesmas Arjowinangun (2022)")
st.caption("Output olah data dipisah: KPI bulanan + breakdown pelayanan + breakdown umur.")

BASE_DIR = os.path.dirname(__file__)

@st.cache_data
def load_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(BASE_DIR, filename)
    return pd.read_csv(path)

# ---- Load data (dengan error message yang jelas)
try:
    kpi = load_csv("kpi_monthly.csv")
    pel = load_csv("breakdown_pelayanan_year.csv")
    umur = load_csv("breakdown_umur_year.csv")
except Exception as e:
    st.error("Gagal membaca file CSV. Pastikan file ada di repo dan namanya benar.")
    st.exception(e)
    st.stop()

# ---- Normalisasi nama kolom (biar tidak KeyError gara-gara spasi/kapital)
kpi.columns = [c.strip() for c in kpi.columns]
pel.columns = [c.strip() for c in pel.columns]
umur.columns = [c.strip() for c in umur.columns]

# ---- Deteksi kolom KPI yang mungkin beda nama
# kamu pernah punya 'growth_pct' vs 'mom_growth_pct'
if "mom_growth_pct" not in kpi.columns and "growth_pct" in kpi.columns:
    kpi = kpi.rename(columns={"growth_pct": "mom_growth_pct"})

# wajib ada month dan total_visits
required_kpi_cols = {"month", "total_visits"}
missing = required_kpi_cols - set(kpi.columns)
if missing:
    st.error(f"Kolom wajib di kpi_monthly.csv tidak ada: {missing}")
    st.write("Kolom yang tersedia:", list(kpi.columns))
    st.stop()

# ---- Sidebar filter bulan
st.sidebar.header("Filter")
months = sorted(kpi["month"].dropna().unique().tolist())
sel_months = st.sidebar.multiselect("Pilih bulan", months, default=months)

k = kpi[kpi["month"].isin(sel_months)].copy()

# ---- KPI Cards
total_visits = int(k["total_visits"].sum()) if len(k) else 0
avg_month = float(k["total_visits"].mean()) if len(k) else 0

c1, c2, c3 = st.columns(3)
c1.metric("Total Kunjungan (bulan terpilih)", f"{total_visits:,}")
c2.metric("Rata-rata / bulan (bulan terpilih)", f"{avg_month:,.1f}")

# female_pct opsional
if "female_pct" in k.columns:
    c3.metric("% Perempuan (rata-rata)", f"{float(k['female_pct'].mean()):.2f}%")
else:
    c3.info("Kolom female_pct tidak ada (opsional).")

st.divider()

# ---- Tren kunjungan
st.subheader("Tren Total Kunjungan per Bulan")
fig_trend = px.line(
    kpi.sort_values("month"),
    x="month",
    y="total_visits",
    markers=True,
    labels={"month": "Bulan", "total_visits": "Total Kunjungan"},
)
st.plotly_chart(fig_trend, use_container_width=True)

# ---- MoM growth (opsional)
if "mom_growth_pct" in kpi.columns:
    st.subheader("Pertumbuhan Kunjungan Bulanan (MoM %)")
    fig_mom = px.bar(
        kpi.sort_values("month"),
        x="month",
        y="mom_growth_pct",
        labels={"month": "Bulan", "mom_growth_pct": "MoM Growth (%)"},
    )
    st.plotly_chart(fig_mom, use_container_width=True)
else:
    st.info("Kolom mom_growth_pct/growth_pct tidak ada, jadi chart MoM tidak ditampilkan.")

st.divider()

# ---- Breakdown charts
left, right = st.columns(2)

with left:
    st.subheader("Komposisi Jenis Pelayanan (Tahunan)")
    if {"sub_category", "value"} <= set(pel.columns):
        fig_pel = px.pie(pel, names="sub_category", values="value")
        st.plotly_chart(fig_pel, use_container_width=True)
    else:
        st.error("CSV breakdown_pelayanan_year.csv harus punya kolom: sub_category, value")
        st.write("Kolom tersedia:", list(pel.columns))

with right:
    st.subheader("Distribusi Umur (Tahunan)")
    if {"sub_category", "value"} <= set(umur.columns):
        umur2 = umur.copy()
        # urutan umur biar rapi (kalau cocok dengan datamu)
        umur_order = ["0-7 hr","8-28 hr","1 bl-1 th","1-4 th","5-9 th","10-14 th",
                      "15-19 th","20-44 th","45-54 th","55-59 th","60-69 th","+70 th"]
        umur2["sub_category"] = pd.Categorical(umur2["sub_category"], categories=umur_order, ordered=True)
        umur2 = umur2.sort_values("sub_category")

        fig_umur = px.bar(
            umur2,
            x="sub_category",
            y="value",
            text="value",
            labels={"sub_category": "Kelompok Umur", "value": "Kunjungan"},
        )
        fig_umur.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig_umur, use_container_width=True)
    else:
        st.error("CSV breakdown_umur_year.csv harus punya kolom: sub_category, value")
        st.write("Kolom tersedia:", list(umur.columns))

st.divider()

# ---- Tabel
st.subheader("Tabel KPI Bulanan")
st.dataframe(kpi.sort_values("month"), use_container_width=True)