import enum
from datetime import datetime
from database import Base
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import relationship


# --- ENUMS DEL SISTEMA ---
class TipoEspacio(str, enum.Enum):
  AULA_TEORICA = "Aula Teórica"
  AULA_COMPUTO = "Aula de Cómputo"
  LABORATORIO_TALLER = "Laboratorio / Taller Especializado"
  AUDITORIO = "Auditorio / Sala Audiovisual"


class RolUsuario(str, enum.Enum):
  PRESIDENTE = "Presidente de Academia"
  SOPORTE = "Soporte Técnico / TI"
  ENCARGADO = "Encargado de Laboratorio"
  LABORATORISTA = "Laboratorista"
  PROFESOR = "Profesor"
  ALUMNO = "Alumno"


class EstadoEquipo(str, enum.Enum):
  OPERATIVO = "Operativo"
  EN_MANTENIMIENTO = "En Mantenimiento"
  FUERA_DE_SERVICIO = "Fuera de Servicio"
  PRESTADO = "Prestado"
  DADO_DE_BAJA = "Dado de Baja"


class PrioridadTicket(str, enum.Enum):
  BAJA = "Baja"
  MEDIA = "Media"
  ALTA = "Alta/Paro de Práctica"


class EstatusTicket(str, enum.Enum):
  ABIERTO = "Abierto"
  EN_REVISION = "En Revisión por Encargado"
  MANTENIMIENTO_AUTORIZADO = "Mantenimiento Autorizado"
  REQUISICION_COMPRA = "Requisición de Compra Generada"
  RESUELTO = "Resuelto"
  CANCELADO = "Cancelado"


class TipoPrestamo(str, enum.Enum):
  EQUIPO = "Equipo Fijo / Herramental"
  ESPACIO_LAB = "Espacio de Laboratorio Completo"


class EstatusPrestamo(str, enum.Enum):
  ACTIVO = "Activo / En Préstamo"
  DEVUELTO = "Devuelto"
  DEVUELTO_CON_INCIDENCIA = "Devuelto con Incidencia"


class TipoRequisicion(str, enum.Enum):
  MANTENIMIENTO_EXTERNO = "Orden de Servicio Técnico / Mantenimiento"
  COMPRA_INSUMO = "Requisición de Compra de Refacción / Insumo"


class EstatusRequisicion(str, enum.Enum):
  SOLICITADA = "Solicitada por Encargado"
  APROBADA = "Aprobada por Presidente"
  RECHAZADA = "Rechazada"
  ATENDIDA = "Atendida / Surtida"


# Nuevos enums de Gestión Colegiada
class EstatusAcuerdo(str, enum.Enum):
  PENDIENTE = "Pendiente"
  EN_PROCESO = "En Proceso"
  CUMPLIDO = "Cumplido"
  CANCELADO = "Cancelado"


class CategoriaEvidencia(str, enum.Enum):
  VISITA_INDUSTRIAL = "Visita Industrial / Estancia"
  PROMOCION_VINCULACION = "Promoción Institucional / Vocacional"
  CONGRESO_SIMPOSIO = "Congreso / Simposio / Ponencia"
  CONCURSO_TORNEO = "Concurso / Torneo de Innovación"
  LOGRO_CERTIFICACION = "Logro Académico / Certificación"
  OTRO = "Otro Evento Colegiado"


class CategoriaEvento(str, enum.Enum):
  JUNTA_ACADEMIA = "Junta de Academia Ordinaria/Extraordinaria"
  EVENTO_ACADEMICO = "Concurso / Congreso / Visita"
  MANTENIMIENTO = "Mantenimiento Mayor de Taller"
  ENTREGA_EVIDENCIA = "Fecha Límite de Evaluaciones/Evidencias"


# --- TABLA INTERMEDIA (N:M): Asignación de Múltiples Laboratorios a Usuarios ---
usuario_laboratorios = Table(
    "usuario_laboratorios",
    Base.metadata,
    Column("usuario_id", Integer, ForeignKey("usuarios.id"), primary_key=True),
    Column(
        "laboratorio_id",
        Integer,
        ForeignKey("laboratorios.id"),
        primary_key=True,
    ),
)


# --- CLASE BASE: AULA (Infraestructura física institucional) ---
class Aula(Base):
  __tablename__ = "aulas"

  id = Column(Integer, primary_key=True, index=True)
  codigo_espacio = Column(String(20), unique=True, nullable=False, index=True)
  edificio = Column(String(50), nullable=False, default="Edificio SIGAO_UTZMG")
  tipo_espacio = Column(
      Enum(TipoEspacio), default=TipoEspacio.AULA_TEORICA, nullable=False
  )
  capacidad_estudiantes = Column(Integer, default=30)
  descripcion = Column(String(255), nullable=True)

  discriminador = Column(String(50))
  __mapper_args__ = {
      "polymorphic_on": discriminador,
      "polymorphic_identity": "aula",
  }


# --- CLASE DERIVADA: LABORATORIO (Hereda de Aula) ---
class Laboratorio(Aula):
  __tablename__ = "laboratorios"

  id = Column(Integer, ForeignKey("aulas.id"), primary_key=True)
  nombre = Column(String(120), nullable=False, unique=True)
  encargado_nombre = Column(String(100), default="Mtro. Jesús Pérez Merlos")

  __mapper_args__ = {
      "polymorphic_identity": "laboratorio",
  }

  encargados = relationship(
      "Usuario",
      secondary=usuario_laboratorios,
      back_populates="laboratorios_asignados",
  )
  equipos = relationship("Equipo", back_populates="laboratorio")
  consumibles = relationship("Consumible", back_populates="laboratorio")
  prestamos = relationship("PrestamoServicio", back_populates="laboratorio")
  requisiciones = relationship("RequisicionLab", back_populates="laboratorio")


# --- USUARIOS Y AUDITORÍA ---
class Usuario(Base):
  __tablename__ = "usuarios"

  id = Column(Integer, primary_key=True, index=True)
  matricula_nomina = Column(String(30), unique=True, nullable=False, index=True)
  nombre_completo = Column(String(120), nullable=False)
  correo = Column(String(100), unique=True, nullable=False)
  password_hash = Column(String(255), nullable=True)  # Nullable para Google SSO
  google_id = Column(
      String(100), unique=True, nullable=True
  )  # Sub identificador de Google
  rol = Column(Enum(RolUsuario), default=RolUsuario.ALUMNO, nullable=False)
  activo = Column(Boolean, default=False)
  fecha_registro = Column(DateTime, default=datetime.utcnow)

  laboratorios_asignados = relationship(
      "Laboratorio",
      secondary=usuario_laboratorios,
      back_populates="encargados",
  )
  tickets_reportados = relationship(
      "TicketIncidencia", back_populates="usuario"
  )
  prestamos = relationship("PrestamoServicio", back_populates="usuario")
  acciones_bitacora = relationship(
      "BitacoraAccion", back_populates="usuario_responsable"
  )
  conexiones = relationship("RegistroConexion", back_populates="usuario")

  # Relaciones con gestión colegiada
  acuerdos_asignados = relationship(
      "AcuerdoMinuta", back_populates="responsable"
  )
  evidencias_subidas = relationship(
      "EvidenciaAcademia", back_populates="docente"
  )


class RegistroConexion(Base):
  __tablename__ = "registro_conexiones"

  id = Column(Integer, primary_key=True, index=True)
  usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
  fecha_hora = Column(DateTime, default=datetime.utcnow)
  ip_origen = Column(String(45), nullable=True)
  user_agent = Column(String(255), nullable=True)
  exitoso = Column(Boolean, default=True)

  usuario = relationship("Usuario", back_populates="conexiones")


class BitacoraAccion(Base):
  __tablename__ = "bitacora_acciones"

  id = Column(Integer, primary_key=True, index=True)
  usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
  fecha_hora = Column(DateTime, default=datetime.utcnow)
  modulo = Column(String(50), nullable=False)
  accion = Column(String(50), nullable=False)
  descripcion = Column(Text, nullable=False)
  ip_origen = Column(String(45), nullable=True)

  usuario_responsable = relationship(
      "Usuario", back_populates="acciones_bitacora"
  )


# --- EQUIPOS, INSUMOS, TICKETS Y PRÉSTAMOS ---
class Equipo(Base):
  __tablename__ = "equipos"

  id_codigo_qr = Column(String(50), primary_key=True, index=True)
  laboratorio_id = Column(Integer, ForeignKey("laboratorios.id"))
  nombre = Column(String(120), nullable=False)
  marca = Column(String(60), nullable=True)
  modelo = Column(String(60), nullable=True)
  num_serie = Column(String(60), nullable=True)
  estatus = Column(
      Enum(EstadoEquipo), default=EstadoEquipo.OPERATIVO, nullable=False
  )
  manual_pdf_url = Column(String(255), nullable=True)
  fecha_baja = Column(DateTime, nullable=True)
  motivo_baja = Column(Text, nullable=True)

  laboratorio = relationship("Laboratorio", back_populates="equipos")
  tickets = relationship("TicketIncidencia", back_populates="equipo")
  mantenimientos = relationship(
      "HistorialMantenimiento", back_populates="equipo"
  )
  prestamos = relationship("PrestamoServicio", back_populates="equipo")
  requisiciones = relationship("RequisicionLab", back_populates="equipo")


class Consumible(Base):
  __tablename__ = "consumibles"

  id_codigo_qr = Column(String(50), primary_key=True, index=True)
  laboratorio_id = Column(Integer, ForeignKey("laboratorios.id"))
  descripcion = Column(String(150), nullable=False)
  categoria = Column(String(60), nullable=True)
  stock_actual = Column(Integer, default=0)
  stock_minimo = Column(Integer, default=5)
  unidad_medida = Column(String(30), default="pza")
  activo = Column(Boolean, default=True)

  laboratorio = relationship("Laboratorio", back_populates="consumibles")
  despachos = relationship("DespachoConsumible", back_populates="consumible")


class DespachoConsumible(Base):
  __tablename__ = "despachos_consumibles"

  id = Column(Integer, primary_key=True, index=True)
  consumible_id = Column(String(50), ForeignKey("consumibles.id_codigo_qr"))
  fecha_hora = Column(DateTime, default=datetime.utcnow)
  cantidad = Column(Integer, nullable=False)
  matricula_solicitante = Column(String(30), nullable=False)
  docente_a_cargo = Column(String(100), nullable=False)

  consumible = relationship("Consumible", back_populates="despachos")


class TicketIncidencia(Base):
  __tablename__ = "tickets_incidencia"

  id = Column(Integer, primary_key=True, index=True)
  equipo_id = Column(String(50), ForeignKey("equipos.id_codigo_qr"))
  usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
  fecha_reporte = Column(DateTime, default=datetime.utcnow)
  matricula_reporta = Column(String(30), nullable=False)
  nombre_reporta = Column(String(100), nullable=False)
  prioridad = Column(
      Enum(PrioridadTicket), default=PrioridadTicket.MEDIA, nullable=False
  )
  descripcion = Column(Text, nullable=False)
  evidencia_multimedia = Column(String(255), nullable=True)
  estatus = Column(
      Enum(EstatusTicket), default=EstatusTicket.ABIERTO, nullable=False
  )
  diagnostico_encargado = Column(Text, nullable=True)

  equipo = relationship("Equipo", back_populates="tickets")
  usuario = relationship("Usuario", back_populates="tickets_reportados")
  requisicion = relationship(
      "RequisicionLab", back_populates="ticket", uselist=False
  )


class HistorialMantenimiento(Base):
  __tablename__ = "historial_mantenimientos"

  id = Column(Integer, primary_key=True, index=True)
  equipo_id = Column(String(50), ForeignKey("equipos.id_codigo_qr"))
  tipo_servicio = Column(String(50))
  fecha_servicio = Column(DateTime, default=datetime.utcnow)
  tecnico_responsable = Column(String(100), nullable=False)
  refacciones = Column(Text, nullable=True)
  observaciones = Column(Text, nullable=False)
  proxima_fecha = Column(DateTime, nullable=True)

  equipo = relationship("Equipo", back_populates="mantenimientos")


class RequisicionLab(Base):
  __tablename__ = "requisiciones_lab"

  id = Column(Integer, primary_key=True, index=True)
  folio = Column(String(30), unique=True, index=True)
  ticket_id = Column(
      Integer, ForeignKey("tickets_incidencia.id"), nullable=True
  )
  laboratorio_id = Column(Integer, ForeignKey("laboratorios.id"))
  equipo_id = Column(
      String(50), ForeignKey("equipos.id_codigo_qr"), nullable=True
  )
  tipo = Column(Enum(TipoRequisicion), nullable=False)
  justificacion = Column(Text, nullable=False)
  especificaciones_tecnicas = Column(Text, nullable=False)
  costo_estimado = Column(Float, nullable=True)
  estatus = Column(
      Enum(EstatusRequisicion),
      default=EstatusRequisicion.SOLICITADA,
      nullable=False,
  )
  encargado_solicita = Column(String(100), nullable=False)
  fecha_solicitud = Column(DateTime, default=datetime.utcnow)
  fecha_autorizacion = Column(DateTime, nullable=True)

  ticket = relationship("TicketIncidencia", back_populates="requisicion")
  laboratorio = relationship("Laboratorio", back_populates="requisiciones")
  equipo = relationship("Equipo", back_populates="requisiciones")


class PrestamoServicio(Base):
  __tablename__ = "prestamos_servicio"

  id = Column(Integer, primary_key=True, index=True)
  tipo = Column(Enum(TipoPrestamo), nullable=False)
  laboratorio_id = Column(Integer, ForeignKey("laboratorios.id"))
  equipo_id = Column(
      String(50), ForeignKey("equipos.id_codigo_qr"), nullable=True
  )
  usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
  rol_solicitante = Column(String(20), nullable=False)
  matricula_numero = Column(String(30), nullable=False)
  nombre_completo = Column(String(120), nullable=False)
  fecha_salida = Column(DateTime, default=datetime.utcnow)
  fecha_devolucion = Column(DateTime, nullable=True)
  estatus = Column(
      Enum(EstatusPrestamo), default=EstatusPrestamo.ACTIVO, nullable=False
  )
  observaciones = Column(Text, nullable=True)

  laboratorio = relationship("Laboratorio", back_populates="prestamos")
  equipo = relationship("Equipo", back_populates="prestamos")
  usuario = relationship("Usuario", back_populates="prestamos")


# --- EJE DE GESTIÓN COLEGIADA Y GOBERNANZA ACADÉMICA ---
class MinutaSesion(Base):
  __tablename__ = "minutas_sesion"

  id = Column(Integer, primary_key=True, index=True)
  folio = Column(String(40), unique=True, index=True)  # Ej. MIN-MEC-2026-09-24
  academia = Column(
      String(100), nullable=False, default="Academia de Mecatrónica"
  )
  periodo_cuatrimestral = Column(String(30), nullable=False)  # Ej. Sep-Dic 2026
  fecha_reunion = Column(Date, nullable=False)
  orden_del_dia = Column(Text, nullable=False)
  desarrollo_acuerdos = Column(Text, nullable=False)
  archivo_acta_firmada_url = Column(String(255), nullable=True)
  presidente_valida = Column(String(120), nullable=False)
  fecha_registro = Column(DateTime, default=datetime.utcnow)

  acuerdos = relationship(
      "AcuerdoMinuta", back_populates="minuta", cascade="all, delete-orphan"
  )


class AcuerdoMinuta(Base):
  __tablename__ = "acuerdos_minuta"

  id = Column(Integer, primary_key=True, index=True)
  minuta_id = Column(Integer, ForeignKey("minutas_sesion.id"), nullable=False)
  responsable_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
  descripcion_acuerdo = Column(Text, nullable=False)
  fecha_limite = Column(Date, nullable=True)
  estatus = Column(
      Enum(EstatusAcuerdo), default=EstatusAcuerdo.PENDIENTE, nullable=False
  )
  observaciones_seguimiento = Column(Text, nullable=True)

  minuta = relationship("MinutaSesion", back_populates="acuerdos")
  responsable = relationship("Usuario", back_populates="acuerdos_asignados")


class EvidenciaAcademia(Base):
  __tablename__ = "evidencias_academia"

  id = Column(Integer, primary_key=True, index=True)
  docente_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
  categoria = Column(Enum(CategoriaEvidencia), nullable=False)
  titulo = Column(String(150), nullable=False)
  descripcion = Column(Text, nullable=False)
  fecha_actividad = Column(Date, nullable=False)
  periodo_cuatrimestral = Column(String(30), nullable=False)
  alumnos_impactados = Column(Integer, default=0)
  archivo_multimedia_url = Column(String(255), nullable=False)
  enlace_externo = Column(String(255), nullable=True)
  fecha_subida = Column(DateTime, default=datetime.utcnow)

  docente = relationship("Usuario", back_populates="evidencias_subidas")


class EventoCalendario(Base):
  __tablename__ = "eventos_calendario"

  id = Column(Integer, primary_key=True, index=True)
  titulo = Column(String(150), nullable=False)
  categoria = Column(
      Enum(CategoriaEvento),
      default=CategoriaEvento.EVENTO_ACADEMICO,
      nullable=False,
  )
  descripcion = Column(Text, nullable=True)
  fecha_inicio = Column(DateTime, nullable=False)
  fecha_fin = Column(DateTime, nullable=True)
  lugar = Column(String(100), nullable=True)
  completado = Column(Boolean, default=False)
