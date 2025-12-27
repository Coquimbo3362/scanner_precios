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

# --- CONFIGURACIÓN DE PÁGINA (Compacta) ---
st.set_page_config(page_title="Club Precios", page_icon="🛒", layout="centered", initial_sidebar_state="collapsed")

# CSS HACK: Achicar encabezados para ganar espacio en el celular
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 0rem; }
        h1 { font-size: 1.5rem !important; margin-bottom: 0rem; }
        .stButton button { width: 100%; border-radius: 10px; }
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

# --- LOGIN (ARREGLADO CON FORMULARIO) ---
if 'user' not in st.session_state: st.session_state['user'] = None

def login():
    st.markdown("### 🌎 Ingreso Global")
    
    tab1, tab2 = st.tabs(["Ingresar", "Crear Cuenta"])
    
    with tab1:
        # Usamos st.form para evitar el error del doble click
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Contraseña", type="password")
            submit_login = st.form_submit_button("Entrar")
            
            if submit_login:
                try:
                    session = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state['user'] = session.user
                    st.rerun()
                except:
                    st.error("Datos incorrectos")

    with tab2:
        with st.form("register_form"):
            new_email = st.text_input("Email")
            new_pass = st.text_input("Contraseña", type="password")
            pais = st.selectbox("País", PAISES_SOPORTADOS)
            ciudad = st.text_input("Ciudad")
            submit_reg = st.form_submit_button("Registrarme")
            
            if submit_reg:
                try:
                    res = supabase.auth.sign_up({"email": new_email, "password": new_pass})
                    if res.user:
                        supabase.table('perfiles').insert({"id": res.user.id, "pais": pais, "ciudad": ciudad}).execute()
                        st.success("Cuenta creada. Ingresa ahora.")
                except Exception as e:
                    st.error(f"Error: {e}")

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
        "imagen_url": "v3.3_final", "sucursal_direccion": data.get('sucursal_direccion'),
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
    1. SUPERMERCADO: Extrae NOMBRE + SUCURSAL (ej: JUMBO UNICENTER).
    2. FECHA Y MONEDA: Fecha (YYYY-MM-DD) y Moneda ISO (ARS, BRL, USD).
    3. PRODUCTOS: Extrae marca, genérico, rubro (de la lista), contenido y unidad.
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
        st.write(f"👤 {st.session_state['user'].email}")
        if st.button("Salir"): logout()

    # Título Compacto
    st.markdown("### 🛒 Club de Precios")
    
    # Instrucciones Claras
    st.info("💡 **Tip:** Si el ticket es largo, saca varias fotos ('Nueva Foto'). Asegúrate de que se superpongan un poco los renglones.")

    # Cámara
    img = st.camera_input("📸 Tomar Foto")
    
    if 'fotos' not in st.session_state: st.session_state['fotos'] = []
    
    if img:
        # Lógica para evitar duplicados al refrescar
        if not st.session_state['fotos'] or st.session_state['fotos'][-1].getvalue() != img.getvalue():
            st.session_state['fotos'].append(img)
            st.toast("Foto guardada")

    if st.session_state['fotos']:
        st.write(f"🎞️ **{len(st.session_state['fotos'])} fotos listas**")
        
        # Galería pequeña
        cols = st.columns(len(st.session_state['fotos']))
        for i, f in enumerate(st.session_state['fotos']): cols[i].image(f, width=80)

        c1, c2 = st.columns(2)
        if c1.button("🗑️ Borrar", use_container_width=True): 
            st.session_state['fotos'] = []
            st.rerun()
            
        if c2.button("🚀 PROCESAR", type="primary", use_container_width=True):
            with st.spinner("⏳ Analizando ticket..."):
                data = procesar_imagenes(st.session_state['fotos'])
                if data:
                    res = guardar_en_supabase(data)
                    if res == "DUPLICADO": st.warning("⚠️ Este ticket ya existe.")
                    elif res:
                        st.balloons()
                        # Feedback completo solicitado en punto 8
                        total_fmt = f"{data.get('moneda', '$')} {data.get('total_pagado')}"
                        st.success(f"✅ **¡Listo!**\n\n🛒 **Items:** {res}\n💰 **Total:** {total_fmt}\n📍 **Lugar:** {data.get('supermercado')}")
                        st.session_state['fotos'] = []
                        time.sleep(5)
                        st.rerun()