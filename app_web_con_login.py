import streamlit as st
import time
import json
import re
import os
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types
from supabase import create_client, Client

# 1. CONFIGURACIÓN VISUAL (LAYOUT WIDE + SIDEBAR COLAPSADA)
st.set_page_config(page_title="Club Precios", page_icon="🛒", layout="wide", initial_sidebar_state="collapsed")

# 2. ESTILOS CSS AGRESIVOS PARA MÓVIL
# Padding-top: 4rem baja todo el contenido para que no lo tape el menú superior.
# Padding-left/right: 0rem elimina los márgenes laterales para que la cámara ocupe todo.
st.markdown("""
    <style>
        .block-container {
            padding-top: 4rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            max-width: 100% !important;
        }
        h1 { 
            font-size: 1.6rem !important; 
            margin-bottom: 0.2rem !important;
            margin-top: 0rem !important;
        }
        /* Botones grandes y fáciles de tocar */
        .stButton button { 
            width: 100%; 
            border-radius: 12px; 
            height: 3.5rem; 
            font-size: 1.2rem; 
            font-weight: bold;
        }
        /* Ocultar elementos molestos de Streamlit */
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- CONFIGURACIÓN BACKEND ---
try:
    load_dotenv()
    URL = st.secrets["SUPABASE_URL"] if "SUPABASE_URL" in st.secrets else os.environ.get("SUPABASE_URL")
    KEY = st.secrets["SUPABASE_KEY"] if "SUPABASE_KEY" in st.secrets else os.environ.get("SUPABASE_KEY")
    GOOGLE_KEY = st.secrets["GOOGLE_API_KEY"] if "GOOGLE_API_KEY" in st.secrets else os.environ.get("GOOGLE_API_KEY")

    if not URL or not KEY or not GOOGLE_KEY:
        st.error("❌ Faltan claves.")
        st.stop()

    supabase: Client = create_client(URL, KEY)
    client = genai.Client(api_key=GOOGLE_KEY)
    MODELO_IA = 'gemini-2.5-flash' 

except Exception as e:
    st.error(f"Error config: {e}")
    st.stop()

# --- DATOS MAESTROS ---
PAISES_SOPORTADOS = ["Argentina", "Brasil", "Uruguay", "Chile", "Paraguay", "Bolivia", "Perú", "Colombia", "México", "España", "USA"]

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

# --- FUNCIONES ---
def limpiar_numero(valor):
    if not valor: return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    texto = str(valor).replace('$', '').replace('kg', '').replace('lt', '').replace('un', '').strip()
    texto = re.sub(r'[^\d.,-]', '', texto)
    try:
        return float(texto)
    except:
        try:
            if ',' in texto and '.' in texto: texto = texto.replace('.', '').replace(',', '.')
            elif ',' in texto: texto = texto.replace(',', '.')
            return float(texto)
        except: return 0.0

def limpiar_fecha(fecha_str):
    if not fecha_str: return "2025-01-01"
    if len(fecha_str) != 10: return time.strftime("%Y-%m-%d")
    return fecha_str

# --- LOGIN ---
if 'user' not in st.session_state: st.session_state['user'] = None

def login():
    st.markdown("### 🌎 Ingreso Global")
    tab1, tab2 = st.tabs(["Ingresar", "Crear Cuenta"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Contraseña", type="password")
            # Botón de submit que evita el doble click
            if st.form_submit_button("Entrar", use_container_width=True):
                try:
                    session = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state['user'] = session.user
                    st.rerun()
                except: st.error("Datos incorrectos")

    with tab2:
        with st.form("register_form"):
            new_email = st.text_input("Email")
            new_pass = st.text_input("Contraseña", type="password")
            c1, c2 = st.columns(2)
            pais = c1.selectbox("País", PAISES_SOPORTADOS)
            ciudad = c2.text_input("Ciudad")
            if st.form_submit_button("Registrarme", use_container_width=True):
                try:
                    res = supabase.auth.sign_up({"email": new_email, "password": new_pass})
                    if res.user:
                        supabase.table('perfiles').insert({"id": res.user.id, "pais": pais, "ciudad": ciudad}).execute()
                        st.success("Cuenta creada. Ingresa ahora.")
                except Exception as e: st.error(f"Error: {e}")

def logout():
    supabase.auth.sign_out()
    st.session_state['user'] = None
    st.rerun()

# --- BACKEND ---
def guardar_en_supabase(data):
    try: user_id = st.session_state['user'].id
    except: user_id = None 
    nombre_super = data['supermercado'].strip().upper()
    
    res_super = supabase.table('supermercados').select('id').ilike('nombre', nombre_super).execute()
    if res_super.data: super_id = res_super.data[0]['id']
    else:
        res_new = supabase.table('supermercados').insert({"nombre": nombre_super}).execute()
        super_id = res_new.data[0]['id']

    ticket_data = {
        "user_id": user_id, "supermercado_id": super_id, "fecha": limpiar_fecha(data['fecha']),
        "hora": data['hora'], "monto_total": limpiar_numero(data['total_pagado']),
        "imagen_url": "v4.0_mobile_ui", "sucursal_direccion": data.get('sucursal_direccion'),
        "sucursal_localidad": data.get('sucursal_localidad'), "sucursal_provincia": data.get('sucursal_provincia'),
        "sucursal_pais": data.get('sucursal_pais'), "moneda": data.get('moneda')
    }
    try:
        res_ticket = supabase.table('tickets').insert(ticket_data).execute()
        ticket_id = res_ticket.data[0]['id']
        items = []
        for item in data['items']:
            items.append({
                "ticket_id": ticket_id, "nombre_producto": item['nombre'],
                "cantidad": limpiar_numero(item['cantidad']), "precio_neto_unitario": limpiar_numero(item['precio_neto_final']),
                "unidad_medida": item['unidad_medida'], "rubro": item.get('rubro'),
                "marca": item.get('marca'), "producto_generico": item.get('producto_generico'),
                "contenido_neto": limpiar_numero(item.get('contenido_neto')), "unidad_contenido": item.get('unidad_contenido')
            })
        supabase.table('items_compra').insert(items).execute()
        return len(items)
    except Exception as e:
        if "unique" in str(e).lower(): return "DUPLICADO"
        st.error(f"Error DB: {e}")
        return False

def procesar_imagenes(lista_imagenes):
    contenido = []
    prompt = f"""
    Analiza este ticket.
    1. SUPERMERCADO: Extrae NOMBRE + SUCURSAL.
    2. FECHA Y MONEDA: Fecha (YYYY-MM-DD) y Moneda ISO (ARS, BRL, USD).
    3. PRODUCTOS: Marca, genérico, rubro (de la lista), contenido y unidad.
    Rubros: {RUBROS_VALIDOS}
    JSON Estricto:
    {{
        "supermercado": "Str", "sucursal_direccion": "Str", "sucursal_localidad": "Str",
        "sucursal_provincia": "Str", "sucursal_pais": "Str", "moneda": "Str",
        "fecha": "YYYY-MM-DD", "hora": "HH:MM", "nro_ticket": "str", "total_pagado": num,
        "items": [
            {{ "nombre": "Str", "cantidad": num, "unidad_medida": "Str", "precio_neto_final": num,
               "marca": "Str", "producto_generico": "Str", "rubro": "Str", "contenido_neto": num, "unidad_contenido": "Str" }}
        ]
    }}
    """
    contenido.append(prompt)
    for img in lista_imagenes: contenido.append(Image.open(img))
    try:
        response = client.models.generate_content(
            model=MODELO_IA, contents=contenido, config=types.GenerateContentConfig(response_mime_type='application/json')
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Error IA: {e}")
        return None

# --- INTERFAZ PRINCIPAL ---
if not st.session_state['user']:
    login()
else:
    with st.sidebar:
        st.header("👤 Cuenta")
        st.write(f"{st.session_state['user'].email}")
        if st.button("Salir"): logout()

    # TÍTULO (VERSIONADO para saber si actualizó)
    st.markdown("### 🛒 Club v4.0")
    
    # MENSAJE DE AYUDA CLARO
    st.info("ℹ️ **IMPORTANTE:** Si el ticket es largo, toma varias fotos secuenciales ('Nueva Foto') superponiendo renglones. La IA unirá todo.")

    # CÁMARA (Sin etiqueta para ahorrar espacio)
    img = st.camera_input("Toma la foto del ticket", label_visibility="collapsed")
    
    if 'fotos' not in st.session_state: st.session_state['fotos'] = []
    
    if img:
        if not st.session_state['fotos'] or st.session_state['fotos'][-1].getvalue() != img.getvalue():
            st.session_state['fotos'].append(img)
            st.toast("✅ Foto agregada")

    if st.session_state['fotos']:
        st.divider()
        st.write(f"🎞️ **{len(st.session_state['fotos'])} fotos listas**")
        
        # Galería
        cols = st.columns(len(st.session_state['fotos']))
        for i, f in enumerate(st.session_state['fotos']): cols[i].image(f, width=80)

        c1, c2 = st.columns(2)
        if c1.button("🗑️ Borrar", use_container_width=True): 
            st.session_state['fotos'] = []
            st.rerun()
            
        if c2.button("🚀 PROCESAR", type="primary", use_container_width=True):
            with st.spinner("⏳ Analizando..."):
                data = procesar_imagenes(st.session_state['fotos'])
                if data:
                    res = guardar_en_supabase(data)
                    if res == "DUPLICADO": st.warning("⚠️ Ya cargaste este ticket.")
                    elif res:
                        st.balloons()
                        # --- RESUMEN FINAL SOLICITADO ---
                        total_fmt = f"{data.get('moneda','$')} {data.get('total_pagado')}"
                        st.success(f"✅ **¡Carga Exitosa!**")
                        
                        col_a, col_b = st.columns(2)
                        col_a.metric("Items", res)
                        col_b.metric("Total", total_fmt)
                        
                        st.caption(f"📍 {data.get('supermercado')}")
                        
                        st.session_state['fotos'] = []
                        time.sleep(6)
                        st.rerun()