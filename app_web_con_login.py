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

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Club Precios", page_icon="🛒", layout="wide", initial_sidebar_state="collapsed")

# --- CSS (Mantenemos el diseño grande) ---
st.markdown("""
    <style>
        .block-container {
            padding-top: 3rem !important;
            padding-bottom: 5rem !important;
            padding-left: 0.1rem !important;
            padding-right: 0.1rem !important;
        }
        h1 { font-size: 1.4rem !important; margin-bottom: 0.5rem; text-align: center; }
        div[data-testid="stCameraInput"], div[data-testid="stFileUploader"] {
            width: 100% !important;
        }
        div[data-testid="stCameraInput"] video {
            border-radius: 15px;
            min-height: 400px !important;
            object-fit: cover !important;
        }
        .stButton button { 
            width: 100%; border-radius: 30px; height: 3.5rem; 
            font-size: 1.2rem; font-weight: bold;
            box-shadow: 0px 4px 6px rgba(0,0,0,0.2);
        }
        small { display: none; }
    </style>
""", unsafe_allow_html=True)

# --- BACKEND ---
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

# --- FUNCIONES LIMPIEZA ---
def limpiar_numero(valor):
    if not valor: return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    texto = str(valor).replace('$', '').replace('kg', '').replace('lt', '').replace('un', '').strip()
    texto = re.sub(r'[^\d.,-]', '', texto)
    try: return float(texto)
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
    st.markdown("### 🌎 Ingreso")
    tab1, tab2 = st.tabs(["Ingresar", "Crear Cuenta"])
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Contraseña", type="password")
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
                        st.success("Cuenta creada.")
                except Exception as e: st.error(f"Error: {e}")

def logout():
    supabase.auth.sign_out()
    st.session_state['user'] = None
    st.rerun()

# --- PROCESAMIENTO ---
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
        "imagen_url": "v4.3_upload", "sucursal_direccion": data.get('sucursal_direccion'),
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
    
    # PROMPT MAS ESTRICTO CONTRA ALUCINACIONES
    prompt = f"""
    Analiza este ticket de compra REAL. NO INVENTES PRODUCTOS que no se lean claramente.
    
    1. SUPERMERCADO: Busca "JUMBO UNICENTER", "COTO SUC...", etc.
    2. ITEMS: 
       - Si hay descuentos (ej: "ANSES", "Frescos Pas") RESTALOS del precio. Quiero el precio FINAL que pagó el cliente.
       - Si la imagen está borrosa, lee solo lo que estés 100% seguro.
    
    Rubros: {RUBROS_VALIDOS}
    
    JSON Estricto:
    {{
        "supermercado": "Nombre Sucursal", "sucursal_direccion": "Str", "sucursal_localidad": "Str",
        "sucursal_provincia": "Str", "sucursal_pais": "Str", "moneda": "ISO",
        "fecha": "YYYY-MM-DD", "hora": "HH:MM", "nro_ticket": "str", "total_pagado": num,
        "items": [
            {{ "nombre": "Nombre Real", "cantidad": num, "unidad_medida": "Un/Kg", "precio_neto_final": num,
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

    st.markdown("<h3 style='text-align: center;'>🛒 Club v4.3</h3>", unsafe_allow_html=True)
    
    # PESTAÑAS: CAMARA vs SUBIR
    tab_cam, tab_up = st.tabs(["📸 Usar Cámara", "📂 Subir Foto (Mejor Calidad)"])
    
    if 'fotos' not in st.session_state: st.session_state['fotos'] = []

    # Opción 1: Cámara Web
    with tab_cam:
        st.info("Para tickets rápidos.")
        img_cam = st.camera_input("Foto", label_visibility="collapsed")
        if img_cam:
            if not st.session_state['fotos'] or st.session_state['fotos'][-1].getvalue() != img_cam.getvalue():
                st.session_state['fotos'].append(img_cam)
                st.toast("✅ Capturada")

    # Opción 2: Subir archivo (Permite Flash y Zoom)
    with tab_up:
        st.info("💡 **Recomendado:** Saca la foto con la cámara de tu celular (con Flash) y súbela aquí.")
        uploaded_files = st.file_uploader("Selecciona fotos", accept_multiple_files=True, type=['jpg','png','jpeg'])
        if uploaded_files:
            # Reemplazamos la lista con lo que suba
            st.session_state['fotos'] = uploaded_files

    # --- ZONA DE PROCESAMIENTO ---
    if st.session_state['fotos']:
        st.divider()
        st.write(f"🎞️ **{len(st.session_state['fotos'])} imágenes seleccionadas**")
        
        cols = st.columns(len(st.session_state['fotos']))
        for i, f in enumerate(st.session_state['fotos']): cols[i].image(f, width=80)

        c1, c2 = st.columns(2)
        if c1.button("🗑️ Limpiar", use_container_width=True): 
            st.session_state['fotos'] = []
            st.rerun()
            
        if c2.button("🚀 PROCESAR TICKET", type="primary", use_container_width=True):
            with st.spinner("🧠 Leyendo ticket con máxima precisión..."):
                data = procesar_imagenes(st.session_state['fotos'])
                if data:
                    res = guardar_en_supabase(data)
                    if res == "DUPLICADO": st.warning("⚠️ Ya existe.")
                    elif res:
                        st.balloons()
                        total_fmt = f"{data.get('moneda','$')} {data.get('total_pagado')}"
                        st.success(f"✅ **¡Carga Exitosa!**")
                        c1, c2 = st.columns(2)
                        c1.metric("Items", res)
                        c2.metric("Total", total_fmt)
                        st.caption(f"📍 {data.get('supermercado')}")
                        st.session_state['fotos'] = []
                        time.sleep(6)
                        st.rerun()