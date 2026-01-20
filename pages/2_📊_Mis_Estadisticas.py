import streamlit as st
import pandas as pd
import altair as alt
from supabase import create_client
import os
from dotenv import load_dotenv

st.set_page_config(page_title="Mis Estadísticas", page_icon="📊", layout="wide")
st.markdown("<style>.block-container {padding-top: 2rem;}</style>", unsafe_allow_html=True)

try:
    load_dotenv()
    URL = st.secrets["SUPABASE_URL"] if "SUPABASE_URL" in st.secrets else os.environ.get("SUPABASE_URL")
    KEY = st.secrets["SUPABASE_KEY"] if "SUPABASE_KEY" in st.secrets else os.environ.get("SUPABASE_KEY")
    supabase = create_client(URL, KEY)
except: st.stop()

if 'user' not in st.session_state or not st.session_state['user']:
    st.warning("⚠️ Inicia sesión primero")
    st.stop()

st.title("📊 Mis Consumos")

# 1. TRAER DATOS
user_id = st.session_state['user'].id
response = supabase.table('items_compra').select('*, tickets!inner(fecha, supermercados(nombre))').eq('tickets.user_id', user_id).execute()

if not response.data:
    st.info("Aún no tienes datos cargados.")
    st.stop()

df = pd.DataFrame(response.data)

# --- FILTRO DE SEGURIDAD (PRECIOS > 0) ---
df = df[df['precio_neto_unitario'] > 0]

if df.empty:
    st.warning("No hay datos válidos (Precios > 0).")
    st.stop()

df['fecha'] = pd.to_datetime(df['tickets'].apply(lambda x: x['fecha']))
df['sucursal_original'] = df['tickets'].apply(lambda x: x['supermercados']['nombre'])
df['gasto_total'] = df['precio_neto_unitario'] * df['cantidad']

# --- LIMPIEZA DE NOMBRES (Estandarización) ---
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

df['supermercado'] = df['sucursal_original'].apply(limpiar_nombre)
df['rubro'] = df['rubro'].fillna('Otros')
df['marca'] = df['marca'].fillna('Genérica')
df['producto_final'] = df['producto_generico'].fillna(df['nombre_producto'])

# --- PARTE A: ANÁLISIS POR PRODUCTO ---
st.markdown("#### 🔎 Evolución de Precio")

lista_productos = sorted(df['producto_final'].unique())
producto_selec = st.selectbox("Selecciona un producto:", lista_productos)

if producto_selec:
    df_prod = df[df['producto_final'] == producto_selec].sort_values('fecha')
    
    precio_actual = df_prod.iloc[-1]['precio_neto_unitario']
    precio_anterior = df_prod.iloc[0]['precio_neto_unitario']
    variacion = ((precio_actual - precio_anterior) / precio_anterior) * 100 if precio_anterior > 0 else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Precio Último", f"${precio_actual:,.2f}")
    c2.metric("Precio Inicial", f"${precio_anterior:,.2f}")
    c3.metric("Variación Histórica", f"{variacion:+.1f}%", delta_color="inverse")

    chart = alt.Chart(df_prod).mark_line(point=True).encode(
        x='fecha:T',
        y=alt.Y('precio_neto_unitario', title='Precio ($)'),
        color='supermercado',
        tooltip=['fecha', 'supermercado', 'precio_neto_unitario', 'marca']
    ).interactive()
    st.altair_chart(chart, use_container_width=True)

# --- PARTE B: DETALLE FILTRADO ---
st.divider()
st.markdown(f"#### 📝 Detalle de Compras ({producto_selec})")

# Usamos el DF filtrado arriba
df_tabla = df_prod[['rubro', 'marca', 'producto_final', 'supermercado', 'fecha', 'precio_neto_unitario', 'cantidad', 'gasto_total']]
df_tabla = df_tabla.sort_values(by='fecha', ascending=False)

df_tabla.columns = ['Rubro', 'Marca', 'Producto', 'Supermercado', 'Fecha', 'Precio Unit.', 'Cant.', 'Total']

st.dataframe(
    df_tabla,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Precio Unit.": st.column_config.NumberColumn(format="$ %.2f"),
        "Total": st.column_config.NumberColumn(format="$ %.2f"),
        "Fecha": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Cant.": st.column_config.NumberColumn(format="%.2f")
    }
)