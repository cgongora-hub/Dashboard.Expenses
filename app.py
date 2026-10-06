import io
import pandas as pd
import requests
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

st.set_page_config(page_title="Dashboard de Gastos", layout="wide")

# Reemplaza con el ID real de tu archivo de Google Drive
id_archivo = "1ngy9_QXNotPVESO_znJ01MrJb8CMlr1r"
url_drive = f"https://drive.google.com/uc?export=download&id={id_archivo}&confirm=t"


@st.cache_data(ttl=600)
def cargar_datos():
  response = requests.get(url_drive)
  return pd.read_excel(io.BytesIO(response.content))


df = cargar_datos()

st.title("📊 Control de Gastos por Proyecto")

if "Anio" in df.columns:
  anios = sorted(df["Anio"].dropna().unique(), reverse=True)
  anio_sel = st.selectbox("Selecciona el Año:", anios)
  df_filtrado = df[df["Anio"] == anio_sel]
else:
  df_filtrado = df.copy()

gb = GridOptionsBuilder.from_dataframe(df_filtrado)
gb.configure_column("Proyecto", rowGroup=True, hide=True)
gb.configure_column("Subpartida")
gb.configure_column("Monto", aggFunc="sum", type=["numericColumn"], precision=2)

gb.configure_grid_options(
    autoGroupColumnDef={
        "headerName": "Proyecto / Subpartida",
        "cellRendererParams": {"suppressCount": False},
    },
    groupDefaultExpanded=0,
)

grid_options = gb.build()

AgGrid(
    df_filtrado,
    gridOptions=grid_options,
    enable_enterprise_modules=True,
    height=450,
    theme="balham",
)
