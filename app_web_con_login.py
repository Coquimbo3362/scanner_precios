import streamlit as st
import time
import json
import os
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types
from supabase import create_client, Client

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Club de Precios Global", page_icon="🌎", layout="centered")

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

# --- DATOS MAESTROS INTERNACIONALES ---
PAISES_SOPORTADOS = ["Argentina", "Uruguay", "Chile", "Brasil", "Paraguay", "Bolivia", "Perú", "Colombia", "México", "España", "USA", "Otro"]

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

# --- GESTIÓN USUARIOS ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

def login():
    st.subheader("🌎 Ingreso Global")
    tab1, tab2 = st.tabs(["Ingresar", "Crear Cuenta"])
    
    with tab1:
        email = st.text_input("Email", key="log_email")
        password = st.text_input("Contraseña", type="password", key="log_pass")
        if st.button("Entrar"):
            try:
                session = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state['user'] = session.user
                st.rerun()
            except:
                st.error("Datos incorrectos")

    with tab2:
        st.markdown("##### Datos de tu residencia")
        new_email = st.text_input("Email", key="reg_email")
        new_pass = st.text_input("Contraseña", type="password", key="reg_pass")
        
        c1, c2 = st.columns(2)
        pais = c1.selectbox("País", PAISES_SOPORTADOS)
        provincia = c2.text_input("Provincia / Estado")
        
        c3, c4 = st.columns(2)
        ciudad = c3.text_input("Ciudad")
        cp = c4.text_input("Código Postal")
        
        if st.button("Registrarme"):
            if not new_email or not new_pass or not ciudad:
                st.warning("Completa los datos geográficos.")
            else:
                try:
                    res = supabase.auth.sign_up({"email": new_email, "password": new_pass})
                    if res.user:
                        supabase.table('perfiles').insert({
                            "id": res.user.id,
                            "pais": pais,
                            "provincia": provincia,
                            "ciudad": ciudad,
                            "codigo_postal": cp
                        }).execute()
                        st.success("¡Bienvenido! Ya puedes ingresar.")
                except Exception as e:
                    st.error(f"Error: {e}")

def logout():
    supabase.auth.sign_out()
    st.session_state['user'] = None
    st.rerun()

# --- GUARDADO ---
def guardar_en_supabase(data):
    try:
        user_id = st.session_state['user'].id
    except:
        user_id = None 

    nombre_super = data['supermercado'].strip().upper()
    
    # Supermercados
    res_super = supabase.table('supermercados').select('id').ilike('nombre', nombre_super).execute()
    if res_super.data:
        super_id = res_super.data[0]['id']
    else:
        res_new = supabase.table('supermercados').insert({"nombre": nombre_super}).execute()
        super_id = res_new.data[0]['id']

    # Ticket INTERNACIONAL
    ticket_data = {
        "user_id": user_id,
        "supermercado_id": super_id,
        "fecha": data['fecha'],
        "hora": data['hora'],
        "monto_total": data['total_pagado'],
        "imagen_url": "cloud_v3.1_intl",
        
        # DATOS GEO + MONEDA
        "sucursal_direccion": data.get('sucursal_direccion'),
        "sucursal_localidad": data.get('sucursal_localidad'),
        "sucursal_provincia": data.get('sucursal_provincia'),
        "sucursal_pais": data.get('sucursal_pais'),
        "moneda": data.get('moneda') # ARS, USD, etc.
    }
    
    try:
        res_ticket = supabase.table('tickets').insert(ticket_data).execute()
        ticket_id = res_ticket.data[0]['id']
        
        items = []
        for item in data['items']:
            items.append({
                "ticket_id": ticket_id,
                "nombre_producto": item['nombre'],
                "cantidad": item['cantidad'],
                "precio_neto_unitario": item['precio_neto_final'],
                "unidad_medida": item['unidad_medida'],
                "rubro": item.get('rubro'),
                "marca": item.get('marca'),
                "producto_generico": item.get('producto_generico'),
                "contenido_neto": item.get('contenido_neto'),
                "unidad_contenido": item.get('unidad_contenido')
            })
            
        supabase.table('items_compra').insert(items).execute()
        return len(items)
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return "DUPLICADO"
        return False

def procesar_imagenes(lista_imagenes):
    contenido = []
    
    # PROMPT INTERNACIONAL
    prompt = f"""
    Analiza este ticket de compra (puede ser de cualquier país).
    
    1. UBICACIÓN Y MONEDA:
       - Detecta la Dirección, Ciudad, Provincia/Estado y PAÍS.
       - Detecta la MONEDA (ISO Code: ARS, BRL, USD, EUR, CLP, UYU). Infiérela por el país y el símbolo (R$ = BRL, $ en Arg = ARS).
    
    2. PRODUCTOS:
       - Clasifica cada item usando la lista de rubros.
       - Detecta marcas y nombres genéricos.
    
    Rubros: {RUBROS_VALIDOS}
    
    JSON Estricto:
    {{
        "supermercado": "Nombre",
        "sucursal_direccion": "Calle...",
        "sucursal_localidad": "Ciudad",
        "sucursal_provincia": "Provincia",
        "sucursal_pais": "País (ej: Argentina, Brasil)",
        "moneda": "Código ISO (ej: ARS)",
        "fecha": "YYYY-MM-DD",
        "hora": "HH:MM",
        "nro_ticket": "str",
        "total_pagado": num,
        "items": [
            {{
                "nombre": "Texto original",
                "cantidad": num,
                "unidad_medida": "Un/Kg",
                "precio_neto_final": num,
                "marca": "Marca",
                "producto_generico": "Nombre limpio",
                "rubro": "Rubro de lista",
                "contenido_neto": num,
                "unidad_contenido": "Unidad"
            }}
        ]
    }}
    """
    contenido.append(prompt)
    for img in lista_imagenes:
        contenido.append(Image.open(img))

    try:
        response = client.models.generate_content(
            model=MODELO_IA,
            contents=contenido,
            config=types.GenerateContentConfig(response_mime_type='application/json')
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Error IA: {e}")
        return None

# --- INTERFAZ ---
if not st.session_state['user']:
    login()
else:
    with st.sidebar:
        st.write(f"👤 {st.session_state['user'].email}")
        try:
            p = supabase.table('perfiles').select('*').eq('id', st.session_state['user'].id).execute().data[0]
            st.success(f"📍 {p['ciudad']}, {p['pais']}")
        except:
            pass
        if st.button("Salir"): logout()

    st.title("🛒 Club de Precios")
    st.caption("v3.1 - Multimoneda y Geolocalización")
    
    img = st.camera_input("📸 Ticket")
    if 'fotos' not in st.session_state: st.session_state['fotos'] = []
    
    if img:
        if not st.session_state['fotos'] or st.session_state['fotos'][-1].getvalue() != img.getvalue():
            st.session_state['fotos'].append(img)
            st.toast("✅ Foto ok")

    if st.session_state['fotos']:
        st.write(f"🎞️ {len(st.session_state['fotos'])} fotos")
        cols = st.columns(len(st.session_state['fotos']))
        for i, f in enumerate(st.session_state['fotos']): cols[i].image(f, width=80)

        c1, c2 = st.columns(2)
        if c1.button("🗑️"): 
            st.session_state['fotos'] = []
            st.rerun()
            
        if c2.button("🚀 PROCESAR"):
            with st.spinner("🌎 Analizando país, moneda y precios..."):
                data = procesar_imagenes(st.session_state['fotos'])
                if data:
                    res = guardar_en_supabase(data)
                    if res == "DUPLICADO": st.warning("⚠️ Ya existe")
                    elif res:
                        st.balloons()
                        loc = f"{data.get('sucursal_pais')} ({data.get('moneda')})"
                        st.success(f"✅ {res} items guardados en **{loc}**")
                        st.session_state['fotos'] = []
                        time.sleep(3)
                        st.rerun()
                    else: st.error("Error al guardar")