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

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Club de Precios", page_icon="🛒", layout="wide", initial_sidebar_state="collapsed")

# CSS: Estilos para la Landing Page y la App
st.markdown("""
    <style>
        /* Ajuste de márgenes */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 3rem !important;
        }
        
        /* Títulos */
        h1 { font-size: 2rem !important; text-align: center; margin-bottom: 0.5rem; color: #FF4B4B; }
        h3 { text-align: center; margin-top: 0; font-weight: 300; }
        
        /* Botones Grandes */
        .stButton button { 
            width: 100%; border-radius: 30px; height: 3.5rem; 
            font-size: 1.1rem; font-weight: bold;
        }
        
        /* Área de carga de archivos */
        div[data-testid="stFileUploader"] {
            border: 2px dashed #FF4B4B;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
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
        st.error("❌ Faltan claves de configuración.")
        st.stop()

    supabase: Client = create_client(URL, KEY)
    client = genai.Client(api_key=GOOGLE_KEY)
    MODELO_IA = 'gemini-2.5-flash' 

except Exception as e:
    st.error(f"Error de sistema: {e}")
    st.stop()

# --- DATOS MAESTROS ---
PAISES_SOPORTADOS = ["Argentina", "Brasil", "Uruguay", "Chile", "Paraguay", "Bolivia", "Perú", "Colombia", "México", "España", "USA", "Otro"]

# Códigos para WhatsApp (E.164)
CODIGOS_PAIS = {
    "Argentina 🇦🇷": "+549",
    "Brasil 🇧🇷": "+55",
    "Uruguay 🇺🇾": "+598",
    "Chile 🇨🇱": "+56",
    "México 🇲🇽": "+52",
    "Colombia 🇨🇴": "+57",
    "España 🇪🇸": "+34",
    "USA 🇺🇸": "+1",
    "Otro": "+"
}

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

# --- LOGIN (LANDING PAGE) ---
if 'user' not in st.session_state: st.session_state['user'] = None

def login():
    # --- ENCABEZADO DE MARKETING ---
    st.markdown("<h1>🛒 Club de Precios</h1>", unsafe_allow_html=True)
    st.markdown("<h3>La inteligencia colectiva contra la inflación</h3>", unsafe_allow_html=True)
    
    st.markdown("""
    <p style='text-align: center; font-size: 1.1em; color: gray;'>
        Sube la foto de tu ticket, organizamos tus gastos y comparamos precios automáticamente.
    </p>
    """, unsafe_allow_html=True)
    
    # --- COLUMNAS DE BENEFICIOS ---
    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("<div style='text-align: center;'>📸<br><b>Escanea</b><br>Saca una foto a tu ticket. La IA hace el resto.</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div style='text-align: center;'>📊<br><b>Controla</b><br>Mira cómo evolucionan tus gastos mes a mes.</div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div style='text-align: center;'>🤝<br><b>Ahorra</b><br>Descubre quién vende más barato en tu zona.</div>", unsafe_allow_html=True)
    st.divider()

    # --- ZONA DE INGRESO ---
    st.info("👇 **Comienza ahora**")
    
    tab1, tab2 = st.tabs(["🔐 Ya soy Socio", "📝 Quiero unirme Gratis"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Ingresar", use_container_width=True):
                try:
                    session = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state['user'] = session.user
                    st.rerun()
                except: st.error("Email o contraseña incorrectos")

    with tab2:
        with st.form("register_form"):
            c_a, c_b = st.columns(2)
            new_email = c_a.text_input("Tu Email")
            new_pass = c_b.text_input("Crea una Contraseña", type="password")
            
            st.markdown("📍 **¿Dónde haces tus compras?**")
            c1, c2, c3 = st.columns(3)
            pais = c1.selectbox("País", PAISES_SOPORTADOS)
            provincia = c2.text_input("Provincia")
            ciudad = c3.text_input("Ciudad")
            
            if st.form_submit_button("Crear Cuenta", use_container_width=True):
                try:
                    res = supabase.auth.sign_up({"email": new_email, "password": new_pass})
                    if res.user:
                        try:
                            supabase.table('perfiles').insert({
                                "id": res.user.id, "pais": pais, "ciudad": ciudad, "provincia": provincia
                            }).execute()
                        except: pass 
                        st.success("¡Cuenta creada! Ya puedes ingresar en la otra pestaña.")
                except Exception as e: st.error(f"Error: {e}")

def logout():
    supabase.auth.sign_out()
    st.session_state['user'] = None
    st.rerun()

# --- BACKEND PROCESAMIENTO ---
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
        "imagen_url": "v5.0_landing", "sucursal_direccion": data.get('sucursal_direccion'),
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
    
    prompt = f"""
    Analiza este ticket de compra.
    
    REGLA DE ORO: Si el nombre del producto ocupa 2 líneas, ÚNELAS. No crees dos items.
    
    1. SUPERMERCADO: Extrae NOMBRE + SUCURSAL (ej: JUMBO UNICENTER).
    2. FECHA Y MONEDA: Fecha YYYY-MM-DD.
    3. PRODUCTOS: Marca, genérico, rubro (de la lista), contenido y unidad.
    
    Rubros: {RUBROS_VALIDOS}
    
    JSON Estricto:
    {{
        "supermercado": "Str", "sucursal_direccion": "Str", "sucursal_localidad": "Str",
        "sucursal_provincia": "Str", "sucursal_pais": "Str", "moneda": "Str",
        "fecha": "YYYY-MM-DD", "hora": "HH:MM", "nro_ticket": "str", "total_pagado": num,
        "items": [
            {{ "nombre": "Nombre Completo", "cantidad": num, "unidad_medida": "Str", "precio_neto_final": num,
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
        
        # 1. GESTIÓN DE TELÉFONO
        with st.expander("📱 Vincular Celular", expanded=True):
            try:
                perfil = supabase.table('perfiles').select('telefono, pais').eq('id', st.session_state['user'].id).execute().data
                tel_actual = perfil[0].get('telefono') if perfil else ""
                if tel_actual is None: tel_actual = ""
                pais_actual = perfil[0].get('pais', 'Argentina') if perfil else "Argentina"
            except:
                tel_actual = ""
                pais_actual = "Argentina"

            pais_key_match = next((k for k in CODIGOS_PAIS if pais_actual in k), "Argentina 🇦🇷")
            sel_pais = st.selectbox("Código", list(CODIGOS_PAIS.keys()), index=list(CODIGOS_PAIS.keys()).index(pais_key_match) if pais_key_match in CODIGOS_PAIS else 0)
            prefijo = CODIGOS_PAIS[sel_pais]
            
            display_num = tel_actual.replace(prefijo, "") if tel_actual.startswith(prefijo) else tel_actual
            numero_local = st.text_input("Número (sin 0/15)", value=display_num)
            
            if st.button("💾 Guardar"):
                tel_final = f"{prefijo}{numero_local}".strip()
                try:
                    datos = {"id": st.session_state['user'].id, "telefono": tel_final, "pais": pais_actual}
                    supabase.table('perfiles').upsert(datos).execute()
                    st.success("Guardado!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")

        # 2. ACTIVAR BOT WHATSAPP
        if tel_actual:
            st.divider()
            # ⬇️⬇️⬇️ EDITA ESTAS DOS LINEAS CON TUS DATOS DE TWILIO ⬇️⬇️⬇️
            TWILIO_NUMBER = "+14155238886"
            TWILIO_CODE = "join quite-empty" 
            # ⬆️⬆️⬆️ ----------------------------------------------------
            
            with st.expander("🤖 Activar Bot"):
                st.write("1. Toca el botón.")
                st.write("2. Envía el mensaje pre-cargado.")
                link_wa = f"https://wa.me/{TWILIO_NUMBER}?text={TWILIO_CODE.replace(' ', '%20')}"
                st.link_button("📲 Abrir WhatsApp", link_wa)

        st.divider()
        if st.button("Salir"): logout()

    # --- PANTALLA PRINCIPAL ---
    st.markdown("<h1>🛒 Club de Precios</h1>", unsafe_allow_html=True)
    st.info("💡 **Tip:** Mantén apretada una foto en tu galería para seleccionar varias a la vez.")

    if 'uploader_key' not in st.session_state: st.session_state['uploader_key'] = 0

    uploaded_files = st.file_uploader(
        "📂 Subir fotos", accept_multiple_files=True, type=['jpg','png','jpeg'],
        key=f"uploader_{st.session_state['uploader_key']}"
    )

    if uploaded_files:
        st.write(f"🎞️ **{len(uploaded_files)} imágenes listas**")
        
        if st.button("🚀 PROCESAR TICKET", type="primary", use_container_width=True):
            with st.spinner("🧠 Analizando..."):
                data = procesar_imagenes(uploaded_files)
                
                if data:
                    res = guardar_en_supabase(data)
                    
                    if res == "DUPLICADO":
                        st.warning("⚠️ Ticket ya cargado.")
                    elif res is not False:
                        st.balloons()
                        total_fmt = f"{data.get('moneda','$')} {data.get('total_pagado')}"
                        st.success(f"✅ **¡Carga Exitosa!**\n\n💰 **{total_fmt}** ({res} items)\n📍 {data.get('supermercado')}")
                        st.session_state['uploader_key'] += 1
                        time.sleep(4)
                        st.rerun()
                    else:
                        st.error("Hubo un error técnico.")