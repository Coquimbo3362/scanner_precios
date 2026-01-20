import streamlit as st
import pandas as pd
import altair as alt
from supabase import create_client
import os
from dotenv import load_dotenv

# Configuración de página
st.set_page_config(page_title="Tablero General", page_icon="📈", layout="wide")
st.markdown("<style>.block-container {padding-top: 2rem;}</style>", unsafe_allow_html=True)

# --- CONEXIÓN ---
try:
    load_dotenv()
    URL = st.secrets["SUPABASE_URL"] if "SUPABASE_URL" in st.secrets else os.environ.get("SUPABASE_URL")
    KEY = st.secrets["SUPABASE_KEY"] if "SUPABASE_KEY" in st.secrets else os.environ.get("SUPABASE_KEY")
    supabase = create_client(URL, KEY)
except: st.stop()

if 'user' not in st.session_state or not st.session_state['user']:
    st.warning("⚠️ Inicia sesión primero")
    st.stop()

st.title("📈 Tablero de Inteligencia")

# --- 1. CARGA Y PROCESAMIENTO ---
@st.cache_data(ttl=60) 
def obtener_datos():
    try:
        response = supabase.table('items_compra').select(
            '*, tickets!inner(fecha, supermercados(nombre))'
        ).execute()
        
        if not response.data: return pd.DataFrame()
        
        df = pd.DataFrame(response.data)
        
        # Aplanar datos
        df['fecha'] = pd.to_datetime(df['tickets'].apply(lambda x: x['fecha']))
        
        df['sucursal_original'] = df['tickets'].apply(
            lambda x: x['supermercados']['nombre'] if x['supermercados'] else "Desconocido"
        )
        
        df['gasto_total'] = df['precio_neto_unitario'] * df['cantidad']
        
        # --- LIMPIEZA DE NOMBRES MEJORADA ---
        def limpiar_nombre(nombre):
            n = nombre.upper() if nombre else ""
            if 'COTO' in n: return 'COTO'
            if 'JUMBO' in n: return 'JUMBO'
            if 'CARREFOUR' in n: return 'CARREFOUR'
            if 'DIA' in n: return 'DIA'
            if 'DISCO' in n: return 'DISCO'
            if 'VEA' in n: return 'VEA'
            if 'MAKRO' in n: return 'MAKRO'
            # Agregamos variaciones de Farmacity
            if 'FARMACITY' in n or 'SIMPLICITY' in n or 'FARMCITY' in n: return 'FARMACITY'
            if 'SELMA' in n: return 'SELMA'
            return n

        df['cadena_comercial'] = df['sucursal_original'].apply(limpiar_nombre)

        # --- Clasificación Tipo ---
        def clasificar_tipo(cadena):
            farmacias = ['FARMACITY', 'SELMA', 'SIMPLICITY']
            if cadena in farmacias: return 'Farmacia'
            return 'Supermercado'

        df['tipo_comercio'] = df['cadena_comercial'].apply(clasificar_tipo)

        # Arreglar los NULLs
        df['producto_final'] = df['producto_generico'].fillna(df['nombre_producto'])
        df['rubro'] = df['rubro'].fillna('Sin Clasificar')
        
        return df

    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame()

df = obtener_datos()

if df.empty:
    st.info("No hay datos cargados aún.")
    st.stop()

# --- 2. FILTROS GENERALES ---
with st.expander("🔎 Filtros Generales", expanded=True):
    c1, c2, c3 = st.columns(3)
    
    # Filtro Tipo
    tipos = ['Todos'] + list(df['tipo_comercio'].unique())
    sel_tipo = c1.selectbox("Tipo de Comercio", tipos)
    
    # Filtrar DF parcial
    df_temp = df if sel_tipo == 'Todos' else df[df['tipo_comercio'] == sel_tipo]
    
    # Filtro Rubro
    rubros = ['Todos'] + list(df_temp['rubro'].unique())
    sel_rubro = c2.selectbox("Rubro", rubros)
    
    # Filtro Fecha
    min_date = df['fecha'].min().date()
    max_date = df['fecha'].max().date()
    sel_fechas = c3.date_input("Rango de Fechas", [min_date, max_date])

# Aplicar filtros generales
if len(sel_fechas) == 2:
    mask = (df['fecha'].dt.date >= sel_fechas[0]) & (df['fecha'].dt.date <= sel_fechas[1])
    if sel_tipo != 'Todos': mask &= (df['tipo_comercio'] == sel_tipo)
    if sel_rubro != 'Todos': mask &= (df['rubro'] == sel_rubro)
    df_filtrado = df[mask]
else:
    df_filtrado = df

# --- 3. GRÁFICOS RESUMEN ---
st.divider()

if df_filtrado.empty:
    st.warning("No hay datos para estos filtros.")
    st.stop()

# Métricas
total_gastado = df_filtrado['gasto_total'].sum()
items_comprados = df_filtrado['cantidad'].sum()
col_met1, col_met2 = st.columns(2)
col_met1.metric("Gasto Total", f"${total_gastado:,.2f}")
col_met2.metric("Unidades", f"{items_comprados:.0f}")

c_chart1, c_chart2 = st.columns([2, 1])

with c_chart1:
    st.subheader("📊 Evolución del Gasto")
    chart_bar = alt.Chart(df_filtrado).mark_bar().encode(
        x=alt.X('yearmonth(fecha):O', title='Mes'),
        y=alt.Y('sum(gasto_total)', title='Monto ($)'),
        color='cadena_comercial',
        tooltip=['yearmonth(fecha)', 'cadena_comercial', 'sum(gasto_total)']
    ).interactive()
    st.altair_chart(chart_bar, use_container_width=True)

with c_chart2:
    st.subheader("🛒 Participación")
    chart_pie = alt.Chart(df_filtrado).mark_arc(innerRadius=50).encode(
        theta=alt.Theta(field="gasto_total", aggregate="sum"),
        color=alt.Color(field="cadena_comercial"),
        tooltip=['cadena_comercial', 'sum(gasto_total)']
    )
    st.altair_chart(chart_pie, use_container_width=True)

# --- 4. DETALLE DE PRODUCTOS (CORREGIDO) ---
st.divider()
st.subheader("📝 Historial de Productos")

# Buscador de Producto
lista_productos_disponibles = ['Todos'] + sorted(list(df_filtrado['producto_final'].unique()))
sel_producto = st.selectbox("🔍 Buscar un producto específico:", lista_productos_disponibles)

# FILTRO DE TABLA (Esto era lo que faltaba conectar)
if sel_producto != 'Todos':
    df_tabla = df_filtrado[df_filtrado['producto_final'] == sel_producto]
else:
    df_tabla = df_filtrado

# Mostrar Tabla
st.dataframe(
    df_tabla[['fecha', 'cadena_comercial', 'producto_final', 'cantidad', 'precio_neto_unitario', 'gasto_total']].sort_values('fecha', ascending=False),
    column_config={
        "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
        "precio_neto_unitario": st.column_config.NumberColumn("Precio Unit.", format="$ %.2f"),
        "gasto_total": st.column_config.NumberColumn("Total", format="$ %.2f"),
        "producto_final": "Producto",
        "cadena_comercial": "Comercio"
    },
    use_container_width=True,
    hide_index=True
)