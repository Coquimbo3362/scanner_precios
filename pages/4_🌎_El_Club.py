import streamlit as st
import pandas as pd
import altair as alt
from supabase import create_client
import os
from dotenv import load_dotenv
import datetime

st.set_page_config(page_title="El Club", page_icon="🌎", layout="wide")

# CSS Ajustes
st.markdown("<style>.block-container {padding-top: 1rem;}</style>", unsafe_allow_html=True)

# --- CONEXIÓN ---
try:
    load_dotenv()
    URL = st.secrets["SUPABASE_URL"] if "SUPABASE_URL" in st.secrets else os.environ.get("SUPABASE_URL")
    KEY = st.secrets["SUPABASE_KEY"] if "SUPABASE_KEY" in st.secrets else os.environ.get("SUPABASE_KEY")
    supabase = create_client(URL, KEY)
except: st.stop()

st.markdown("### 🌎 Inteligencia del Club")
st.caption("Comparativa de precios basada en los tickets de todos los socios.")

# --- 1. DATOS GLOBALES (DE TODOS LOS USUARIOS) ---
# Traemos los últimos 1000 items cargados por CUALQUIER usuario
response = supabase.table('items_compra').select(
    'precio_neto_unitario, nombre_producto, producto_generico, rubro, marca, tickets(fecha, sucursal_localidad, supermercados(nombre))'
).order('created_at', desc=True).limit(1000).execute()

if not response.data:
    st.info("Aún no hay suficientes datos en la comunidad.")
    st.stop()

df = pd.DataFrame(response.data)

# Aplanar datos
df['Fecha'] = pd.to_datetime(df['tickets'].apply(lambda x: x['fecha']))
df['Supermercado'] = df['tickets'].apply(lambda x: x['supermercados']['nombre'])
df['Localidad'] = df['tickets'].apply(lambda x: x['sucursal_localidad'])
df['Producto'] = df['producto_generico'].fillna(df['nombre_producto'])
df['Precio'] = df['precio_neto_unitario']

# --- KPI 1: RANKING DE SUPERMERCADOS (¿Quién es más barato hoy?) ---
st.subheader("🏆 Ranking de Precios Promedio")
st.caption("Precio promedio por item en cada cadena (basado en lo que compran los socios).")

# Agrupamos por super y calculamos precio promedio (simplificado)
# En el futuro esto se hará con una 'Canasta Básica' definida.
ranking = df.groupby('Supermercado')['Precio'].mean().reset_index().sort_values('Precio')

chart_rank = alt.Chart(ranking).mark_bar().encode(
    x=alt.X('Precio', title='Precio Promedio ($)'),
    y=alt.Y('Supermercado', sort='x'),
    color=alt.Color('Precio', scale=alt.Scale(scheme='greens', reverse=True)),
    tooltip=['Supermercado', alt.Tooltip('Precio', format='$,.0f')]
).properties(height=300)

st.altair_chart(chart_rank, use_container_width=True)

# --- KPI 2: BUSCADOR COMUNITARIO ---
st.divider()
st.subheader("🔍 Comparador de Productos")

lista_prods = sorted(df['Producto'].unique().astype(str))
prod_selec = st.selectbox("¿Qué producto quieres comparar?", lista_prods)

if prod_selec:
    df_prod = df[df['Producto'] == prod_selec]
    
    # Métricas
    min_val = df_prod['Precio'].min()
    avg_val = df_prod['Precio'].mean()
    max_val = df_prod['Precio'].max()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Mínimo Conseguido", f"${min_val:,.0f}")
    c2.metric("Promedio Club", f"${avg_val:,.0f}")
    c3.metric("Máximo Detectado", f"${max_val:,.0f}")
    
    # Gráfico de dispersión (Scatter Plot)
    # Muestra cada compra como un punto. Eje X fecha, Eje Y precio.
    st.markdown("#### Dispersión de precios")
    scatter = alt.Chart(df_prod).mark_circle(size=100).encode(
        x='Fecha',
        y='Precio',
        color='Supermercado',
        tooltip=['Fecha', 'Supermercado', 'Precio', 'Localidad']
    ).interactive()
    
    st.altair_chart(scatter, use_container_width=True)
    
    # Tabla de oportunidades
    st.markdown("#### ¿Dónde se consiguió más barato?")
    mejores_precios = df_prod.sort_values('Precio').head(5)[['Supermercado', 'Precio', 'Fecha', 'Localidad']]
    st.dataframe(mejores_precios, use_container_width=True, hide_index=True)

# --- KPI 3: INFLACIÓN POR RUBRO (Comunidad) ---
st.divider()
st.subheader("📈 Tendencia por Rubro")
rubro_selec = st.selectbox("Selecciona Rubro", df['rubro'].unique())

if rubro_selec:
    df_rubro = df[df['rubro'] == rubro_selec]
    linea = alt.Chart(df_rubro).mark_line(interpolate='basis').encode(
        x='yearmonth(Fecha)',
        y='mean(Precio)',
        color='rubro'
    ).properties(height=300)
    st.altair_chart(linea, use_container_width=True)