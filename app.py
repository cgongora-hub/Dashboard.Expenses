import gc
import io
import os
import re
import gdown
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

st.set_page_config(page_title="Dashboard de Gastos", layout="wide")

id_archivo = "1ngy9_QXNotPVESO_znJ01MrJb8CMlr1r"

COLUMNAS_NECESARIAS = [
    "PeriodoAno",
    "PeriodoMensual",
    "EstadoCronograma",
    "Empresa",
    "ProyectoDimension1",
    "DesPCG2",
    "DesPCG3",
    "DesPCG",
    "MontoS",
]


@st.cache_data(ttl=600)
def cargar_datos():
  url_drive = f"https://drive.google.com/uc?id={id_archivo}"
  archivo_temporal = "gastos_erp.xlsx"

  gdown.download(url_drive, archivo_temporal, quiet=True)

  df = pd.read_excel(
      archivo_temporal,
      sheet_name="Data",
      usecols=lambda col: str(col).strip() in COLUMNAS_NECESARIAS,
  )

  if os.path.exists(archivo_temporal):
    os.remove(archivo_temporal)

  df.columns = df.columns.astype(str).str.strip()

  if "EstadoCronograma" in df.columns:
    df = df[
        df["EstadoCronograma"].astype(str).str.strip().isin(["Cobrado", "Pagado"])
    ].copy()

  if "MontoS" in df.columns:
    df["MontoS"] = pd.to_numeric(df["MontoS"], errors="coerce").fillna(0)

  gc.collect()
  return df


try:
  df_raw = cargar_datos()
except Exception as e:
  st.error(f"Error al procesar los datos: {e}")
  st.stop()

st.title("📊 Control de Gastos por Proyecto")

df = df_raw.copy()

st.sidebar.header("Filtros de Control")

# Filtro Empresa
if "Empresa" in df.columns:
  empresas = ["Todas"] + sorted(df["Empresa"].dropna().unique().tolist())
  empresa_sel = st.sidebar.selectbox("Empresa:", empresas)
  if empresa_sel != "Todas":
    df = df[df["Empresa"] == empresa_sel]

# Filtro Proyecto
col_proyecto = (
    "ProyectoDimension1" if "ProyectoDimension1" in df.columns else None
)
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
# CONSTRUCCIÓN DE LA TABLA DINÁMICA
# ---------------------------------------------------------
index_cols = [c for c in ["DesPCG2", "DesPCG3", "DesPCG"] if c in df.columns]

MESES_MAP = {
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


def obtener_nombre_mes(val, anio_actual):
  val_str = str(val).strip()
  if val_str.upper() in ["TOTAL GENERAL", "TOTAL"]:
    return "TOTAL GENERAL"

  sufijo_ano = ""
  if anio_actual:
    s_anio = re.sub(r"\D", "", str(anio_actual))
    if len(s_anio) >= 2:
      sufijo_ano = f"-{s_anio[-2:]}"

  # 1. Buscar coincidencia por nombre de mes
  for num, abrev in MESES_MAP.items():
    if abrev.lower() in val_str.lower():
      return f"{abrev}{sufijo_ano}"

  # 2. Extraer el número del mes con regex (del 1 al 12)
  numeros = re.findall(r"\d+", val_str)
  if numeros:
    for n in reversed(numeros):
      num_int = int(n)
      if 1 <= num_int <= 12:
        return f"{MESES_MAP[num_int]}{sufijo_ano}"

  return f"{val_str}{sufijo_ano}"


def obtener_orden_mes(val):
  val_str = str(val).strip()
  for num, abrev in MESES_MAP.items():
    if abrev.lower() in val_str.lower():
      return num
  numeros = re.findall(r"\d+", val_str)
  if numeros:
    for n in reversed(numeros):
      num_int = int(n)
      if 1 <= num_int <= 12:
        return num_int
  return 99


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

  # Ordenar cronológicamente del mes 1 al 12
  columnas_meses_raw = sorted(columnas_meses_raw, key=obtener_orden_mes)

  df_pivot["Total General"] = df_pivot[columnas_meses_raw].sum(axis=1)

  columnas_finales = index_cols + columnas_meses_raw + ["Total General"]
  df_display = df_pivot[columnas_finales]

  num_cols = columnas_meses_raw + ["Total General"]
  df_display[num_cols] = df_display[num_cols].round(2)
else:
  df_display = df.copy()
  columnas_meses_raw = []
  num_cols = ["MontoS"] if "MontoS" in df.columns else []

df_display.columns = [str(c) for c in df_display.columns]
num_cols_str = [str(c) for c in num_cols]
index_cols_str = [str(c) for c in index_cols]

# ---------------------------------------------------------
# CONFIGURACIÓN DE AGGRID
# ---------------------------------------------------------
gb = GridOptionsBuilder.from_dataframe(df_display)

if "DesPCG2" in df_display.columns:
  gb.configure_column("DesPCG2", rowGroup=True, hide=True)
if "DesPCG3" in df_display.columns:
  gb.configure_column("DesPCG3", rowGroup=True, hide=True)
if "DesPCG" in df_display.columns:
  gb.configure_column("DesPCG", rowGroup=True, hide=True)

js_formatter = JsCode("""
function(params) {
    if (params.value === undefined || params.value === null) return '0.00';
    return params.value.toLocaleString('es-PE', {minimumFractionDigits: 2, maximumFractionDigits: 2});
}
""")

for col_str in num_cols_str:
  nombre_cabecera = obtener_nombre_mes(col_str, anio_sel)
  ancho_col = 150 if col_str == "Total General" else 125

  gb.configure_column(
      col_str,
      headerName=nombre_cabecera,
      aggFunc="sum",
      type=["numericColumn"],
      valueFormatter=js_formatter,
      minWidth=ancho_col,
      width=ancho_col,
      suppressMenu=True,  # Quita el icono de filtro interno para dar 100% de espacio al texto
  )

for col in df_display.columns:
  if col not in index_cols_str and col not in num_cols_str:
    gb.configure_column(col, hide=True)

gb.configure_grid_options(
    autoGroupColumnDef={
        "headerName": "Grupo / Subpartida / Detalle",
        "cellRendererParams": {"suppressCount": False},
        "minWidth": 400,
        "width": 450,
    },
    groupDefaultExpanded=0,
    suppressAggFuncInHeader=True,
)

grid_options = gb.build()

# CSS interno inyectado directamente a la tabla para ocultar la marca de agua
css_ocultar_marca = {
    ".ag-watermark": {"display": "none !important", "opacity": "0 !important"}
}

AgGrid(
    df_display,
    gridOptions=grid_options,
    enable_enterprise_modules=True,
    allow_unsafe_jscode=True,
    height=550,
    theme="balham",
    custom_css=css_ocultar_marca,  # <-- Esto aplica el CSS dentro del marco
)
