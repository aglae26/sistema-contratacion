import enum
# pyrefly: ignore [missing-import]
from sqlalchemy import Column, Integer, String, ForeignKey, Date, Numeric, Boolean, Enum, ForeignKey
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import relationship
from database import Base 

# 1. Definimos los estados permitidos como un Enum nativo de Python
class EstadoEmpleado(str, enum.Enum):
    REGISTRADO = "REGISTRADO"
    EN_REVISION = "EN_REVISION"
    APROBADO = "APROBADO"
    CONTRATADO = "CONTRATADO"

class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, index=True)
    nit = Column(String(20), unique=True, nullable=False, index=True)
    razon_social = Column(String(150), nullable=False)

    sedes = relationship("Sede", back_populates="empresa", cascade="all, delete-orphan")
    
    contratos = relationship("Contrato", back_populates="empresa")


class Empleado(Base):
    __tablename__ = "empleados"

    id = Column(Integer, primary_key=True, index=True)
    nombres = Column(String(100), nullable=False)
    apellidos = Column(String(100), nullable=False)
    tipo_documento = Column(String(50), nullable=False) 
    numero_documento = Column(String(20), unique=True, nullable=False, index=True)
    fecha_nacimiento = Column(Date, nullable=True)
    lugar_expedicion = Column(String(100), nullable=True)
    direccion_residencia = Column(String(200), nullable=True) 
    telefono = Column(String(20), nullable=True)

    # Relación con la tabla Contrato
    contratos = relationship("Contrato", back_populates="empleado", cascade="all, delete-orphan")

    estado = Column(
        Enum(EstadoEmpleado, name="estado_empleado_enum", create_type=True), 
        default=EstadoEmpleado.REGISTRADO, 
        nullable=False
    )


class Contrato(Base):
    __tablename__ = "contratos"

    id = Column(Integer, primary_key=True, index=True)
    
    # Datos del Contrato / Tipo de contrato
    tipo_contrato = Column(String(50), nullable=False) # 'INDEFINIDO', 'FIJO', 'TIEMPO_PARCIAL'
    cargo_desempenar = Column(String(100), nullable=False)
    fecha_inicio_labores = Column(Date, nullable=False)
    fecha_finalizacion_labores = Column(Date, nullable=True) # Nullable porque el Indefinido no tiene fin
    
    # Remuneración (Tus dos modalidades detectadas)
    salario_numeros = Column(Numeric(12, 2), nullable=False) # El valor numérico base
    salario_letras = Column(String(200), nullable=False)     # Texto traducido para la cláusula cuarta
    pago_por_kilo = Column(Boolean, default=False)           # True si aplica "por kilo clasificado"
    remuneracion_valor_kilo = Column(String(50), nullable=True) # Texto descriptivo si aplica por kilo
    forma_pago = Column(String(50), default="QUINCENAL")

    # Ubicación y Logística (Exigidos por Fijos y Parciales)
    sede_trabajo = Column(String(150), nullable=False)
    ciudad = Column(String(100), nullable=True)
    departamento = Column(String(100), nullable=True)
    funciones_especificas = Column(String(1000), nullable=True) # Para la cláusula segunda de tiempo parcial

    # Periodo de Prueba
    aplica_periodo_prueba = Column(Boolean, default=False)
    duracion_periodo_prueba = Column(String(50), default="No aplica") # Ej: "18 DÍAS"

    # Datos del cierre / Firma
    dia_firma = Column(String(5), nullable=False)
    mes_firma = Column(String(20), nullable=False)
    anio_firma = Column(String(5), nullable=False)

    # Llaves Foráneas
    empleado_id = Column(Integer, ForeignKey("empleados.id", ondelete="CASCADE"))
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="RESTRICT"))

    # Relaciones
    empleado = relationship("Empleado", back_populates="contratos")
    empresa = relationship("Empresa", back_populates="contratos")

class Sede(Base):
    __tablename__ = "sedes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)      # Ej: "Planta Principal", "Bodega Sur", "Finca La María"
    direccion = Column(String(200), nullable=False)   # La dirección exacta de esa sede
    ciudad = Column(String(100), nullable=True)
    departamento = Column(String(100), nullable=True)

    # Llave foránea para saber a qué empresa pertenece esta sede
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="CASCADE"))
    
    # Relación inversa corregida con back_populates exacto 
    empresa = relationship("Empresa", back_populates="sedes")