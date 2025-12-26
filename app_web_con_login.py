import streamlit as st
import time
import json
import os
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types
from supabase import create_client, Client
from gotrue.errors import AuthApiError

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Club de Precios", page_icon="🛒", layout="centered")

# --- CARGA DE SECRETOS ---
try:
    load_dotenv()
    # Prioridad: st.secrets (Nube) -> os.environ (Local)
    URL = st.secrets["SUPABASE_URL"] if "SUPABASE_URL" in st.secrets else os.environ.get("SUPABASE_URL")
    KEY = st.secrets["SUPABASE_KEY"] if "SUPABASE_KEY" in st.secrets else os.environ.get("SUPABASE_KEY")
    GOOGLE_KEY = st.secrets["GOOGLE_API_KEY"] if "GOOGLE_API_KEY" in st.secrets else os.environ.get("GOOGLE_API_KEY")

    if not URL or not KEY or not GOOGLE_KEY:
        st.error("❌ Faltan claves de configuración.")
        st.stop()

    supabase: Client = create_client(URL, KEY)
    client = genai.Client(api_key=GOOGLE_KEY)
    
    # Usamos el modelo moderno que confirmamos que funciona
    MODELO_IA = 'gemini-2.5-flash' 

except Exception as e:
    st.error(f"❌ Error de configuración inicial: {e}")
    st.stop()

# --- LISTA DE RUBROS ---
RUBROS_VALIDOS = """
- Almacén
- Bebidas s/Alcohol
- Bebidas c/Alcohol
- Carnicería
- Pescadería
- Frutas y Verduras
- Lácteos
- Quesos y Fiambres
- Panadería y Galletitas
- Golosinas
- Congelados y Helados
- Comida Elaborada / Rotisería
- Limpieza
- Perfumería e Higiene
- Bebés y Maternidad
- Mascotas
- Electro y Tecnología
- Juguetería
- Ropa y Calzado
- Librería
- Hogar, Muebles y Bazar
- Ferretería y Herramientas
- Automotor
- Otros
"""

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
            st.error(f"Error: Email o contraseña incorrectos.")

    if col2.button("Registrarme"):
        try:
            response = supabase.auth.sign_up({"email": email, "password": password})
            # Si el autoconfirm está activado en Supabase, entra directo
            if response.session:
                st.session_state['user'] = response.session.user
                st.rerun()
            else:
                st.success("Cuenta creada. Intenta ingresar.")
        except Exception as e:
            st.error(f"Error al registrar: {e}")

def logout():
    supabase.auth.sign_out()
    st.session_state['user'] = None
    st.rerun()

# --- LÓGICA DE IA Y BASE DE DATOS ---
def guardar_en_supabase(data):
    try:
        user_id = st.session_state['user'].id
    except:
        user_id = None 

    nombre_super_ia = data['supermercado'].strip().upper()
    
    # 1. Buscar/Crear Super
    res_super = supabase.table('supermercados').select('id').ilike('nombre', nombre_super_ia).execute()
    if res_super.data:
        super_id = res_super.data[0]['id']
    else:
        res_new = supabase.table('supermercados').insert({"nombre": nombre_super_ia}).execute()
        super_id = res_new.data[0]['id']

    # 2. Insertar Ticket (Cabecera)
    ticket_data = {
        "user_id": user_id,
        "supermercado_id": super_id,
        "fecha": data['fecha'],
        "hora": data['hora'],
        "monto_total": data['total_pagado'],
        "imagen_url": "cloud_v2"
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
                "unidad_medida": item['unidad_medida'],
                # NUEVOS CAMPOS CLASIFICADOS
                "rubro": item.get('rubro'),
                "marca": item.get('marca'),
                "producto_generico": item.get('producto_generico'),
                "contenido_neto": item.get('contenido_neto'),
                "unidad_contenido": item.get('unidad_contenido')
            })
            
        supabase.table('items_compra').insert(items_a_insertar).execute()
        return len(items_a_insertar)
        
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return "DUPLICADO"
        st.error(f"Error DB Detalle: {e}")
        return False

def procesar_imagenes(lista_imagenes):
    contenido = []
    
    prompt = f"""
    Analiza estas imágenes de un ticket de compra. Une la información.
    
    Tu misión es extraer y CLASIFICAR cada producto.
    
    Lista de Rubros permitidos: {RUBROS_VALIDOS}
    
    Devuelve un JSON estricto con esta estructura:
    {{
        "supermercado": "Nombre del super",
        "fecha": "YYYY-MM-DD",
        "hora": "HH:MM",
        "nro_ticket": "string",
        "total_pagado": número,
        "items": [
            {{
                "nombre": "Texto original del ticket",
                "cantidad": número,
                "unidad_medida": "Un/Kg/Lt",
                "precio_neto_final": número (precio unitario real pagado),
                
                "marca": "Marca detectada (o null)",
                "producto_generico": "Nombre limpio (ej: Aceite Girasol)",
                "rubro": "Uno de la lista de permitidos",
                "contenido_neto": número (ej: 1.5),
                "unidad_contenido": "Unidad normalizada (lt, kg, cc, gr)"
            }}
        ]
    }}
    Si falta año asume 2025.
    """
    contenido.append(prompt)
    
    # Convertir imágenes para la nueva librería
    for img_file in lista_imagenes:
        img = Image.open(img_file)
        contenido.append(img)

    try:
        # Llamada a la API Nueva (google-genai)
        response = client.models.generate_content(
            model=MODELO_IA,
            contents=contenido,
            config=types.GenerateContentConfig(
                response_mime_type='application/json'
            )
        )
        
        texto_limpio = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(texto_limpio)
        
    except Exception as e:
        st.error(f"Error Inteligencia Artificial: {e}")
        return None

# --- INTERFAZ DE USUARIO ---

if not st.session_state['user']:
    login()
else:
    with st.sidebar:
        st.write(f"👤 {st.session_state['user'].email}")
        if st.button("Cerrar Sesión"):
            logout()

    st.title("🛒 Club de Precios")
    st.caption("v2.0 - Clasificación Automática")
    
    img_file_buffer = st.camera_input("📸 Escanear Ticket")

    if 'fotos_acumuladas' not in st.session_state:
        st.session_state['fotos_acumuladas'] = []

    if img_file_buffer is not None:
        bytes_data = img_file_buffer.getvalue()
        if not st.session_state['fotos_acumuladas'] or st.session_state['fotos_acumuladas'][-1].getvalue() != bytes_data:
            st.session_state['fotos_acumuladas'].append(img_file_buffer)
            st.toast("✅ Foto agregada")

    if st.session_state['fotos_acumuladas']:
        st.divider()
        st.write(f"🎞️ **{len(st.session_state['fotos_acumuladas'])} capturas listas**")
        
        # Galería horizontal
        cols = st.columns(len(st.session_state['fotos_acumuladas']))
        for idx, foto in enumerate(st.session_state['fotos_acumuladas']):
            cols[idx].image(foto, width=80)

        col1, col2 = st.columns(2)
        if col1.button("🗑️ Borrar", use_container_width=True):
            st.session_state['fotos_acumuladas'] = []
            st.rerun()

        if col2.button("🚀 PROCESAR AHORA", type="primary", use_container_width=True):
            with st.spinner("🤖 Leyendo y clasificando productos..."):
                data = procesar_imagenes(st.session_state['fotos_acumuladas'])
                
                if data:
                    res = guardar_en_supabase(data)
                    
                    if res == "DUPLICADO":
                        st.warning("⚠️ Este ticket ya fue cargado anteriormente.")
                    elif res:
                        st.balloons()
                        st.success(f"✅ ¡Éxito! Se guardaron {res} productos.")
                        st.session_state['fotos_acumuladas'] = []
                        time.sleep(3)
                        st.rerun()
                    else:
                        st.error("No se pudieron guardar los datos.")