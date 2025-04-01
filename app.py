import streamlit as st
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import pandas as pd
from datetime import datetime
import json
import os

# Configuración de la página
st.set_page_config(page_title="Gestor de Contactos con Firebase", page_icon="📞", layout="wide")

# Función para inicializar Firebase de forma segura
@st.cache_resource
def inicializar_firebase():
    if not firebase_admin._apps:
        try:
            # Detectar entorno (desarrollo local o Streamlit Cloud)
            if os.path.exists(".streamlit/secrets.toml"):
                st.write("🔑 Usando credenciales locales")
                # Entorno de desarrollo local con .streamlit/secrets.toml
                try:
                    # Obtener credenciales de st.secrets
                    firebase_secrets = st.secrets["firebase"]
                    
                    # Crear diccionario de credenciales
                    cred_dict = {
                        "type": firebase_secrets["type"],
                        "project_id": firebase_secrets["project_id"],
                        "private_key_id": firebase_secrets["private_key_id"],
                        "private_key": firebase_secrets["private_key"].replace('\\n', '\n'),
                        "client_email": firebase_secrets["client_email"],
                        "client_id": firebase_secrets["client_id"],
                        "auth_uri": firebase_secrets["auth_uri"],
                        "token_uri": firebase_secrets["token_uri"],
                        "auth_provider_x509_cert_url": firebase_secrets["auth_provider_x509_cert_url"],
                        "client_x509_cert_url": firebase_secrets["client_x509_cert_url"],
                        "universe_domain": firebase_secrets["universe_domain"]
                    }
                    
                    cred = credentials.Certificate(cred_dict)
                    firebase_admin.initialize_app(cred)
                except Exception as e:
                    st.error(f"Error con credenciales locales: {e}")
                    return None
            else:
                # Entorno de Streamlit Cloud
                st.write("☁️ Usando credenciales de Streamlit Cloud")
                
                # Verificar si están disponibles las variables de entorno individuales
                if all(key in st.secrets.keys() for key in [
                    "FIREBASE_TYPE", "FIREBASE_PROJECT_ID", "FIREBASE_PRIVATE_KEY_ID",
                    "FIREBASE_PRIVATE_KEY", "FIREBASE_CLIENT_EMAIL"
                ]):
                    # Crear diccionario de credenciales desde variables individuales
                    cred_dict = {
                        "type": st.secrets["FIREBASE_TYPE"],
                        "project_id": st.secrets["FIREBASE_PROJECT_ID"],
                        "private_key_id": st.secrets["FIREBASE_PRIVATE_KEY_ID"],
                        "private_key": st.secrets["FIREBASE_PRIVATE_KEY"].replace('\\n', '\n'),
                        "client_email": st.secrets["FIREBASE_CLIENT_EMAIL"],
                        "client_id": st.secrets["FIREBASE_CLIENT_ID"],
                        "auth_uri": st.secrets["FIREBASE_AUTH_URI"],
                        "token_uri": st.secrets["FIREBASE_TOKEN_URI"],
                        "auth_provider_x509_cert_url": st.secrets["FIREBASE_AUTH_PROVIDER_X509_CERT_URL"],
                        "client_x509_cert_url": st.secrets["FIREBASE_CLIENT_X509_CERT_URL"],
                        "universe_domain": st.secrets["FIREBASE_UNIVERSE_DOMAIN"]
                    }
                    
                    cred = credentials.Certificate(cred_dict)
                    firebase_admin.initialize_app(cred)
                else:
                    # Intentar usar firebase_credentials como JSON
                    try:
                        json_str = st.secrets["FIREBASE_CREDENTIALS"]
                        cred_dict = json.loads(json_str)
                        cred = credentials.Certificate(cred_dict)
                        firebase_admin.initialize_app(cred)
                    except Exception as e:
                        st.error(f"Error con credenciales JSON: {e}")
                        
                        # Último intento - usando firebase como clave
                        try:
                            firebase_dict = st.secrets["firebase"]
                            if isinstance(firebase_dict, dict):
                                cred = credentials.Certificate(firebase_dict)
                            else:
                                cred_dict = json.loads(firebase_dict)
                                cred = credentials.Certificate(cred_dict)
                            firebase_admin.initialize_app(cred)
                        except Exception as e2:
                            st.error(f"Error en último intento: {e2}")
                            return None
            
            return firestore.client()
        except Exception as e:
            st.error(f"Error al inicializar Firebase: {e}")
            return None
    
    return firestore.client()

# Inicializar Firestore
db = inicializar_firebase()
conexion_exitosa = db is not None

# Quitar los mensajes de depuración después de la conexión
st.empty()

# Título de la aplicación
st.title("📋 Gestor de Contactos con Firebase")

# Crear las pestañas principales
tab1, tab2, tab3 = st.tabs(["Agregar Contacto", "Ver Contactos", "Buscar Contactos"])

# Pestaña: Agregar Contacto
with tab1:
    st.header("Agregar Nuevo Contacto")
    
    # Formulario para agregar contacto
    with st.form(key="contacto_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            nombre = st.text_input("Nombre")
            email = st.text_input("Email")
            telefono = st.text_input("Teléfono")
        
        with col2:
            direccion = st.text_input("Dirección")
            ciudad = st.text_input("Ciudad")
            categoria = st.selectbox(
                "Categoría", 
                options=["Familiar", "Amigo", "Trabajo", "Escuela", "Otro"]
            )
        
        notas = st.text_area("Notas adicionales")
        submit_button = st.form_submit_button(label="Guardar Contacto")
        
        # Cuando se presiona el botón de guardar
        if submit_button:
            if not nombre or not email:
                st.error("Nombre y email son campos obligatorios.")
            elif conexion_exitosa:
                # Crear documento para guardar en Firestore
                data = {
                    "nombre": nombre,
                    "email": email,
                    "telefono": telefono,
                    "direccion": direccion,
                    "ciudad": ciudad,
                    "categoria": categoria,
                    "notas": notas,
                    "fecha_creacion": datetime.now()
                }
                
                # Guardar en Firestore
                try:
                    db.collection("contactos").add(data)
                    st.success(f"Contacto {nombre} guardado exitosamente!")
                    # Limpiar formulario mostrando un placeholder vacío
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
            else:
                st.error("No hay conexión con Firebase.")

# Pestaña: Ver Contactos
with tab2:
    st.header("Lista de Contactos")
    
    if conexion_exitosa:
        # Botón para actualizar la lista
        if st.button("Actualizar Lista"):
            st.experimental_rerun()
            
        # Recuperar contactos de Firestore
        try:
            contactos_ref = db.collection("contactos").order_by("nombre").stream()
            contactos = []
            
            for doc in contactos_ref:
                contacto_data = doc.to_dict()
                # Agregar el ID del documento
                contacto_data["id"] = doc.id
                
                # Convertir el timestamp a formato legible si existe
                if "fecha_creacion" in contacto_data:
                    if isinstance(contacto_data["fecha_creacion"], datetime):
                        contacto_data["fecha_creacion"] = contacto_data["fecha_creacion"].strftime("%d/%m/%Y %H:%M")
                
                contactos.append(contacto_data)
            
            # Mostrar contactos en una tabla
            if contactos:
                df = pd.DataFrame(contactos)
                
                # Reordenar y seleccionar columnas para mostrar
                columnas_mostrar = ["nombre", "email", "telefono", "categoria", "ciudad", "id"]
                columnas_disponibles = [col for col in columnas_mostrar if col in df.columns]
                
                st.dataframe(
                    df[columnas_disponibles],
                    use_container_width=True,
                    column_config={
                        "id": st.column_config.TextColumn("ID", width="small"),
                        "nombre": st.column_config.TextColumn("Nombre", width="medium"),
                        "email": st.column_config.TextColumn("Email", width="medium"),
                        "telefono": st.column_config.TextColumn("Teléfono", width="small"),
                        "categoria": st.column_config.TextColumn("Categoría", width="small"),
                        "ciudad": st.column_config.TextColumn("Ciudad", width="small")
                    }
                )
                
                # Sección para ver detalles o eliminar un contacto
                with st.expander("Ver detalles de contacto"):
                    id_seleccionado = st.selectbox(
                        "Selecciona un contacto para ver detalles:", 
                        options=[c["id"] for c in contactos],
                        format_func=lambda x: next((c["nombre"] for c in contactos if c["id"] == x), "")
                    )
                    
                    if id_seleccionado:
                        contacto_seleccionado = next((c for c in contactos if c["id"] == id_seleccionado), None)
                        if contacto_seleccionado:
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.subheader(contacto_seleccionado["nombre"])
                                st.write(f"📧 {contacto_seleccionado.get('email', 'N/A')}")
                                st.write(f"📞 {contacto_seleccionado.get('telefono', 'N/A')}")
                                st.write(f"🏷️ {contacto_seleccionado.get('categoria', 'N/A')}")
                            
                            with col2:
                                st.write(f"🏠 {contacto_seleccionado.get('direccion', 'N/A')}")
                                st.write(f"🏙️ {contacto_seleccionado.get('ciudad', 'N/A')}")
                                if "fecha_creacion" in contacto_seleccionado:
                                    st.write(f"📅 {contacto_seleccionado['fecha_creacion']}")
                            
                            st.write("📝 Notas:")
                            st.write(contacto_seleccionado.get("notas", "Sin notas"))
                            
                            # Botón para eliminar
                            if st.button("🗑️ Eliminar contacto", key="del_btn"):
                                try:
                                    db.collection("contactos").document(id_seleccionado).delete()
                                    st.success("Contacto eliminado exitosamente!")
                                    st.experimental_rerun()
                                except Exception as e:
                                    st.error(f"Error al eliminar: {e}")
            else:
                st.info("No hay contactos guardados en la base de datos.")
        
        except Exception as e:
            st.error(f"Error al recuperar contactos: {e}")
    else:
        st.error("No hay conexión con Firebase.")

# Pestaña: Buscar Contactos
with tab3:
    st.header("Buscar Contactos")
    
    if conexion_exitosa:
        # Campo de búsqueda
        busqueda = st.text_input("Buscar por nombre, email o ciudad:")
        
        if busqueda:
            try:
                # Búsqueda en Firebase
                # Nota: Firestore no permite búsquedas de texto completo de forma nativa
                # Esta es una implementación simple que recupera todos los documentos y filtra localmente
                
                contactos_ref = db.collection("contactos").stream()
                resultados = []
                
                for doc in contactos_ref:
                    contacto = doc.to_dict()
                    contacto["id"] = doc.id
                    
                    # Buscar en diferentes campos
                    if (busqueda.lower() in contacto.get("nombre", "").lower() or
                        busqueda.lower() in contacto.get("email", "").lower() or
                        busqueda.lower() in contacto.get("ciudad", "").lower()):
                        resultados.append(contacto)
                
                if resultados:
                    st.write(f"Se encontraron {len(resultados)} resultados:")
                    
                    for contacto in resultados:
                        with st.container():
                            st.subheader(contacto["nombre"])
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"📧 {contacto.get('email', 'N/A')}")
                                st.write(f"📞 {contacto.get('telefono', 'N/A')}")
                                
                            with col2:
                                st.write(f"🏷️ {contacto.get('categoria', 'N/A')}")
                                st.write(f"🏙️ {contacto.get('ciudad', 'N/A')}")
                            
                            st.divider()
                else:
                    st.info("No se encontraron contactos que coincidan con la búsqueda.")
            
            except Exception as e:
                st.error(f"Error en la búsqueda: {e}")
    else:
        st.error("No hay conexión con Firebase.")

# Información adicional
with st.sidebar:
    st.title("Información")
    st.info("""
    ## Gestor de Contactos con Firebase
    
    Esta aplicación permite:
    
    - Agregar contactos a Firebase
    - Ver la lista de contactos
    - Buscar contactos por nombre, email o ciudad
    - Eliminar contactos
    
    Los datos se almacenan en Firestore (base de datos de Firebase).
    """)
    
    if not conexion_exitosa:
        st.error("""
        ### ⚠️ Error de conexión
        
        La aplicación no pudo conectarse a Firebase. Verifica la configuración de tus secretos en Streamlit Cloud.
        
        Para más información, consulta la sección de "Ayuda" a continuación.
        """)
        
        with st.expander("Ayuda con la configuración"):
            st.write("""
            ### Configuración de credenciales en Streamlit Cloud
            
            Para configurar las credenciales correctamente:
            
            1. Ve a la configuración de tu aplicación en Streamlit Cloud
            2. En Advanced Settings > Secrets, configura tus credenciales en formato JSON
            
            Ejemplo:
            ```
            FIREBASE_CREDENTIALS = {"type": "service_account", "project_id": "tu-proyecto", ...}
            ```
            
            O como variables individuales:
            ```
            FIREBASE_TYPE = "service_account"
            FIREBASE_PROJECT_ID = "tu-proyecto"
            FIREBASE_PRIVATE_KEY_ID = "tu-private-key-id"
            FIREBASE_PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
            ...
            ```
            """)
    
    st.write("Desarrollado con Streamlit + Firebase")
