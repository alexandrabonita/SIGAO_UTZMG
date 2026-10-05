from datetime import date, datetime
import hashlib
import io
import json
import os
import secrets
import shutil
from typing import List, Optional
from database import Base, engine, get_db
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import models
import requests
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

# Crear tablas en SQLite
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SIGAO-UTZMG | Sistema Integral de Gestión Académica y Operativa"
)

os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

GOOGLE_CLIENT_ID = os.getenv(
    "GOOGLE_CLIENT_ID", "TU_GOOGLE_CLIENT_ID.apps.googleusercontent.com"
)


# --- SEGURIDAD: HASHING NATIVO ---
def generar_hash_password(password: str) -> str:
  salt = secrets.token_hex(16)
  hash_obj = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
  return f"{salt}${hash_obj}"


def verificar_password(password: str, hashed_guardado: str) -> bool:
  try:
    if not hashed_guardado or "$" not in hashed_guardado:
      return False
    salt, hash_original = hashed_guardado.split("$")
    hash_nuevo = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return secrets.compare_digest(hash_original, hash_nuevo)
  except Exception:
    return False


# --- AUDITORÍA Y SESIÓN ---
def registrar_auditoria(
    db: Session,
    usuario_id: Optional[int],
    modulo: str,
    accion: str,
    descripcion: str,
    ip: str = "127.0.0.1",
):
  log = models.BitacoraAccion(
      usuario_id=usuario_id,
      modulo=modulo,
      accion=accion,
      descripcion=descripcion,
      ip_origen=ip,
  )
  db.add(log)
  db.commit()


def get_current_user(request: Request, db: Session = Depends(get_db)):
  user_id = request.cookies.get("session_user_id")
  if not user_id:
    return None
  try:
    return (
        db.query(models.Usuario)
        .filter(
            models.Usuario.id == int(user_id), models.Usuario.activo == True
        )
        .first()
    )
  except Exception:
    return None


def require_user(request: Request, db: Session = Depends(get_db)):
  usr = get_current_user(request, db)
  if not usr:
    raise HTTPException(
        status_code=303, headers={"Location": "/login"}, detail="No autorizado"
    )
  return usr


# --- SEMILLERO INICIAL DE ESPACIOS ESTRUCTURALES Y CUENTAS ---
@app.on_event("startup")
def bootstrap_datos():
  db = next(get_db())

  # 1. Catálogo de laboratorios y espacios por edificio
  labs_iniciales = [
      ("A103", "Laboratorio de Cómputo 1", "Edificio A"),
      ("A105", "Laboratorio de Cómputo 2", "Edificio A"),
      ("A201", "Laboratorio de Cómputo 3", "Edificio A"),
      ("A206", "Laboratorio de Cómputo 4", "Edificio A"),
      ("A209", "Laboratorio de Redes", "Edificio A"),
      ("A210", "Laboratorio de CISCO", "Edificio A"),
      ("B1-1", "Laboratorio de Instrumentación", "Edificio B"),
      ("B1-2", "Laboratorio de Máquinas CNC", "Edificio B"),
      ("B2", "Laboratorio de Manufactura Asistida", "Edificio B"),
      ("B3", "Laboratorio de PLC’s", "Edificio B"),
      ("B4", "Laboratorio de Mecatrónica", "Edificio B"),
      ("B5-1", "Laboratorio de Electrónica Digital", "Edificio B"),
      ("B5-2", "Laboratorio de Electrónica Robótica", "Edificio B"),
      ("B6", "Laboratorio de Metrología", "Edificio B"),
      ("BM1", "Laboratorio de Analógica", "Edificio B"),
      ("C1", "Laboratorio de Máquinas y Herramientas", "Edificio C"),
      ("C2a", "Laboratorio de Química", "Edificio C"),
      ("C3", "Laboratorio de Resistencia de Materiales", "Edificio C"),
      ("C4", "Laboratorio de Máquinas Eléctricas", "Edificio C"),
      (
          "C5",
          "Laboratorio de Instalaciones Eléctricas y Renovables",
          "Edificio C",
      ),
      ("C6", "Laboratorio de Turismo", "Edificio C"),
      ("C7", "Laboratorio de Hotelería", "Edificio C"),
      ("D11", "Laboratorio de Paramédico", "Edificio D"),
      ("E108", "Laboratorio de Medios", "Edificio E"),
      ("E211", "Laboratorio de Diseño", "Edificio E"),
  ]

  for codigo, nom, edif in labs_iniciales:
    if not db.query(models.Laboratorio).filter_by(codigo_espacio=codigo).first():
      db.add(
          models.Laboratorio(
              codigo_espacio=codigo,
              nombre=nom,
              edificio=edif,
              tipo_espacio=models.TipoEspacio.LABORATORIO_TALLER,
              encargado_nombre="Mtro. Jesús Pérez Merlos",
              capacidad_estudiantes=25,
          )
      )
  db.commit()

  # 2. Cuentas operativas base (Contraseña: 123456)
  cuentas_base = [
      (
          "PRES-01",
          "Mtro. Jesús Pérez Merlos",
          "jperezm@utzmg.edu.mx",
          models.RolUsuario.PRESIDENTE,
      ),
      (
          "SOP-01",
          "ISC Cristina Alexandra Morán Garabito",
          "cmoran@utzmg.edu.mx",
          models.RolUsuario.SOPORTE,
      ),
      (
          "DOC-01",
          "Ing. Cristina Alexandra Morán Garabito",
          "cmoran_docente@utzmg.edu.mx",
          models.RolUsuario.PROFESOR,
      ),
      (
          "ENC-01",
          "Ing. Dario del Toro de la Paz",
          "dario.deltoro@utzmg.edu.mx",
          models.RolUsuario.ENCARGADO,
      ),
  ]

  for mat, nom, corr, rol in cuentas_base:
    if (
        not db.query(models.Usuario)
        .filter_by(matricula_nomina=mat)
        .first()
    ):
      u = models.Usuario(
          matricula_nomina=mat,
          nombre_completo=nom,
          correo=corr,
          password_hash=generar_hash_password("123456"),
          rol=rol,
          activo=True,
      )
      if mat == "ENC-01":
        lab_demo = (
            db.query(models.Laboratorio).filter_by(codigo_espacio="B1-2").first()
        )
        if lab_demo:
          u.laboratorios_asignados.append(lab_demo)
      db.add(u)
  db.commit()


# --- AUTENTICACIÓN ---
@app.get("/login", response_class=HTMLResponse)
async def login_view(request: Request):
  return templates.TemplateResponse(
      request=request,
      name="login.html",
      context={"error": None, "google_client_id": GOOGLE_CLIENT_ID},
  )


@app.post("/login")
async def login_action(
    request: Request,
    matricula_nomina: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
  ip = request.client.host if request.client else "127.0.0.1"
  u = (
      db.query(models.Usuario)
      .filter(models.Usuario.matricula_nomina == matricula_nomina.strip())
      .first()
  )

  if not u or not verificar_password(password, u.password_hash):
    if u:
      db.add(
          models.RegistroConexion(
              usuario_id=u.id,
              ip_origen=ip,
              user_agent=request.headers.get("user-agent"),
              exitoso=False,
          )
      )
      db.commit()
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": "Credenciales inválidas.",
            "google_client_id": GOOGLE_CLIENT_ID,
        },
    )

  if not u.activo:
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": (
                "Tu cuenta está en proceso de validación por el Presidente de"
                " Academia o Soporte."
            ),
            "google_client_id": GOOGLE_CLIENT_ID,
        },
    )

  db.add(
      models.RegistroConexion(
          usuario_id=u.id,
          ip_origen=ip,
          user_agent=request.headers.get("user-agent"),
          exitoso=True,
      )
  )
  db.commit()

  resp = RedirectResponse(url="/", status_code=303)
  resp.set_cookie(key="session_user_id", value=str(u.id), httponly=True)
  return resp


@app.get("/registro", response_class=HTMLResponse)
async def registro_view(request: Request):
  return templates.TemplateResponse(
      request=request,
      name="registro.html",
      context={"mensaje": None, "google_client_id": GOOGLE_CLIENT_ID},
  )


@app.post("/registro")
async def registro_action(
    request: Request,
    matricula_nomina: str = Form(...),
    nombre_completo: str = Form(...),
    correo: str = Form(...),
    password: str = Form(...),
    rol_solicitado: str = Form("Alumno"),
    db: Session = Depends(get_db),
):
  correo_limpio = correo.strip().lower()
  matricula_limpia = matricula_nomina.strip().upper()

  # 1. Validación estricta del dominio institucional
  if not correo_limpio.endswith("@utzmg.edu.mx"):
    return templates.TemplateResponse(
        request=request,
        name="registro.html",
        context={
            "error": (
                "Acceso restringido: Es obligatorio registrarte con tu correo"
                " institucional @utzmg.edu.mx."
            ),
            "google_client_id": GOOGLE_CLIENT_ID,
        },
    )

  # 2. Verificar existencia previa
  existe = (
      db.query(models.Usuario)
      .filter(
          (models.Usuario.matricula_nomina == matricula_limpia)
          | (models.Usuario.correo == correo_limpio)
      )
      .first()
  )
  if existe:
    return templates.TemplateResponse(
        request=request,
        name="registro.html",
        context={
            "error": "La matrícula o correo ya se encuentran registrados.",
            "google_client_id": GOOGLE_CLIENT_ID,
        },
    )

  # 3. Validación condicional por perfil
  es_alumno = (
      rol_solicitado == models.RolUsuario.ALUMNO.value
      or rol_solicitado == "Alumno"
  )

  try:
    rol_enum = models.RolUsuario(rol_solicitado)
  except ValueError:
    rol_enum = models.RolUsuario.ALUMNO

  cuenta_activa = True if es_alumno else False

  nuevo_u = models.Usuario(
      matricula_nomina=matricula_limpia,
      nombre_completo=nombre_completo.strip(),
      correo=correo_limpio,
      password_hash=generar_hash_password(password),
      rol=rol_enum,
      activo=cuenta_activa,
  )
  db.add(nuevo_u)
  db.commit()

  if cuenta_activa:
    mensaje_exito = (
        "Cuenta de estudiante verificada y activada con éxito. Ya puedes"
        " iniciar sesión."
    )
  else:
    mensaje_exito = (
        f"Solicitud con perfil de '{rol_solicitado}' registrada correctamente."
        " Tu cuenta quedará activa una vez validada por el Presidente de"
        " Academia o Soporte Técnico."
    )

  return templates.TemplateResponse(
      request=request,
      name="registro.html",
      context={"exito": mensaje_exito, "google_client_id": GOOGLE_CLIENT_ID},
  )


# --- CALLBACK GOOGLE SSO ---
@app.post("/auth/google")
async def google_auth_callback(
    request: Request,
    credential: str = Form(...),
    db: Session = Depends(get_db),
):
  try:
    token_info_resp = requests.get(
        f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}",
        timeout=10,
    )
    if token_info_resp.status_code != 200:
      raise HTTPException(
          status_code=400, detail="Token de Google inválido o expirado"
      )

    id_info = token_info_resp.json()
    correo = id_info.get("email", "").lower()
    google_id = id_info.get("sub")
    nombre = id_info.get("name", "Usuario UTZMG")

    if not correo.endswith("@utzmg.edu.mx"):
      return HTMLResponse(
          "<script>alert('Error: Solo se permiten correos institucionales"
          " @utzmg.edu.mx'); window.location.href='/login';</script>"
      )

    u = db.query(models.Usuario).filter(models.Usuario.correo == correo).first()
    if not u:
      matricula = correo.split("@")[0].upper()
      es_docente = not matricula.replace("-", "").isdigit()
      rol = models.RolUsuario.PROFESOR if es_docente else models.RolUsuario.ALUMNO
      activo = not es_docente

      u = models.Usuario(
          matricula_nomina=matricula,
          nombre_completo=nombre,
          correo=correo,
          google_id=google_id,
          rol=rol,
          activo=activo,
      )
      db.add(u)
      db.commit()
    else:
      if not u.google_id:
        u.google_id = google_id
        db.commit()

    if not u.activo:
      return HTMLResponse(
          "<script>alert('Tu cuenta está registrada pero requiere validación del"
          " Presidente de Academia.'); window.location.href='/login';</script>"
      )

    ip = request.client.host if request.client else "127.0.0.1"
    db.add(
        models.RegistroConexion(
            usuario_id=u.id,
            ip_origen=ip,
            user_agent=request.headers.get("user-agent"),
            exitoso=True,
        )
    )
    db.commit()

    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(key="session_user_id", value=str(u.id), httponly=True)
    return resp

  except Exception as e:
    return HTMLResponse(
        f"<script>alert('Error al autenticar con Google: {str(e)}');"
        " window.location.href='/login';</script>"
    )


@app.get("/logout")
async def logout():
  resp = RedirectResponse(url="/login", status_code=303)
  resp.delete_cookie("session_user_id")
  return resp


# --- DASHBOARD PRINCIPAL ---
@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  equipos_total = (
      db.query(models.Equipo)
      .filter(models.Equipo.estatus != models.EstadoEquipo.DADO_DE_BAJA)
      .count()
  )
  equipos_fuera = (
      db.query(models.Equipo)
      .filter(models.Equipo.estatus == models.EstadoEquipo.FUERA_DE_SERVICIO)
      .count()
  )
  insumos_alerta = (
      db.query(models.Consumible)
      .filter(
          models.Consumible.stock_actual <= models.Consumible.stock_minimo,
          models.Consumible.activo == True,
      )
      .all()
  )

  query = db.query(models.TicketIncidencia)
  if usuario.rol == models.RolUsuario.ENCARGADO:
    labs_ids = [l.id for l in usuario.laboratorios_asignados]
    query = query.join(models.Equipo).filter(
        models.Equipo.laboratorio_id.in_(labs_ids)
    )
  elif usuario.rol in [models.RolUsuario.PROFESOR, models.RolUsuario.ALUMNO]:
    query = query.filter(models.TicketIncidencia.usuario_id == usuario.id)

  tickets = query.order_by(desc(models.TicketIncidencia.fecha_reporte)).all()
  prestamos_activos = (
      db.query(models.PrestamoServicio)
      .filter(models.PrestamoServicio.estatus == models.EstatusPrestamo.ACTIVO)
      .all()
  )

  acuerdos_pendientes = (
      db.query(models.AcuerdoMinuta)
      .filter(models.AcuerdoMinuta.estatus != models.EstatusAcuerdo.CUMPLIDO)
      .count()
  )
  total_evidencias = db.query(models.EvidenciaAcademia).count()

  return templates.TemplateResponse(
      request=request,
      name="dashboard.html",
      context={
          "usuario": usuario,
          "equipos_total": equipos_total,
          "equipos_fuera": equipos_fuera,
          "insumos_alerta": insumos_alerta,
          "tickets": tickets,
          "prestamos_activos": prestamos_activos,
          "acuerdos_pendientes": acuerdos_pendientes,
          "total_evidencias": total_evidencias,
      },
  )


# --- GESTIÓN DE USUARIOS (ADMIN) ---
@app.get("/admin/usuarios", response_class=HTMLResponse)
async def admin_usuarios_view(
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  if usuario.rol not in [
      models.RolUsuario.PRESIDENTE,
      models.RolUsuario.SOPORTE,
  ]:
    raise HTTPException(status_code=403, detail="Acceso denegado")

  pendientes = (
      db.query(models.Usuario)
      .filter(models.Usuario.activo == False)
      .order_by(desc(models.Usuario.fecha_registro))
      .all()
  )
  activos = (
      db.query(models.Usuario)
      .filter(models.Usuario.activo == True)
      .order_by(models.Usuario.nombre_completo)
      .all()
  )
  laboratorios = db.query(models.Laboratorio).all()
  roles = [r.value for r in models.RolUsuario]

  return templates.TemplateResponse(
      request=request,
      name="admin_usuarios.html",
      context={
          "usuario": usuario,
          "pendientes": pendientes,
          "activos": activos,
          "laboratorios": laboratorios,
          "roles": roles,
      },
  )


@app.post("/admin/usuarios/{target_id}/aprobar")
async def aprobar_usuario(
    target_id: int,
    request: Request,
    rol: str = Form(...),
    laboratorios_ids: List[int] = Form([]),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  if usuario.rol not in [
      models.RolUsuario.PRESIDENTE,
      models.RolUsuario.SOPORTE,
  ]:
    raise HTTPException(status_code=403)

  target = (
      db.query(models.Usuario).filter(models.Usuario.id == target_id).first()
  )
  if target:
    target.activo = True
    target.rol = models.RolUsuario(rol)
    labs = (
        db.query(models.Laboratorio)
        .filter(models.Laboratorio.id.in_(laboratorios_ids))
        .all()
    )
    target.laboratorios_asignados = labs
    registrar_auditoria(
        db,
        usuario.id,
        "Usuarios",
        "APROBACION",
        f"Aprobó a {target.nombre_completo} ({target.matricula_nomina}) con rol"
        f" {rol}",
        request.client.host if request.client else "127.0.0.1",
    )
    db.commit()
  return RedirectResponse(url="/admin/usuarios", status_code=303)


@app.post("/admin/usuarios/{target_id}/editar")
async def editar_usuario(
    target_id: int,
    request: Request,
    nombre_completo: str = Form(...),
    matricula_nomina: str = Form(...),
    correo: str = Form(...),
    rol: str = Form(...),
    laboratorios_ids: List[int] = Form([]),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  if usuario.rol not in [
      models.RolUsuario.PRESIDENTE,
      models.RolUsuario.SOPORTE,
  ]:
    raise HTTPException(status_code=403)

  target = (
      db.query(models.Usuario).filter(models.Usuario.id == target_id).first()
  )
  if target:
    target.nombre_completo = nombre_completo.strip()
    target.matricula_nomina = matricula_nomina.strip()
    target.correo = correo.strip()
    target.rol = models.RolUsuario(rol)
    labs = (
        db.query(models.Laboratorio)
        .filter(models.Laboratorio.id.in_(laboratorios_ids))
        .all()
    )
    target.laboratorios_asignados = labs
    registrar_auditoria(
        db,
        usuario.id,
        "Usuarios",
        "EDICION",
        f"Modificó datos y rol de {target.nombre_completo}"
        f" ({target.matricula_nomina})",
        request.client.host if request.client else "127.0.0.1",
    )
    db.commit()
  return RedirectResponse(url="/admin/usuarios", status_code=303)


@app.post("/admin/usuarios/{target_id}/estado")
async def toggle_usuario_estado(
    target_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  if usuario.rol not in [
      models.RolUsuario.PRESIDENTE,
      models.RolUsuario.SOPORTE,
  ]:
    raise HTTPException(status_code=403)

  target = (
      db.query(models.Usuario).filter(models.Usuario.id == target_id).first()
  )
  if target and target.id != usuario.id:
    target.activo = not target.activo
    accion = "ACTIVAR" if target.activo else "SUSPENDER/BAJA"
    registrar_auditoria(
        db,
        usuario.id,
        "Usuarios",
        accion,
        f"{accion} cuenta de {target.nombre_completo}",
        request.client.host if request.client else "127.0.0.1",
    )
    db.commit()
  return RedirectResponse(url="/admin/usuarios", status_code=303)


# --- AUDITORÍA Y CONEXIONES ---
@app.get("/admin/auditoria", response_class=HTMLResponse)
async def auditoria_view(
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  if usuario.rol not in [
      models.RolUsuario.PRESIDENTE,
      models.RolUsuario.SOPORTE,
  ]:
    raise HTTPException(status_code=403)

  logs_acciones = (
      db.query(models.BitacoraAccion)
      .order_by(desc(models.BitacoraAccion.fecha_hora))
      .limit(100)
      .all()
  )
  logs_conexiones = (
      db.query(models.RegistroConexion)
      .order_by(desc(models.RegistroConexion.fecha_hora))
      .limit(100)
      .all()
  )

  return templates.TemplateResponse(
      request=request,
      name="auditoria.html",
      context={
          "usuario": usuario,
          "acciones": logs_acciones,
          "conexiones": logs_conexiones,
      },
  )


# --- GESTIÓN COLEGIADA (MINUTAS Y EVIDENCIAS) ---
@app.get("/academia/minutas", response_class=HTMLResponse)
async def ver_minutas(
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  minutas = (
      db.query(models.MinutaSesion)
      .order_by(desc(models.MinutaSesion.fecha_reunion))
      .all()
  )
  docentes = (
      db.query(models.Usuario)
      .filter(
          models.Usuario.rol.in_([
              models.RolUsuario.PROFESOR,
              models.RolUsuario.ENCARGADO,
              models.RolUsuario.PRESIDENTE,
          ])
      )
      .all()
  )
  return templates.TemplateResponse(
      request=request,
      name="minutas.html",
      context={"usuario": usuario, "minutas": minutas, "docentes": docentes},
  )


@app.post("/academia/minutas/nueva")
async def crear_minuta(
    request: Request,
    academia: str = Form(...),
    periodo_cuatrimestral: str = Form(...),
    fecha_reunion: str = Form(...),
    orden_del_dia: str = Form(...),
    desarrollo_acuerdos: str = Form(...),
    acta_pdf: UploadFile = File(None),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  if usuario.rol not in [
      models.RolUsuario.PRESIDENTE,
      models.RolUsuario.SOPORTE,
  ]:
    raise HTTPException(status_code=403)

  archivo_url = None
  if acta_pdf and acta_pdf.filename:
    nom = (
        f"minuta_{datetime.now().strftime('%Y%m%d%H%M%S')}_{acta_pdf.filename}"
    )
    destino = os.path.join("static/uploads", nom)
    with open(destino, "wb") as buf:
      shutil.copyfileobj(acta_pdf.file, buf)
    archivo_url = f"/static/uploads/{nom}"

  folio_m = f"MIN-{datetime.now().strftime('%y%m%d%H%M')}"
  minuta = models.MinutaSesion(
      folio=folio_m,
      academia=academia.strip(),
      periodo_cuatrimestral=periodo_cuatrimestral.strip(),
      fecha_reunion=datetime.strptime(fecha_reunion, "%Y-%m-%d").date(),
      orden_del_dia=orden_del_dia.strip(),
      desarrollo_acuerdos=desarrollo_acuerdos.strip(),
      archivo_acta_firmada_url=archivo_url,
      presidente_valida=usuario.nombre_completo,
  )
  db.add(minuta)
  registrar_auditoria(
      db,
      usuario.id,
      "Academia",
      "MINUTA_ALTA",
      f"Registró minuta folio {folio_m}",
  )
  db.commit()
  return RedirectResponse(url="/academia/minutas", status_code=303)


@app.get("/academia/evidencias", response_class=HTMLResponse)
async def ver_evidencias(
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  evidencias = (
      db.query(models.EvidenciaAcademia)
      .order_by(desc(models.EvidenciaAcademia.fecha_actividad))
      .all()
  )
  categorias = [c.value for c in models.CategoriaEvidencia]
  return templates.TemplateResponse(
      request=request,
      name="evidencias.html",
      context={
          "usuario": usuario,
          "evidencias": evidencias,
          "categorias": categorias,
      },
  )


@app.post("/academia/evidencias/subir")
async def subir_evidencia(
    request: Request,
    categoria: str = Form(...),
    titulo: str = Form(...),
    descripcion: str = Form(...),
    fecha_actividad: str = Form(...),
    periodo_cuatrimestral: str = Form(...),
    alumnos_impactados: int = Form(0),
    archivo_multimedia: UploadFile = File(...),
    enlace_externo: str = Form(""),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  nom = f"evid_{datetime.now().strftime('%Y%m%d%H%M%S')}_{archivo_multimedia.filename}"
  destino = os.path.join("static/uploads", nom)
  with open(destino, "wb") as buf:
    shutil.copyfileobj(archivo_multimedia.file, buf)

  ev = models.EvidenciaAcademia(
      docente_id=usuario.id,
      categoria=models.CategoriaEvidencia(categoria),
      titulo=titulo.strip(),
      descripcion=descripcion.strip(),
      fecha_actividad=datetime.strptime(fecha_actividad, "%Y-%m-%d").date(),
      periodo_cuatrimestral=periodo_cuatrimestral.strip(),
      alumnos_impactados=alumnos_impactados,
      archivo_multimedia_url=f"/static/uploads/{nom}",
      enlace_externo=enlace_externo.strip() or None,
  )
  db.add(ev)
  registrar_auditoria(
      db,
      usuario.id,
      "Evidencias",
      "SUBIDA",
      f"Subió evidencia académica: {titulo}",
  )
  db.commit()
  return RedirectResponse(url="/academia/evidencias", status_code=303)


# --- TICKETS, EQUIPOS Y ESCÁNER ---
@app.get("/scanner", response_class=HTMLResponse)
async def scanner(
    request: Request, usuario: models.Usuario = Depends(require_user)
):
  return templates.TemplateResponse(
      request=request, name="scanner.html", context={"usuario": usuario}
  )


@app.get("/equipos", response_class=HTMLResponse)
async def equipos_view(
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  equipos = (
      db.query(models.Equipo)
      .filter(models.Equipo.estatus != models.EstadoEquipo.DADO_DE_BAJA)
      .all()
  )
  bajas = (
      db.query(models.Equipo)
      .filter(models.Equipo.estatus == models.EstadoEquipo.DADO_DE_BAJA)
      .all()
  )
  laboratorios = db.query(models.Laboratorio).all()
  return templates.TemplateResponse(
      request=request,
      name="equipos.html",
      context={
          "equipos": equipos,
          "bajas": bajas,
          "laboratorios": laboratorios,
          "usuario": usuario,
      },
  )


@app.post("/equipos/nuevo")
async def nuevo_equipo(
    request: Request,
    id_codigo_qr: str = Form(...),
    laboratorio_id: int = Form(...),
    nombre: str = Form(...),
    marca: str = Form(""),
    modelo: str = Form(""),
    num_serie: str = Form(""),
    manual_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  if usuario.rol not in [
      models.RolUsuario.LABORATORISTA,
      models.RolUsuario.ENCARGADO,
      models.RolUsuario.SOPORTE,
      models.RolUsuario.PRESIDENTE,
  ]:
    raise HTTPException(status_code=403)

  manual_url = None
  if manual_file and manual_file.filename:
    nombre_archivo = f"manual_{id_codigo_qr}_{manual_file.filename}"
    destino = os.path.join("static/uploads", nombre_archivo)
    with open(destino, "wb") as buffer:
      shutil.copyfileobj(manual_file.file, buffer)
    manual_url = f"/static/uploads/{nombre_archivo}"

  equipo = models.Equipo(
      id_codigo_qr=id_codigo_qr.strip(),
      laboratorio_id=laboratorio_id,
      nombre=nombre.strip(),
      marca=marca.strip(),
      modelo=modelo.strip(),
      num_serie=num_serie.strip(),
      manual_pdf_url=manual_url,
  )
  db.add(equipo)
  registrar_auditoria(
      db,
      usuario.id,
      "Equipos",
      "ALTA",
      f"Registró nuevo equipo: {nombre} ({id_codigo_qr})",
      request.client.host if request.client else "127.0.0.1",
  )
  db.commit()
  return RedirectResponse(url="/equipos", status_code=303)


@app.post("/equipos/{codigo_qr}/baja")
async def dar_baja_equipo(
    codigo_qr: str,
    request: Request,
    motivo: str = Form(...),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  if usuario.rol not in [
      models.RolUsuario.PRESIDENTE,
      models.RolUsuario.SOPORTE,
      models.RolUsuario.ENCARGADO,
  ]:
    raise HTTPException(status_code=403)

  eq = (
      db.query(models.Equipo)
      .filter(models.Equipo.id_codigo_qr == codigo_qr)
      .first()
  )
  if eq:
    eq.estatus = models.EstadoEquipo.DADO_DE_BAJA
    eq.fecha_baja = datetime.utcnow()
    eq.motivo_baja = motivo
    registrar_auditoria(
        db,
        usuario.id,
        "Equipos",
        "BAJA",
        f"Dio de baja equipo {codigo_qr}. Motivo: {motivo}",
        request.client.host if request.client else "127.0.0.1",
    )
    db.commit()
  return RedirectResponse(url="/equipos", status_code=303)


@app.get("/equipos/{codigo_qr}/reportar", response_class=HTMLResponse)
async def vista_reportar(
    codigo_qr: str,
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  equipo = (
      db.query(models.Equipo)
      .filter(models.Equipo.id_codigo_qr == codigo_qr)
      .first()
  )
  if not equipo:
    raise HTTPException(status_code=404, detail="Equipo no registrado")
  return templates.TemplateResponse(
      request=request,
      name="reportar_falla.html",
      context={"equipo": equipo, "usuario": usuario},
  )


@app.post("/tickets/crear")
async def crear_ticket(
    request: Request,
    equipo_id: str = Form(...),
    prioridad: str = Form(...),
    descripcion: str = Form(...),
    evidencia: UploadFile = File(None),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  evidencia_url = None
  if evidencia and evidencia.filename:
    nom = f"evidencia_{datetime.now().strftime('%Y%m%d%H%M%S')}_{evidencia.filename}"
    destino = os.path.join("static/uploads", nom)
    with open(destino, "wb") as buf:
      shutil.copyfileobj(evidencia.file, buf)
    evidencia_url = f"/static/uploads/{nom}"

  ticket = models.TicketIncidencia(
      equipo_id=equipo_id,
      usuario_id=usuario.id,
      matricula_reporta=usuario.matricula_nomina,
      nombre_reporta=usuario.nombre_completo,
      prioridad=prioridad,
      descripcion=descripcion,
      evidencia_multimedia=evidencia_url,
  )
  db.add(ticket)

  if prioridad == models.PrioridadTicket.ALTA:
    eq = (
        db.query(models.Equipo)
        .filter(models.Equipo.id_codigo_qr == equipo_id)
        .first()
    )
    if eq:
      eq.estatus = models.EstadoEquipo.FUERA_DE_SERVICIO

  registrar_auditoria(
      db,
      usuario.id,
      "Tickets",
      "ALTA",
      f"Ticket creado para equipo {equipo_id} ({prioridad})",
      request.client.host if request.client else "127.0.0.1",
  )
  db.commit()
  return RedirectResponse(url="/", status_code=303)


@app.post("/tickets/{ticket_id}/evaluar")
async def evaluar_ticket_encargado(
    ticket_id: int,
    request: Request,
    decision: str = Form(...),
    diagnostico: str = Form(...),
    justificacion: str = Form(""),
    especificaciones: str = Form(""),
    costo_estimado: float = Form(0.0),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  ticket = (
      db.query(models.TicketIncidencia)
      .filter(models.TicketIncidencia.id == ticket_id)
      .first()
  )
  if not ticket:
    raise HTTPException(status_code=404)

  ticket.diagnostico_encargado = diagnostico

  if decision == "MANTENIMIENTO":
    ticket.estatus = models.EstatusTicket.MANTENIMIENTO_AUTORIZADO
    req = models.RequisicionLab(
        folio=f"REQ-MANT-{datetime.utcnow().strftime('%y%m%d%H%M')}",
        ticket_id=ticket.id,
        laboratorio_id=ticket.equipo.laboratorio_id,
        equipo_id=ticket.equipo_id,
        tipo=models.TipoRequisicion.MANTENIMIENTO_EXTERNO,
        justificacion=justificacion or diagnostico,
        especificaciones_tecnicas=especificaciones,
        costo_estimado=costo_estimado,
        encargado_solicita=usuario.nombre_completo,
    )
    db.add(req)
  elif decision == "COMPRA":
    ticket.estatus = models.EstatusTicket.REQUISICION_COMPRA
    req = models.RequisicionLab(
        folio=f"REQ-MAT-{datetime.utcnow().strftime('%y%m%d%H%M')}",
        ticket_id=ticket.id,
        laboratorio_id=ticket.equipo.laboratorio_id,
        equipo_id=ticket.equipo_id,
        tipo=models.TipoRequisicion.COMPRA_INSUMO,
        justificacion=justificacion or diagnostico,
        especificaciones_tecnicas=especificaciones,
        costo_estimado=costo_estimado,
        encargado_solicita=usuario.nombre_completo,
    )
    db.add(req)
  else:
    ticket.estatus = models.EstatusTicket.EN_REVISION

  registrar_auditoria(
      db,
      usuario.id,
      "Tickets",
      "EVALUACION",
      f"Evaluó ticket #{ticket.id}: {decision}",
      request.client.host if request.client else "127.0.0.1",
  )
  db.commit()
  return RedirectResponse(url="/", status_code=303)


# --- REQUISICIONES, PRÉSTAMOS E IMPRESIÓN ---
@app.get("/requisiciones", response_class=HTMLResponse)
async def ver_requisiciones(
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  query = db.query(models.RequisicionLab)
  if usuario.rol == models.RolUsuario.ENCARGADO:
    labs_ids = [l.id for l in usuario.laboratorios_asignados]
    query = query.filter(models.RequisicionLab.laboratorio_id.in_(labs_ids))

  reqs = query.order_by(desc(models.RequisicionLab.fecha_solicitud)).all()
  return templates.TemplateResponse(
      request=request,
      name="requisiciones.html",
      context={"usuario": usuario, "requisiciones": reqs},
  )


@app.get("/requisiciones/{req_id}/imprimir", response_class=HTMLResponse)
async def imprimir_requisicion(
    req_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  req = (
      db.query(models.RequisicionLab)
      .filter(models.RequisicionLab.id == req_id)
      .first()
  )
  if not req:
    raise HTTPException(status_code=404)
  return templates.TemplateResponse(
      request=request,
      name="formato_requisicion.html",
      context={"req": req, "usuario": usuario},
  )


@app.get("/reportes/tickets-impresion", response_class=HTMLResponse)
async def imprimir_reporte_tickets(
    request: Request,
    estatus: str = None,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  query = db.query(models.TicketIncidencia)
  if estatus and estatus != "TODOS":
    query = query.filter(models.TicketIncidencia.estatus == estatus)
  tickets = query.order_by(desc(models.TicketIncidencia.fecha_reporte)).all()

  return templates.TemplateResponse(
      request=request,
      name="reporte_tickets_print.html",
      context={
          "tickets": tickets,
          "estatus_filtro": estatus,
          "usuario": usuario,
      },
  )


@app.get("/equipos/etiquetas", response_class=HTMLResponse)
async def imprimir_etiquetas(
    request: Request,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_user),
):
  equipos = (
      db.query(models.Equipo)
      .filter(models.Equipo.estatus != models.EstadoEquipo.DADO_DE_BAJA)
      .all()
  )
  base_url = str(request.base_url).rstrip("/")
  return templates.TemplateResponse(
      request=request,
      name="imprimir_qr.html",
      context={
          "equipos": equipos,
          "base_url": base_url,
          "usuario": usuario,
      },
  )
