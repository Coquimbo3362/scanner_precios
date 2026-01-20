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

# --- CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Club de Precios", page_icon="🛒", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
        .block-container { padding-top: 3rem !important; padding-bottom: 2rem !important; }
        h1 { font-size: 1.8rem !important; text-align: center; margin-bottom: 1rem; }
        div[data-testid="stFileUploader"] {
            width: 100% !important; padding: 15px; border: 2px dashed #4CAF50; border-radius: 15px; text-align: center;
        }
        .stButton button { 
            width: 100%; border-radius: 30px; height: 3.5rem; font-size: 1.2rem; font-weight: bold;
            background-color: #FF4B4B; color: white; border: none;
        }
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

PAISES_SOPORTADOS = ["Argentina", "Brasil", "Uruguay", "Chile", "Paraguay", "Bolivia", "Perú", "Colombia", "México", "España", "USA", "Otro"]
CODIGOS_PAIS = {"Argentina 🇦🇷": "+549", "Brasil 🇧🇷": "+55", "Uruguay 🇺🇾": "+598", "Chile 🇨🇱": "+56", "México 🇲🇽": "+52", "Colombia 🇨🇴": "+57", "España 🇪🇸": "+34", "USA 🇺🇸": "+1", "Otro": "+"}

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
- Farmacia
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
    st.markdown("### 🌎 Ingreso Global")
    tab1, tab2 = st.tabs(["Ingresar", "Crear Cuenta"])
    with tab1:
        email = st.text_input("Email", key="l_email")
        password = st.text_input("Contraseña", type="password", key="l_pass")
        if st.button("Entrar", key="btn_ent"):
            try:
                session = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state['user'] = session.user
                st.rerun()
            except: st.error("Email o contraseña incorrectos")
    with tab2:
        new_email = st.text_input("Email Reg")
        new_pass = st.text_input("Pass Reg", type="password")
        c1, c2 = st.columns(2)
        pais = c1.selectbox("País", PAISES_SOPORTADOS)
        ciudad = c2.text_input("Ciudad")
        if st.button("Registrarme"):
            try:
                res = supabase.auth.sign_up({"email": new_email, "password": new_pass})
                if res.user:
                    try: supabase.table('perfiles').insert({"id": res.user.id, "pais": pais, "ciudad": ciudad}).execute()
                    except: pass
                    st.success("Cuenta creada.")
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
        "imagen_url": "v5.1_codigos", "sucursal_direccion": data.get('sucursal_direccion'),
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
                "contenido_neto": limpiar_numero(item.get('contenido_neto')), 
                "unidad_contenido": item.get('unidad_contenido'),
                "codigo_barras": item.get('codigo_barras') # NUEVO CAMPO
            })
        if items:
            supabase.table('items_compra').insert(items).execute()
            return len(items)
        else: return 0
    except Exception as e:
        if "unique" in str(e).lower(): return "DUPLICADO"
        st.error(f"Error DB: {e}")
        return False

def procesar_imagenes(lista_imagenes):
    contenido = []
    
    # --- PROMPT MEJORADO PARA LEER CÓDIGOS ---
    prompt = f"""
    Analiza este ticket. REGLA DE ORO: Si el nombre ocupa 2 líneas, ÚNELAS.
    
    NUEVA MISIÓN: Extraer el CÓDIGO DE BARRAS (EAN).
    - En tickets como COTO, suele estar DEBAJO del nombre del producto (ej: 000264.. 779007...).
    - El código EAN suele tener 13 dígitos y empezar con 779 (Argentina).
    - Si lo encuentras, extráelo en el campo "codigo_barras".
    - Para productos frescos (carne, verdura) suele no haber EAN, déjalo null.
    
    1. SUPERMERCADO: Nombre + Sucursal.
    2. PRODUCTOS: Marca, genérico, rubro, contenido, unidad y CÓDIGO.
    
    Rubros: {RUBROS_VALIDOS}
    
    JSON Estricto:
    {{
        "supermercado": "Str", "sucursal_direccion": "Str", "sucursal_localidad": "Str",
        "sucursal_provincia": "Str", "sucursal_pais": "Str", "moneda": "Str",
        "fecha": "YYYY-MM-DD", "hora": "HH:MM", "nro_ticket": "str", "total_pagado": num,
        "items": [
            {{ "nombre": "Str", "codigo_barras": "Str o null", "cantidad": num, "unidad_medida": "Str", "precio_neto_final": num,
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

# --- APP PRINCIPAL ---
if not st.session_state['user']:
    login()
else:
    with st.sidebar:
        st.header("👤 Mi Cuenta")
        st.write(f"{st.session_state['user'].email}")
        
        with st.expander("📱 Vincular Celular", expanded=True):
            try:
                perfil = supabase.table('perfiles').select('telefono, pais').eq('id', st.session_state['user'].id).execute().data
                tel_actual = perfil[0].get('telefono') if perfil else ""
                if tel_actual is None: tel_actual = ""
                pais_actual = perfil[0].get('pais', 'Argentina') if perfil else "Argentina"
            except:
                tel_actual = ""; pais_actual = "Argentina"

            pais_key = next((k for k in CODIGOS_PAIS if pais_actual in k), "Argentina 🇦🇷")
            sel_pais = st.selectbox("Código", list(CODIGOS_PAIS.keys()), index=list(CODIGOS_PAIS.keys()).index(pais_key))
            prefijo = CODIGOS_PAIS[sel_pais]
            display_num = tel_actual.replace(prefijo, "") if tel_actual.startswith(prefijo) else tel_actual
            num_local = st.text_input("Número", value=display_num)
            
            if st.button("Guardar"):
                try:
                    supabase.table('perfiles').upsert({"id": st.session_state['user'].id, "telefono": f"{prefijo}{num_local}".strip(), "pais": pais_actual}).execute()
                    st.success("Guardado!"); time.sleep(1); st.rerun()
                except Exception as e: st.error(f"Error: {e}")

        # BOTÓN WHATSAPP
        TWILIO_NUMBER = "+14155238886"
        TWILIO_CODE = "join quite-empty" # <--- REVISA QUE ESTE SEA TU CÓDIGO ACTUAL
        
        if tel_actual:
            st.divider()
            with st.expander("🤖 Bot WhatsApp"):
                st.link_button("📲 Abrir y Activar", f"https://wa.me/{TWILIO_NUMBER}?text={TWILIO_CODE.replace(' ', '%20')}")

        st.divider()
        if st.button("Salir"): logout()

    # PANTALLA PRINCIPAL
    st.markdown("<h1>🛒 Club de Precios v5.1</h1>", unsafe_allow_html=True)
    st.info("💡 **Tip:** Asegúrate de que los números debajo de los productos sean legibles en la foto.")

    if 'uploader_key' not in st.session_state: st.session_state['uploader_key'] = 0

    uploaded_files = st.file_uploader("📂 Subir fotos", accept_multiple_files=True, type=['jpg','png','jpeg'], key=f"uploader_{st.session_state['uploader_key']}")

    if uploaded_files:
        st.write(f"🎞️ **{len(uploaded_files)} imágenes**")
        if st.button("🚀 PROCESAR TICKET", type="primary", use_container_width=True):
            with st.spinner("🧠 Leyendo códigos EAN y precios..."):
                data = procesar_imagenes(uploaded_files)
                if data:
                    res = guardar_en_supabase(data)
                    if res == "DUPLICADO": st.warning("⚠️ Ticket ya cargado.")
                    elif res is not False:
                        st.balloons()
                        total = f"{data.get('moneda','$')} {data.get('total_pagado')}"
                        st.success(f"✅ **¡Carga Exitosa!**\n\n💰 **{total}** ({res} items)\n📍 {data.get('supermercado')}")
                        st.session_state['uploader_key'] += 1
                        time.sleep(4)
                        st.rerun()
                    else: st.error("Error técnico.")