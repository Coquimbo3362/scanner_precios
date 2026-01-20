import streamlit as st
import pandas as pd
import altair as alt
from supabase import create_client
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Configuración
st.set_page_config(page_title="Análisis Pareto", page_icon="⚖️", layout="wide")
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

st.title("⚖️ Análisis de Pareto (80/20)")
st.markdown("""
**¿En qué se va el dinero?**  
La Ley de Pareto sugiere que el **80% de tu gasto** proviene de solo el **20% de los productos**. 
Aquí identificamos esos productos "VITALES" para que sepas dónde conviene comprarlos.
""")

# --- 1. CARGA DE DATOS ---
@st.cache_data(ttl=60)
def obtener_datos():
    try:
        # Traemos datos brutos
        response = supabase.table('items_compra').select(
            '*, tickets!inner(fecha, supermercados(nombre))'
        ).execute()
        
        if not response.data: return pd.DataFrame()
        
        df = pd.DataFrame(response.data)
        
        # Procesamiento básico
        df['fecha'] = pd.to_datetime(df['tickets'].apply(lambda x: x['fecha']))
        df['sucursal_original'] = df['tickets'].apply(lambda x: x['supermercados']['nombre'] if x['supermercados'] else "Desconocido")
        df['gasto_total'] = df['precio_neto_unitario'] * df['cantidad']
        
        # Limpieza Nombres y Tipos
        def limpiar_nombre(nombre):
            n = nombre.upper() if nombre else ""
            if 'COTO' in n: return 'COTO'
            if 'JUMBO' in n: return 'JUMBO'
            if 'CARREFOUR' in n: return 'CARREFOUR'
            if 'DIA' in n: return 'DIA'
            if 'DISCO' in n: return 'DISCO'
            if 'VEA' in n: return 'VEA'
            if 'MAKRO' in n: return 'MAKRO'
            if 'FARMACITY' in n or 'SIMPLICITY' in n or 'FARMCITY' in n: return 'FARMACITY'
            if 'SELMA' in n: return 'SELMA'
            return n

        df['cadena'] = df['sucursal_original'].apply(limpiar_nombre)
        
        def clasificar_tipo(cadena):
            if cadena in ['FARMACITY', 'SELMA', 'SIMPLICITY']: return 'Farmacia'
            return 'Supermercado'
        
        df['tipo_comercio'] = df['cadena'].apply(clasificar_tipo)
        
        # Nombres de producto limpios
        df['producto_final'] = df['producto_generico'].fillna(df['nombre_producto'])
        df['rubro'] = df['rubro'].fillna('Otros')
        
        return df
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

df_raw = obtener_datos()

if df_raw.empty:
    st.info("Faltan datos para el análisis.")
    st.stop()

# --- 2. FILTROS ---
with st.expander("🔎 Configurar Análisis", expanded=True):
    c1, c2, c3 = st.columns(3)
    
    # Filtro Tipo
    tipos = ['Todos'] + list(df_raw['tipo_comercio'].unique())
    sel_tipo = c1.selectbox("Tipo de Comercio", tipos)
    
    # Filtro Rubro
    df_temp = df_raw if sel_tipo == 'Todos' else df_raw[df_raw['tipo_comercio'] == sel_tipo]
    rubros = ['Todos'] + sorted(list(df_temp['rubro'].unique()))
    sel_rubro = c2.selectbox("Rubro", rubros)
    
    # Filtro Fecha (Default: Últimos 90 días)
    hoy = datetime.now().date()
    hace_3_meses = hoy - timedelta(days=90)
    sel_fechas = c3.date_input("Período", [hace_3_meses, hoy])

# Aplicar Filtros
mask = (df_raw['fecha'].dt.date >= sel_fechas[0]) & (df_raw['fecha'].dt.date <= sel_fechas[1])
if sel_tipo != 'Todos': mask &= (df_raw['tipo_comercio'] == sel_tipo)
if sel_rubro != 'Todos': mask &= (df_raw['rubro'] == sel_rubro)

df = df_raw[mask].copy()

if df.empty:
    st.warning("No hay compras en este período con estos filtros.")
    st.stop()

# --- 3. CÁLCULO DE PARETO ---
# Agrupamos por producto y sumamos gasto
pareto = df.groupby('producto_final')['gasto_total'].sum().reset_index()
pareto = pareto.sort_values('gasto_total', ascending=False)

# Cálculos acumulados
total_general = pareto['gasto_total'].sum()
pareto['porcentaje'] = (pareto['gasto_total'] / total_general) * 100
pareto['acumulado'] = pareto['porcentaje'].cumsum()

# Definir Categoría ABC
# A: Hasta el 80% del gasto (Los Vitales)
# B: del 80% al 95%
# C: El resto (Triviales)
def clasificar_abc(acumulado):
    if acumulado <= 80: return 'A - Vital (80% Gasto)'
    elif acumulado <= 95: return 'B - Importante'
    else: return 'C - Trivial'

pareto['categoria'] = pareto['acumulado'].apply(clasificar_abc)

# --- 4. VISUALIZACIÓN ---
st.divider()

# Métricas Resumen
prods_a = pareto[pareto['categoria'].str.contains('A -')]['producto_final'].count()
gasto_a = pareto[pareto['categoria'].str.contains('A -')]['gasto_total'].sum()
total_prods = pareto['producto_final'].count()

c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
c_kpi1.metric("Total Gastado (Período)", f"${total_general:,.0f}")
c_kpi2.metric("Productos Vitales (Clase A)", f"{prods_a} de {total_prods}", help="Son pocos productos que se llevan casi todo tu dinero.")
c_kpi3.metric("Gasto en Vitales", f"${gasto_a:,.0f} ({gasto_a/total_general*100:.1f}%)")

# Gráfico de Barras Pareto (Top 20 productos)
st.subheader("📊 Top Productos que más impactan tu bolsillo")
chart_data = pareto.head(20) # Mostramos solo el top 20 para que entre en pantalla

base = alt.Chart(chart_data).encode(
    x=alt.X('producto_final', sort='-y', axis=alt.Axis(labelAngle=-45, title=None)),
    tooltip=['producto_final', alt.Tooltip('gasto_total', format='$,.2f'), 'acumulado']
)

bars = base.mark_bar().encode(
    y=alt.Y('gasto_total', title='Gasto Total ($)'),
    color=alt.Color('categoria', scale=alt.Scale(domain=['A - Vital (80% Gasto)', 'B - Importante', 'C - Trivial'], range=['#FF4B4B', '#FFAA00', '#CCCCCC']))
)

line = base.mark_line(color='red', point=True).encode(
    y=alt.Y('acumulado', title='% Acumulado', scale=alt.Scale(domain=[0, 100])),
)

st.altair_chart((bars + line).resolve_scale(y='independent'), use_container_width=True)

# --- 5. ANÁLISIS DETALLADO (DRILL DOWN) ---
st.divider()
st.subheader("🧐 Analizador de Compra")
st.info("Selecciona un producto de la lista 'Vital' para ver su historial y dónde conviene comprarlo.")

# Lista solo con los productos Clase A y B para no ensuciar
lista_vitales = pareto[pareto['acumulado'] <= 95]['producto_final'].unique()
prod_selec = st.selectbox("Seleccionar Producto:", lista_vitales)

if prod_selec:
    # Filtramos el DF original (el que tiene todas las fechas)
    df_historia = df[df['producto_final'] == prod_selec].sort_values('fecha', ascending=False)
    
    # Métricas del producto
    precio_min = df_historia['precio_neto_unitario'].min()
    precio_max = df_historia['precio_neto_unitario'].max()
    super_barato = df_historia.loc[df_historia['precio_neto_unitario'].idxmin()]['cadena']
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Mejor Precio Pagado", f"${precio_min:,.2f}")
    m2.metric("Dónde", super_barato)
    m3.metric("Precio Máximo Pagado", f"${precio_max:,.2f}")
    
    # Gráfico de evolución del precio
    chart_line = alt.Chart(df_historia).mark_line(point=True).encode(
        x='fecha:T',
        y=alt.Y('precio_neto_unitario', title='Precio Unitario ($)', scale=alt.Scale(zero=False)),
        color='cadena',
        tooltip=['fecha', 'cadena', 'precio_neto_unitario', 'cantidad']
    ).properties(height=300)
    
    st.altair_chart(chart_line, use_container_width=True)
    
    # Tabla detalle
    st.write("Historial de compras:")
    st.dataframe(
        df_historia[['fecha', 'cadena', 'precio_neto_unitario', 'cantidad', 'gasto_total']],
        hide_index=True,
        column_config={
            "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
            "precio_neto_unitario": st.column_config.NumberColumn("Precio Unit.", format="$ %.2f"),
            "gasto_total": st.column_config.NumberColumn("Total Ticket", format="$ %.2f")
        },
        use_container_width=True
    )