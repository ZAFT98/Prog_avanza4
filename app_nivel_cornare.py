"""
Centro de Monitoreo Climático Marinilla
---------------------------------------
Aplicación Streamlit para consulta y visualización de datos
de la estación de Marinilla.

Ejecutar:
    streamlit run app_marinilla.py
"""

import base64
from io import BytesIO
from pathlib import Path

import requests
import pandas as pd
import streamlit as st
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================================================
# CONFIGURACIÓN
# ==============================================================
API_BASE_URL = "https://marco.cornare.gov.co/api/v1/estaciones"
LAT_DEFECTO = 6.1806
LON_DEFECTO = -75.32974

LLAVE_FECHA = "level_date"
LLAVE_VALOR = "level"

CANDIDATOS_LAT = ["lat", "latitude", "latitud"]
CANDIDATOS_LON = ["lng", "lon", "longitude", "longitud"]

# Logo que acompaña la aplicación
LOGO_PATH = Path(__file__).with_name("logo_alcaldia_marinilla.png")

ESTACIONES = {
    "31": {
        "nombre": "Estación Marinilla",
        "ubicacion": "Marinilla, Antioquia",
        "descripcion": "Monitoreo de nivel hídrico",
    }
}

st.set_page_config(
    page_title="Centro de Monitoreo Climático Marinilla",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ==============================================================
# ESTILOS
# ==============================================================
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(180deg, #f3fbf6 0%, #ffffff 100%);
    }

    .block-container {
        max-width: 1450px;
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }

    .top-header {
        background: white;
        border-radius: 18px;
        padding: 16px 24px;
        box-shadow: 0 4px 18px rgba(0, 75, 45, .10);
        border: 1px solid #dceee3;
        margin-bottom: 18px;
    }

    .main-title {
        color: #006b3c;
        font-size: 2.15rem;
        font-weight: 800;
        line-height: 1.1;
        margin: 0;
        margin-top: 25px;
    }

    .subtitle {
        color: #31516e;
        margin-top: 5px;
        font-size: 1rem;
    }

    .station-card {
        background: white;
        border-left: 7px solid #006b3c;
        border-radius: 16px;
        padding: 17px 22px;
        box-shadow: 0 4px 16px rgba(0, 75, 45, .08);
        margin: 12px 0 18px 0;
    }

    .station-name {
        color: #006b3c;
        font-size: 1.45rem;
        font-weight: 800;
        margin-top: 15px;
    }

    .station-info {
        color: #5e6b73;
        margin-top: 4px;
    }

    .section-title {
        color: #006b3c;
        font-size: 1.3rem;
        font-weight: 800;
        margin: 22px 0 10px 0;
    }

    div[data-testid="stMetric"] {
        background: white;
        border: 1px solid #dceee3;
        border-radius: 15px;
        padding: 13px;
        box-shadow: 0 3px 12px rgba(0, 75, 45, .06);
    }

    div[data-testid="stMetricLabel"] {
        color: #006b3c;
    }

    div[data-testid="stMetricValue"] {
        color: #123b68;
    }

    .info-box {
        background: #eaf7ef;
        border-radius: 12px;
        padding: 13px 17px;
        color: #24563e;
        border: 1px solid #d2ebda;
    }

    .footer {
        text-align: center;
        color: #718078;
        font-size: .84rem;
        padding: 28px 0 8px;
    }

    .stButton > button {
        background-color: #006b3c;
        color: white;
        border: none;
        border-radius: 9px;
        font-weight: 700;
    }

    div[data-baseweb="tab-list"] {
        gap: 8px;
    }

    button[data-baseweb="tab"] {
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================
# FUNCIONES
# ==============================================================
def mostrar_logo():
    if LOGO_PATH.exists():
        st.image(LOGO_PATH, width=155)


def obtener_serie_nivel(codigo_estacion, desde, hasta, calidad=1, timeout=30):
    url = f"{API_BASE_URL}/{codigo_estacion}/nivel"
    params = {"desde": desde, "hasta": hasta, "calidad": calidad}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
    }

    try:
        resp = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            verify=False,
        )
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"HTTP {resp.status_code}"
    except requests.exceptions.RequestException as e:
        return None, f"Error de red: {e}"


def obtener_todas_las_paginas(datos_json, timeout=30):
    registros = list(datos_json.get("values", []))
    siguiente_url = datos_json.get("next")

    while siguiente_url:
        try:
            resp = requests.get(
                siguiente_url,
                timeout=timeout,
                verify=False,
            )
        except requests.exceptions.RequestException:
            break

        if resp.status_code != 200:
            break

        pagina = resp.json()
        registros.extend(pagina.get("values", []))
        siguiente_url = pagina.get("next")

    return registros


def detectar_coordenadas(datos_json):
    if not isinstance(datos_json, dict):
        return LAT_DEFECTO, LON_DEFECTO, False

    lat = next((datos_json[k] for k in CANDIDATOS_LAT if k in datos_json), None)
    lon = next((datos_json[k] for k in CANDIDATOS_LON if k in datos_json), None)

    if lat is not None and lon is not None:
        try:
            return float(lat), float(lon), True
        except (TypeError, ValueError):
            pass

    return LAT_DEFECTO, LON_DEFECTO, False


def preparar_dataframe(registros):
    df = pd.DataFrame(registros)

    df = df.rename(
        columns={
            LLAVE_FECHA: "fecha",
            LLAVE_VALOR: "nivel",
        }
    )

    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["nivel"] = pd.to_numeric(df["nivel"], errors="coerce")

    return (
        df.dropna(subset=["fecha", "nivel"])
        .sort_values("fecha")
        .reset_index(drop=True)
    )


def calcular_indice_calidad(df):
    if df.empty or len(df) < 2:
        return 0.0, 0, 0

    df_idx = df.set_index("fecha")
    frecuencia_tipica = df["fecha"].diff().dropna().mode()

    if len(frecuencia_tipica) == 0:
        return 0.0, 0, 0

    frecuencia_tipica = frecuencia_tipica[0]

    rango_completo = pd.date_range(
        start=df_idx.index.min(),
        end=df_idx.index.max(),
        freq=frecuencia_tipica,
    )

    esperados = len(rango_completo)
    huecos = max(0, esperados - len(df_idx))
    completitud = max(0.0, 1 - (huecos / esperados)) if esperados else 0

    q1 = df["nivel"].quantile(.25)
    q3 = df["nivel"].quantile(.75)
    iqr = q3 - q1

    lim_inf = q1 - 1.5 * iqr
    lim_sup = q3 + 1.5 * iqr

    es_outlier = (
        (df["nivel"] < lim_inf)
        | (df["nivel"] > lim_sup)
        | (df["nivel"] < 0)
    )

    proporcion_outliers = es_outlier.mean()

    indice = (
        completitud * .7
        + (1 - proporcion_outliers) * .3
    ) * 100

    return round(indice, 1), huecos, int(es_outlier.sum())


# ==============================================================
# ENCABEZADO
# ==============================================================
header_left, header_right = st.columns([5, 1])

with header_left:
    st.markdown(
        '<div class="main-title">CENTRO DE MONITOREO CLIMÁTICO MARINILLA</div>'
        '<div class="subtitle">Sistema de consulta, visualización y análisis '
        'de información ambiental e hidrológica</div>',
        unsafe_allow_html=True,
    )

with header_right:
    mostrar_logo()


# ==============================================================
# CONTROLES PRINCIPALES — SIN BARRA LATERAL
# ==============================================================
st.markdown('<div class="section-title">Consulta de información</div>',
            unsafe_allow_html=True)

c1, c2, c3, c4, c5 = st.columns([1.3, 2, 1.5, 1.5, 1.2])

with c1:
    codigo_estacion = st.selectbox(
        "Estación",
        options=["31", "208"],
        index=0,
        format_func=lambda x: (
            "31 · Marinilla"
            if x == "31"
            else "208 · Rionegro"
        ),
    )

with c2:
    rango = st.date_input(
        "Rango de fechas",
        value=(
            pd.Timestamp("2026-07-01").date(),
            pd.Timestamp("2026-08-31").date(),
        ),
    )

with c3:
    calidad = st.selectbox(
        "Calidad",
        [1, 0],
        index=0,
        format_func=lambda x: (
            "Datos validados"
            if x == 1
            else "Todos los datos"
        ),
    )

with c4:
    vista = st.selectbox(
        "Vista inicial",
        ["Resumen", "Serie temporal", "Datos"],
    )

with c5:
    st.write("")
    consultar = st.button(
        "🔄 Actualizar",
        use_container_width=True,
    )

if isinstance(rango, tuple) and len(rango) == 2:
    fecha_desde = rango[0].strftime("%Y-%m-%d")
    fecha_hasta = rango[1].strftime("%Y-%m-%d")
else:
    fecha_desde = pd.Timestamp(rango).strftime("%Y-%m-%d")
    fecha_hasta = fecha_desde


# ==============================================================
# CONSULTA AUTOMÁTICA AL ABRIR Y AL ACTUALIZAR
# ==============================================================
params_actuales = (codigo_estacion, fecha_desde, fecha_hasta, calidad)

if (
    "ultima_consulta" not in st.session_state
    or st.session_state.ultima_consulta != params_actuales
    or consultar
):
    with st.spinner("Cargando información de la estación..."):
        datos_crudos, error = obtener_serie_nivel(
            codigo_estacion,
            fecha_desde,
            fecha_hasta,
            calidad,
        )

    st.session_state.ultima_consulta = params_actuales
    st.session_state.datos_crudos = datos_crudos
    st.session_state.error = error


datos_crudos = st.session_state.get("datos_crudos")
error = st.session_state.get("error")

# ==============================================================
# INFORMACIÓN DE ESTACIÓN
# ==============================================================
info = ESTACIONES.get(
    codigo_estacion,
    {
        "nombre": f"Estación {codigo_estacion}",
        "ubicacion": "Estación seleccionada",
        "descripcion": "Monitoreo ambiental",
    },
)

st.markdown(
    f"""
    <div class="station-card">
        <div class="station-name">📍 {info["nombre"]}</div>
        <div class="station-info">
            <b>Código:</b> {codigo_estacion}
            &nbsp; · &nbsp;
            <b>Ubicación:</b> {info["ubicacion"]}
            &nbsp; · &nbsp;
            <b>Variable:</b> Nivel hídrico
        </div>
        <div class="station-info">{info["descripcion"]}</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ==============================================================
# RESULTADOS
# ==============================================================
if error:
    st.error(f"❌ No fue posible consultar la estación: {error}")

elif not datos_crudos:
    st.warning(
        "No hay registros para la estación y rango seleccionado."
    )

else:
    registros = obtener_todas_las_paginas(datos_crudos)
    df = preparar_dataframe(registros)

    if df.empty:
        st.warning("La API respondió, pero no se encontraron datos válidos.")
    else:
        lat, lon, coords_reales = detectar_coordenadas(datos_crudos)
        indice_calidad, huecos, n_outliers = calcular_indice_calidad(df)

        # ==========================================================
        # RESUMEN
        # ==========================================================
        st.markdown(
            '<div class="section-title">Resumen de monitoreo</div>',
            unsafe_allow_html=True,
        )

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric("Lecturas", f"{len(df):,}")
        col2.metric("Nivel promedio", f"{df['nivel'].mean():.2f}")
        col3.metric("Nivel mínimo", f"{df['nivel'].min():.2f}")
        col4.metric("Nivel máximo", f"{df['nivel'].max():.2f}")
        col5.metric("Calidad", f"{indice_calidad} / 100")

        # ==========================================================
        # PESTAÑAS
        # ==========================================================
        tab_resumen, tab_serie, tab_mapa, tab_datos = st.tabs(
            ["📊 Resumen", "📈 Serie temporal", "📍 Ubicación", "📋 Datos"]
        )

        with tab_resumen:
            a, b = st.columns([2, 1])

            with a:
                st.markdown("#### Evolución reciente")
                st.line_chart(
                    df.set_index("fecha")["nivel"],
                    height=390,
                )

            with b:
                st.markdown("#### Indicadores")
                st.markdown(
                    f"""
                    <div class="info-box">
                    <b>Periodo consultado</b><br>
                    {fecha_desde} → {fecha_hasta}<br><br>
                    <b>Huecos detectados:</b> {huecos}<br>
                    <b>Outliers:</b> {n_outliers}<br>
                    <b>Última lectura:</b> {df.iloc[-1]['nivel']:.2f}<br>
                    <b>Fecha última lectura:</b>
                    {df.iloc[-1]['fecha'].strftime('%Y-%m-%d %H:%M')}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                st.markdown("#### Interpretación")
                st.write(
                    "La serie permite observar cambios del nivel a lo "
                    "largo del periodo seleccionado y detectar aumentos, "
                    "disminuciones y valores atípicos."
                )

        with tab_serie:
            st.markdown("#### Comportamiento del nivel")
            st.line_chart(
                df.set_index("fecha")["nivel"],
                height=500,
            )

        with tab_mapa:
            st.markdown("#### Ubicación de la estación")

            if not coords_reales:
                st.info(
                    "La API no proporcionó coordenadas. "
                    "Se muestra una ubicación de referencia."
                )

            st.map(
                pd.DataFrame(
                    {
                        "lat": [lat],
                        "lon": [lon],
                    }
                ),
                zoom=11,
            )

        with tab_datos:
            st.markdown("#### Registros consultados")
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )

            csv = df.to_csv(index=False).encode("utf-8")

            st.download_button(
                "⬇️ Descargar datos CSV",
                csv,
                file_name=(
                    f"monitoreo_marinilla_estacion_"
                    f"{codigo_estacion}.csv"
                ),
                mime="text/csv",
            )

        with st.expander("🔎 Detalle de calidad de los datos"):
            st.write(f"**Huecos de reporte:** {huecos}")
            st.write(
                f"**Outliers detectados:** "
                f"{n_outliers} de {len(df)} lecturas"
            )
            st.write(
                "El índice combina completitud de la serie (70%) "
                "y proporción de datos sin outliers (30%)."
            )


# ==============================================================
# PIE DE PÁGINA
# ==============================================================
st.markdown(
    """
    <div class="footer">
        <b>Centro de Monitoreo Climático Marinilla</b><br>
        Monitoreo y visualización de información ambiental e hidrológica<br>
        Información consultada desde MARCO / CORNARE
    </div>
    """,
    unsafe_allow_html=True,
)
