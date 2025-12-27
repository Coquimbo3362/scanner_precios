import streamlit as st
import pandas as pd
import altair as alt
from supabase import create_client
import os
from dotenv import load_dotenv

st.set_page_config(page_title="Estadísticas", page_icon="📊", layout="wide")

# CSS para achicar espacios
st.markdown("<style>.block-container {padding-top: 1rem;}</style>", unsafe_allow_html=True)

try:
    load_dotenv()
    URL = st.secrets["SUPABASE_URL"] if "SUPABASE_URL" in st.secrets else os.environ.get("SUPABASE_URL")
    KEY = st.secrets["SUPABASE_KEY"] if "SUPABASE_KEY" in st.secrets else os.environ.get("SUPABASE_KEY")
    supabase = create_client(URL, KEY)
except: st.stop()

if 'user' not in st.session_state or not st.session_state['user']:
    st.warning("⚠️ Inicia sesión primero")
    st.stop()

st.markdown("### 📊 Análisis de Precios")

# 1. TRAER DATOS
user_id = st.session_state['user'].id
response = supabase.table('items_compra').select('*, tickets!inner(fecha, supermercados(nombre))').eq('tickets.user_id', user_id).execute()

if not response.data:
    st.info("Aún no tienes datos.")
    st.stop()

df = pd.DataFrame(response.data)
df['fecha'] = pd.to_datetime(df['tickets'].apply(lambda x: x['fecha']))
df['supermercado'] = df['tickets'].apply(lambda x: x['supermercados']['nombre'])

# Limpieza para visualización
df['rubro'] = df['rubro'].fillna('Otros')
df['marca'] = df['marca'].fillna('Genérica')
df['producto_generico'] = df['producto_generico'].fillna(df['nombre_producto'])

# --- PARTE A: ANÁLISIS POR PRODUCTO (Punto 7) ---
st.markdown("#### 🔎 Evolución de Precio (Inflación)")

# Selector de producto (Los ordenamos alfabéticamente)
lista_productos = sorted(df['producto_generico'].unique())
producto_selec = st.selectbox("Selecciona un producto para ver su historia:", lista_productos)

if producto_selec:
    # Filtramos datos
    df_prod = df[df['producto_generico'] == producto_selec].sort_values('fecha')
    
    # Mostramos métricas
    precio_actual = df_prod.iloc[-1]['precio_neto_unitario']
    precio_anterior = df_prod.iloc[0]['precio_neto_unitario']
    variacion = ((precio_actual - precio_anterior) / precio_anterior) * 100 if precio_anterior > 0 else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Precio Último", f"${precio_actual:,.2f}")
    c2.metric("Precio Inicial", f"${precio_anterior:,.2f}")
    c3.metric("Variación Histórica", f"{variacion:+.1f}%", delta_color="inverse")

    # Gráfico de Línea
    chart = alt.Chart(df_prod).mark_line(point=True).encode(
        x='fecha:T',
        y=alt.Y('precio_neto_unitario', title='Precio ($)'),
        color='supermercado',
        tooltip=['fecha', 'supermercado', 'precio_neto_unitario', 'marca']
    ).interactive()
    st.altair_chart(chart, use_container_width=True)

# --- PARTE B: DETALLE ESTRUCTURADO (Punto 6) ---
st.divider()
st.markdown("#### 📝 Detalle de Compras (Árbol)")

# Ordenamos para simular árbol: Rubro -> Marca -> Producto
df_tabla = df[['rubro', 'marca', 'producto_generico', 'supermercado', 'fecha', 'precio_neto_unitario']]
df_tabla = df_tabla.sort_values(by=['rubro', 'marca', 'producto_generico', 'fecha'], ascending=[True, True, True, False])

# Renombramos columnas para que se vea bonito
df_tabla.columns = ['Rubro', 'Marca', 'Producto', 'Supermercado', 'Fecha', 'Precio']

st.dataframe(
    df_tabla,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Precio": st.column_config.NumberColumn(format="$ %.2f"),
        "Fecha": st.column_config.DateColumn(format="DD/MM/YYYY")
    }
)