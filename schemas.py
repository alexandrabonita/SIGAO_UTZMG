from datetime import date, datetime
from typing import List, Optional
import models
from pydantic import BaseModel, ConfigDict


# --- AULA Y LABORATORIO ---
class AulaBase(BaseModel):
  codigo_espacio: str
  edificio: str = "Edificio SIGAO_UTZMG"
  tipo_espacio: models.TipoEspacio = models.TipoEspacio.AULA_TEORICA
  capacidad_estudiantes: int = 30
  descripcion: Optional[str] = None


class AulaCreate(AulaBase):
  pass


class AulaOut(AulaBase):
  id: int
  model_config = ConfigDict(from_attributes=True)


class LaboratorioBase(AulaBase):
  nombre: str
  encargado_nombre: Optional[str] = "Mtro. Jesús Pérez Merlos"
  tipo_espacio: models.TipoEspacio = models.TipoEspacio.LABORATORIO_TALLER


class LaboratorioCreate(LaboratorioBase):
  pass


class LaboratorioOut(LaboratorioBase):
  id: int
  model_config = ConfigDict(from_attributes=True)


# --- USUARIO ---
class UsuarioBase(BaseModel):
  matricula_nomina: str
  nombre_completo: str
  correo: str
  rol: models.RolUsuario = models.RolUsuario.ALUMNO


class UsuarioCreate(UsuarioBase):
  password: Optional[str] = None


class UsuarioOut(UsuarioBase):
  id: int
  activo: bool
  fecha_registro: datetime
  laboratorios_asignados: List[LaboratorioOut] = []
  model_config = ConfigDict(from_attributes=True)


# --- AUDITORÍA Y CONEXIÓN ---
class RegistroConexionOut(BaseModel):
  id: int
  usuario_id: int
  fecha_hora: datetime
  ip_origen: Optional[str] = None
  user_agent: Optional[str] = None
  exitoso: bool
  model_config = ConfigDict(from_attributes=True)


class BitacoraAccionOut(BaseModel):
  id: int
  usuario_id: Optional[int] = None
  fecha_hora: datetime
  modulo: str
  accion: str
  descripcion: str
  ip_origen: Optional[str] = None
  model_config = ConfigDict(from_attributes=True)


# --- EQUIPO E INSUMOS ---
class EquipoBase(BaseModel):
  id_codigo_qr: str
  laboratorio_id: int
  nombre: str
  marca: Optional[str] = None
  modelo: Optional[str] = None
  num_serie: Optional[str] = None
  estatus: models.EstadoEquipo = models.EstadoEquipo.OPERATIVO
  manual_pdf_url: Optional[str] = None


class EquipoCreate(EquipoBase):
  pass


class EquipoOut(EquipoBase):
  fecha_baja: Optional[datetime] = None
  motivo_baja: Optional[str] = None
  laboratorio: Optional[LaboratorioOut] = None
  model_config = ConfigDict(from_attributes=True)


class ConsumibleBase(BaseModel):
  id_codigo_qr: str
  laboratorio_id: int
  descripcion: str
  categoria: Optional[str] = None
  stock_actual: int = 0
  stock_minimo: int = 5
  unidad_medida: str = "pza"


class ConsumibleCreate(ConsumibleBase):
  pass


class ConsumibleOut(ConsumibleBase):
  activo: bool
  laboratorio: Optional[LaboratorioOut] = None
  model_config = ConfigDict(from_attributes=True)


class DespachoConsumibleBase(BaseModel):
  consumible_id: str
  cantidad: int
  matricula_solicitante: str
  docente_a_cargo: str


class DespachoConsumibleCreate(DespachoConsumibleBase):
  pass


class DespachoConsumibleOut(DespachoConsumibleBase):
  id: int
  fecha_hora: datetime
  model_config = ConfigDict(from_attributes=True)


# --- TICKETS, REQUISICIONES Y PRÉSTAMOS ---
class TicketIncidenciaBase(BaseModel):
  equipo_id: str
  prioridad: models.PrioridadTicket = models.PrioridadTicket.MEDIA
  descripcion: str
  evidencia_multimedia: Optional[str] = None


class TicketIncidenciaCreate(TicketIncidenciaBase):
  pass


class TicketIncidenciaOut(TicketIncidenciaBase):
  id: int
  usuario_id: Optional[int] = None
  matricula_reporta: str
  nombre_reporta: str
  fecha_reporte: datetime
  estatus: models.EstatusTicket
  diagnostico_encargado: Optional[str] = None
  equipo: Optional[EquipoOut] = None
  model_config = ConfigDict(from_attributes=True)


class RequisicionLabBase(BaseModel):
  folio: str
  ticket_id: Optional[int] = None
  laboratorio_id: int
  equipo_id: Optional[str] = None
  tipo: models.TipoRequisicion
  justificacion: str
  especificaciones_tecnicas: str
  costo_estimado: Optional[float] = None
  encargado_solicita: str


class RequisicionLabCreate(RequisicionLabBase):
  pass


class RequisicionLabOut(RequisicionLabBase):
  id: int
  estatus: models.EstatusRequisicion
  fecha_solicitud: datetime
  fecha_autorizacion: Optional[datetime] = None
  model_config = ConfigDict(from_attributes=True)


class HistorialMantenimientoBase(BaseModel):
  equipo_id: str
  tipo_servicio: str
  tecnico_responsable: str
  refacciones: Optional[str] = None
  observaciones: str
  proxima_fecha: Optional[datetime] = None


class HistorialMantenimientoCreate(HistorialMantenimientoBase):
  pass


class HistorialMantenimientoOut(HistorialMantenimientoBase):
  id: int
  fecha_servicio: datetime
  model_config = ConfigDict(from_attributes=True)


class PrestamoServicioBase(BaseModel):
  tipo: models.TipoPrestamo
  laboratorio_id: int
  equipo_id: Optional[str] = None
  rol_solicitante: str
  matricula_numero: str
  nombre_completo: str
  observaciones: Optional[str] = None


class PrestamoServicioCreate(PrestamoServicioBase):
  pass


class PrestamoServicioOut(PrestamoServicioBase):
  id: int
  usuario_id: Optional[int] = None
  fecha_salida: datetime
  fecha_devolucion: Optional[datetime] = None
  estatus: models.EstatusPrestamo
  laboratorio: Optional[LaboratorioOut] = None
  equipo: Optional[EquipoOut] = None
  model_config = ConfigDict(from_attributes=True)


# --- ESQUEMAS DE GESTIÓN COLEGIADA ---
class AcuerdoMinutaBase(BaseModel):
  minuta_id: int
  responsable_id: Optional[int] = None
  descripcion_acuerdo: str
  fecha_limite: Optional[date] = None
  estatus: models.EstatusAcuerdo = models.EstatusAcuerdo.PENDIENTE
  observaciones_seguimiento: Optional[str] = None


class AcuerdoMinutaOut(AcuerdoMinutaBase):
  id: int
  responsable: Optional[UsuarioOut] = None
  model_config = ConfigDict(from_attributes=True)


class MinutaSesionBase(BaseModel):
  folio: str
  academia: str = "Academia de Mecatrónica"
  periodo_cuatrimestral: str
  fecha_reunion: date
  orden_del_dia: str
  desarrollo_acuerdos: str
  archivo_acta_firmada_url: Optional[str] = None
  presidente_valida: str


class MinutaSesionOut(MinutaSesionBase):
  id: int
  fecha_registro: datetime
  acuerdos: List[AcuerdoMinutaOut] = []
  model_config = ConfigDict(from_attributes=True)


class EvidenciaAcademiaBase(BaseModel):
  categoria: models.CategoriaEvidencia
  titulo: str
  descripcion: str
  fecha_actividad: date
  periodo_cuatrimestral: str
  alumnos_impactados: int = 0
  archivo_multimedia_url: str
  enlace_externo: Optional[str] = None


class EvidenciaAcademiaOut(EvidenciaAcademiaBase):
  id: int
  docente_id: int
  fecha_subida: datetime
  docente: Optional[UsuarioOut] = None
  model_config = ConfigDict(from_attributes=True)


class EventoCalendarioBase(BaseModel):
  titulo: str
  categoria: models.CategoriaEvento = models.CategoriaEvento.EVENTO_ACADEMICO
  descripcion: Optional[str] = None
  fecha_inicio: datetime
  fecha_fin: Optional[datetime] = None
  lugar: Optional[str] = None
  completado: bool = False


class EventoCalendarioOut(EventoCalendarioBase):
  id: int
  model_config = ConfigDict(from_attributes=True)
