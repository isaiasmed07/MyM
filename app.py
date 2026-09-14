import datetime
import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# 1. Cargar variables de entorno
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    st.error("❌ No se encontró DATABASE_URL en el archivo .env")
    st.stop()

# 2. Configurar SQLAlchemy
Base = declarative_base()


class Producto(Base):
    __tablename__ = "productos"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), unique=True, nullable=False)
    unidad_medida = Column(String(20), nullable=False)
    compras = relationship("Compra", back_populates="producto")


class Compra(Base):
    __tablename__ = "compras"
    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    cantidad = Column(Numeric(10, 2), nullable=False)
    unidad_usada = Column(String(20), nullable=False)
    costo_total = Column(Numeric(10, 2), nullable=False)
    producto = relationship("Producto", back_populates="compras")


@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)


engine = get_engine()
SessionLocal = sessionmaker(bind=engine)

# 3. Interfaz de Streamlit
st.set_page_config(
    page_title="Control de Compras - Lácteos",
    page_icon="🧀",
    layout="centered"
)

st.title("🧀 Control de Compras de Lácteos")

session = SessionLocal()

# --- FORMULARIO: NUEVO PRODUCTO ---
with st.expander("➕ Crear Nuevo Producto (Haz clic aquí si no existe en la lista)"):
    with st.form("form_nuevo_producto", clear_on_submit=True):
        nuevo_nombre = st.text_input(
            "Nombre del Producto", placeholder="Ej: Cuajada"
        )
        nueva_unidad = st.selectbox(
            "Unidad de Medida por Defecto", ["Libras", "Unidades", "Litros"]
        )
        btn_crear_prod = st.form_submit_button("Guardar Producto")

        if btn_crear_prod:
            nombre_limpio = nuevo_nombre.strip().capitalize()
            if nombre_limpio:
                try:
                    prod = Producto(
                        nombre=nombre_limpio,
                        unidad_medida=nueva_unidad
                    )
                    session.add(prod)
                    session.commit()
                    st.success(f"✅ Producto '{nombre_limpio}' registrado.")
                    st.rerun()
                except Exception:
                    session.rollback()
                    st.error("⚠️ El producto ya existe o falló la conexión.")
            else:
                st.warning("⚠️ Escribe un nombre válido.")

# --- FORMULARIO: REGISTRO DE COMPRA ---
st.subheader("📝 Registrar Nueva Compra")

productos_db = session.query(Producto).order_by(Producto.nombre).all()
opciones_productos = {p.nombre: p for p in productos_db}

if not opciones_productos:
    st.info("No hay productos registrados. Agrega uno en la sección de arriba.")
else:
    with st.form("form_compra", clear_on_submit=True):
        # Fecha
        fecha_compra = st.date_input("Fecha de Compra", value=datetime.date.today())

        # Producto
        prod_seleccionado = st.selectbox(
            "Seleccionar Producto", list(opciones_productos.keys())
        )
        prod_obj = opciones_productos[prod_seleccionado]

        col1, col2 = st.columns(2)

        # Cantidad y Unidad
        with col1:
            cantidad = st.number_input(
                "Cantidad Comprada", min_value=0.01, step=1.0, format="%.2f"
            )

        with col2:
            idx_default = 0 if prod_obj.unidad_medida == "Libras" else 1
            unidad = st.selectbox(
                "Unidad",
                ["Libras", "Unidades", "Litros"],
                index=idx_default
            )

        # Costo Total
        costo_total = st.number_input(
            "Costo Total ($)", min_value=0.01, step=1.0, format="%.2f"
        )

        btn_guardar = st.form_submit_button("💾 Guardar Compra")

        if btn_guardar:
            try:
                nueva_compra = Compra(
                    producto_id=prod_obj.id,
                    fecha=fecha_compra,
                    cantidad=cantidad,
                    unidad_usada=unidad,
                    costo_total=costo_total,
                )
                session.add(nueva_compra)
                session.commit()
                st.success(
                    f"✅ Registrado: {cantidad} {unidad} de {prod_obj.nombre} por ${costo_total:.2f}"
                )
                st.rerun()
            except Exception as e:
                session.rollback()
                st.error(f"Error al guardar la compra: {e}")

# --- HISTORIAL DE COMPRAS ---
st.markdown("---")
st.subheader("📊 Historial Reciente")

compras_query = (
    session.query(
        Compra.fecha,
        Producto.nombre,
        Compra.cantidad,
        Compra.unidad_usada,
        Compra.costo_total,
    )
    .join(Producto)
    .order_by(Compra.fecha.desc(), Compra.id.desc())
    .limit(10)
    .all()
)

if compras_query:
    df = pd.DataFrame(
        compras_query,
        columns=["Fecha", "Producto", "Cantidad", "Unidad", "Costo Total ($)"],
    )
    st.dataframe(df, use_container_width=True)

session.close()