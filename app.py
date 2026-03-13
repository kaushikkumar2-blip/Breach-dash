import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Shipment Breach Dashboard", layout="wide", page_icon="📦")

st.markdown("""
<style>
    .main-header {
        font-size: 2rem; font-weight: 700;
        background: linear-gradient(90deg, #1a1a2e, #16213e, #0f3460);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        padding-bottom: 0.5rem;
    }
    .metric-card {
        background: #f8fafc; border-radius: 12px;
        padding: 1rem; border-left: 4px solid #0f3460;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    .stTabs [data-baseweb="tab"] { font-weight: 600; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; }
</style>
""", unsafe_allow_html=True)

# ── Data Loading ─────────────────────────────────────────────────────────────
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df['shipped_lpd_date_key'] = pd.to_datetime(
        df['shipped_lpd_date_key'].astype(str), format='%Y%m%d'
    )
    # Safe breach %
    df['overall_breach_percent'] = np.where(
        df['Breach_Den'] > 0,
        df['Breach_Num'] / df['Breach_Den'],
        np.nan
    )
    return df

# ── File uploader / default path ─────────────────────────────────────────────
st.markdown('<p class="main-header">📦 Shipment Breach Performance Dashboard</p>',
            unsafe_allow_html=True)

uploaded = st.file_uploader("Upload your CSV file", type="csv")
if uploaded:
    df_raw = load_data(uploaded)
else:
    st.info("Upload a CSV to begin. Showing sample structure below.")
    st.stop()
# ── Sidebar Filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filters")

    weeks = sorted(df_raw['week_num_in_year'].dropna().unique())
    sel_weeks = st.multiselect("Week Number", weeks, default=weeks)

    dh_names = sorted(df_raw['dh_name'].dropna().unique())
    sel_dh = st.multiselect("DH Name", dh_names, default=dh_names)

    seller_types = sorted(df_raw['seller_type'].dropna().unique())
    sel_seller = st.multiselect("Seller Type", seller_types, default=seller_types)

    # pincodes = sorted(df_raw['dest_pincode'].dropna().unique())
    # sel_pin = st.multiselect("Pincode", pincodes, default=pincodes)

# Apply filters
df = df_raw[
    df_raw['week_num_in_year'].isin(sel_weeks) &
    df_raw['dh_name'].isin(sel_dh) &
    df_raw['seller_type'].isin(sel_seller) 
].copy()

if df.empty:
    st.warning("No data matches the selected filters.")
    st.stop()

# ── Top KPIs ──────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
total_breach_pct = (df['Breach_Num'].sum() / df['Breach_Den'].sum() * 100) if df['Breach_Den'].sum() > 0 else 0
lm_pct   = (df['LM_breach_num'].sum()       / df['Breach_Den'].sum() * 100) if df['Breach_Den'].sum() > 0 else 0
e2e_pct  = (df['E2E_breach_num'].sum()      / df['Breach_Den'].sum() * 100) if df['Breach_Den'].sum() > 0 else 0
ups_pct  = (df['upstream_breach_num'].sum() / df['Breach_Den'].sum() * 100) if df['Breach_Den'].sum() > 0 else 0

col1.metric("Overall Breach %",   f"{total_breach_pct:.2f}%")
col2.metric("LM Breach %",        f"{lm_pct:.2f}%")
col3.metric("E2E Breach %",       f"{e2e_pct:.2f}%")
col4.metric("Upstream Breach %",  f"{ups_pct:.2f}%")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Seller Breach Trend",
    "📊 Seller Performance Comparison",
    "🔍 Breach Reason Analysis",
    "🗺️ DH / Pincode Pivot"
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — Seller Breach Trend
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Date × Seller Type — Breach %")

    grp1 = (
        df.groupby(['shipped_lpd_date_key', 'seller_type'])
          .agg(Total_Breach_Num=('Breach_Num', 'sum'),
               Total_Breach_Den=('Breach_Den', 'sum'))
          .reset_index()
    )
    grp1['Breach_%'] = np.where(
        grp1['Total_Breach_Den'] > 0,
        (grp1['Total_Breach_Num'] / grp1['Total_Breach_Den'] * 100).round(2),
        np.nan
    )
    grp1['Date'] = grp1['shipped_lpd_date_key'].dt.strftime('%Y-%m-%d')

    # Pivot table display
    pivot1 = grp1.pivot_table(
        index='Date', columns='seller_type', values='Breach_%'
    ).reset_index()
    st.dataframe(pivot1, use_container_width=True)

    # Line chart
    fig1 = px.line(
        grp1, x='shipped_lpd_date_key', y='Breach_%',
        color='seller_type', markers=True,
        title="Breach % Trend by Seller Type",
        labels={'shipped_lpd_date_key': 'Date', 'Breach_%': 'Breach %',
                'seller_type': 'Seller Type'}
    )
    fig1.update_layout(hovermode='x unified', legend_title_text='Seller Type')
    st.plotly_chart(fig1, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — Seller Performance Comparison (vs previous day)
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Seller Performance vs Previous Day")

    daily_seller = (
        df.groupby(['shipped_lpd_date_key', 'seller_type'])
          .agg(Breach_Num=('Breach_Num', 'sum'), Breach_Den=('Breach_Den', 'sum'))
          .reset_index()
    )
    daily_seller['Breach_%'] = np.where(
        daily_seller['Breach_Den'] > 0,
        daily_seller['Breach_Num'] / daily_seller['Breach_Den'],
        np.nan
    )
    daily_seller = daily_seller.sort_values(['seller_type', 'shipped_lpd_date_key'])
    daily_seller['prev_Breach_%'] = daily_seller.groupby('seller_type')['Breach_%'].shift(1)
    daily_seller['Change'] = np.select(
        [daily_seller['Breach_%'] < daily_seller['prev_Breach_%'],
         daily_seller['Breach_%'] > daily_seller['prev_Breach_%']],
        ['Improved', 'Worsened'],
        default='No Change'
    )

    summary = (
        daily_seller.dropna(subset=['prev_Breach_%'])
          .groupby('shipped_lpd_date_key')['Change']
          .value_counts().unstack(fill_value=0).reset_index()
    )
    for col in ['Improved', 'Worsened', 'No Change']:
        if col not in summary.columns:
            summary[col] = 0
    summary['Date'] = summary['shipped_lpd_date_key'].dt.strftime('%Y-%m-%d')
    display_summary = summary[['Date', 'Improved', 'Worsened', 'No Change']]

    st.dataframe(display_summary, use_container_width=True)

    fig2 = go.Figure()
    fig2.add_bar(x=summary['Date'], y=summary['Improved'],  name='Improved',  marker_color='#22c55e')
    fig2.add_bar(x=summary['Date'], y=summary['Worsened'],  name='Worsened',  marker_color='#ef4444')
    fig2.add_bar(x=summary['Date'], y=summary['No Change'], name='No Change', marker_color='#94a3b8')
    fig2.update_layout(barmode='stack', title='Daily Seller Performance Change',
                       xaxis_title='Date', yaxis_title='Number of Sellers',
                       legend_title='Status')
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Detailed Seller Change Log")
    detail = daily_seller[['shipped_lpd_date_key', 'seller_type', 'Breach_%', 'prev_Breach_%', 'Change']].dropna()
    detail = detail.rename(columns={
        'shipped_lpd_date_key': 'Date',
        'seller_type': 'Seller Type',
        'Breach_%': 'Today Breach %',
        'prev_Breach_%': 'Prev Day Breach %'
    })
    detail['Today Breach %']    = (detail['Today Breach %']    * 100).round(2)
    detail['Prev Day Breach %'] = (detail['Prev Day Breach %'] * 100).round(2)
    detail['Date'] = detail['Date'].dt.strftime('%Y-%m-%d')
    st.dataframe(detail, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — Breach Reason Analysis
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Breach Reason Analysis")

    total_den = df['Breach_Den'].sum()
    reasons = pd.DataFrame({
        'Breach Type': ['Last Mile (LM)', 'End-to-End (E2E)', 'Upstream'],
        'Breach Count': [
            df['LM_breach_num'].sum(),
            df['E2E_breach_num'].sum(),
            df['upstream_breach_num'].sum()
        ],
        'Breach %': [
            round(df['LM_breach_num'].sum()       / total_den * 100, 2) if total_den > 0 else 0,
            round(df['E2E_breach_num'].sum()      / total_den * 100, 2) if total_den > 0 else 0,
            round(df['upstream_breach_num'].sum() / total_den * 100, 2) if total_den > 0 else 0,
        ]
    })
    st.dataframe(reasons, use_container_width=True, hide_index=True)

    fig3 = px.bar(
        reasons, x='Breach Type', y='Breach %', color='Breach Type',
        text='Breach %', title='Breach % by Reason',
        color_discrete_sequence=['#3b82f6', '#f59e0b', '#ef4444']
    )
    fig3.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
    fig3.update_layout(showlegend=False, yaxis_title='Breach %')
    st.plotly_chart(fig3, use_container_width=True)

    # Trend over time by reason
    st.subheader("Reason Breach % Trend Over Time")
    daily_reason = (
        df.groupby('shipped_lpd_date_key')
          .agg(LM=('LM_breach_num', 'sum'),
               E2E=('E2E_breach_num', 'sum'),
               Upstream=('upstream_breach_num', 'sum'),
               Den=('Breach_Den', 'sum'))
          .reset_index()
    )
    for col in ['LM', 'E2E', 'Upstream']:
        daily_reason[f'{col}_%'] = np.where(
            daily_reason['Den'] > 0,
            daily_reason[col] / daily_reason['Den'] * 100, np.nan
        )
    fig3b = px.line(
        daily_reason.melt(
            id_vars='shipped_lpd_date_key',
            value_vars=['LM_%', 'E2E_%', 'Upstream_%'],
            var_name='Reason', value_name='Breach %'
        ),
        x='shipped_lpd_date_key', y='Breach %', color='Reason', markers=True,
        title='Daily Breach % by Reason',
        labels={'shipped_lpd_date_key': 'Date'}
    )
    st.plotly_chart(fig3b, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — DH / Pincode Pivot Analysis
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("Pivot Table — DH × Seller Type × Week × Pincode")

    pivot_agg = (
        df.groupby(['dh_name', 'seller_type', 'week_num_in_year', 'dest_pincode'])
          ['overall_breach_percent']
          .mean()
          .reset_index()
          .rename(columns={'overall_breach_percent': 'Avg Breach %'})
    )
    pivot_agg['Avg Breach %'] = (pivot_agg['Avg Breach %'] * 100).round(2)
    st.dataframe(pivot_agg, use_container_width=True)

    # Top DHs by Breach %
    st.subheader("Top DHs by Breach %")
    top_dh = (
        df.groupby('dh_name')
          .agg(Breach_Num=('Breach_Num', 'sum'), Breach_Den=('Breach_Den', 'sum'))
          .reset_index()
    )
    top_dh['Breach_%'] = np.where(
        top_dh['Breach_Den'] > 0,
        top_dh['Breach_Num'] / top_dh['Breach_Den'] * 100, np.nan
    ).round(2)
    top_dh = top_dh.sort_values('Breach_%', ascending=False).head(20)

    fig4a = px.bar(
        top_dh, x='Breach_%', y='dh_name', orientation='h',
        title='Top 20 DHs by Breach %', text='Breach_%',
        color='Breach_%', color_continuous_scale='Reds'
    )
    fig4a.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
    fig4a.update_layout(yaxis={'categoryorder': 'total ascending'},
                        xaxis_title='Breach %', yaxis_title='DH Name',
                        coloraxis_showscale=False)
    st.plotly_chart(fig4a, use_container_width=True)

    # Pincode-wise distribution
    st.subheader("Pincode-wise Breach Distribution")
    top_pin = (
        df.groupby('dest_pincode')
          .agg(Breach_Num=('Breach_Num', 'sum'), Breach_Den=('Breach_Den', 'sum'))
          .reset_index()
    )
    top_pin['Breach_%'] = np.where(
        top_pin['Breach_Den'] > 0,
        top_pin['Breach_Num'] / top_pin['Breach_Den'] * 100, np.nan
    ).round(2)
    top_pin = top_pin.dropna().sort_values('Breach_%', ascending=False).head(30)

    fig4b = px.bar(
        top_pin, x='dest_pincode', y='Breach_%',
        title='Top 30 Pincodes by Breach %', text='Breach_%',
        color='Breach_%', color_continuous_scale='YlOrRd'
    )
    fig4b.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
    fig4b.update_layout(xaxis_title='Pincode', yaxis_title='Breach %',
                        xaxis_type='category', coloraxis_showscale=False)
    st.plotly_chart(fig4b, use_container_width=True)

    # Overall breach trend over time
    st.subheader("Overall Breach % Trend Over Time")
    daily_overall = (
        df.groupby('shipped_lpd_date_key')
          .agg(Breach_Num=('Breach_Num', 'sum'), Breach_Den=('Breach_Den', 'sum'))
          .reset_index()
    )
    daily_overall['Breach_%'] = np.where(
        daily_overall['Breach_Den'] > 0,
        daily_overall['Breach_Num'] / daily_overall['Breach_Den'] * 100, np.nan
    )
    fig4c = px.area(
        daily_overall, x='shipped_lpd_date_key', y='Breach_%',
        title='Overall Breach % Over Time',
        labels={'shipped_lpd_date_key': 'Date', 'Breach_%': 'Breach %'},
        color_discrete_sequence=['#0f3460']
    )
    fig4c.update_layout(hovermode='x')
    st.plotly_chart(fig4c, use_container_width=True)

st.caption("Dashboard built with Streamlit · Plotly · Pandas")
