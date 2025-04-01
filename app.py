import streamlit as st
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import json
import pandas as pd
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="Gestor de Contactos con Firebase", page_icon="📞", layout="wide")

# Inicializar Firebase (solo una vez)
@st.cache_resource
def inicializar_firebase():
    # Verifica si Firebase ya está inicializado
    if not firebase_admin._apps:
        # IMPORTANTE: Reemplaza esto con las credenciales de tu proyecto Firebase
        # Este es solo un ejemplo de estructura, NO son credenciales reales
        key_dict = {
            "type": "service_account",
            "project_id": "tu-proyecto-id",
            "private_key_id": "tu-private-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\ntu-clave-privada\n-----END PRIVATE KEY-----\n",
            "client_email": "firebase-adminsdk-ejemplo@tu-proyecto-id.iam.gserviceaccount.com",
            "client_id": "tu-client-id",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-ejemplo%40tu-proyecto-id.iam.gserviceaccount.com",
            "universe_domain": "googleapis.com"
        }
        
        # Si prefieres usar un archivo JSON en lugar del diccionario:
        # cred = credentials.Certificate('ruta/a/tu-archivo-credenciales.json')
        
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    
    return firestore.client()

# Alternativa de inicialización utilizando secretos de Streamlit
# Para producción, es mejor usar st.secrets para manejar credenciales:
# @st.cache_resource
# def inicializar_firebase():
#     if not firebase_admin._apps:
#         key_dict = st.secrets["firebase"]
#         cred = credentials.Certificate(key_dict)
#         firebase_admin.initialize_app(cred)
#     return firestore.client()

# Inicializar Firestore
try:
    db = inicializar_firebase()
    conexion_exitosa = True
except Exception as e:
    st.error(f"Error al conectar con Firebase: {e}")
    conexion_exitosa = False
    db = None

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
                st.error("No hay conexión con Firebase. Revisa tus credenciales.")

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
        st.error("No hay conexión con Firebase. Revisa tus credenciales.")

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
        st.error("No hay conexión con Firebase. Revisa tus credenciales.")

# Información adicional
with st.sidebar:
    st.title("Información")
    st.info("""
    ## Configuración de Firebase
    
    Para que esta aplicación funcione, debes:
    
    1. Crear un proyecto en [Firebase Console](https://console.firebase.google.com/)
    2. Activar Firestore en tu proyecto
    3. Generar una clave privada para cuenta de servicio
    4. Reemplazar las credenciales en el código
    
    [Ver documentación de Firebase](https://firebase.google.com/docs/firestore/quickstart)
    """)
    
    st.warning("""
    ## Importante
    
    No subas tus credenciales de Firebase a repositorios públicos.
    Para producción, usa variables de entorno o secretos de Streamlit.
    """)
