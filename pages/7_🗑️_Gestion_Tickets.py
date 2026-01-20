import streamlit as st
import pandas as pd
import time
from supabase import create_client
import os
from dotenv import load_dotenv

st.set_page_config(page_title="Gestión de Tickets", page_icon="🗑️", layout="centered")

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

st.title("🗑️ Gestión de Tickets")
st.info("Aquí puedes ver tu historial y eliminar tickets incorrectos o duplicados.")

# --- 1. TRAER TICKETS DEL USUARIO ---
user_id = st.session_state['user'].id

# Traemos tickets con el nombre del super
response = supabase.table('tickets').select(
    'id, fecha, hora, monto_total, supermercados(nombre)'
).eq('user_id', user_id).order('fecha', desc=True).execute()

tickets = response.data

if not tickets:
    st.warning("No tienes tickets cargados.")
    st.stop()

# --- 2. SELECCIONAR TICKET ---
# Creamos un diccionario para el selectbox: "Texto Bonito" -> "ID Real"
opciones_visuales = {}
for t in tickets:
    nombre_super = t['supermercados']['nombre'] if t['supermercados'] else "Desconocido"
    texto = f"{t['fecha']} | {nombre_super} | ${t['monto_total']}"
    opciones_visuales[texto] = t['id']

st.divider()
st.subheader("1. Selecciona el Ticket")
seleccion = st.selectbox("Elige cuál quieres revisar o borrar:", list(opciones_visuales.keys()))
ticket_id_seleccionado = opciones_visuales[seleccion]

# --- 3. MOSTRAR DETALLE (PREVIEW) ---
st.subheader("2. Contenido del Ticket")
st.write("Revisa los productos antes de borrar:")

# Traer items de ese ticket
res_items = supabase.table('items_compra').select('*').eq('ticket_id', ticket_id_seleccionado).execute()
df_items = pd.DataFrame(res_items.data)

if not df_items.empty:
    st.dataframe(
        df_items[['nombre_producto', 'cantidad', 'precio_neto_unitario', 'rubro']],
        hide_index=True,
        use_container_width=True
    )
else:
    st.warning("Este ticket está vacío (no tiene items).")

# --- 4. BOTÓN DE BORRADO ---
st.divider()
st.subheader("3. Acción")

col1, col2 = st.columns([3, 1])
with col1:
    st.write("Si lo borras, esta acción no se puede deshacer.")
with col2:
    if st.button("🗑️ Eliminar Ticket", type="primary", use_container_width=True):
        try:
            # Borramos el ticket (Supabase borrará los items en cascada automáticamente)
            supabase.table('tickets').delete().eq('id', ticket_id_seleccionado).execute()
            
            st.success("✅ Ticket eliminado correctamente.")
            time.sleep(2)
            st.rerun() # Recargar la página para actualizar la lista
        except Exception as e:
            st.error(f"Error al borrar: {e}")