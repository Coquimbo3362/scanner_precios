import streamlit as st
import time
import json
import os
from PIL import Image
from dotenv import load_dotenv
import google.generativeai as genai
from supabase import create_client, Client
from gotrue.errors import AuthApiError # Para manejar errores de login

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Club de Precios", page_icon="🛒", layout="centered")

# --- CARGA DE SECRETOS (Compatibilidad Local y Nube) ---
# Si estamos en local, usa .env. Si estamos en la nube, usa st.secrets
try:
    load_dotenv()
    # Prioridad: st.secrets (Nube) -> os.environ (Local)
    URL = st.secrets["SUPABASE_URL"] if "SUPABASE_URL" in st.secrets else os.environ.get("SUPABASE_URL")
    KEY = st.secrets["SUPABASE_KEY"] if "SUPABASE_KEY" in st.secrets else os.environ.get("SUPABASE_KEY")
    GOOGLE_KEY = st.secrets["GOOGLE_API_KEY"] if "GOOGLE_API_KEY" in st.secrets else os.environ.get("GOOGLE_API_KEY")

    supabase: Client = create_client(URL, KEY)
    genai.configure(api_key=GOOGLE_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    st.error(f"❌ Error de configuración: {e}")
    st.stop()

# --- GESTIÓN DE SESIÓN ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

def login():
    st.subheader("🔐 Ingreso Socios")
    email = st.text_input("Email")
    password = st.text_input("Contraseña", type="password")
    
    col1, col2 = st.columns(2)
    
    if col1.button("Ingresar"):
        try:
            session = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state['user'] = session.user
            st.rerun()
        except Exception as e:
            st.error("Email o contraseña incorrectos")

    if col2.button("Registrarme"):
        try:
            # Crea el usuario en Supabase Auth
            response = supabase.auth.sign_up({"email": email, "password": password})
            st.success("¡Cuenta creada! Revisa tu email para confirmar o intenta ingresar.")
        except Exception as e:
            st.error(f"Error al registrar: {e}")

def logout():
    supabase.auth.sign_out()
    st.session_state['user'] = None
    st.rerun()

# --- FUNCIONES DEL ESCÁNER (Tu lógica original) ---
def guardar_en_supabase(data):
    # ... (Mismo código de antes) ...
    # Solo agregamos el user_id para saber QUIÉN escaneó
    try:
        user_id = st.session_state['user'].id
    except:
        user_id = None # Por si acaso

    nombre_super_ia = data['supermercado'].strip().upper()
    
    # Buscar/Crear Super
    res_super = supabase.table('supermercados').select('id').ilike('nombre', nombre_super_ia).execute()
    if res_super.data:
        super_id = res_super.data[0]['id']
    else:
        res_new = supabase.table('supermercados').insert({"nombre": nombre_super_ia}).execute()
        super_id = res_new.data[0]['id']

    # Insertar Ticket
    ticket_data = {
        "user_id": user_id, # <--- GUARDAMOS EL USUARIO
        "supermercado_id": super_id,
        "fecha": data['fecha'],
        "hora": data['hora'],
        "monto_total": data['total_pagado'],
        "imagen_url": "cloud_upload"
    }
    
    try:
        res_ticket = supabase.table('tickets').insert(ticket_data).execute()
        ticket_id = res_ticket.data[0]['id']
        
        items_a_insertar = []
        for item in data['items']:
            items_a_insertar.append({
                "ticket_id": ticket_id,
                "nombre_producto": item['nombre'],
                "cantidad": item['cantidad'],
                "precio_neto_unitario": item['precio_neto_final'],
                "unidad_medida": item['unidad_medida']
            })
        supabase.table('items_compra').insert(items_a_insertar).execute()
        return len(items_a_insertar)
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return "DUPLICADO"
        return False

def procesar_imagenes(lista_imagenes):
    # ... (Mismo código de IA de antes) ...
    contenido = []
    prompt = """
    Analiza estas imágenes de un ticket. Une la información.
    JSON estricto: {"supermercado": "Nombre", "fecha": "YYYY-MM-DD", "hora": "HH:MM", "nro_ticket": "str", "total_pagado": num, "items": [{"nombre": "Prod", "cantidad": num, "unidad_medida": "Un/Kg/Lt", "precio_neto_final": num}]}
    Si falta año asume 2025.
    """
    contenido.append(prompt)
    for img_file in lista_imagenes:
        img = Image.open(img_file)
        contenido.append(img)
    try:
        result = model.generate_content(contenido)
        texto = result.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(texto)
        return data
    except Exception as e:
        st.error(f"Error IA: {e}")
        return None

# --- FLUJO PRINCIPAL ---

if not st.session_state['user']:
    # Si NO está logueado, muestra pantalla de login
    login()
else:
    # Si ESTÁ logueado, muestra la App
    st.sidebar.write(f"Hola, {st.session_state['user'].email}")
    if st.sidebar.button("Cerrar Sesión"):
        logout()

    st.title("🛒 Escáner de Precios")
    
    # --- AQUÍ VA TU INTERFAZ DE CÁMARA (Igual que antes) ---
    img_file_buffer = st.camera_input("📸 Saca una foto")

    if 'fotos_acumuladas' not in st.session_state:
        st.session_state['fotos_acumuladas'] = []

    if img_file_buffer is not None:
        bytes_data = img_file_buffer.getvalue()
        if not st.session_state['fotos_acumuladas'] or st.session_state['fotos_acumuladas'][-1].getvalue() != bytes_data:
            st.session_state['fotos_acumuladas'].append(img_file_buffer)
            st.toast("✅ Foto agregada")

    if st.session_state['fotos_acumuladas']:
        st.write(f"🎞️ Fotos: {len(st.session_state['fotos_acumuladas'])}")
        cols = st.columns(len(st.session_state['fotos_acumuladas']))
        for idx, foto in enumerate(st.session_state['fotos_acumuladas']):
            cols[idx].image(foto, width=100)

        col1, col2 = st.columns(2)
        if col1.button("🗑️ Limpiar"):
            st.session_state['fotos_acumuladas'] = []
            st.rerun()

        if col2.button("🚀 PROCESAR"):
            with st.spinner("Analizando ticket..."):
                data = procesar_imagenes(st.session_state['fotos_acumuladas'])
                if data:
                    res = guardar_en_supabase(data)
                    if res == "DUPLICADO":
                        st.warning("⚠️ Ticket ya cargado.")
                    elif res:
                        st.balloons()
                        st.success(f"✅ ¡Guardado! {res} items.")
                        st.session_state['fotos_acumuladas'] = []
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Error al guardar.")