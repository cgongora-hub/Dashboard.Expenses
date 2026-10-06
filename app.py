import io
import os
import gdown
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

st.set_page_config(page_title="Dashboard de Gastos", layout="wide")

id_archivo = "1ngy9_QXNotPVESO_znJ01MrJb8CMlr1r"


@st.cache_data(ttl=300)
def cargar_datos():
  url_drive = f"https://drive.google.com/uc?id={id_archivo}"
  archivo_temporal = "gastos_erp.xlsx"
  gdown.download(url_drive, archivo_temporal, quiet=True)

  # Especificamos sheet_name="Data" para que lea la pestaña correcta del ERP
  df = pd.read_excel(archivo_temporal, sheet_name="Data")

  # Limpiar espacios invisibles en los nombres de las columnas
  df.columns = df.columns.astype(str).str.strip()
  return df


try:
  df_raw = cargar_datos()
except Exception as e:
  st.error(f"Error al descargar o leer la pestaña 'Data': {e}")
  st.stop()

st.title("📊 Control de Gastos por Proyecto")

# Panel de diagnóstico
with st.expander("🔍 DIAGNÓSTICO DE COLUMNAS"):
  st.write("**Columnas detectadas en la pestaña 'Data':**", list(df_raw.columns))

df = df_raw.copy()

# 1. Filtro estricto EstadoCronograma
if "EstadoCronograma" in df.columns:
  df = df[df["EstadoCronograma"].astype(str).str.strip().isin(["Cobrado", "Pagado"])]

st.sidebar.header("Filtros de Control")

# Filtro Empresa
if "Empresa" in df.columns:
  empresas = ["Todas"] + sorted(df["Empresa"].dropna().unique().tolist())
  empresa_sel = st.sidebar.selectbox("Empresa:", empresas)
  if empresa_sel != "Todas":
    df = df[df["Empresa"] == empresa_sel]

# Filtro Proyecto
col_proyecto = "ProyectoDimension1" if "ProyectoDimension1" in df.columns else None
if col_proyecto:
  proyectos = ["Todos"] + sorted(df[col_proyecto].dropna().unique().tolist())
  proyecto_sel = st.sidebar.selectbox("Proyecto:", proyectos)
  if proyecto_sel != "Todos":
    df = df[df[col_proyecto] == proyecto_sel]

# Filtro Año
col_ano = "PeriodoAno" if "PeriodoAno" in df.columns else None
if col_ano:
  anios = sorted(df[col_ano].dropna().unique(), reverse=True)
  anio_sel = st.sidebar.selectbox("Año:", anios)
  df = df[df[col_ano] == anio_sel]

# Filtro Mes
col_mes = "PeriodoMensual" if "PeriodoMensual" in df.columns else None
if col_mes:
  meses = ["Todos"] + sorted(df[col_mes].dropna().unique().tolist())
  mes_sel = st.sidebar.selectbox("Mes:", meses)
  if mes_sel != "Todos":
    df = df[df[col_mes] == mes_sel]

# Agrupación y Árbol (Tree Grid)
gb = GridOptionsBuilder.from_dataframe(df)

if "DesPCG2" in df.columns:
  gb.configure_column("DesPCG2", rowGroup=True, hide=True)
if "DesPCG3" in df.columns:
  gb.configure_column("DesPCG3", rowGroup=True, hide=True)
if "DesPCG" in df.columns:
  gb.configure_column("DesPCG", headerName="Detalle Final")

if "MontoS" in df.columns:
  gb.configure_column(
      "MontoS",
      headerName="Monto (S/)",
      aggFunc="sum",
      type=["numericColumn"],
      precision=2,
  )

columnas_visibles = ["DesPCG2", "DesPCG3", "DesPCG", "MontoS"]
for col in df.columns:
  if col not in columnas_visibles:
    gb.configure_column(col, hide=True)

gb.configure_grid_options(
    autoGroupColumnDef={
        "headerName": "Grupo / Subpartida / Detalle",
        "cellRendererParams": {"suppressCount": False},
        "minWidth": 400,
    },
    groupDefaultExpanded=0,
)

grid_options = gb.build()

AgGrid(
    df,
    gridOptions=grid_options,
    enable_enterprise_modules=True,
    height=550,
    theme="balham",
)
