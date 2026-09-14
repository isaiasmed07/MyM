import os
import streamlit as st
import pandas as pd
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
class Producto(Base):
    __tablename__ = 'productos'
    id = Column(Integer, primary_key=True)
    nombre = Column(String, unique=True, nullable=False)
    compras = relationship("Compra", back_populates="producto")

class Compra(Base):
    __tablename__ = 'compras'
    id = Column(Integer, primary_key=True)
    fecha = Column(Date, nullable=False)
    producto_id = Column(Integer, ForeignKey('productos.id'), nullable=False)
    cantidad = Column(Float, nullable=False)
    unidad = Column(String, nullable=False)
    costo_total = Column(Float, nullable=False)
    producto = relationship("Producto", back_populates="compras")

# --- ACTUALIZACIÓN DE ESTRUCTURA EN PRUEBAS ---
# Para asegurarse de que las tablas se creen con las nuevas columnas
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    st.error(f"Error creando tablas: {e}")

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control de Compras - Lácteos", page_icon="🧀", layout="centered")
st.title("🧀 Control de Compras de Lácteos")

# Botón temporal para reiniciar la base de datos si cambian las columnas
with st.sidebar:
    st.subheader("🛠️ Herramientas de Desarrollo")
    if st.button("⚠️ Recrear Tablas (Borra datos)"):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        st.success("Tablas recreadas con la nueva estructura. Recarga la página.")
        st.rerun()

# --- PESTAÑAS / NAVEGACIÓN ---
tab_registrar, tab_historial = st.tabs(["📝 Registrar Compra", "📊 Historial Completo"])

# ==========================================
# PESTAÑA 1: REGISTRAR COMPRA
# ==========================================
with tab_registrar:
    with SessionLocal() as db_session:
        # 1. Crear Nuevo Producto
        with st.expander("➕ Crear Nuevo Producto (Haz clic aquí si no existe en la lista)"):
            nuevo_prod_nombre = st.text_input("Nombre del Nuevo Producto", key="input_nuevo_prod")
            if st.button("Guardar Producto"):
                if nuevo_prod_nombre.strip():
                    prod_existente = db_session.query(Producto).filter(Producto.nombre.ilike(nuevo_prod_nombre.strip())).first()
                    if prod_existente:
                        st.warning("Este producto ya existe en el sistema.")
                    else:
                        nuevo_p = Producto(nombre=nuevo_prod_nombre.strip())
                        db_session.add(nuevo_p)
                        db_session.commit()
                        st.success(f"¡Producto '{nuevo_prod_nombre}' creado con éxito!")
                        st.rerun()
                else:
                    st.error("Escribe un nombre válido para el producto.")

        st.subheader("📝 Registrar Nueva Compra")
        
        productos_db = db_session.query(Producto).order_by(Producto.nombre).all()
        opciones_productos = {p.nombre: p.id for p in productos_db}

    if not opciones_productos:
        st.info("No hay productos registrados aún. Crea uno arriba para empezar.")
    else:
        fecha_compra = st.date_input("Fecha de Compra", value=date.today())
        producto_sel = st.selectbox("Seleccionar Producto", options=list(opciones_productos.keys()), index=None, placeholder="Elige un producto...")
        
        col1, col2 = st.columns(2)
        with col1:
            cantidad = st.number_input("Cantidad Comprada", min_value=0.0, value=0.0, step=0.5)
        with col2:
            unidad = st.selectbox("Unidad", options=["Libras", "Kilos", "Unidades", "Bloques", "Litros"])

        costo_total = st.number_input("Costo Total ($)", min_value=0.0, value=0.0, step=1.0)

        st.write("")
        with st.popover("💾 Guardar Compra", use_container_width=True):
            st.markdown("**¿Confirmar el registro de la compra?**")
            st.write(f"- **Producto:** {producto_sel}")
            st.write(f"- **Cantidad:** {cantidad} {unidad}")
            st.write(f"- **Total:** ${costo_total:.2f}")
            
            if st.button("Sí, Confirmar y Guardar", type="primary", use_container_width=True):
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
# PESTAÑA 2: HISTORIAL COMPLETO
# ==========================================
with tab_historial:
    st.subheader("📊 Historial de Compras")
    
    try:
        with SessionLocal() as db_session:
            query = text("""
                SELECT c.id, c.fecha, p.nombre AS producto, c.cantidad, c.unidad, c.costo_total 
                FROM compras c
                JOIN productos p ON c.producto_id = p.id
                ORDER BY c.fecha DESC, c.id DESC
            """)
            result = db_session.execute(query).fetchall()

            datos = [{
                "ID": row.id,
                "Fecha": str(row.fecha),
                "Producto": row.producto,
                "Cantidad": row.cantidad,
                "Unidad": row.unidad,
                "Costo Total ($)": f"${row.costo_total:.2f}"
            } for row in result]

        if datos:
            df = pd.DataFrame(datos)
            filtro_prod = st.multiselect("Filtrar por producto:", options=df["Producto"].unique())
            if filtro_prod:
                df = df[df["Producto"].isin(filtro_prod)]

            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay compras registradas en el historial.")
    except Exception as err:
        st.error(f"Error al cargar el historial de compras: {err}")