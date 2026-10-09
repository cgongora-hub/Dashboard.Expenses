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


def a_numero(serie):
    """
    Convierte texto con formato (comas de miles, S/, espacios, paréntesis
    para negativos) a número. Pensado para los montos que vienen del Sheets
    como texto, ej: "1,857,047.00" -> 1857047.0
    """
    s = serie.astype(str).str.strip()
    # negativos entre paréntesis: (123) -> -123
    s = s.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    # quitar todo lo que no sea dígito, signo o punto decimal
    s = s.str.replace(r"[^\d.\-]", "", regex=True)
    return pd.to_numeric(s, errors="coerce").fillna(0)


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

    # NO se filtra por DesPCG2 del Excel: las filas en estado "Pendiente"
    # vienen sin DesPCG2/DesPCG3 (bug de O360) y se perderían.
    # El grupo N y la jerarquía se toman del Sheets vía la llave DesPCG.
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

# Presupuesto global numérico (limpia comas de miles, S/, etc.)
if COL_PPTO_GLOBAL in df_ppto.columns:
    df_ppto[COL_PPTO_GLOBAL] = a_numero(df_ppto[COL_PPTO_GLOBAL])
else:
    st.sidebar.error(f"No existe la columna '{COL_PPTO_GLOBAL}'")
    df_ppto[COL_PPTO_GLOBAL] = 0

# Columnas de años en el presupuesto (ya renombradas a 2022, 2023, ...)
# Se detecta cualquier encabezado que CONTENGA un año 20xx (tolera espacios, .0, etc.)
mapa_cols_anio = {}  # año(int) -> nombre real de columna
for c in df_ppto.columns:
    m = re.search(r"(20\d{2})", str(c))
    if m and str(c) not in [COL_PPTO_GLOBAL, "DesPCG", "PROYECTO"]:
        mapa_cols_anio[int(m.group(1))] = c
        df_ppto[c] = a_numero(df_ppto[c])

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

# --- Jerarquía DesPCG3 -> DesPCG desde el SHEETS (completo, no del Excel) ---
# El Sheets tiene DesPCG2, DesPCG3 y DesPCG para cada partida N, y cubre
# todas las partidas del grupo. Así evitamos el bug de O360 (pendientes
# sin DesPCG2/DesPCG3 en el Excel).
agg_jerarquia = {"DesPCG": ("DesPCG", "first")}
if "DesPCG3" in df_ppto_activo.columns:
    agg_jerarquia["DesPCG3"] = ("DesPCG3", "first")

jerarquia = (
    df_ppto_activo.groupby("DesPCG_key").agg(**agg_jerarquia).reset_index()
)

if "DesPCG3" not in jerarquia.columns:
    jerarquia["DesPCG3"] = "(Sin DesPCG3)"


# --- PROGRAMADO (del presupuesto, proyectos activos) ---
if anio_sel == "Todos":
    df_ppto_activo["_programado"] = df_ppto_activo[COL_PPTO_GLOBAL]
else:
    col = mapa_cols_anio.get(int(anio_sel))
    if col is not None:
        df_ppto_activo["_programado"] = df_ppto_activo[col]
    else:
        st.sidebar.warning(f"No hay columna de presupuesto para el año {anio_sel}")
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
        width=156, minWidth=145, maxWidth=195,
        suppressSizeToFit=True,  # no se estira para llenar el espacio
    )

# --- Fila de totales (fijada abajo, en negrita) ---
fila_total = {"DesPCG3": "TOTAL GENERAL", "DesPCG": ""}
for c in num_cols_t1:
    fila_total[c] = float(tabla1[c].sum())

gb1.configure_grid_options(
    suppressFieldDotNotation=True,
    autoGroupColumnDef={
        "headerName": "Subpartida / Detalle",
        "cellRendererParams": {"suppressCount": False},
        "minWidth": 380,
        "flex": 1,  # absorbe el espacio sobrante para que lo numérico quede angosto
        "valueGetter": JsCode(
            """
            function(params) {
                if (params.node.rowPinned) { return 'TOTAL GENERAL'; }
                return undefined;
            }
            """
        ),
    },
    groupDefaultExpanded=0,
    suppressAggFuncInHeader=True,
    pinnedBottomRowData=[fila_total],
    getRowStyle=JsCode(
        """
        function(params) {
            if (params.node.rowPinned) {
                return { 'font-weight': '700', 'background-color': '#f5f5f5' };
            }
        }
        """
    ),
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


# =========================================================
# TABLA 2 — Servicios por cobrar por proyecto
# =========================================================

st.markdown("<br>", unsafe_allow_html=True)
st.subheader("Servicios por cobrar por proyecto")

# Usa el MISMO filtro de año del sidebar (compartido con la Tabla 1)
anio_sel_t2 = anio_sel

# --- Mapeo DesPCG_key -> PROYECTO (desde el Sheets, solo activos) ---
mapa_proyecto = (
    df_ppto_activo.groupby("DesPCG_key")
    .agg(PROYECTO=("PROYECTO_norm", "first"))
    .reset_index()
)

# --- Jerarquía (misma que Tabla 1) ---
jerarquia_t2 = jerarquia.copy()

# --- Excel: solo partidas activas, estado Pendiente, año propio ---
df_exc_t2 = df_excel[df_excel["DesPCG_key"].isin(llaves_activas)].copy()
if anio_sel_t2 != "Todos":
    df_exc_t2 = df_exc_t2[df_exc_t2["PeriodoAno"] == anio_sel_t2]

df_exc_t2 = df_exc_t2[df_exc_t2["EstadoCronograma"] == "Pendiente"].copy()

# --- Asignar a cada fila del Excel su proyecto (vía DesPCG_key) ---
df_exc_t2 = df_exc_t2.merge(mapa_proyecto, on="DesPCG_key", how="left")

# --- Pivote: filas = DesPCG_key, columnas = proyecto, valores = suma MontoS ---
if not df_exc_t2.empty:
    pivote = pd.pivot_table(
        df_exc_t2,
        index="DesPCG_key",
        columns="PROYECTO",
        values="MontoS",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    pivote.columns.name = None
else:
    pivote = pd.DataFrame({"DesPCG_key": []})

# --- Unir jerarquía (DesPCG3, DesPCG) con el pivote ---
tabla2 = jerarquia_t2.merge(pivote, on="DesPCG_key", how="left")

# Columnas de proyectos activos (las que existen en el pivote)
cols_proyecto = [
    c for c in tabla2.columns
    if c not in ["DesPCG_key", "DesPCG3", "DesPCG"]
]

# Asegurar que TODOS los proyectos activos tengan columna (aunque estén en 0)
for p in sorted(proyectos_activos):
    if p not in tabla2.columns:
        tabla2[p] = 0
cols_proyecto = sorted([p for p in proyectos_activos if p in tabla2.columns])

# Rellenar y redondear
for c in cols_proyecto:
    tabla2[c] = pd.to_numeric(tabla2[c], errors="coerce").fillna(0)

tabla2["DesPCG3"] = tabla2["DesPCG3"].fillna("(Sin DesPCG3)")
tabla2["DesPCG"] = tabla2["DesPCG"].fillna(tabla2["DesPCG_key"])

tabla2 = tabla2[["DesPCG3", "DesPCG"] + cols_proyecto]
tabla2[cols_proyecto] = tabla2[cols_proyecto].round(2)


# --- Render Tabla 2 ---
gb2 = GridOptionsBuilder.from_dataframe(tabla2)
gb2.configure_column("DesPCG3", rowGroup=True, hide=True)
gb2.configure_column("DesPCG", rowGroup=True, hide=True)

for c in cols_proyecto:
    gb2.configure_column(
        c,
        aggFunc="sum",
        type=["numericColumn"],
        valueFormatter=js_fmt,
        width=150, minWidth=130,
        suppressSizeToFit=True,
    )

# Fila de totales
fila_total_t2 = {"DesPCG3": "TOTAL GENERAL", "DesPCG": ""}
for c in cols_proyecto:
    fila_total_t2[c] = float(tabla2[c].sum())

gb2.configure_grid_options(
    suppressFieldDotNotation=True,
    autoGroupColumnDef={
        "headerName": "Subpartida / Detalle",
        "cellRendererParams": {"suppressCount": False},
        "minWidth": 360,
        "pinned": "left",
        "valueGetter": JsCode(
            """
            function(params) {
                if (params.node.rowPinned) { return 'TOTAL GENERAL'; }
                return undefined;
            }
            """
        ),
    },
    groupDefaultExpanded=0,
    suppressAggFuncInHeader=True,
    pinnedBottomRowData=[fila_total_t2],
    getRowStyle=JsCode(
        """
        function(params) {
            if (params.node.rowPinned) {
                return { 'font-weight': '700', 'background-color': '#f5f5f5' };
            }
        }
        """
    ),
)

AgGrid(
    tabla2,
    gridOptions=gb2.build(),
    enable_enterprise_modules=True,
    allow_unsafe_jscode=True,
    height=500,
    theme="balham",
    custom_css=custom_css,
)
