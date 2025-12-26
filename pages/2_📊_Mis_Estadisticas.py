import streamlit as st
import pandas as pd
from supabase import create_client
import os
from dotenv import load_dotenv

st.set_page_config(page_title="Mis Estadísticas", page_icon="📊")

# --- RECUPERAR SESIÓN Y CONEXIÓN ---
# (Repetimos la conexión porque cada página corre independiente)
try:
    load_dotenv()
    URL = st.secrets["SUPABASE_URL"] if "SUPABASE_URL" in st.secrets else os.environ.get("SUPABASE_URL")
    KEY = st.secrets["SUPABASE_KEY"] if "SUPABASE_KEY" in st.secrets else os.environ.get("SUPABASE_KEY")
    supabase = create_client(URL, KEY)
except:
    st.error("Error de conexión")
    st.stop()

# Verificar si hay usuario logueado (La sesión se comparte entre páginas)
if 'user' not in st.session_state or st.session_state['user'] is None:
    st.warning("⚠️ Debes iniciar sesión en la página principal primero.")
    st.stop()

# --- TÍTULO ---
st.title("📊 Mis Consumos")
st.write(f"Viendo datos de: **{st.session_state['user'].email}**")

# --- 1. TRAER DATOS DE SUPABASE ---
user_id = st.session_state['user'].id

# Consulta SQL implícita: Trae todos mis tickets y sus items
response = supabase.table('items_compra').select(
    '*, tickets!inner(fecha, supermercados(nombre))'
).eq('tickets.user_id', user_id).execute()

data = response.data

if not data:
    st.info("Aún no tienes tickets cargados. Ve al Escáner y sube el primero.")
else:
    # Convertir a DataFrame (Excel poderoso de Python)
    df = pd.DataFrame(data)
    
    # Limpieza de datos para gráficos
    # Los datos vienen anidados (tickets -> fecha), hay que aplanarlos
    df['fecha'] = df['tickets'].apply(lambda x: x['fecha'])
    df['supermercado'] = df['tickets'].apply(lambda x: x['supermercados']['nombre'])
    df['total_item'] = df['cantidad'] * df['precio_neto_unitario']
    
    # --- GRÁFICO 1: GASTO POR RUBRO ---
    st.subheader("💰 Gasto por Rubro")
    gasto_rubro = df.groupby('rubro')['total_item'].sum().sort_values(ascending=False)
    st.bar_chart(gasto_rubro)

    # --- GRÁFICO 2: EVOLUCIÓN EN EL TIEMPO ---
    st.subheader("📅 Evolución de mis compras")
    df['fecha'] = pd.to_datetime(df['fecha'])
    gasto_fecha = df.groupby('fecha')['total_item'].sum()
    st.line_chart(gasto_fecha)

    # --- TABLA DETALLADA ---
    st.divider()
    st.subheader("📝 Detalle de productos")
    st.dataframe(df[['fecha', 'supermercado', 'nombre_producto', 'precio_neto_unitario', 'rubro']])
