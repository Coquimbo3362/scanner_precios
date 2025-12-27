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

# --- 1. CONFIGURACIÓN VISUAL (AJUSTES NUEVOS) ---
# Cambiamos layout="centered" por "wide" para que la cámara use todo el ancho del celular
st.set_page_config(page_title="Club Precios", page_icon="🛒", layout="wide", initial_sidebar_state="collapsed")

# CSS HACK MEJORADO:
# - padding-top: 3.5rem -> Baja el contenido para que la barra de menú no tape el título.
# - padding-left/right: 0.5rem -> Aprovecha los bordes del celular para la cámara.
st.markdown("""
    <style>
        .block-container {
            padding-top: 3.5rem !important;
            padding-bottom: 1rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        h1 { font-size: 1.8rem !important; margin-bottom: 0.5rem; }
        .stButton button { width: 100%; border-radius: 12px; height: 3rem; font-size: 1.1rem; }
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

# --- LOGIN (FORMULARIO) ---
if 'user' not in st.session_state: st.session_state['user'] = None

def login():
    st.markdown("### 🌎 Ingreso Global")
    tab1, tab2 = st.tabs(["Ingresar", "Crear Cuenta"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Contraseña", type="password")
            submit_login = st.form_submit_button("Entrar", use_container_width=True)
            
            if submit_login:
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
            submit_reg = st.form_submit_button("Registrarme", use_container_width=True)
            
            if submit_reg:
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
        "imagen_url": "v3.4_wide_ui", "sucursal_direccion": data.get('sucursal_direccion'),
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
    Analiza este ticket de compra.
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

    # Título visible y espaciado correctamente
    st.markdown("### 🛒 Club de Precios")
    
    # Mensaje de ayuda (Texto corregido)
    st.info("💡 **Tip:** Si el ticket es largo, **toma** varias fotos ('Nueva Foto'). Asegúrate de que se superpongan un poco los renglones.")

    # CÁMARA
    # El label_visibility='collapsed' esconde el título "Tomar Foto" para ganar espacio
    img = st.camera_input("Tomar Foto", label_visibility="collapsed")
    
    if 'fotos' not in st.session_state: st.session_state['fotos'] = []
    
    if img:
        if not st.session_state['fotos'] or st.session_state['fotos'][-1].getvalue() != img.getvalue():
            st.session_state['fotos'].append(img)
            st.toast("✅ Foto guardada")

    # Muestra lista de fotos si hay alguna
    if st.session_state['fotos']:
        st.divider()
        st.write(f"🎞️ **{len(st.session_state['fotos'])} fotos listas**")
        
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
                        # --- FEEDBACK DE RESULTADO ---
                        st.success(f"✅ **¡Carga Exitosa!**")
                        
                        col_a, col_b = st.columns(2)
                        col_a.metric("Items", res)
                        col_b.metric("Total", f"{data.get('moneda','$')} {data.get('total_pagado')}")
                        
                        st.caption(f"📍 {data.get('supermercado')}")
                        
                        st.session_state['fotos'] = []
                        time.sleep(5)
                        st.rerun()