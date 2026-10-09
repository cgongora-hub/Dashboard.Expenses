import gc
import os
import re
import gdown
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

st.set_page_config(page_title="Servicios por Cobrar", layout="wide")

# --- BLOQUE CSS ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"], [class*="st-"], p, span, h1, h2, h3, h4, h5, h6, div {
        font-family: 'Inter', sans-serif !important;
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# IDENTIFICADORES
# =========================================================

ID_EXCEL = "1ngy9_QXNotPVESO_znJ01MrJb8CMlr1r"
ID_SHEETS = "1xbZZ7TIBdAb9-55ma8EBHgKNv7doTmqmckWE95wHVqs"

PESTANA_PRESUPUESTO = "PresupuestoFeesIngresosProyectos"
PESTANA_LISTADO = "ListadoProyectos"

GRUPO_FIJO = "N. INGRESOS DE EMPRESAS DE SERVICIOS"
COL_PPTO_GLOBAL = "Presupuesto.Global.inc.IGV"


# =========================================================
# NORMALIZACIÓN DE LLAVE
# =========================================================

def normalizar_llave(serie):
    return (
        serie.astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.replace("–", "-", regex=False)
        .str.replace("—", "-", regex=False)
    )


# =========================================================
# CARGA EXCEL
# =========================================================

COLUMNAS_EXCEL = [
    "PeriodoAno",
    "EstadoCronograma",
    "DesPCG2",
    "DesPCG3",
    "DesPCG",
    "MontoS",
]


@st.cache_data(ttl=600)
def cargar_excel():
    url = f"https://drive.google.com/uc?id={ID_EXCEL}"
    tmp = "gastos_erp_d2.xlsx"
    gdown.download(url, tmp, quiet=True)
    df = pd.read_excel(
        tmp,
        sheet_name="Data",
        usecols=lambda c: str(c).strip() in COLUMNAS_EXCEL,
    )
    if os.path.exists(tmp):
        os.remove(tmp)

    df.columns = df.columns.astype(str).str.strip()

    if "DesPCG2" in df.columns:
        df = df[df["DesPCG2"].astype(str).str.strip() == GRUPO_FIJO].copy()

    df["MontoS"] = pd.to_numeric(df["MontoS"], errors="coerce").fillna(0)
    df["PeriodoAno"] = pd.to_numeric(df["PeriodoAno"], errors="coerce").astype("Int64")
    df["EstadoCronograma"] = df["EstadoCronograma"].astype(str).str.strip()
    df["DesPCG_key"] = normalizar_llave(df["DesPCG"])

    gc.collect()
    return df


@st.cache_data(ttl=600)
def cargar_sheet(nombre_pestana):
    url = (
        f"https://docs.google.com/spreadsheets/d/{ID_SHEETS}"
        f"/gviz/tq?tqx=out:csv&sheet={nombre_pestana}"
    )
    df = pd.read_csv(url)
    df.columns = df.columns.astype(str).str.strip()
    return df


# =========================================================
# CARGAS
# =========================================================

try:
    df_excel = cargar_excel()
    df_ppto = cargar_sheet(PESTANA_PRESUPUESTO)
    df_listado = cargar_sheet(PESTANA_LISTADO)
except Exception as e:
    st.error(f"Error cargando datos: {e}")
    st.stop()


# =========================================================
# PROYECTOS ACTIVOS
# =========================================================

col_estado = None
for c in ["Estado_Activo", "Estado Activo", "EstadoActivo"]:
    if c in df_listado.columns:
        col_estado = c
        break

proyectos_activos = (
    df_listado.loc[
        df_listado[col_estado].astype(str).str.strip().str.lower() == "activo",
        "Proyecto",
    ]
    .astype(str)
    .str.strip()
    .unique()
    .tolist()
)


# =========================================================
# PRESUPUESTO: llave + proyecto + activo
# =========================================================

df_ppto["DesPCG_key"] = normalizar_llave(df_ppto["DesPCG"])
df_ppto["PROYECTO_norm"] = df_ppto["PROYECTO"].astype(str).str.strip()
df_ppto["es_activo"] = df_ppto["PROYECTO_norm"].isin(proyectos_activos)

# Presupuesto global numérico
df_ppto[COL_PPTO_GLOBAL] = pd.to_numeric(
    df_ppto[COL_PPTO_GLOBAL], errors="coerce"
).fillna(0)

# Columnas de años en el presupuesto (ya renombradas a 2022, 2023, ...)
cols_anio_ppto = [c for c in df_ppto.columns if re.fullmatch(r"20\d{2}", str(c))]
for c in cols_anio_ppto:
    df_ppto[c] = pd.to_numeric(df_ppto[c], errors="coerce").fillna(0)

# Solo partidas de proyectos activos
df_ppto_activo = df_ppto[df_ppto["es_activo"]].copy()


# =========================================================
# TÍTULO Y FILTRO DE AÑO
# =========================================================

st.markdown(
    '''
    <div style="display:flex;align-items:center;gap:14px;">
        <svg width="40" height="40" viewBox="0 0 40 40">
            <rect x="2"  y="24" width="9" height="14" rx="1.5" fill="#ffcc00"/>
            <rect x="15" y="14" width="9" height="24" rx="1.5" fill="#ffcc00"/>
            <rect x="28" y="4"  width="9" height="34" rx="1.5" fill="#595959"/>
        </svg>
        <span style="font-size:38px;font-weight:700;color:#595959;">Servicios por Cobrar</span>
    </div>
    ''',
    unsafe_allow_html=True,
)

st.sidebar.header("Filtros de Control")

anios_excel = sorted(df_excel["PeriodoAno"].dropna().unique().tolist())
anio_actual = 2026 if 2026 in anios_excel else (max(anios_excel) if anios_excel else None)

opciones_ano = ["Todos"] + anios_excel
idx_default = opciones_ano.index(anio_actual) if anio_actual in opciones_ano else 0

anio_sel = st.sidebar.selectbox("Año:", opciones_ano, index=idx_default)


# =========================================================
# CÁLCULO TABLA 1 — Resumen de Servicios por Cobrar
# =========================================================

# --- Mapa DesPCG_key -> (DesPCG3, DesPCG) para jerarquía, desde el presupuesto activo ---
# (se usa el texto "bonito" original para mostrar)
jerarquia = (
    df_ppto_activo.groupby("DesPCG_key")
    .agg(DesPCG=("DesPCG", "first"))
    .reset_index()
)

# Traer DesPCG3 desde el Excel (que es donde vive ese nivel con los montos)
mapa_pcg3 = (
    df_excel.dropna(subset=["DesPCG3"])
    .groupby("DesPCG_key")
    .agg(DesPCG3=("DesPCG3", "first"))
    .reset_index()
)
jerarquia = jerarquia.merge(mapa_pcg3, on="DesPCG_key", how="left")


# --- PROGRAMADO (del presupuesto, proyectos activos) ---
if anio_sel == "Todos":
    df_ppto_activo["_programado"] = df_ppto_activo[COL_PPTO_GLOBAL]
else:
    col = str(anio_sel)
    if col in df_ppto_activo.columns:
        df_ppto_activo["_programado"] = df_ppto_activo[col]
    else:
        df_ppto_activo["_programado"] = 0

programado = (
    df_ppto_activo.groupby("DesPCG_key")["_programado"].sum().reset_index()
)
programado.columns = ["DesPCG_key", "Programado"]


# --- Filtrar Excel a partidas de proyectos activos ---
llaves_activas = set(df_ppto_activo["DesPCG_key"].unique())
df_exc = df_excel[df_excel["DesPCG_key"].isin(llaves_activas)].copy()

# Filtro de año en el Excel
if anio_sel != "Todos":
    df_exc = df_exc[df_exc["PeriodoAno"] == anio_sel]


# --- FACTURADO (Cobrado + Pendiente) ---
facturado = (
    df_exc[df_exc["EstadoCronograma"].isin(["Cobrado", "Pendiente"])]
    .groupby("DesPCG_key")["MontoS"].sum().reset_index()
)
facturado.columns = ["DesPCG_key", "Facturado"]

# --- COBRADO (solo Cobrado) ---
cobrado = (
    df_exc[df_exc["EstadoCronograma"] == "Cobrado"]
    .groupby("DesPCG_key")["MontoS"].sum().reset_index()
)
cobrado.columns = ["DesPCG_key", "Cobrado"]


# --- Unir todo sobre la jerarquía ---
tabla1 = jerarquia.merge(programado, on="DesPCG_key", how="outer")
tabla1 = tabla1.merge(facturado, on="DesPCG_key", how="outer")
tabla1 = tabla1.merge(cobrado, on="DesPCG_key", how="outer")

for c in ["Programado", "Facturado", "Cobrado"]:
    tabla1[c] = pd.to_numeric(tabla1[c], errors="coerce").fillna(0)

# --- Columnas derivadas ---
tabla1["Por Cobrar"] = tabla1["Facturado"] - tabla1["Cobrado"]
# Por Facturar = Programado - Facturado, pero 0 si Programado <= 0
tabla1["Por Facturar"] = (tabla1["Programado"] - tabla1["Facturado"]).where(
    tabla1["Programado"] > 0, 0
)

# Rellenar textos faltantes de jerarquía
tabla1["DesPCG3"] = tabla1["DesPCG3"].fillna("(Sin DesPCG3)")
tabla1["DesPCG"] = tabla1["DesPCG"].fillna(tabla1["DesPCG_key"])

# Orden de columnas finales
tabla1 = tabla1[
    ["DesPCG3", "DesPCG", "Programado", "Facturado", "Cobrado", "Por Cobrar", "Por Facturar"]
]
tabla1 = tabla1.round(2)


# =========================================================
# RENDER TABLA 1
# =========================================================

st.subheader("Resumen de Servicios por Cobrar")

num_cols_t1 = ["Programado", "Facturado", "Cobrado", "Por Cobrar", "Por Facturar"]

gb1 = GridOptionsBuilder.from_dataframe(tabla1)

gb1.configure_column("DesPCG3", rowGroup=True, hide=True)
gb1.configure_column("DesPCG", rowGroup=True, hide=True)

js_fmt = JsCode(
    """
    function(params) {
        if (params.value === undefined || params.value === null) return '0.00';
        return params.value.toLocaleString('es-PE', {
            minimumFractionDigits: 2, maximumFractionDigits: 2
        });
    }
    """
)

for c in num_cols_t1:
    gb1.configure_column(
        c,
        aggFunc="sum",
        type=["numericColumn"],
        valueFormatter=js_fmt,
        minWidth=130,
    )

gb1.configure_grid_options(
    suppressFieldDotNotation=True,
    autoGroupColumnDef={
        "headerName": "Subpartida / Detalle",
        "cellRendererParams": {"suppressCount": False},
        "minWidth": 380,
    },
    groupDefaultExpanded=0,
    suppressAggFuncInHeader=True,
)

custom_css = {
    ".ag-watermark": {"display": "none !important", "opacity": "0 !important"},
    ".ag-root-wrapper": {"font-family": "'Inter', sans-serif !important"},
    ".ag-header-cell-label": {"font-family": "'Inter', sans-serif !important"},
    ".ag-cell": {"font-family": "'Inter', sans-serif !important"},
}

AgGrid(
    tabla1,
    gridOptions=gb1.build(),
    enable_enterprise_modules=True,
    allow_unsafe_jscode=True,
    height=500,
    theme="balham",
    custom_css=custom_css,
)
