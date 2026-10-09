import gc
import os
import re
import gdown
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Servicios por Cobrar", layout="wide")

# =========================================================
# IDENTIFICADORES DE ARCHIVOS
# =========================================================

ID_EXCEL = "1ngy9_QXNotPVESO_znJ01MrJb8CMlr1r"          # Excel en Drive (pestaña Data)
ID_SHEETS = "1xbZZ7TIBdAb9-55ma8EBHgKNv7doTmqmckWE95wHVqs"  # Google Sheets

PESTANA_PRESUPUESTO = "PresupuestoFeesIngresosProyectos"
PESTANA_LISTADO = "ListadoProyectos"

GRUPO_FIJO = "N. INGRESOS DE EMPRESAS DE SERVICIOS"


# =========================================================
# UTILIDAD: normalizar texto para cruces (llave DesPCG)
# =========================================================

def normalizar_llave(serie):
    """
    Limpia una columna de texto para usarla como llave de cruce:
    quita espacios al inicio/fin, colapsa espacios dobles y unifica
    el guion. NO cambia mayúsculas ni puntos (esos sí deben coincidir).
    """
    return (
        serie.astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)   # espacios dobles -> uno
        .str.replace("–", "-", regex=False)      # guion largo -> guion normal
        .str.replace("—", "-", regex=False)
    )


# =========================================================
# CARGA 1 — EXCEL (ejecución real)
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

    # Solo el grupo de ingresos de empresas de servicios
    if "DesPCG2" in df.columns:
        df = df[df["DesPCG2"].astype(str).str.strip() == GRUPO_FIJO].copy()

    # Monto numérico
    if "MontoS" in df.columns:
        df["MontoS"] = pd.to_numeric(df["MontoS"], errors="coerce").fillna(0)

    # Año como entero
    if "PeriodoAno" in df.columns:
        df["PeriodoAno"] = pd.to_numeric(
            df["PeriodoAno"], errors="coerce"
        ).astype("Int64")

    # Llave de cruce normalizada
    if "DesPCG" in df.columns:
        df["DesPCG_key"] = normalizar_llave(df["DesPCG"])

    gc.collect()
    return df


# =========================================================
# CARGA 2 y 3 — GOOGLE SHEETS (público, vía CSV)
# =========================================================

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
# EJECUCIÓN DE CARGAS
# =========================================================

try:
    df_excel = cargar_excel()
except Exception as e:
    st.error(f"Error cargando el Excel: {e}")
    st.stop()

try:
    df_ppto = cargar_sheet(PESTANA_PRESUPUESTO)
except Exception as e:
    st.error(f"Error cargando presupuesto (Sheets): {e}")
    st.stop()

try:
    df_listado = cargar_sheet(PESTANA_LISTADO)
except Exception as e:
    st.error(f"Error cargando listado de proyectos (Sheets): {e}")
    st.stop()


# =========================================================
# PROYECTOS ACTIVOS
# =========================================================

# En ListadoProyectos: columna "Proyecto" y columna "Estado_Activo" == "Activo"
col_estado = None
for c in ["Estado_Activo", "Estado Activo", "EstadoActivo"]:
    if c in df_listado.columns:
        col_estado = c
        break

if col_estado is None or "Proyecto" not in df_listado.columns:
    st.error(
        "No se encontraron las columnas esperadas en ListadoProyectos "
        f"(se necesita 'Proyecto' y 'Estado_Activo'). "
        f"Columnas vistas: {list(df_listado.columns)}"
    )
    st.stop()

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
# MAPEO PARTIDA (DesPCG) -> PROYECTO, solo activos
# =========================================================

# En PresupuestoFees: "DesPCG" y "PROYECTO"
if "DesPCG" not in df_ppto.columns or "PROYECTO" not in df_ppto.columns:
    st.error(
        "No se encontraron 'DesPCG' y 'PROYECTO' en el presupuesto. "
        f"Columnas vistas: {list(df_ppto.columns)}"
    )
    st.stop()

df_ppto["DesPCG_key"] = normalizar_llave(df_ppto["DesPCG"])
df_ppto["PROYECTO_norm"] = df_ppto["PROYECTO"].astype(str).str.strip()

# Marcar qué filas del presupuesto son de proyecto activo
df_ppto["es_activo"] = df_ppto["PROYECTO_norm"].isin(proyectos_activos)

# Set de llaves DesPCG que pertenecen a proyectos activos
llaves_activas = set(
    df_ppto.loc[df_ppto["es_activo"], "DesPCG_key"].unique()
)


# =========================================================
# DIAGNÓSTICO DE CRUCE (TEMPORAL)
# =========================================================

st.title("🔎 Capa 1 — Validación de datos (temporal)")

c1, c2, c3 = st.columns(3)
c1.metric("Filas Excel (grupo N)", len(df_excel))
c2.metric("Filas Presupuesto", len(df_ppto))
c3.metric("Proyectos activos", len(proyectos_activos))

st.write("**Proyectos activos:**", proyectos_activos)

# Llaves presentes en cada fuente
llaves_excel = set(df_excel["DesPCG_key"].unique()) if "DesPCG_key" in df_excel else set()
llaves_ppto = set(df_ppto["DesPCG_key"].unique())

st.subheader("Cruce de llaves DesPCG (Excel ↔ Presupuesto)")

cruzan = llaves_excel & llaves_ppto
solo_excel = llaves_excel - llaves_ppto
solo_ppto = llaves_ppto - llaves_excel

d1, d2, d3 = st.columns(3)
d1.metric("✅ Cruzan en ambos", len(cruzan))
d2.metric("⚠️ Solo en Excel", len(solo_excel))
d3.metric("⚠️ Solo en Presupuesto", len(solo_ppto))

st.markdown(
    "Las partidas que aparecen **solo en uno** de los lados son las que "
    "NO van a cruzar bien (por diferencias de texto: espacios, puntos, "
    "guiones, mayúsculas). Revísalas:"
)

with st.expander("Ver partidas SOLO en Excel (no están en el presupuesto)"):
    st.write(sorted(solo_excel))

with st.expander("Ver partidas SOLO en Presupuesto (no están en el Excel)"):
    st.write(sorted(solo_ppto))

st.subheader("Proyectos activos y sus llaves")
st.metric("Llaves DesPCG de proyectos activos", len(llaves_activas))

# Vista rápida de columnas disponibles (para confirmar nombres)
with st.expander("Columnas detectadas en cada fuente"):
    st.write("**Excel (Data):**", list(df_excel.columns))
    st.write("**Presupuesto:**", list(df_ppto.columns))
    st.write("**ListadoProyectos:**", list(df_listado.columns))

# Años disponibles en el Excel
if "PeriodoAno" in df_excel.columns:
    anios = sorted(df_excel["PeriodoAno"].dropna().unique().tolist())
    st.write("**Años en el Excel (PeriodoAno):**", anios)
