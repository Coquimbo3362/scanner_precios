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

st.set_page_config(page_title="Club de Precios Global", page_icon="🌎", layout="centered")

# --- CONFIGURACIÓN ---
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

# --- FUNCIONES DE LIMPIEZA ---
def limpiar_numero(valor):
    if not valor: return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    texto = str(valor).replace('$', '').replace('kg', '').replace('lt', '').replace('un', '').strip()
    texto = re.sub(r'[^\d.,-]', '', texto)
    try:
        return float(texto)
    except:
        try:
            if ',' in texto and '.' in texto:
                texto = texto.replace('.', '').replace(',', '.')
            elif ',' in texto:
                texto = texto.replace(',', '.')
            return float(texto)
        except:
            return 0.0

def limpiar_fecha(fecha_str):
    if not fecha_str: return "2025-01-01"
    if len(fecha_str) != 10: return time.strftime("%Y-%m-%d")
    return fecha_str

# --- GESTIÓN USUARIOS ---
if 'user' not in st.session_state: st.session_state['user'] = None

def login():
    st.subheader("🌎 Ingreso Global")
    tab1, tab2 = st.tabs(["Ingresar", "Crear Cuenta"])
    with tab1:
        email = st.text_input("Email", key="l_email")
        password = st.text_input("Contraseña", type="password", key="l_pass")
        if st.button("Entrar"):
            try:
                session = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state['user'] = session.user
                st.rerun()
            except: st.error("Datos incorrectos")
    with tab2:
        new_email = st.text_input("Email", key="r_email")
        new_pass = st.text_input("Contraseña", type="password", key="r_pass")
        pais = st.selectbox("País", PAISES_SOPORTADOS)
        ciudad = st.text_input("Ciudad")
        if st.button("Registrarme"):
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

# --- GUARDADO ---
def guardar_en_supabase(data):
    try: user_id = st.session_state['user'].id
    except: user_id = None 

    nombre_super = data['supermercado'].strip().upper()
    
    # Busca/Crea Supermercado (Ahora incluirá la sucursal, ej: "COTO SUC 188")
    res_super = supabase.table('supermercados').select('id').ilike('nombre', nombre_super).execute()
    if res_super.data:
        super_id = res_super.data[0]['id']
    else:
        res_new = supabase.table('supermercados').insert({"nombre": nombre_super}).execute()
        super_id = res_new.data[0]['id']

    fecha_limpia = limpiar_fecha(data['fecha'])
    ticket_data = {
        "user_id": user_id,
        "supermercado_id": super_id,
        "fecha": fecha_limpia,
        "hora": data['hora'],
        "monto_total": limpiar_numero(data['total_pagado']),
        "imagen_url": "cloud_v3.2_sucursal",
        "sucursal_direccion": data.get('sucursal_direccion'),
        "sucursal_localidad": data.get('sucursal_localidad'),
        "sucursal_provincia": data.get('sucursal_provincia'),
        "sucursal_pais": data.get('sucursal_pais'),
        "moneda": data.get('moneda')
    }
    
    try:
        res_ticket = supabase.table('tickets').insert(ticket_data).execute()
        ticket_id = res_ticket.data[0]['id']
        items = []
        for item in data['items']:
            items.append({
                "ticket_id": ticket_id,
                "nombre_producto": item['nombre'],
                "cantidad": limpiar_numero(item['cantidad']),
                "precio_neto_unitario": limpiar_numero(item['precio_neto_final']),
                "unidad_medida": item['unidad_medida'],
                "rubro": item.get('rubro'),
                "marca": item.get('marca'),
                "producto_generico": item.get('producto_generico'),
                "contenido_neto": limpiar_numero(item.get('contenido_neto')),
                "unidad_contenido": item.get('unidad_contenido')
            })
        supabase.table('items_compra').insert(items).execute()
        return len(items)
    except Exception as e:
        st.error(f"❌ Error DB: {e}")
        if "unique" in str(e).lower(): return "DUPLICADO"
        return False

def procesar_imagenes(lista_imagenes):
    contenido = []
    
    # --- PROMPT ACTUALIZADO PARA SUCURSALES ---
    prompt = f"""
    Analiza este ticket de compra.
    
    1. SUPERMERCADO (IMPORTANTE):
       - Extrae el NOMBRE COMERCIAL + SUCURSAL/LOCALIDAD.
       - Ejemplos: "JUMBO UNICENTER", "COTO SUC 64", "CARREFOUR VTE LOPEZ".
       - Si no dice sucursal, usa la dirección para distinguirlo (Ej: "DIA AV MAIPU").
    
    2. FECHA Y MONEDA:
       - Fecha: YYYY-MM-DD.
       - Moneda: ISO Code (ARS, USD, BRL).
    
    3. PRODUCTOS:
       - Extrae marca, genérico, rubro (de la lista permitida), contenido y unidad.
       - Contenido Neto: SOLO números (ej: 1.5). Unidad en campo aparte.
    
    Rubros: {RUBROS_VALIDOS}
    
    JSON Estricto:
    {{
        "supermercado": "Nombre + Sucursal",
        "sucursal_direccion": "Calle...",
        "sucursal_localidad": "Ciudad",
        "sucursal_provincia": "Provincia",
        "sucursal_pais": "País",
        "moneda": "ISO",
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
                "rubro": "Rubro",
                "contenido_neto": num,
                "unidad_contenido": "Unidad"
            }}
        ]
    }}
    """
    contenido.append(prompt)
    for img in lista_imagenes: contenido.append(Image.open(img))

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
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
        if st.button("Salir"): logout()

    st.title("🛒 Club de Precios")
    st.caption("v3.2 - Sucursales Detalladas")
    
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
            with st.spinner("🏢 Identificando sucursal y precios..."):
                data = procesar_imagenes(st.session_state['fotos'])
                if data:
                    res = guardar_en_supabase(data)
                    if res == "DUPLICADO": st.warning("⚠️ Ya existe")
                    elif res:
                        st.balloons()
                        # Mostramos qué sucursal detectó
                        st.success(f"✅ Cargado en **{data['supermercado']}** ({res} items)")
                        st.session_state['fotos'] = []
                        time.sleep(3)
                        st.rerun()