import os
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="UTS Big Data - Dashboard", layout="wide")

st.title("Dashboard Kunjungan Puskesmas Arjowinangun (2022)")
st.caption("Output olah data dipisah: KPI bulanan + breakdown pelayanan + breakdown umur.")

BASE_DIR = os.path.dirname(__file__)

MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
    7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des"
}

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

# ---- Deteksi kolom KPI yang mungkin beda nama (legacy)
if "mom_growth_pct" not in kpi.columns and "growth_pct" in kpi.columns:
    kpi = kpi.rename(columns={"growth_pct": "mom_growth_pct"})

# ---- Validasi kolom wajib
required_kpi_cols = {"month", "total_visits"}
missing = required_kpi_cols - set(kpi.columns)
if missing:
    st.error(f"Kolom wajib di kpi_monthly.csv tidak ada: {missing}")
    st.write("Kolom yang tersedia:", list(kpi.columns))
    st.stop()

# ---- Enrich month label
kpi["month"] = pd.to_numeric(kpi["month"], errors="coerce")
kpi["month_name"] = kpi["month"].map(MONTH_NAMES)

# ---- Sidebar filter bulan
st.sidebar.header("Filter")
months = sorted([m for m in kpi["month"].dropna().unique().tolist() if int(m) in MONTH_NAMES])
sel_months = st.sidebar.multiselect("Pilih bulan", months, default=months)

k = kpi[kpi["month"].isin(sel_months)].copy()

# ---- KPI helper
def safe_mean(df: pd.DataFrame, col: str) -> float | None:
    if col in df.columns and len(df):
        return float(pd.to_numeric(df[col], errors="coerce").mean())
    return None

# =========================
# Tabs layout
# =========================
tab1, tab2, tab3 = st.tabs(["📌 KPI Overview", "📈 Tren Bulanan", "🧩 Breakdown Tahunan"])

# =========================
# TAB 1: KPI Overview
# =========================
with tab1:
    st.subheader("Ringkasan KPI (bulan terpilih)")

    total_visits = int(k["total_visits"].sum()) if len(k) else 0
    avg_month = float(k["total_visits"].mean()) if len(k) else 0

    # Peak & low month (di bulan terpilih)
    if len(k):
        peak = k.loc[k["total_visits"].idxmax()]
        low = k.loc[k["total_visits"].idxmin()]
        peak_label = f"{int(peak['month'])} ({MONTH_NAMES.get(int(peak['month']), '-')})"
        low_label = f"{int(low['month'])} ({MONTH_NAMES.get(int(low['month']), '-')})"
    else:
        peak = low = None
        peak_label = low_label = "-"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Kunjungan", f"{total_visits:,}")
    c2.metric("Rata-rata / Bulan", f"{avg_month:,.1f}")

    if peak is not None:
        c3.metric("Bulan Tertinggi", peak_label, f"{int(peak['total_visits']):,}")
    else:
        c3.metric("Bulan Tertinggi", "-")

    if low is not None:
        c4.metric("Bulan Terendah", low_label, f"{int(low['total_visits']):,}")
    else:
        c4.metric("Bulan Terendah", "-")

    st.divider()

    # KPI opsional: % perempuan
    female_avg = safe_mean(k, "female_pct")
    new_avg = safe_mean(k, "new_pct")
    old_avg = safe_mean(k, "old_pct")

    c5, c6, c7 = st.columns(3)
    if female_avg is not None:
        c5.metric("% Perempuan (rata-rata)", f"{female_avg:.2f}%")
    else:
        c5.info("female_pct tidak tersedia")

    if new_avg is not None:
        c6.metric("% Pasien Baru (rata-rata)", f"{new_avg:.2f}%")
    else:
        c6.info("new_pct tidak tersedia")

    if old_avg is not None:
        c7.metric("% Pasien Lama (rata-rata)", f"{old_avg:.2f}%")
    else:
        c7.info("old_pct tidak tersedia")

    # DW% (dihitung dari total)
    if {"dw_total", "total_visits"} <= set(k.columns) and len(k):
        dw_pct_avg = float((k["dw_total"] / k["total_visits"] * 100).mean())
        st.metric("% Dalam Wilayah (DW) (rata-rata)", f"{dw_pct_avg:.2f}%")

    st.markdown(
        "**Interpretasi singkat:** KPI ini membantu melihat beban layanan, bulan puncak/terendah, "
        "serta karakteristik pasien (gender, baru/lama, DW/LW) untuk perencanaan SDM dan program."
    )

# =========================
# TAB 2: Tren Bulanan
# =========================
with tab2:
    st.subheader("Tren Total Kunjungan per Bulan")
    fig_trend = px.line(
        kpi.sort_values("month"),
        x="month_name",
        y="total_visits",
        markers=True,
        labels={"month_name": "Bulan", "total_visits": "Total Kunjungan"},
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    # ---- MoM growth
    if "mom_growth_pct" in kpi.columns:
        st.subheader("Pertumbuhan Kunjungan Bulanan (MoM %)")
        fig_mom = px.bar(
            kpi.sort_values("month"),
            x="month_name",
            y="mom_growth_pct",
            labels={"month_name": "Bulan", "mom_growth_pct": "MoM Growth (%)"},
        )
        st.plotly_chart(fig_mom, use_container_width=True)
    else:
        st.info("Kolom mom_growth_pct tidak ada, chart MoM tidak ditampilkan.")

    st.divider()

    # ---- Gender % trend
    if "female_pct" in kpi.columns:
        st.subheader("Persentase Kunjungan Perempuan per Bulan")
        fig_gender = px.line(
            kpi.sort_values("month"),
            x="month_name",
            y="female_pct",
            markers=True,
            labels={"month_name": "Bulan", "female_pct": "% Perempuan"},
        )
        st.plotly_chart(fig_gender, use_container_width=True)

    # ---- Baru vs Lama (stacked)
    if {"new_total", "old_total"} <= set(kpi.columns):
        st.subheader("Pasien Baru vs Pasien Lama (per bulan)")
        tmp_newold = kpi.sort_values("month")[["month_name", "new_total", "old_total"]].melt(
            id_vars="month_name", var_name="kategori", value_name="kunjungan"
        )
        tmp_newold["kategori"] = tmp_newold["kategori"].replace({
            "new_total": "Pasien Baru",
            "old_total": "Pasien Lama",
        })
        fig_newold = px.bar(
            tmp_newold,
            x="month_name",
            y="kunjungan",
            color="kategori",
            barmode="stack",
            labels={"month_name": "Bulan", "kunjungan": "Jumlah Kunjungan", "kategori": ""},
        )
        st.plotly_chart(fig_newold, use_container_width=True)

    # ---- DW vs LW (stacked)
    if {"dw_total", "lw_total"} <= set(kpi.columns):
        st.subheader("Dalam Wilayah (DW) vs Luar Wilayah (LW) (per bulan)")
        tmp_dwlw = kpi.sort_values("month")[["month_name", "dw_total", "lw_total"]].melt(
            id_vars="month_name", var_name="wilayah", value_name="kunjungan"
        )
        tmp_dwlw["wilayah"] = tmp_dwlw["wilayah"].replace({
            "dw_total": "Dalam Wilayah (DW)",
            "lw_total": "Luar Wilayah (LW)",
        })
        fig_dwlw = px.bar(
            tmp_dwlw,
            x="month_name",
            y="kunjungan",
            color="wilayah",
            barmode="stack",
            labels={"month_name": "Bulan", "kunjungan": "Jumlah Kunjungan", "wilayah": ""},
        )
        st.plotly_chart(fig_dwlw, use_container_width=True)

    st.divider()

    # ---- Persentase tambahan (lebih “KPI banget”)
    c1, c2 = st.columns(2)

    with c1:
        if "new_pct" in kpi.columns:
            st.subheader("% Pasien Baru per Bulan")
            fig_newpct = px.line(
                kpi.sort_values("month"),
                x="month_name",
                y="new_pct",
                markers=True,
                labels={"month_name": "Bulan", "new_pct": "% Pasien Baru"},
            )
            st.plotly_chart(fig_newpct, use_container_width=True)

    with c2:
        if {"dw_total", "total_visits"} <= set(kpi.columns):
            kpi2 = kpi.copy()
            kpi2["dw_pct"] = (kpi2["dw_total"] / kpi2["total_visits"] * 100).round(2)
            st.subheader("% Dalam Wilayah (DW) per Bulan")
            fig_dwpct = px.line(
                kpi2.sort_values("month"),
                x="month_name",
                y="dw_pct",
                markers=True,
                labels={"month_name": "Bulan", "dw_pct": "% DW"},
            )
            st.plotly_chart(fig_dwpct, use_container_width=True)

# =========================
# TAB 3: Breakdown Tahunan
# =========================
with tab3:
    st.subheader("Breakdown Tahunan")

    left, right = st.columns(2)

    with left:
        st.markdown("### Jenis Pelayanan (Tahunan)")
        if {"sub_category", "value"} <= set(pel.columns):
            pel2 = pel.sort_values("value", ascending=False)
            fig_pel = px.bar(
                pel2,
                x="value",
                y="sub_category",
                orientation="h",
                labels={"sub_category": "Jenis Pelayanan", "value": "Kunjungan"},
            )
            st.plotly_chart(fig_pel, use_container_width=True)
        else:
            st.error("CSV breakdown_pelayanan_year.csv harus punya kolom: sub_category, value")
            st.write("Kolom tersedia:", list(pel.columns))

    with right:
        st.markdown("### Distribusi Umur (Tahunan)")
        if {"sub_category", "value"} <= set(umur.columns):
            umur2 = umur.copy()
            umur_order = ["0-7 hr", "8-28 hr", "1 bl-1 th", "1-4 th", "5-9 th", "10-14 th",
                          "15-19 th", "20-44 th", "45-54 th", "55-59 th", "60-69 th", "+70 th"]
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

    st.subheader("Tabel KPI Bulanan (Data Curated)")
    st.dataframe(kpi.sort_values("month"), use_container_width=True)