import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder

st.set_page_config(page_title="Dashboard de Gastos", layout="wide")

# Reemplaza 'TU_ID_AQUI' con el ID del enlace público de tu Excel en Google Drive
url_drive = "https://drive.google.com/uc?export=download&id=TU_ID_AQUI"

@st.cache_data(ttl=600)
def cargar_datos():
    return pd.read_excel(url_drive)

df = cargar_datos()

st.title("📊 Control de Gastos por Proyecto")

if 'Anio' in df.columns:
    anios = sorted(df['Anio'].dropna().unique(), reverse=True)
    anio_sel = st.selectbox("Selecciona el Año:", anios)
    df_filtrado = df[df['Anio'] == anio_sel]
else:
    df_filtrado = df.copy()

gb = GridOptionsBuilder.from_dataframe(df_filtrado)
gb.configure_column("Proyecto", rowGroup=True, hide=True)
gb.configure_column("Subpartida")
gb.configure_column("Monto", aggFunc="sum", type=["numericColumn"], precision=2)

gb.configure_grid_options(
    autoGroupColumnDef={
        "headerName": "Proyecto / Subpartida",
        "cellRendererParams": {"suppressCount": False}
    },
    groupDefaultExpanded=0
)

grid_options = gb.build()

AgGrid(
    df_filtrado,
    gridOptions=grid_options,
    enable_enterprise_modules=True,
    height=450,
    theme="balham"
)
