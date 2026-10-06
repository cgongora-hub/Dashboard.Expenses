import io
import os
import gdown
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

st.set_page_config(page_title="Dashboard de Gastos", layout="wide")

id_archivo = "1ngy9_QXNotPVESO_znJ01MrJb8CMlr1r"


@st.cache_data(ttl=300)
def cargar_datos():
  url_drive = f"https://drive.google.com/uc?id={id_archivo}"
  archivo_temporal = "gastos_erp.xlsx"
  gdown.download(url_drive, archivo_temporal, quiet=True)

  df = pd.read_excel(archivo_temporal, sheet_name="Data")
  df.columns = df.columns.astype(str).str.strip()
  return df


try:
  df_raw = cargar_datos()
except Exception as e:
  st.error(f"Error al cargar los datos de la pestaña 'Data': {e}")
  st.stop()

st.title("📊 Control de Gastos por Proyecto")

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
anio_sel = None
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

# ---------------------------------------------------------
# CONSTRUCCIÓN DE LA TABLA DINÁMICA (MESES EN COLUMNAS)
# ---------------------------------------------------------
index_cols = [c for c in ["DesPCG2", "DesPCG3", "DesPCG"] if c in df.columns]


def obtener_nombre_mes(val, anio_actual):
  if str(val) == "Total General":
    return "TOTAL GENERAL"

  meses_map = {
      1: "Ene",
      2: "Feb",
      3: "Mar",
      4: "Abr",
      5: "May",
      6: "Jun",
      7: "Jul",
      8: "Ago",
      9: "Sep",
      10: "Oct",
      11: "Nov",
      12: "Dic",
  }

  # Obtener sufijo de año de 2 dígitos (ejemplo: 2026 -> "-26")
  sufijo_ano = ""
  if anio_actual:
    try:
      sufijo_ano = f"-{str(int(float(str(anio_actual))))[-2:]}"
    except (ValueError, TypeError):
      sufijo_ano = f"-{str(anio_actual)[-2:]}"

  try:
    num = int(float(str(val).strip()))
    mes_nombre = meses_map.get(num, str(val))
    return f"{mes_nombre}{sufijo_ano}"
  except (ValueError, TypeError):
    return f"{str(val)}{sufijo_ano}"


if index_cols and col_mes and "MontoS" in df.columns and not df.empty:
  df_pivot = pd.pivot_table(
      df,
      index=index_cols,
      columns=col_mes,
      values="MontoS",
      aggfunc="sum",
      fill_value=0,
  ).reset_index()

  df_pivot.columns.name = None

  columnas_meses_raw = [c for c in df_pivot.columns if c not in index_cols]

  try:
    columnas_meses_raw = sorted(
        columnas_meses_raw, key=lambda x: int(float(str(x)))
    )
  except ValueError:
    columnas_meses_raw = sorted(columnas_meses_raw)

  # Columna con la suma del Total General
  df_pivot["Total General"] = df_pivot[columnas_meses_raw].sum(axis=1)

  columnas_finales = index_cols + columnas_meses_raw + ["Total General"]
  df_display = df_pivot[columnas_finales]

  num_cols = columnas_meses_raw + ["Total General"]
  df_display[num_cols] = df_display[num_cols].round(2)

else:
  df_display = df.copy()
  columnas_meses_raw = []
  num_cols = ["MontoS"] if "MontoS" in df.columns else []

# Normalizar los nombres de columnas a texto
df_display.columns = [str(c) for c in df_display.columns]
num_cols_str = [str(c) for c in num_cols]
index_cols_str = [str(c) for c in index_cols]

# ---------------------------------------------------------
# CONFIGURACIÓN DE AGGRID (TREE GRID EN 3 NIVELES)
# ---------------------------------------------------------
gb = GridOptionsBuilder.from_dataframe(df_display)

# Ocultar e integrar los 3 niveles jerárquicos dentro del mismo
