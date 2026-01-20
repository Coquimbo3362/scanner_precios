import streamlit as st
import pandas as pd
import altair as alt
from supabase import create_client
import os
from dotenv import load_dotenv

st.set_page_config(page_title="El Club", page_icon="🌎", layout="wide")
st.markdown("<style>.block-container {padding-top: 2rem;}</style>", unsafe_allow_html=True)

try:
    load_dotenv()
    URL = st.secrets["SUPABASE_URL"] if "SUPABASE_URL" in st.secrets else os.environ.get("SUPABASE_URL")
    KEY = st.secrets["SUPABASE_KEY"] if "SUPABASE_KEY" in st.secrets else os.environ.get("SUPABASE_KEY")
    supabase = create_client(URL, KEY)
except: st.stop()

st.title("🌎 Inteligencia del Club")
st.caption("Comparativa basada en datos de todos los socios.")

# --- DATOS GLOBALES ---
# Traemos últimos 2000 registros para tener muestra
response = supabase.table('items_compra').select(
    'precio_neto_unitario, nombre_producto, producto_generico, rubro, marca, tickets(fecha, sucursal_localidad, supermercados(nombre))'
).order('created_at', desc=True).limit(2000).execute()

if not response.data:
    st.info("Faltan datos en la comunidad.")
    st.stop()

df = pd.DataFrame(response.data)

# --- FILTRO DE SEGURIDAD (PRECIOS > 0) ---
df = df[df['precio_neto_unitario'] > 0]

if df.empty:
    st.warning("No hay datos válidos.")
    st.stop()

# Procesamiento
df['Fecha'] = pd.to_datetime(df['tickets'].apply(lambda x: x['fecha']))
df['sucursal_raw'] = df['tickets'].apply(lambda x: x['supermercados']['nombre'] if x['supermercados'] else 'Desconocido')
df['Localidad'] = df['tickets'].apply(lambda x: x['sucursal_localidad'] or 'S/D')
df['Producto'] = df['producto_generico'].fillna(df['nombre_producto'])
df['Precio'] = df['precio_neto_unitario']

# Limpieza de Supermercados (Igual que en las otras apps)
def limpiar_nombre(nombre):
    n = nombre.upper()
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

df['Supermercado'] = df['sucursal_raw'].apply(limpiar_nombre)

# --- KPI 1: RANKING PRECIOS ---
st.subheader("🏆 Ranking de Precios Promedio")
st.caption("Quién vende más barato (promedio general).")

ranking = df.groupby('Supermercado')['Precio'].mean().reset_index().sort_values('Precio')

chart_rank = alt.Chart(ranking).mark_bar().encode(
    x=alt.X('Precio', title='Precio Promedio ($)'),
    y=alt.Y('Supermercado', sort='x'),
    color=alt.Color('Precio', scale=alt.Scale(scheme='greens', reverse=True)),
    tooltip=['Supermercado', alt.Tooltip('Precio', format='$,.0f')]
).properties(height=300)

st.altair_chart(chart_rank, use_container_width=True)

# --- KPI 2: COMPARADOR ---
st.divider()
st.subheader("🔍 Comparador de Productos")

lista_prods = sorted(df['Producto'].unique().astype(str))
prod_selec = st.selectbox("¿Qué producto quieres comparar?", lista_prods)

if prod_selec:
    df_prod = df[df['Producto'] == prod_selec]
    
    min_val = df_prod['Precio'].min()
    avg_val = df_prod['Precio'].mean()
    max_val = df_prod['Precio'].max()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Mínimo Conseguido", f"${min_val:,.0f}")
    c2.metric("Promedio Club", f"${avg_val:,.0f}")
    c3.metric("Máximo Detectado", f"${max_val:,.0f}")
    
    st.markdown("#### Dispersión de precios")
    scatter = alt.Chart(df_prod).mark_circle(size=100).encode(
        x='Fecha',
        y='Precio',
        color='Supermercado',
        tooltip=['Fecha', 'Supermercado', 'Precio', 'Localidad']
    ).interactive()
    
    st.altair_chart(scatter, use_container_width=True)
    
    st.markdown("#### Oportunidades (Top 5 Baratos)")
    mejores = df_prod.sort_values('Precio').head(5)[['Supermercado', 'Precio', 'Fecha', 'Localidad']]
    st.dataframe(mejores, use_container_width=True, hide_index=True, column_config={"Precio": st.column_config.NumberColumn(format="$ %.2f"), "Fecha": st.column_config.DateColumn(format="DD/MM/YYYY")})