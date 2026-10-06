import streamlit as st
import pandas as pd
import gdown
import os
from st_aggrid import AgGrid, GridOptionsBuilder

st.set_page_config(page_title="Dashboard de Gastos", layout="wide")

# ATENCIÓN: Pega AQUÍ solo el código alfanumérico, sin diagonales ni "https"
id_archivo = 1ngy9_QXNotPVESO_znJ01MrJb8CMlr1r


@st.cache_data(ttl=300)
def cargar_datos():
    url_drive = f"https://drive.google.com/uc?id={id_archivo}"
    archivo_temporal = "gastos_erp.xlsx"
    
    # gdown fuerza la descarga saltándose las pantallas de advertencia de Google
    gdown.download(url_drive, archivo_temporal, quiet=False)
    
    # Ahora pandas lee el archivo físico correctamente
    return pd.read_excel(archivo_temporal)

# Intentar cargar los datos y mostrar un mensaje claro si falla
try:
    df = cargar_datos()
except Exception as e:
    st.error("Hubo un problema al conectar con Google Drive. Verifica que el enlace sea público.")
    st.stop()


st.title("📊 Control de Gastos por Proyecto")

# Ajusta "Anio" al nombre real de la columna en tu Excel si es necesario
if "Anio" in df.columns:
    anios = sorted(df["Anio"].dropna().unique(), reverse=True)
    anio_sel = st.selectbox("Selecciona el Año:", anios)
    df_filtrado = df[df["Anio"] == anio_sel]
else:
    df_filtrado = df.copy()

gb = GridOptionsBuilder.from_dataframe(df_filtrado)
# Ajusta "Proyecto", "Subpartida" y "Monto" a los nombres reales de tus columnas
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
