import streamlit as st
import pandas as pd
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types
from supabase import create_client, Client

st.set_page_config(page_title="Buscador", page_icon="🔎", layout="wide")

# --- CONFIGURACIÓN ---
try:
    load_dotenv()
    URL = st.secrets["SUPABASE_URL"] if "SUPABASE_URL" in st.secrets else os.environ.get("SUPABASE_URL")
    KEY = st.secrets["SUPABASE_KEY"] if "SUPABASE_KEY" in st.secrets else os.environ.get("SUPABASE_KEY")
    GOOGLE_KEY = st.secrets["GOOGLE_API_KEY"] if "GOOGLE_API_KEY" in st.secrets else os.environ.get("GOOGLE_API_KEY")
    
    supabase = create_client(URL, KEY)
    client = genai.Client(api_key=GOOGLE_KEY)
except:
    st.error("Error de configuración")
    st.stop()

if 'user' not in st.session_state or not st.session_state['user']:
    st.warning("⚠️ Inicia sesión primero")
    st.stop()

st.markdown("### 🔎 ¿Está barato o caro?")
st.info("Saca una foto al producto (frente o etiqueta) y te diré si ya lo compraste antes.")

# --- 1. ENTRADA DE IMAGEN ---
img_buffer = st.camera_input("Foto del producto", label_visibility="collapsed")

if img_buffer:
    st.image(img_buffer, width=150, caption="Producto detectado")
    
    with st.spinner("🤖 Identificando producto..."):
        # A. PREGUNTAR A LA IA QUÉ ES
        img = Image.open(img_buffer)
        prompt = "Identifica este producto. Devuelve SOLO el nombre genérico y la marca. Ejemplo: 'Aceite de Girasol Cocinero'. Se breve."
        
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt, img]
            )
            producto_detectado = response.text.strip()
            st.success(f"Busco: **{producto_detectado}**")
            
            # B. BUSCAR EN LA BASE DE DATOS (Búsqueda de texto)
            # Usamos 'ilike' con comodines % para buscar coincidencias parciales
            terminos = producto_detectado.split()
            # Tomamos las palabras clave (ej: Aceite, Cocinero)
            busqueda = f"%{terminos[0]}%" 
            if len(terminos) > 1: busqueda += f"{terminos[1]}%"

            response_db = supabase.table('items_compra').select(
                'precio_neto_unitario, nombre_producto, fecha:tickets(fecha), super:tickets(supermercados(nombre))'
            ).ilike('nombre_producto', busqueda).order('precio_neto_unitario', desc=False).execute()
            
            resultados = response_db.data
            
            if resultados:
                st.write(f"✅ Encontré {len(resultados)} referencias:")
                
                df = pd.DataFrame(resultados)
                # Aplanar datos
                df['Supermercado'] = df['super'].apply(lambda x: x['supermercados']['nombre'])
                df['Fecha'] = df['fecha'].apply(lambda x: x['fecha'])
                df['Producto'] = df['nombre_producto']
                df['Precio'] = df['precio_neto_unitario']
                
                # Mostrar tabla ordenada por precio (más barato primero)
                st.dataframe(
                    df[['Precio', 'Supermercado', 'Fecha', 'Producto']],
                    hide_index=True,
                    column_config={"Precio": st.column_config.NumberColumn(format="$ %.2f")}
                )
                
                min_price = df.iloc[0]['Precio']
                st.metric("Mejor Precio Histórico", f"${min_price:,.2f}", f"en {df.iloc[0]['Supermercado']}")
                
            else:
                st.warning(f"No encontré '{producto_detectado}' en tu historial de compras.")
                
        except Exception as e:
            st.error(f"Error: {e}")