import os
import streamlit as st
import pandas as pd
import bcrypt
from datetime import date
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

load_dotenv()

# --- CONEXIÓN BASE DE DATOS ---
DATABASE_URL = os.getenv("DATABASE_URL")

@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)

engine = get_engine()
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# --- MODELOS ---
class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False) # 'Admin' o 'Usuario'

class Producto(Base):
    __tablename__ = 'productos'
    id = Column(Integer, primary_key=True)
    nombre = Column(String, unique=True, nullable=False)
    compras = relationship("Compra", back_populates="producto", cascade="all, delete-orphan")

class Compra(Base):
    __tablename__ = 'compras'
    id = Column(Integer, primary_key=True)
    fecha = Column(Date, nullable=False)
    producto_id = Column(Integer, ForeignKey('productos.id'), nullable=False)
    cantidad = Column(Float, nullable=False)
    unidad = Column(String, nullable=False)
    costo_total = Column(Float, nullable=False)
    producto = relationship("Producto", back_populates="compras")

Base.metadata.create_all(bind=engine)

# --- FUNCIONES DE SEGURIDAD Y SEMBRADO ---
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def seed_users():
    """Crea los usuarios iniciales si la tabla de usuarios está vacía."""
    with SessionLocal() as db:
        if db.query(Usuario).count() == 0:
            admin_user = Usuario(
                username="admin",
                password_hash=hash_password("admin123"),
                role="Admin"
            )
            standard_user = Usuario(
                username="usuario",
                password_hash=hash_password("user123"),
                role="Usuario"
            )
            db.add_all([admin_user, standard_user])
            db.commit()

seed_users()

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control de Compras - Lácteos", page_icon="🧀", layout="centered")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.session_state.username = None

def login():
    st.title("🔐 Iniciar Sesión")
    with st.form("login_form"):
        user_input = st.text_input("Usuario").strip().lower()
        pass_input = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Ingresar", type="primary", use_container_width=True)
        
        if submit:
            with SessionLocal() as db:
                usuario_db = db.query(Usuario).filter(Usuario.username == user_input).first()
                if usuario_db and check_password(pass_input, usuario_db.password_hash):
                    st.session_state.logged_in = True
                    st.session_state.user_role = usuario_db.role
                    st.session_state.username = usuario_db.username
                    st.toast(f"¡Bienvenido, {usuario_db.username}!", icon="👋")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")

def logout():
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.session_state.username = None
    st.rerun()

if not st.session_state.logged_in:
    login()
    st.stop()

# --- BARRA LATERAL (SESIÓN) ---
with st.sidebar:
    st.write(f"👤 **Usuario:** {st.session_state.username.capitalize()}")
    st.write(f"🔑 **Rol:** {st.session_state.user_role}")
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        logout()

st.title("🧀 Control de Compras de Lácteos")

if st.session_state.user_role == "Admin":
    tab_registrar, tab_historial, tab_productos, tab_usuarios = st.tabs(["📝 Registrar Compra", "📊 Historial / Editar", "🏷️ Productos", "👥 Usuarios"])
else:
    tab_registrar, tab_historial = st.tabs(["📝 Registrar Compra", "📊 Historial Completo"])

# ==========================================
# PESTAÑA 1: REGISTRAR COMPRA
# ==========================================
with tab_registrar:
    with SessionLocal() as db_session:
        productos_db = db_session.query(Producto).order_by(Producto.nombre).all()
        opciones_productos = {p.nombre: p.id for p in productos_db}

    if not opciones_productos:
        st.info("No hay productos registrados aún. Un Administrador debe crearlos en la pestaña '🏷️ Productos'.")
    else:
        st.subheader("📝 Registrar Nueva Compra")
        fecha_compra = st.date_input("Fecha de Compra", value=date.today(), key="reg_fecha")
        producto_sel = st.selectbox("Seleccionar Producto", options=list(opciones_productos.keys()), index=None, placeholder="Elige un producto...", key="reg_prod")
        
        col1, col2 = st.columns(2)
        with col1:
            cantidad = st.number_input("Cantidad Comprada", min_value=0.0, value=0.0, step=0.5, key="reg_cant")
        with col2:
            unidad = st.selectbox("Unidad", options=["Libras", "Kilos", "Unidades", "Bloques", "Litros"], key="reg_uni")

        costo_total = st.number_input("Costo Total ($)", min_value=0.0, value=0.0, step=1.0, key="reg_costo")

        st.write("")
        with st.popover("💾 Guardar Compra", use_container_width=True):
            st.markdown("**¿Confirmar el registro de la compra?**")
            st.write(f"- **Producto:** {producto_sel}")
            st.write(f"- **Cantidad:** {cantidad} {unidad}")
            st.write(f"- **Total:** ${costo_total:.2f}")
            
            if st.button("Sí, Confirmar y Guardar", type="primary", use_container_width=True, key="btn_save_reg"):
                if not producto_sel:
                    st.error("Por favor selecciona un producto.")
                elif cantidad <= 0 or costo_total <= 0:
                    st.error("La cantidad y el costo deben ser mayores a 0.")
                else:
                    with SessionLocal() as db_session:
                        nueva_compra = Compra(
                            fecha=fecha_compra,
                            producto_id=opciones_productos[producto_sel],
                            cantidad=cantidad,
                            unidad=unidad,
                            costo_total=costo_total
                        )
                        db_session.add(nueva_compra)
                        db_session.commit()
                    st.toast("¡Compra guardada con éxito!", icon="✅")
                    st.rerun()

# ==========================================
# PESTAÑA 2: HISTORIAL COMPLETO Y EDICIÓN
# ==========================================
with tab_historial:
    st.subheader("📊 Historial de Compras")
    
    with SessionLocal() as db_session:
        registros = (
            db_session.query(Compra)
            .join(Producto, Compra.producto_id == Producto.id)
            .order_by(Compra.fecha.desc(), Compra.id.desc())
            .all()
        )
        
        productos_list = db_session.query(Producto).order_by(Producto.nombre).all()
        dict_prod_id = {p.nombre: p.id for p in productos_list}

        if registros:
            datos = [{
                "ID": c.id,
                "Fecha": str(c.fecha),
                "Producto": c.producto.nombre,
                "Cantidad": c.cantidad,
                "Unidad": c.unidad,
                "Costo Total ($)": f"${c.costo_total:.2f}"
            } for c in registros]

            df = pd.DataFrame(datos)
            filtro_prod = st.multiselect("Filtrar por producto:", options=df["Producto"].unique(), key="filter_prod")
            if filtro_prod:
                df = df[df["Producto"].isin(filtro_prod)]

            st.dataframe(df, use_container_width=True, hide_index=True)

            if st.session_state.user_role == "Admin":
                st.markdown("---")
                st.subheader("⚙️ Modificar o Eliminar Registro (Admin)")

                opciones_compras = {f"ID #{c.id} - {c.fecha} - {c.producto.nombre} (${c.costo_total:.2f})": c.id for c in registros}
                compra_sel_label = st.selectbox("Selecciona un registro para editar o borrar:", options=list(opciones_compras.keys()), index=None, placeholder="Elige un registro...")

                if compra_sel_label:
                    compra_id = opciones_compras[compra_sel_label]
                    compra_obj = db_session.query(Compra).get(compra_id)

                    if compra_obj:
                        with st.expander("✏️ Editar Registro", expanded=True):
                            edit_fecha = st.date_input("Fecha", value=compra_obj.fecha, key=f"edit_f_{compra_id}")
                            edit_prod_nombre = st.selectbox(
                                "Producto", 
                                options=list(dict_prod_id.keys()), 
                                index=list(dict_prod_id.keys()).index(compra_obj.producto.nombre),
                                key=f"edit_p_{compra_id}"
                            )
                            
                            col_e1, col_e2 = st.columns(2)
                            with col_e1:
                                edit_cant = st.number_input("Cantidad", min_value=0.0, value=float(compra_obj.cantidad), step=0.5, key=f"edit_c_{compra_id}")
                            with col_e2:
                                unidades_lista = ["Libras", "Kilos", "Unidades", "Bloques", "Litros"]
                                edit_uni = st.selectbox("Unidad", options=unidades_lista, index=unidades_lista.index(compra_obj.unidad) if compra_obj.unidad in unidades_lista else 0, key=f"edit_u_{compra_id}")
                            
                            edit_costo = st.number_input("Costo Total ($)", min_value=0.0, value=float(compra_obj.costo_total), step=1.0, key=f"edit_cost_{compra_id}")

                            col_btn1, col_btn2 = st.columns([1, 1])
                            with col_btn1:
                                if st.button("💾 Actualizar Registro", type="primary", use_container_width=True, key=f"btn_upd_{compra_id}"):
                                    compra_obj.fecha = edit_fecha
                                    compra_obj.producto_id = dict_prod_id[edit_prod_nombre]
                                    compra_obj.cantidad = edit_cant
                                    compra_obj.unidad = edit_uni
                                    compra_obj.costo_total = edit_costo
                                    db_session.commit()
                                    st.toast("¡Registro actualizado correctamente!", icon="✏️")
                                    st.rerun()
                            
                            with col_btn2:
                                with st.popover("🗑️ Eliminar Registro", use_container_width=True):
                                    st.warning(f"¿Seguro que deseas eliminar la compra ID #{compra_id}?")
                                    if st.button("Sí, Eliminar Definitivamente", type="primary", use_container_width=True, key=f"btn_del_{compra_id}"):
                                        db_session.delete(compra_obj)
                                        db_session.commit()
                                        st.toast("Registro eliminado.", icon="🗑️")
                                        st.rerun()
        else:
            st.info("Aún no hay compras registradas en el historial.")

# ==========================================
# PESTAÑA 3: PRODUCTOS (SOLO ADMIN)
# ==========================================
if st.session_state.user_role == "Admin":
    with tab_productos:
        st.subheader("🏷️ Administración de Productos (Admin)")
        
        with SessionLocal() as db_session:
            with st.form("form_nuevo_prod", clear_on_submit=True):
                n_nombre = st.text_input("Nombre del Nuevo Producto")
                if st.form_submit_button("➕ Crear Producto"):
                    if n_nombre.strip():
                        prod_existente = db_session.query(Producto).filter(Producto.nombre.ilike(n_nombre.strip())).first()
                        if prod_existente:
                            st.warning("Este producto ya existe.")
                        else:
                            db_session.add(Producto(nombre=n_nombre.strip()))
                            db_session.commit()
                            st.toast(f"Producto '{n_nombre}' creado con éxito.", icon="✅")
                            st.rerun()
                    else:
                        st.error("Ingresa un nombre válido.")

            st.markdown("---")
            prods = db_session.query(Producto).order_by(Producto.nombre).all()
            if prods:
                st.write("**Productos Registrados:**")
                for p in prods:
                    col_p1, col_p2 = st.columns([3, 1])
                    with col_p1:
                        st.write(f"• **{p.nombre}**")
                    with col_p2:
                        with st.popover("🗑️ Borrar", use_container_width=True):
                            st.warning(f"Borrar '{p.nombre}' eliminará también sus compras asociadas.")
                            if st.button("Confirmar", key=f"del_prod_{p.id}", use_container_width=True):
                                db_session.delete(p)
                                db_session.commit()
                                st.toast(f"Producto '{p.nombre}' eliminado.", icon="🗑️")
                                st.rerun()

# ==========================================
# PESTAÑA 4: GESTIÓN DE USUARIOS (SOLO ADMIN)
# ==========================================
    with tab_usuarios:
        st.subheader("👥 Administración de Usuarios")
        
        with SessionLocal() as db_session:
            with st.form("form_nuevo_usuario", clear_on_submit=True):
                st.write("**Crear Nuevo Usuario**")
                new_username = st.text_input("Nombre de Usuario").strip().lower()
                new_password = st.text_input("Contraseña", type="password")
                new_role = st.selectbox("Rol", options=["Usuario", "Admin"])
                
                if st.form_submit_button("➕ Registrar Usuario"):
                    if new_username and new_password:
                        user_exists = db_session.query(Usuario).filter(Usuario.username == new_username).first()
                        if user_exists:
                            st.warning("El usuario ya existe.")
                        else:
                            nuevo_u = Usuario(
                                username=new_username,
                                password_hash=hash_password(new_password),
                                role=new_role
                            )
                            db_session.add(nuevo_u)
                            db_session.commit()
                            st.toast(f"Usuario '{new_username}' registrado correctamente.", icon="✅")
                            st.rerun()
                    else:
                        st.error("Completa todos los campos.")
            
            st.markdown("---")
            st.write("**Usuarios Existentes:**")
            users_list = db_session.query(Usuario).all()
            for u in users_list:
                col_u1, col_u2 = st.columns([3, 1])
                with col_u1:
                    st.write(f"• **{u.username.capitalize()}** ({u.role})")
                with col_u2:
                    if u.username != st.session_state.username: # Prevenir auto-eliminación
                        with st.popover("🗑️ Borrar", use_container_width=True):
                            st.warning(f"¿Eliminar usuario '{u.username}'?")
                            if st.button("Confirmar", key=f"del_user_{u.id}", use_container_width=True):
                                db_session.delete(u)
                                db_session.commit()
                                st.toast(f"Usuario '{u.username}' eliminado.", icon="🗑️")
                                st.rerun()