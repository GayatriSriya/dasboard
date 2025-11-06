import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ------------------------
# Page layout and CSS
# ------------------------
# st.set_page_config(layout="wide")

# Custom padding via CSS (left 10px, right 50px, top 10px)
st.markdown(
    """
    <style>
    .reportview-container {
        padding-left: 10px;
        padding-right: 100px;
        padding-top: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🏪 Warehouse-Cluster Geo Dashboard")

# ------------------------
# CSV Upload
# ------------------------
uploaded_file = st.file_uploader("Upload your warehouse-cluster CSV", type=["csv"])
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    # Convert coordinates to float
    df['latitude'] = df['latitude'].astype(float)
    df['longitude'] = df['longitude'].astype(float)
    df['wh_lat'] = df['wh_lat'].astype(float)
    df['wh_long'] = df['wh_long'].astype(float)
    df['distance_km'] = df['distance_km'].astype(float)
    df['dist_from_wh'] = df['dist_from_wh'].astype(float)

    # ------------------------
    # Warehouse selection on top
    # ------------------------
    warehouses = df['warehouse_name'].unique()
    selected_warehouse = st.selectbox("Select Warehouse", warehouses)

    wh_data = df[df['warehouse_name'] == selected_warehouse]
    if wh_data.empty:
        st.warning("No cluster data for this warehouse.")
        st.stop()

    wh_lat = wh_data.iloc[0]['wh_lat']
    wh_long = wh_data.iloc[0]['wh_long']

    # ------------------------
    # Aggregate cluster info for centroids
    # ------------------------
    cluster_data = wh_data.groupby('k_means').agg({
        'latitude': 'mean',
        'longitude': 'mean',
        'partner_gmv': 'sum',
        'distance_km': 'mean',
        'customer_id': 'count',
        'cx_status': lambda x: list(x)
    }).reset_index()

    # Precompute cluster summary info for hover
    cluster_data['transacting_count'] = cluster_data['cx_status'].apply(lambda x: x.count('Transacting'))
    cluster_data['non_transacting_count'] = cluster_data['cx_status'].apply(lambda x: x.count('Non-Transacting'))

    # ------------------------
    # Cluster summary table
    # ------------------------
    cluster_summary = wh_data.groupby('k_means').agg(
        transacting_count=('cx_status', lambda x: (x=='Transacting').sum()),
        non_transacting_count=('cx_status', lambda x: (x=='Non-Transacting').sum()),
        avg_pgmv_transacting=('partner_gmv', lambda x: x[wh_data.loc[x.index,'cx_status']=='Transacting'].mean()),
        avg_pgmv_nontransacting=('partner_gmv', lambda x: x[wh_data.loc[x.index,'cx_status']=='Non-Transacting'].mean()),
        avg_dist_transacting=('dist_from_wh', lambda x: x[wh_data.loc[x.index,'cx_status']=='Transacting'].mean()),
        avg_dist_nontransacting=('dist_from_wh', lambda x: x[wh_data.loc[x.index,'cx_status']=='Non-Transacting'].mean())
    ).reset_index()

    # ------------------------
    # Plotly Map
    # ------------------------
    fig = go.Figure()

    # Cluster centroids (blue)
    fig.add_trace(go.Scattermapbox(
        lat=cluster_data['latitude'],
        lon=cluster_data['longitude'],
        mode='markers+text',
        marker=dict(size=20, color='blue', opacity=0.9),
        text=[f"Cluster {c}" for c in cluster_data['k_means']],
        textfont=dict(color='black', size=12),
        hovertext=[
            f"Cluster: {row['k_means']}<br>"
            f"Transacting CX: {row['transacting_count']}<br>"
            f"Non-Transacting CX: {row['non_transacting_count']}<br>"
            f"Avg distance_km: {row['distance_km']:.2f}<br>"
            f"Total GMV: {row['partner_gmv']:.2f}"
            for _, row in cluster_data.iterrows()
        ],
        hoverinfo='text',
        name='Clusters'
    ))

    # Lines from warehouse → clusters
    for _, row in cluster_data.iterrows():
        fig.add_trace(go.Scattermapbox(
            lat=[wh_lat, row['latitude']],
            lon=[wh_long, row['longitude']],
            mode='lines',
            line=dict(width=2, color='gray'),
            hoverinfo='none',
            showlegend=False
        ))

    # Customer nodes - single trace per type
    transacting = wh_data[wh_data['cx_status']=='Transacting']
    non_transacting = wh_data[wh_data['cx_status']=='Non-Transacting']

    # Transacting CX
    fig.add_trace(go.Scattermapbox(
        lat=transacting['latitude'],
        lon=transacting['longitude'],
        mode='markers',
        marker=dict(size=8, color='green', opacity=0.8),
        text=(
            "Customer: " + transacting['customer_id'].astype(str) + "<br>" +
            "Last Order: " + transacting['last_order_date'].astype(str) + "<br>" +
            "Distance from WH: " + transacting['dist_from_wh'].round(2).astype(str) + " km<br>" +
            "PGMV: " + transacting['partner_gmv'].round(2).astype(str) + "<br>" +
            "Cluster: " + transacting['k_means'].astype(str)
        ),
        hoverinfo='text',
        name='Transacting CX'
    ))

    # Non-Transacting CX
    fig.add_trace(go.Scattermapbox(
        lat=non_transacting['latitude'],
        lon=non_transacting['longitude'],
        mode='markers',
        marker=dict(size=8, color='red', opacity=0.8),
        text=(
            "Customer: " + non_transacting['customer_id'].astype(str) + "<br>" +
            "Last Order: " + non_transacting['last_order_date'].astype(str) + "<br>" +
            "Distance from WH: " + non_transacting['dist_from_wh'].round(2).astype(str) + " km<br>" +
            "PGMV: " + non_transacting['partner_gmv'].round(2).astype(str) + "<br>" +
            "Cluster: " + non_transacting['k_means'].astype(str)
        ),
        hoverinfo='text',
        name='Non-Transacting CX'
    ))

    # Map layout
    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox_zoom=8,
        mapbox_center={"lat": wh_lat, "lon": wh_long},
        height=700, width=10000,
#         margin={"r":0,"t":0,"l":0,"b":0},
#         showlegend=True
    )

    st.plotly_chart(fig, use_container_width=True)

    # Cluster summary table - full width
    st.markdown("### Cluster Summary")
    st.dataframe(cluster_summary, use_container_width=True)

else:
    st.info("Please upload a CSV file to continue.")
