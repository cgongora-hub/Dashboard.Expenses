import gc
import os
import re
import gdown
import pandas as pd
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
import plotly.graph_objects as go

st.set_page_config(page_title="Gráfico de Cobranza", layout="wide")

# --- BLOQUE CSS ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"], [class*="st-"], p, span, h1, h2, h3, h4, h5, h6, div {
        font-family: 'Inter', sans-serif !important;
    }
    .block-container {
        padding-top: 1rem; padding-bottom: 0rem;
        padding-left: 1rem !important; padding-right: 1rem !important;
        max-width: 100% !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# ACTUALIZACIÓN DIARIA (caché por día + recarga 00:01 Lima)
# =========================================================
TZ_LIMA = ZoneInfo("America/Lima")


def clave_del_dia():
    return datetime.now(TZ_LIMA).strftime("%Y-%m-%d")


st.markdown(
    """
    <script>
    (function() {
        function msHastaRecarga() {
            const ahora = new Date();
            const limaStr = ahora.toLocaleString("en-US", {timeZone: "America/Lima"});
            const lima = new Date(limaStr);
            const objetivo = new Date(lima);
            objetivo.setHours(0, 1, 0, 0);
            if (lima >= objetivo) { objetivo.setDate(objetivo.getDate() + 1); }
            return objetivo - lima;
        }
        setTimeout(function() { window.location.reload(); }, msHastaRecarga());
    })();
    </script>
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
COL_PPTO_GLOBAL = "Presupuesto.Global.inc.IGV"


# =========================================================
# UTILIDADES
# =========================================================
def normalizar_llave(serie):
    return (
        serie.astype(str).str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.replace("–", "-", regex=False)
        .str.replace("—", "-", regex=False)
    )


def a_numero(serie):
    s = serie.astype(str).str.strip()
    s = s.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    s = s.str.replace(r"[^\d.\-]", "", regex=True)
    return pd.to_numeric(s, errors="coerce").fillna(0)


COLUMNAS_EXCEL = [
    "PeriodoAno", "EstadoCronograma", "Empresa",
    "DesPCG2", "DesPCG3", "DesPCG", "MontoS",
]


@st.cache_data(ttl=86400)
def cargar_excel(dia):
    url = f"https://drive.google.com/uc?id={ID_EXCEL}"
    tmp = "gastos_erp_d3.xlsx"
    gdown.download(url, tmp, quiet=True)
    df = pd.read_excel(
        tmp, sheet_name="Data",
        usecols=lambda c: str(c).strip() in COLUMNAS_EXCEL,
    )
    if os.path.exists(tmp):
        os.remove(tmp)
    df.columns = df.columns.astype(str).str.strip()
    df["MontoS"] = pd.to_numeric(df["MontoS"], errors="coerce").fillna(0)
    df["PeriodoAno"] = pd.to_numeric(df["PeriodoAno"], errors="coerce").astype("Int64")
    df["EstadoCronograma"] = df["EstadoCronograma"].astype(str).str.strip()
    if "Empresa" in df.columns:
        df["Empresa"] = df["Empresa"].astype(str).str.strip()
    df["DesPCG_key"] = normalizar_llave(df["DesPCG"])
    gc.collect()
    return df


@st.cache_data(ttl=86400)
def cargar_sheet(nombre_pestana, dia):
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
_dia = clave_del_dia()
try:
    df_excel = cargar_excel(_dia)
    df_ppto = cargar_sheet(PESTANA_PRESUPUESTO, _dia)
    df_listado = cargar_sheet(PESTANA_LISTADO, _dia)
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
    ].astype(str).str.strip().unique().tolist()
)


# =========================================================
# PRESUPUESTO: llave, proyecto, DesPCG3, programado
# =========================================================
df_ppto["DesPCG_key"] = normalizar_llave(df_ppto["DesPCG"])
df_ppto["PROYECTO_norm"] = df_ppto["PROYECTO"].astype(str).str.strip()
df_ppto["es_activo"] = df_ppto["PROYECTO_norm"].isin(proyectos_activos)

if COL_PPTO_GLOBAL in df_ppto.columns:
    df_ppto[COL_PPTO_GLOBAL] = a_numero(df_ppto[COL_PPTO_GLOBAL])
else:
    df_ppto[COL_PPTO_GLOBAL] = 0

mapa_cols_anio = {}
for c in df_ppto.columns:
    m = re.search(r"(20\d{2})", str(c))
    if m and str(c) not in [COL_PPTO_GLOBAL, "DesPCG", "PROYECTO"]:
        mapa_cols_anio[int(m.group(1))] = c
        df_ppto[c] = a_numero(df_ppto[c])

df_ppto_activo = df_ppto[df_ppto["es_activo"]].copy()

# Mapeo por partida: DesPCG_key -> PROYECTO y DesPCG3
agg_map = {"PROYECTO": ("PROYECTO_norm", "first")}
if "DesPCG3" in df_ppto_activo.columns:
    agg_map["DesPCG3"] = ("DesPCG3", "first")
mapa_part = df_ppto_activo.groupby("DesPCG_key").agg(**agg_map).reset_index()
if "DesPCG3" not in mapa_part.columns:
    mapa_part["DesPCG3"] = "(Sin tipo)"


# =========================================================
# TÍTULO Y FILTROS
# =========================================================
st.markdown(
    '''
    <div style="display:flex;align-items:center;gap:14px;">
        <svg width="40" height="40" viewBox="0 0 40 40">
            <rect x="2"  y="24" width="9" height="14" rx="1.5" fill="#ffcc00"/>
            <rect x="15" y="14" width="9" height="24" rx="1.5" fill="#ffcc00"/>
            <rect x="28" y="4"  width="9" height="34" rx="1.5" fill="#595959"/>
        </svg>
        <span style="font-size:38px;font-weight:700;color:#595959;">Avance de Cobranza</span>
    </div>
    ''',
    unsafe_allow_html=True,
)

st.sidebar.header("Filtros de Control")

# --- Año (por defecto "Todos") ---
anios_excel = sorted(df_excel["PeriodoAno"].dropna().unique().tolist())
opciones_ano = ["Todos"] + anios_excel
anio_sel = st.sidebar.selectbox("Año:", opciones_ano, index=0)

# --- Empresa de servicio ---
if "Empresa" in df_excel.columns:
    empresas = sorted(df_excel["Empresa"].dropna().unique().tolist())
    opciones_emp = ["Todas"] + empresas
    emp_sel = st.sidebar.selectbox("Empresa:", opciones_emp, index=0)
else:
    emp_sel = "Todas"

# --- Proyecto ---
opciones_proy = ["Todos"] + sorted(proyectos_activos)
proy_sel = st.sidebar.selectbox("Proyecto:", opciones_proy, index=0)

# --- Tipo de servicio (DesPCG3) ---
tipos = sorted(mapa_part["DesPCG3"].dropna().unique().tolist())
opciones_tipo = ["Todos"] + tipos
tipo_sel = st.sidebar.selectbox("Tipo de servicio:", opciones_tipo, index=0)

# --- Agrupación de las barras ---
dim = st.sidebar.radio("Ver barras por:", ["Proyecto", "Tipo de servicio"], index=0)


# =========================================================
# PREPARACIÓN DE DATOS PARA EL GRÁFICO
# =========================================================
llaves_activas = set(df_ppto_activo["DesPCG_key"].unique())

# Excel: solo partidas activas + año
df_exc = df_excel[df_excel["DesPCG_key"].isin(llaves_activas)].copy()
if anio_sel != "Todos":
    df_exc = df_exc[df_exc["PeriodoAno"] == anio_sel]

# Añadir PROYECTO y DesPCG3 a cada fila.
# Se quitan DesPCG2/DesPCG3 del Excel (vienen incompletas por el bug de O360)
# para que al cruzar quede solo la DesPCG3 del Sheets, sin colisión de nombres.
df_exc = df_exc.drop(columns=["DesPCG2", "DesPCG3"], errors="ignore").merge(
    mapa_part, on="DesPCG_key", how="left"
)

# Aplicar filtros de empresa, proyecto y tipo
if emp_sel != "Todas" and "Empresa" in df_exc.columns:
    df_exc = df_exc[df_exc["Empresa"] == emp_sel]
if proy_sel != "Todos":
    df_exc = df_exc[df_exc["PROYECTO"] == proy_sel]
if tipo_sel != "Todos":
    df_exc = df_exc[df_exc["DesPCG3"] == tipo_sel]

# Programado (del presupuesto activo, mismo año y filtros)
pp = df_ppto_activo.copy()
if anio_sel == "Todos":
    pp["_prog"] = pp[COL_PPTO_GLOBAL]
else:
    col = mapa_cols_anio.get(int(anio_sel))
    pp["_prog"] = pp[col] if col is not None else 0
pp = pp.merge(mapa_part[["DesPCG_key", "DesPCG3"]], on="DesPCG_key", how="left")
if emp_sel != "Todas" and "EMPRESA" in pp.columns:
    pp = pp[pp["EMPRESA"].astype(str).str.strip() == emp_sel]
if proy_sel != "Todos":
    pp = pp[pp["PROYECTO_norm"] == proy_sel]
if tipo_sel != "Todos":
    pp = pp[pp["DesPCG3"] == tipo_sel]

# Columna de agrupación
col_grupo = "PROYECTO" if dim == "Proyecto" else "DesPCG3"
col_grupo_pp = "PROYECTO_norm" if dim == "Proyecto" else "DesPCG3"

# Agregados por grupo
cob = df_exc[df_exc["EstadoCronograma"] == "Cobrado"].groupby(col_grupo)["MontoS"].sum()
pend = df_exc[df_exc["EstadoCronograma"] == "Pendiente"].groupby(col_grupo)["MontoS"].sum()
prog = pp.groupby(col_grupo_pp)["_prog"].sum()

cats = sorted(set(cob.index) | set(pend.index) | set(prog.index))
df_g = pd.DataFrame(index=cats)
df_g["Cobrado"] = cob
df_g["Por Cobrar"] = pend
df_g["Programado"] = prog
df_g = df_g.fillna(0)
df_g["Facturado"] = df_g["Cobrado"] + df_g["Por Cobrar"]
df_g["Por Facturar"] = (df_g["Programado"] - df_g["Facturado"]).clip(lower=0)

# Ordenar y quitar vacíos
df_g = df_g.sort_values("Facturado", ascending=True)
df_g = df_g[df_g[["Cobrado", "Por Cobrar", "Por Facturar"]].sum(axis=1) > 0]


# =========================================================
# GRÁFICO
# =========================================================
if df_g.empty:
    st.info("No hay datos para graficar con los filtros seleccionados.")
else:
    fig = go.Figure()
    fig.add_bar(
        y=df_g.index, x=df_g["Cobrado"], name="Cobrado",
        orientation="h", marker_color="#595959",
        hovertemplate="Cobrado: S/ %{x:,.2f}<extra></extra>",
    )
    fig.add_bar(
        y=df_g.index, x=df_g["Por Cobrar"], name="Por Cobrar",
        orientation="h", marker_color="#ffcc00",
        hovertemplate="Por Cobrar: S/ %{x:,.2f}<extra></extra>",
    )
    fig.add_bar(
        y=df_g.index, x=df_g["Por Facturar"], name="Por Facturar",
        orientation="h", marker_color="#bdbdbd",
        hovertemplate="Por Facturar: S/ %{x:,.2f}<extra></extra>",
    )
    fig.update_layout(
        barmode="stack",
        height=max(320, 46 * len(df_g) + 130),
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        font=dict(family="Inter, sans-serif", size=13),
        xaxis=dict(title="", tickformat=",.0f", gridcolor="#eee"),
        yaxis=dict(title=""),
        plot_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Totales rápidos debajo
    t_cob = df_g["Cobrado"].sum()
    t_pc = df_g["Por Cobrar"].sum()
    t_pf = df_g["Por Facturar"].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("Cobrado", f"S/ {t_cob:,.2f}")
    c2.metric("Por Cobrar", f"S/ {t_pc:,.2f}")
    c3.metric("Por Facturar", f"S/ {t_pf:,.2f}")
