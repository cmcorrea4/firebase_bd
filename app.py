import streamlit as st
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from firebase_admin import storage
import pandas as pd
from datetime import datetime
import json
import os
import base64
import uuid

# Configuración de la página
st.set_page_config(page_title="Gestor de Clientes con Firebase", page_icon="🏢", layout="wide")

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
                    firebase_admin.initialize_app(cred, {
                        'storageBucket': f"{firebase_secrets['project_id']}.appspot.com"
                    })
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
                    firebase_admin.initialize_app(cred, {
                        'storageBucket': f"{cred_dict['project_id']}.appspot.com"
                    })
                else:
                    # Intentar usar firebase_credentials como JSON
                    try:
                        json_str = st.secrets["FIREBASE_CREDENTIALS"]
                        cred_dict = json.loads(json_str)
                        cred = credentials.Certificate(cred_dict)
                        firebase_admin.initialize_app(cred, {
                            'storageBucket': f"{cred_dict['project_id']}.appspot.com"
                        })
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
                            firebase_admin.initialize_app(cred, {
                                'storageBucket': f"{cred_dict['project_id']}.appspot.com"
                            })
                        except Exception as e2:
                            st.error(f"Error en último intento: {e2}")
                            return None
            
            # Crear un diccionario con las referencias necesarias
            db = firestore.client()
            bucket = storage.bucket()
            return {"db": db, "bucket": bucket}
        except Exception as e:
            st.error(f"Error al inicializar Firebase: {e}")
            return None
    
    # Si ya está inicializado, devolver las referencias
    return {"db": firestore.client(), "bucket": storage.bucket()}

# Inicializar Firestore y Storage
firebase_refs = inicializar_firebase()
conexion_exitosa = firebase_refs is not None

if conexion_exitosa:
    db = firebase_refs["db"]
    bucket = firebase_refs["bucket"]

# Quitar los mensajes de depuración después de la conexión
st.empty()

# Título de la aplicación
st.title("🏢 Gestor de Clientes con Firebase")

# Función para obtener todos los clientes
def obtener_clientes():
    if not conexion_exitosa:
        return []
    try:
        clientes_ref = db.collection("clientes").order_by("nombre").stream()
        clientes = []
        
        for doc in clientes_ref:
            cliente_data = doc.to_dict()
            # Agregar el ID del documento
            cliente_data["id"] = doc.id
            
            # Convertir el timestamp a formato legible si existe
            if "fecha_creacion" in cliente_data and isinstance(cliente_data["fecha_creacion"], datetime):
                cliente_data["fecha_creacion"] = cliente_data["fecha_creacion"].strftime("%d/%m/%Y %H:%M")
            
            clientes.append(cliente_data)
        return clientes
    except Exception as e:
        st.error(f"Error al recuperar clientes: {e}")
        return []

# Función para subir archivo PDF a Firebase Storage
def subir_archivo(cliente_id, archivo, descripcion):
    try:
        # Generar nombre único para el archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"{cliente_id}/{timestamp}_{archivo.name}"
        
        # Referencia al archivo en Storage
        blob = bucket.blob(nombre_archivo)
        
        # Subir archivo
        blob.upload_from_file(archivo, content_type="application/pdf")
        
        # Hacer público el archivo (opcional, depende de tus necesidades de seguridad)
        blob.make_public()
        
        # Obtener URL del archivo
        url_archivo = blob.public_url
        
        # Crear registro del archivo en Firestore
        archivo_data = {
            "nombre": archivo.name,
            "descripcion": descripcion,
            "url": url_archivo,
            "ruta_storage": nombre_archivo,
            "fecha_subida": datetime.now()
        }
        
        # Obtener referencia al documento del cliente
        doc_ref = db.collection("clientes").document(cliente_id)
        
        # Obtener el documento actual
        doc = doc_ref.get()
        
        if doc.exists:
            # Verificar si ya tiene archivos
            cliente_data = doc.to_dict()
            archivos = cliente_data.get("archivos", [])
            
            # Añadir el nuevo archivo
            archivos.append(archivo_data)
            
            # Actualizar el documento en Firestore
            doc_ref.update({"archivos": archivos})
            
            return True, "Archivo subido exitosamente"
        else:
            return False, "No se encontró el cliente seleccionado"
            
    except Exception as e:
        return False, f"Error al subir archivo: {str(e)}"

# Función para eliminar archivo de Firebase Storage
def eliminar_archivo(cliente_id, indice_archivo):
    try:
        # Obtener documento del cliente
        doc_ref = db.collection("clientes").document(cliente_id)
        doc = doc_ref.get()
        
        if doc.exists:
            cliente_data = doc.to_dict()
            archivos = cliente_data.get("archivos", [])
            
            if 0 <= indice_archivo < len(archivos):
                # Obtener información del archivo a eliminar
                archivo = archivos[indice_archivo]
                ruta_storage = archivo.get("ruta_storage")
                
                # Eliminar del Storage
                if ruta_storage:
                    blob = bucket.blob(ruta_storage)
                    blob.delete()
                
                # Eliminar del array de archivos
                archivos.pop(indice_archivo)
                
                # Actualizar el documento en Firestore
                doc_ref.update({"archivos": archivos})
                
                return True, "Archivo eliminado exitosamente"
            else:
                return False, "Índice de archivo no válido"
        else:
            return False, "No se encontró el cliente seleccionado"
    except Exception as e:
        return False, f"Error al eliminar archivo: {str(e)}"

# Crear las pestañas principales
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Agregar Cliente", "Ver Clientes", "Buscar Clientes", "Registrar Capacitación", "Gestionar Archivos"])

# Pestaña: Agregar Cliente
with tab1:
    st.header("Agregar Nuevo Cliente")
    
    # Formulario para agregar cliente
    with st.form(key="cliente_form"):
        # Información del contacto
        st.subheader("Información del Contacto")
        col1, col2 = st.columns(2)
        
        with col1:
            nombre = st.text_input("Nombre del Contacto")
            email = st.text_input("Email")
            telefono = st.text_input("Teléfono")
        
        with col2:
            empresa = st.text_input("Nombre de la Empresa")
            cargo = st.text_input("Cargo en la Empresa")
            categoria = st.selectbox(
                "Categoría", 
                options=["Potencial", "Activo", "Inactivo", "Prioritario", "Otro"]
            )
        
        # Dirección y notas
        st.subheader("Información Adicional")
        col3, col4 = st.columns(2)
        
        with col3:
            direccion = st.text_input("Dirección")
            ciudad = st.text_input("Ciudad")
            pais = st.text_input("País")
        
        with col4:
            industria = st.text_input("Industria")
            sitio_web = st.text_input("Sitio Web")
            rut = st.text_input("RUT/ID Fiscal")
        
        notas = st.text_area("Notas adicionales")
        submit_button = st.form_submit_button(label="Guardar Cliente")
        
        # Cuando se presiona el botón de guardar
        if submit_button:
            if not nombre or not empresa:
                st.error("Nombre del contacto y Nombre de la empresa son campos obligatorios.")
            elif conexion_exitosa:
                # Crear documento para guardar en Firestore
                data = {
                    "nombre": nombre,
                    "email": email,
                    "telefono": telefono,
                    "empresa": empresa,
                    "cargo": cargo,
                    "categoria": categoria,
                    "direccion": direccion,
                    "ciudad": ciudad,
                    "pais": pais,
                    "industria": industria,
                    "sitio_web": sitio_web,
                    "rut": rut,
                    "notas": notas,
                    "fecha_creacion": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "archivos": [],
                    "capacitaciones": []
                }
                
                # Guardar en Firestore
                try:
                    db.collection("clientes").add(data)
                    st.success(f"Cliente {nombre} ({empresa}) guardado exitosamente!")
                    # Limpiar formulario mostrando un placeholder vacío
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
            else:
                st.error("No hay conexión con Firebase.")

# Pestaña: Ver Clientes
with tab2:
    st.header("Lista de Clientes")
    
    if conexion_exitosa:
        # Botón para actualizar la lista
        if st.button("Actualizar Lista"):
            st.experimental_rerun()
            
        # Recuperar clientes de Firestore
        clientes = obtener_clientes()
            
        # Mostrar clientes en una tabla
        if clientes:
            df = pd.DataFrame(clientes)
            
            # Reordenar y seleccionar columnas para mostrar
            columnas_mostrar = ["nombre", "empresa", "email", "telefono", "categoria", "ciudad", "id"]
            columnas_disponibles = [col for col in columnas_mostrar if col in df.columns]
            
            st.dataframe(
                df[columnas_disponibles],
                use_container_width=True,
                column_config={
                    "id": st.column_config.TextColumn("ID", width="small"),
                    "nombre": st.column_config.TextColumn("Nombre", width="medium"),
                    "empresa": st.column_config.TextColumn("Empresa", width="medium"),
                    "email": st.column_config.TextColumn("Email", width="medium"),
                    "telefono": st.column_config.TextColumn("Teléfono", width="small"),
                    "categoria": st.column_config.TextColumn("Categoría", width="small"),
                    "ciudad": st.column_config.TextColumn("Ciudad", width="small")
                }
            )
            
            # Sección para ver detalles o eliminar un cliente
            with st.expander("Ver detalles de cliente"):
                id_seleccionado = st.selectbox(
                    "Selecciona un cliente para ver detalles:", 
                    options=[c["id"] for c in clientes],
                    format_func=lambda x: f"{next((c['nombre'] for c in clientes if c['id'] == x), '')} - {next((c['empresa'] for c in clientes if c['id'] == x), '')}"
                )
                
                if id_seleccionado:
                    cliente_seleccionado = next((c for c in clientes if c["id"] == id_seleccionado), None)
                    if cliente_seleccionado:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader(f"{cliente_seleccionado.get('nombre')} ({cliente_seleccionado.get('cargo', 'N/A')})")
                            st.subheader(f"🏢 {cliente_seleccionado.get('empresa')}")
                            st.write(f"📧 {cliente_seleccionado.get('email', 'N/A')}")
                            st.write(f"📞 {cliente_seleccionado.get('telefono', 'N/A')}")
                            st.write(f"🏷️ {cliente_seleccionado.get('categoria', 'N/A')}")
                            if cliente_seleccionado.get('sitio_web'):
                                st.write(f"🌐 {cliente_seleccionado.get('sitio_web')}")
                        
                        with col2:
                            st.write(f"🏠 {cliente_seleccionado.get('direccion', 'N/A')}")
                            st.write(f"🏙️ {cliente_seleccionado.get('ciudad', 'N/A')}, {cliente_seleccionado.get('pais', 'N/A')}")
                            st.write(f"🏭 Industria: {cliente_seleccionado.get('industria', 'N/A')}")
                            st.write(f"🆔 RUT/ID: {cliente_seleccionado.get('rut', 'N/A')}")
                            if "fecha_creacion" in cliente_seleccionado:
                                st.write(f"📅 {cliente_seleccionado['fecha_creacion']}")
                        
                        st.write("📝 Notas:")
                        st.write(cliente_seleccionado.get("notas", "Sin notas"))
                        
                        # Mostrar capacitaciones si existen
                        if "capacitaciones" in cliente_seleccionado and cliente_seleccionado["capacitaciones"]:
                            with st.expander("🎓 Capacitaciones realizadas"):
                                # Asegurarse de que las capacitaciones son una lista
                                capacitaciones = cliente_seleccionado["capacitaciones"]
                                if not isinstance(capacitaciones, list):
                                    st.error("Error: El formato de capacitaciones no es válido.")
                                else:
                                    for cap in capacitaciones:
                                        try:
                                            st.write(f"- **{cap.get('nombre', 'Sin nombre')}** ({cap.get('fecha', 'Sin fecha')})")
                                            st.write(f"  Estado: {cap.get('estado', 'No especificado')}")
                                            if cap.get('detalles'):
                                                st.write(f"  Detalles: {cap.get('detalles')}")
                                            st.write("---")
                                        except Exception as e:
                                            st.error(f"Error al mostrar capacitación: {e}")
                                            st.write("---")
                        
                        # Mostrar archivos si existen
                        if "archivos" in cliente_seleccionado and cliente_seleccionado["archivos"]:
                            with st.expander("📁 Archivos del cliente"):
                                for archivo in cliente_seleccionado["archivos"]:
                                    col_arch1, col_arch2 = st.columns([3, 1])
                                    with col_arch1:
                                        st.write(f"**{archivo.get('nombre', 'Sin nombre')}**")
                                        st.write(f"Descripción: {archivo.get('descripcion', 'Sin descripción')}")
                                        if archivo.get('fecha_subida') and isinstance(archivo.get('fecha_subida'), datetime):
                                            st.write(f"Subido: {archivo.get('fecha_subida').strftime('%d/%m/%Y %H:%M')}")
                                    
                                    with col_arch2:
                                        if archivo.get('url'):
                                            st.markdown(f"[Descargar PDF]({archivo.get('url')})")
                                    
                                    st.write("---")
                        
                        # Botón para eliminar
                        if st.button("🗑️ Eliminar cliente", key="del_btn"):
                            try:
                                # Primero eliminamos los archivos del Storage
                                if "archivos" in cliente_seleccionado and cliente_seleccionado["archivos"]:
                                    for archivo in cliente_seleccionado["archivos"]:
                                        if archivo.get("ruta_storage"):
                                            try:
                                                blob = bucket.blob(archivo.get("ruta_storage"))
                                                blob.delete()
                                            except Exception:
                                                pass  # Continuar aunque falle alguna eliminación
                                
                                # Luego eliminamos el documento
                                db.collection("clientes").document(id_seleccionado).delete()
                                st.success("Cliente eliminado exitosamente!")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"Error al eliminar: {e}")
        else:
            st.info("No hay clientes guardados en la base de datos.")
    else:
        st.error("No hay conexión con Firebase.")

# Pestaña: Buscar Clientes
with tab3:
    st.header("Buscar Clientes")
    
    if conexion_exitosa:
        # Campo de búsqueda
        col_busq1, col_busq2 = st.columns([3, 1])
        with col_busq1:
            busqueda = st.text_input("Buscar por nombre, empresa, email o ciudad:")
        
        with col_busq2:
            filtro_categoria = st.selectbox(
                "Filtrar por categoría",
                options=["Todos", "Potencial", "Activo", "Inactivo", "Prioritario", "Otro"]
            )
        
        if busqueda or filtro_categoria != "Todos":
            try:
                # Búsqueda en Firebase
                # Nota: Firestore no permite búsquedas de texto completo de forma nativa
                # Esta es una implementación simple que recupera todos los documentos y filtra localmente
                
                clientes = obtener_clientes()
                resultados = []
                
                for cliente in clientes:
                    # Aplicar filtro de búsqueda de texto
                    coincide_texto = not busqueda or (
                        busqueda.lower() in cliente.get("nombre", "").lower() or
                        busqueda.lower() in cliente.get("empresa", "").lower() or
                        busqueda.lower() in cliente.get("email", "").lower() or
                        busqueda.lower() in cliente.get("ciudad", "").lower()
                    )
                    
                    # Aplicar filtro de categoría
                    coincide_categoria = filtro_categoria == "Todos" or cliente.get("categoria") == filtro_categoria
                    
                    # Si cumple ambos filtros, añadir a resultados
                    if coincide_texto and coincide_categoria:
                        resultados.append(cliente)
                
                if resultados:
                    st.write(f"Se encontraron {len(resultados)} resultados:")
                    
                    for cliente in resultados:
                        with st.container():
                            col1, col2 = st.columns([2, 1])
                            
                            with col1:
                                st.subheader(f"{cliente.get('nombre')} - {cliente.get('empresa')}")
                                st.write(f"📧 {cliente.get('email', 'N/A')} | 📞 {cliente.get('telefono', 'N/A')}")
                                
                            with col2:
                                st.write(f"🏷️ {cliente.get('categoria', 'N/A')}")
                                st.write(f"🏙️ {cliente.get('ciudad', 'N/A')}, {cliente.get('pais', 'N/A')}")
                            
                            # Mostrar capacitaciones si existen (resumidas)
                            if "capacitaciones" in cliente and cliente["capacitaciones"]:
                                st.write(f"🎓 {len(cliente['capacitaciones'])} capacitaciones registradas")
                            
                            # Mostrar archivos si existen (resumidos)
                            if "archivos" in cliente and cliente["archivos"]:
                                st.write(f"📁 {len(cliente['archivos'])} archivos adjuntos")
                                
                            # Botón para ver detalles completos
                            if st.button(f"Ver detalles completos", key=f"ver_{cliente['id']}"):
                                # Redireccionar a la pestaña de detalles
                                st.session_state.cliente_seleccionado = cliente["id"]
                                st.experimental_rerun()
                            
                            st.divider()
                else:
                    st.info("No se encontraron clientes que coincidan con los criterios de búsqueda.")
            
            except Exception as e:
                st.error(f"Error en la búsqueda: {e}")
    else:
        st.error("No hay conexión con Firebase.")

# Pestaña: Registrar Capacitación
with tab4:
    st.header("Registrar Capacitación")
    
    if conexion_exitosa:
        # Obtener la lista de clientes
        clientes = obtener_clientes()
        
        if not clientes:
            st.info("No hay clientes registrados para asignar capacitaciones.")
        else:
            # Formulario para registrar capacitación
            with st.form(key="capacitacion_form"):
                # Selector de cliente
                cliente_id = st.selectbox(
                    "Seleccionar cliente:",
                    options=[c["id"] for c in clientes],
                    format_func=lambda x: f"{next((c['nombre'] for c in clientes if c['id'] == x), '')} - {next((c['empresa'] for c in clientes if c['id'] == x), '')}"
                )
                
                # Mostrar información del cliente seleccionado
                if cliente_id:
                    cliente = next((c for c in clientes if c["id"] == cliente_id), None)
                    if cliente:
                        st.write(f"Empresa: {cliente.get('empresa', 'N/A')}")
                        st.write(f"Email: {cliente.get('email', 'N/A')}")
                        st.write(f"Teléfono: {cliente.get('telefono', 'N/A')}")
                
                # Campos de la capacitación
                st.subheader("Información de la capacitación")
                
                nombre_capacitacion = st.text_input("Nombre de la capacitación")
                
                col1, col2 = st.columns(2)
                with col1:
                    fecha_capacitacion = st.date_input("Fecha de la capacitación", datetime.now())
                    
                with col2:
                    estado_capacitacion = st.selectbox(
                        "Estado",
                        options=["Completada", "En progreso", "Pendiente", "Cancelada"]
                    )
                
                col3, col4 = st.columns(2)
                with col3:
                    instructor = st.text_input("Instructor/Responsable")
                    
                with col4:
                    ubicacion = st.text_input("Ubicación/Modalidad")
                
                detalles_capacitacion = st.text_area("Detalles de la capacitación")
                
                # Botón para guardar
                submit_button = st.form_submit_button("Registrar capacitación")
                
                if submit_button:
                    if not nombre_capacitacion:
                        st.error("El nombre de la capacitación es obligatorio.")
                    else:
                        try:
                            # Preparar datos de la capacitación
                            capacitacion = {
                                "nombre": nombre_capacitacion,
                                "fecha": fecha_capacitacion.strftime("%d/%m/%Y"),
                                "estado": estado_capacitacion,
                                "instructor": instructor,
                                "ubicacion": ubicacion,
                                "detalles": detalles_capacitacion,
                                "fecha_registro": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                            }
                            
                            # Obtener referencia al documento del cliente
                            doc_ref = db.collection("clientes").document(cliente_id)
                            
                            # Obtener el documento actual
                            doc = doc_ref.get()
                            
                            if doc.exists:
                                # Verificar si ya tiene capacitaciones
                                cliente_data = doc.to_dict()
                                capacitaciones = cliente_data.get("capacitaciones", [])
                                
                                # Añadir la nueva capacitación
                                capacitaciones.append(capacitacion)
                                
                                # Actualizar el documento en Firestore
                                doc_ref.update({"capacitaciones": capacitaciones})
                                
                                st.success(f"Capacitación registrada exitosamente para {cliente.get('nombre')} de {cliente.get('empresa')}!")
                                # Redirigir o limpiar el formulario
                                st.experimental_rerun()
                            else:
                                st.error("No se pudo encontrar el cliente seleccionado.")
                        
                        except Exception as e:
                            st.error(f"Error al registrar la capacitación: {e}")
            
            # Sección para ver capacitaciones por cliente
            with st.expander("Ver capacitaciones por cliente"):
                cliente_ver_id = st.selectbox(
                    "Seleccionar cliente para ver capacitaciones:",
                    options=[c["id"] for c in clientes],
                    format_func=lambda x: f"{next((c['nombre'] for c in clientes if c['id'] == x), '')} - {next((c['empresa'] for c in clientes if c['id'] == x), '')}",
                    key="ver_capacitaciones"
                )
                
                if cliente_ver_id:
                    # Obtener el cliente actualizado de Firestore para tener datos actualizados
                    try:
                        doc = db.collection("clientes").document(cliente_ver_id).get()
                        if doc.exists:
                            cliente_data = doc.to_dict()
                            cliente_data["id"] = doc.id
                            
                            if "capacitaciones" in cliente_data and cliente_data["capacitaciones"]:
                                st.subheader(f"Capacitaciones de {cliente_data.get('nombre')} ({cliente_data.get('empresa')})")
                                
                                # Asegurarse de que las capacitaciones son una lista
                                capacitaciones = cliente_data["capacitaciones"]
                                if not isinstance(capacitaciones, list):
                                    st.error("Error: El formato de capacitaciones no es válido.")
                                    capacitaciones = []  # Crear una lista vacía para evitar errores
                                
                                for i, cap in enumerate(capacitaciones):
                                    try:
                                        with st.container():
                                            col1, col2, col3 = st.columns([3, 2, 1])
                                            
                                            with col1:
                                                st.write(f"**{cap.get('nombre', 'Sin nombre')}**")
                                                detalles = cap.get('detalles', '')
                                                if detalles:
                                                    st.write(detalles)
                                                instructor = cap.get('instructor', '')
                                                if instructor:
                                                    st.write(f"Instructor: {instructor}")
                                                ubicacion = cap.get('ubicacion', '')
                                                if ubicacion:
                                                    st.write(f"Ubicación: {ubicacion}")
                                            
                                            with col2:
                                                st.write(f"Fecha: {cap.get('fecha', 'N/A')}")
                                            
                                            with col3:
                                                estado_color = {
                                                    "Completada": "green",
                                                    "En progreso": "blue",
                                                    "Pendiente": "orange",
                                                    "Cancelada": "red"
                                                }
                                                estado = cap.get('estado', 'N/A')
                                                color = estado_color.get(estado, "gray")
                                                st.markdown(f"<span style='color:{color};font-weight:bold'>{estado}</span>", unsafe_allow_html=True)
                                            
                                            # Opción para eliminar capacitación específica
                                            if st.button("Eliminar esta capacitación", key=f"del_cap_{i}"):
                                                try:
                                                    # Eliminar esta capacitación específica
                                                    nuevas_capacitaciones = capacitaciones.copy()
                                                    nuevas_capacitaciones.pop(i)
                                                    
                                                    # Actualizar documento
                                                    db.collection("clientes").document(cliente_ver_id).update({
                                                        "capacitaciones": nuevas_capacitaciones
                                                    })
                                                    
                                                    st.success("Capacitación eliminada correctamente")
                                                    st.experimental_rerun()
                                                except Exception as e:
                                                    st.error(f"Error al eliminar capacitación: {e}")
                                            
                                            st.divider()
                                    except Exception as e:
                                        st.error(f"Error al mostrar capacitación {i+1}: {e}")
                                        st.divider()
                            else:
                                st.info(f"{cliente_data.get('nombre')} ({cliente_data.get('empresa')}) no tiene capacitaciones registradas.")
                    except Exception as e:
                        st.error(f"Error al obtener capacitaciones: {e}")
    else:
        st.error("No hay conexión con Firebase.")

# Pestaña: Gestionar Archivos
with tab5:
    st.header("Gestionar Archivos PDF")
    
    if conexion_exitosa:
        # Obtener la lista de clientes
        clientes = obtener_clientes()
        
        if not clientes:
            st.info("No hay clientes registrados para gestionar archivos.")
        else:
            # Subir nuevos archivos
            st.subheader("Subir nuevo archivo PDF")
            
            # Formulario para subir archivo
            with st.form(key="archivo_form"):
                # Selector de cliente
                cliente_id = st.selectbox(
                    "Seleccionar cliente:",
                    options=[c["id"] for c in clientes],
                    format_func=lambda x: f"{next((c['nombre'] for c in clientes if c['id'] == x), '')} - {next((c['empresa'] for c in clientes if c['id'] == x), '')}",
                    key="subir_archivo_cliente"
                )
                
                # Mostrar información del cliente seleccionado
                if cliente_id:
                    cliente = next((c for c in clientes if c["id"] == cliente_id), None)
                    if cliente:
                        st.write(f"Empresa: {cliente.get('empresa', 'N/A')}")
                
                # Campos para el archivo
                archivo_pdf = st.file_uploader("Seleccionar archivo PDF", type="pdf")
                descripcion_archivo = st.text_area("Descripción del archivo")
                
                # Botón para subir
                submit_button = st.form_submit_button("Subir archivo")
                
                if submit_button:
                    if not archivo_pdf:
                        st.error("Debes seleccionar un archivo PDF para subir.")
                    elif not cliente_id:
                        st.error("Debes seleccionar un cliente.")
                    else:
                        # Intentar subir el archivo
                        exito, mensaje = subir_archivo(cliente_id, archivo_pdf, descripcion_archivo)
                        
                        if exito:
                            st.success(mensaje)
                            st.experimental_rerun()
                        else:
                            st.error(mensaje)
            
            # Gestionar archivos existentes
            st.subheader("Gestionar archivos existentes")
            
            cliente_ver_id = st.selectbox(
                "Seleccionar cliente para ver archivos:",
                options=[c["id"] for c in clientes],
                format_func=lambda x: f"{next((c['nombre'] for c in clientes if c['id'] == x), '')} - {next((c['empresa'] for c in clientes if c['id'] == x), '')}",
                key="ver_archivos"
            )
            
            if cliente_ver_id:
                # Obtener el cliente actualizado de Firestore para tener datos actualizados
                try:
                    doc = db.collection("clientes").document(cliente_ver_id).get()
                    if doc.exists:
                        cliente_data = doc.to_dict()
                        cliente_data["id"] = doc.id
                        
                        if "archivos" in cliente_data and cliente_data["archivos"]:
                            st.write(f"Archivos de {cliente_data.get('nombre')} ({cliente_data.get('empresa')})")
                            
                            for i, archivo in enumerate(cliente_data["archivos"]):
                                with st.container():
                                    col1, col2, col3 = st.columns([3, 2, 1])
                                    
                                    with col1:
                                        st.write(f"**{archivo.get('nombre', 'Sin nombre')}**")
                                        st.write(f"Descripción: {archivo.get('descripcion', 'Sin descripción')}")
                                    
                                    with col2:
                                        if archivo.get('fecha_subida') and isinstance(archivo.get('fecha_subida'), datetime):
                                            st.write(f"Subido: {archivo.get('fecha_subida').strftime('%d/%m/%Y %H:%M')}")
                                    
                                    with col3:
                                        if archivo.get('url'):
                                            st.markdown(f"[Descargar PDF]({archivo.get('url')})")
                                            
                                    # Vista previa del PDF (si es posible) o ícono
                                    if archivo.get('url'):
                                        st.components.v1.iframe(archivo.get('url'), height=200)
                                    
                                    # Botón para eliminar archivo
                                    if st.button("Eliminar este archivo", key=f"del_archivo_{i}"):
                                        exito, mensaje = eliminar_archivo(cliente_ver_id, i)
                                        if exito:
                                            st.success(mensaje)
                                            st.experimental_rerun()
                                        else:
                                            st.error(mensaje)
                                    
                                    st.divider()
                        else:
                            st.info(f"{cliente_data.get('nombre')} ({cliente_data.get('empresa')}) no tiene archivos adjuntos.")
                except Exception as e:
                    st.error(f"Error al obtener archivos: {e}")
    else:
        st.error("No hay conexión con Firebase.")

# Información adicional
with st.sidebar:
    st.title("Información")
    st.info("""
    ## Gestor de Clientes con Firebase
    
    Esta aplicación permite:
    
    - Agregar clientes a Firebase
    - Ver la lista de clientes
    - Buscar clientes por nombre, empresa, email o ciudad
    - Registrar capacitaciones para clientes
    - Gestionar archivos PDF por cliente
    - Eliminar clientes, capacitaciones o archivos
    
    Los datos se almacenan en Firestore (base de datos de Firebase).
    Los archivos PDF se almacenan en Firebase Storage.
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
