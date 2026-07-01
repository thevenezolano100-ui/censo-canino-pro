from flask import Flask, render_template, request, redirect, url_for, Response, jsonify, flash, make_response
from datetime import datetime, date, timedelta
import csv
import io
import os
import smtplib
from email.mime.text import MIMEText
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
import traceback

app = Flask(__name__)
app.secret_key = 'clave_secreta_censo_master_v14'

# ==========================================
# RUTAS ABSOLUTAS Y BASE DE DATOS
# ==========================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db_path = os.path.join(BASE_DIR, 'censo_pro_v14.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Sesión requerida."
login_manager.login_message_category = "danger"

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException): return e.get_response()
    return f"""
    <div style="font-family: Arial; padding: 40px; background: #fff3f3; color: #dc3545; border: 2px solid #dc3545; border-radius: 10px; margin: 20px;">
        <h1 style="margin-top:0;">⚠️ Diagnóstico Técnico Avanzado</h1>
        <p>Fallo interno detectado:</p>
        <pre style="background: #212529; color: #10b981; padding: 20px; border-radius: 5px; overflow-x: auto;">{traceback.format_exc()}</pre>
    </div>
    """, 500

# ==========================================
# MODELOS DE BASE DE DATOS
# ==========================================
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(20), default='Ciudadano') 
    nombre = db.Column(db.String(100))
    apellido = db.Column(db.String(100))
    cedula = db.Column(db.String(20))
    whatsapp = db.Column(db.String(20))
    direccion = db.Column(db.Text)

@login_manager.user_loader
def load_user(user_id): return Usuario.query.get(int(user_id))

class Carrusel(db.Model):
    id = db.Column(db.Integer, primary_key=True); imagen = db.Column(db.String(200), nullable=False)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True); archivo = db.Column(db.String(200), nullable=False)

class ManualDoc(db.Model):
    id = db.Column(db.Integer, primary_key=True); archivo = db.Column(db.String(200), nullable=False)

class Medicamento(db.Model):
    id = db.Column(db.Integer, primary_key=True); nombre = db.Column(db.String(100), nullable=False); stock = db.Column(db.Integer, default=0); unidad = db.Column(db.String(50), nullable=False)

class Consulta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow); peso = db.Column(db.String(20))
    sintomas = db.Column(db.Text); diagnostico = db.Column(db.Text); tratamiento = db.Column(db.Text)
    canino_id = db.Column(db.Integer, db.ForeignKey('canino.id'), nullable=False)

class NotaHospitalizacion(db.Model):
    id = db.Column(db.Integer, primary_key=True); fecha = db.Column(db.DateTime, default=datetime.utcnow)
    temperatura = db.Column(db.String(20)); frecuencia_card = db.Column(db.String(20))
    evolucion = db.Column(db.Text, nullable=False); veterinario = db.Column(db.String(100))
    canino_id = db.Column(db.Integer, db.ForeignKey('canino.id'), nullable=False)

class Cita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha_hora = db.Column(db.DateTime, nullable=False); motivo = db.Column(db.String(200), nullable=False)
    estado = db.Column(db.String(20), default='Pendiente') 
    canino_id = db.Column(db.Integer, db.ForeignKey('canino.id'), nullable=False)

class Vacuna(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(100), nullable=False); fecha_aplicacion = db.Column(db.Date, nullable=False); fecha_proxima = db.Column(db.Date, nullable=False)
    canino_id = db.Column(db.Integer, db.ForeignKey('canino.id'), nullable=False)

class RegistroReproductivo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo_evento = db.Column(db.String(100), nullable=False) 
    fecha_evento = db.Column(db.Date, nullable=False)
    fecha_esperada_parto = db.Column(db.Date, nullable=True) 
    notas = db.Column(db.Text)
    estado = db.Column(db.String(50), default='Activo (En Progreso)') 
    canino_id = db.Column(db.Integer, db.ForeignKey('canino.id'), nullable=False)

class Canino(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    consultas = db.relationship('Consulta', backref='paciente', lazy=True, cascade="all, delete-orphan")
    notas_internado = db.relationship('NotaHospitalizacion', backref='paciente', lazy=True, cascade="all, delete-orphan")
    citas = db.relationship('Cita', backref='paciente', lazy=True, cascade="all, delete-orphan")
    vacunas_historial = db.relationship('Vacuna', backref='paciente', lazy=True, cascade="all, delete-orphan")
    registros_reproductivos = db.relationship('RegistroReproductivo', backref='madre', lazy=True, cascade="all, delete-orphan")
    
    foto = db.Column(db.String(200)); nombre = db.Column(db.String(100)); raza = db.Column(db.String(100))
    edad = db.Column(db.String(50)); sexo = db.Column(db.String(20)); estado_tenencia = db.Column(db.String(50))
    nombre_propietario = db.Column(db.String(100)); estado_salud = db.Column(db.String(100)); sector = db.Column(db.String(100))
    whatsapp_propietario = db.Column(db.String(20)); latitud = db.Column(db.Float); longitud = db.Column(db.Float)
    situacion = db.Column(db.String(100), default='Censo Normal'); reportado_por = db.Column(db.String(100)); cubiculo_jaula = db.Column(db.String(50), default="N/A") 
    
    esterilizado = db.Column(db.Boolean, default=False); desparasitado = db.Column(db.Boolean, default=False)
    vacuna_parvovirus = db.Column(db.Boolean, default=False); vacuna_moquillo = db.Column(db.Boolean, default=False)
    vacuna_triple = db.Column(db.Boolean, default=False); vacuna_sextuple = db.Column(db.Boolean, default=False); vacuna_antirrabica = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(username='admin').first():
        db.session.add(Usuario(username='admin', password=generate_password_hash('admin123'), rol='Admin', nombre='Administrador', apellido='Principal', cedula='0000', whatsapp='0000', direccion='Sede'))
        db.session.commit()

# ==========================================
# OFFLINE PWA Y AUTENTICACIÓN
# ==========================================
@app.route('/sw.js')
def sw():
    res = make_response(app.send_static_file('sw.js')); res.headers['Content-Type'] = 'application/javascript'; res.headers['Cache-Control'] = 'no-cache'; return res

@app.route('/manifest.json')
def manifest(): return make_response(app.send_static_file('manifest.json'))

@app.route('/api/sincronizar_offline', methods=['POST'])
def sincronizar_offline():
    datos = request.get_json() or []
    for item in datos:
        try: lat = float(item.get('latitud') or 0)
        except: lat = 0
        try: lon = float(item.get('longitud') or 0)
        except: lon = 0
        nuevo = Canino(
            nombre=item.get('nombre'), raza=item.get('raza'), edad=item.get('edad'), sexo=item.get('sexo'), estado_tenencia=item.get('estado_tenencia'),
            nombre_propietario=item.get('nombre_propietario'), whatsapp_propietario=item.get('whatsapp_propietario'), estado_salud=item.get('estado_salud'), 
            sector=item.get('sector'), latitud=lat, longitud=lon, situacion=item.get('situacion', 'Censo Normal'), reportado_por="Sincronizado Offline", foto="",
            esterilizado=item.get('esterilizado') == 'on', desparasitado=item.get('desparasitado') == 'on', vacuna_parvovirus=item.get('vacuna_parvovirus') == 'on', 
            vacuna_moquillo=item.get('vacuna_moquillo') == 'on', vacuna_triple=item.get('vacuna_triple') == 'on', vacuna_sextuple=item.get('vacuna_sextuple') == 'on', vacuna_antirrabica=item.get('vacuna_antirrabica') == 'on'
        )
        db.session.add(nuevo)
    db.session.commit()
    return jsonify({'status': 'exito'})

@app.route('/registro', methods=['GET', 'POST'])
def registro_publico():
    if request.method == 'POST':
        user = request.form.get('username')
        if Usuario.query.filter_by(username=user).first(): flash('Usuario ya registrado.', 'danger'); return redirect(url_for('registro_publico'))
        nuevo = Usuario(username=user, password=generate_password_hash(request.form.get('password')), nombre=request.form.get('nombre'), apellido=request.form.get('apellido'), cedula=request.form.get('cedula'), whatsapp=request.form.get('whatsapp'), direccion=request.form.get('direccion'), rol='Ciudadano')
        db.session.add(nuevo); db.session.commit(); flash('Cuenta creada. Inicia sesión.', 'success'); return redirect(url_for('login'))
    return render_template('registro_publico.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('inicio'))
    if request.method == 'POST':
        user = Usuario.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')): login_user(user); return redirect(url_for('inicio'))
        flash('Credenciales incorrectas.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))

# ==========================================
# RUTAS CORE
# ==========================================
@app.route('/', methods=['GET', 'POST'])
@login_required
def inicio():
    if request.method == 'POST':
        f = request.files.get('foto'); n_f = secure_filename(f.filename) if f and f.filename else ""
        if n_f: f.save(os.path.join(app.config['UPLOAD_FOLDER'], n_f))
        try: lat = float(request.form.get('latitud') or 0)
        except: lat = 0
        try: lon = float(request.form.get('longitud') or 0)
        except: lon = 0
        
        # Seguridad extra: Si un Ciudadano manipula el HTML para enviar "Hospitalizado", el servidor lo bloquea.
        situacion_recibida = request.form.get('situacion', 'Censo Normal')
        if situacion_recibida == 'Hospitalizado' and current_user.rol != 'Admin':
            situacion_recibida = 'Censo Normal'

        nuevo = Canino(
            foto=n_f, nombre=request.form.get('nombre'), raza=request.form.get('raza'), edad=request.form.get('edad'), 
            sexo=request.form.get('sexo'), estado_tenencia=request.form.get('estado_tenencia'), nombre_propietario=request.form.get('nombre_propietario'), 
            whatsapp_propietario=request.form.get('whatsapp_propietario'), estado_salud=request.form.get('estado_salud'), sector=request.form.get('sector'), 
            latitud=lat, longitud=lon, situacion=situacion_recibida, reportado_por=current_user.nombre, cubiculo_jaula=request.form.get('cubiculo_jaula', 'N/A'),
            esterilizado=request.form.get('esterilizado')=='on', desparasitado=request.form.get('desparasitado')=='on', vacuna_parvovirus=request.form.get('vacuna_parvovirus')=='on', 
            vacuna_moquillo=request.form.get('vacuna_moquillo')=='on', vacuna_triple=request.form.get('vacuna_triple')=='on', vacuna_sextuple=request.form.get('vacuna_sextuple')=='on', vacuna_antirrabica=request.form.get('vacuna_antirrabica')=='on'
        )
        db.session.add(nuevo); db.session.commit(); flash('Registro guardado.', 'success'); return redirect(url_for('inicio'))
            
    p = request.args.get('page', 1, type=int); b = request.args.get('buscar')
    q = Canino.query.filter(Canino.nombre.contains(b) | Canino.nombre_propietario.contains(b) | Canino.sector.contains(b)) if b else Canino.query
    return render_template('index.html', caninos=q.order_by(Canino.id.desc()).paginate(page=p, per_page=10, error_out=False), busqueda=b, carrusel=Carrusel.query.all())

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    if current_user.rol != 'Admin': return redirect(url_for('inicio'))
    p = Canino.query.get_or_404(id)
    if request.method == 'POST':
        f = request.files.get('foto')
        if f and f.filename: p.foto = secure_filename(f.filename); f.save(os.path.join(app.config['UPLOAD_FOLDER'], p.foto))
        p.nombre = request.form.get('nombre'); p.raza = request.form.get('raza'); p.edad = request.form.get('edad')
        p.sexo = request.form.get('sexo'); p.estado_tenencia = request.form.get('estado_tenencia'); p.nombre_propietario = request.form.get('nombre_propietario')
        p.whatsapp_propietario = request.form.get('whatsapp_propietario'); p.estado_salud = request.form.get('estado_salud'); p.sector = request.form.get('sector')
        p.situacion = request.form.get('situacion'); p.cubiculo_jaula = request.form.get('cubiculo_jaula', 'N/A')
        p.esterilizado = request.form.get('esterilizado')=='on'; p.desparasitado = request.form.get('desparasitado')=='on'; p.vacuna_parvovirus = request.form.get('vacuna_parvovirus')=='on'
        p.vacuna_moquillo = request.form.get('vacuna_moquillo')=='on'; p.vacuna_triple = request.form.get('vacuna_triple')=='on'; p.vacuna_sextuple = request.form.get('vacuna_sextuple')=='on'; p.vacuna_antirrabica = request.form.get('vacuna_antirrabica')=='on'
        db.session.commit(); flash('Expediente actualizado.', 'success'); return redirect(url_for('inicio'))
    return render_template('editar.html', perro=p)

@app.route('/eliminar/<int:id>')
@login_required
def eliminar(id):
    if current_user.rol != 'Admin': return redirect(url_for('inicio'))
    db.session.delete(Canino.query.get_or_404(id)); db.session.commit(); flash('Canino eliminado.', 'success'); return redirect(url_for('inicio'))

# ============================================================
# MÓDULO HOSPITALIZACIÓN: BLINDADO SOLO PARA ADMIN
# ============================================================
@app.route('/hospitalizacion', methods=['GET'])
@login_required
def hospitalizacion_pizarra(): 
    if current_user.rol != 'Admin': 
        flash('Acceso Denegado. Solo el personal médico Administrador puede acceder a la Unidad de Cuidados.', 'danger')
        return redirect(url_for('inicio'))
    return render_template('hospitalizacion.html', pacientes=Canino.query.filter_by(situacion='Hospitalizado').all())

@app.route('/hospitalizacion/nota/<int:id>', methods=['POST'])
@login_required
def agregar_nota_hospitalizacion(id):
    if current_user.rol != 'Admin': return redirect(url_for('inicio'))
    db.session.add(NotaHospitalizacion(temperatura=request.form.get('temperatura'), frecuencia_card=request.form.get('frecuencia_card'), evolucion=request.form.get('evolucion'), veterinario=current_user.nombre, canino_id=id))
    db.session.commit(); flash('Evolución guardada.', 'success'); return redirect(url_for('hospitalizacion_pizarra'))

@app.route('/hospitalizacion/eliminar_nota/<int:id>')
@login_required
def eliminar_nota_hospitalizacion(id):
    if current_user.rol != 'Admin': return redirect(url_for('inicio'))
    nota = NotaHospitalizacion.query.get_or_404(id)
    db.session.delete(nota); db.session.commit(); flash('Nota clínica eliminada.', 'success'); return redirect(url_for('hospitalizacion_pizarra'))

@app.route('/hospitalizacion/alta/<int:id>')
@login_required
def dar_alta_hospitalizacion(id): 
    if current_user.rol != 'Admin': return redirect(url_for('inicio'))
    p = Canino.query.get_or_404(id); p.situacion = 'Censo Normal'; p.estado_salud = 'Sano'; db.session.commit(); flash('Alta médica ejecutada con éxito.', 'success'); return redirect(url_for('hospitalizacion_pizarra'))

# ==========================================
# RESTO DE RUTAS OPERATIVAS (SIN CAMBIOS)
# ==========================================
@app.route('/reproduccion/<int:id>', methods=['GET', 'POST'])
@login_required
def reproduccion(id):
    p = Canino.query.get_or_404(id)
    if request.method == 'POST':
        try:
            tipo = request.form.get('tipo_evento'); f_evento_str = request.form.get('fecha_evento', '').strip()
            f_evento = datetime.strptime(f_evento_str, '%Y-%m-%d').date() if f_evento_str else date.today()
            f_parto_str = request.form.get('fecha_esperada_parto', '').strip()
            f_parto = datetime.strptime(f_parto_str, '%Y-%m-%d').date() if f_parto_str else None
            nuevo_registro = RegistroReproductivo(tipo_evento=tipo, fecha_evento=f_evento, fecha_esperada_parto=f_parto, notas=request.form.get('notas'), estado=request.form.get('estado', 'Activo (En Progreso)'), canino_id=p.id)
            db.session.add(nuevo_registro); db.session.commit(); flash('Registro reproductivo guardado.', 'success'); return redirect(url_for('reproduccion', id=p.id))
        except: db.session.rollback(); flash('Error de procesamiento.', 'danger')
    return render_template('reproduccion.html', perro=p)

@app.route('/reproduccion/eliminar/<int:id>')
@login_required
def eliminar_reproduccion(id):
    r = RegistroReproductivo.query.get_or_404(id); p_id = r.canino_id
    db.session.delete(r); db.session.commit(); flash('Evento reproductivo removido.', 'success'); return redirect(url_for('reproduccion', id=p_id))

@app.route('/citas', methods=['GET', 'POST'])
@login_required
def gestion_citas():
    if request.method == 'POST':
        db.session.add(Cita(fecha_hora=datetime.strptime(request.form.get('fecha_hora'), '%Y-%m-%dT%H:%M'), motivo=request.form.get('motivo'), canino_id=request.form.get('canino_id')))
        db.session.commit(); flash('Cita agendada.', 'success'); return redirect(url_for('gestion_citas'))
    return render_template('citas.html', citas=Cita.query.order_by(Cita.fecha_hora.asc()).all(), perros=Canino.query.all())

@app.route('/citas/aceptar/<int:id>')
@login_required
def aceptar_cita(id):
    c = Cita.query.get_or_404(id); c.estado = 'Completada'
    db.session.add(Consulta(peso="N/A", sintomas=f"Cita Programada - {c.motivo}", diagnostico="Evaluación Concluida", tratamiento=f"Cita concluida con éxito.", canino_id=c.canino_id))
    db.session.commit(); flash('Cita completada e historial actualizado.', 'success'); return redirect(url_for('gestion_citas'))

@app.route('/citas/rechazar/<int:id>')
@login_required
def rechazar_cita(id): c = Cita.query.get_or_404(id); c.estado = 'Cancelada'; db.session.commit(); return redirect(url_for('gestion_citas'))

@app.route('/alertas', methods=['GET', 'POST'])
@login_required
def alertas():
    if request.method == 'POST':
        t = request.form.get('tipo'); can_id = request.form.get('canino_id'); f_ap = datetime.strptime(request.form.get('fecha_aplicacion'), '%Y-%m-%d').date()
        db.session.add(Vacuna(tipo=t, fecha_aplicacion=f_ap, fecha_proxima=f_ap + timedelta(days=365), canino_id=can_id))
        db.session.commit(); flash('Alerta programada.', 'success'); return redirect(url_for('alertas'))
    return render_template('alertas.html', alertas=Vacuna.query.order_by(Vacuna.fecha_proxima.asc()).all(), hoy=date.today(), perros=Canino.query.all())

@app.route('/alertas/aceptar/<int:id>')
@login_required
def aceptar_alerta(id):
    alerta = Vacuna.query.get_or_404(id); perro = Canino.query.get(alerta.canino_id)
    if 'Parvovirus' in alerta.tipo: perro.vacuna_parvovirus = True
    elif 'Antirrábica' in alerta.tipo: perro.vacuna_antirrabica = True
    elif 'Moquillo' in alerta.tipo: perro.vacuna_moquillo = True
    elif 'Triple' in alerta.tipo: perro.vacuna_triple = True
    elif 'Sextuple' in alerta.tipo: perro.vacuna_sextuple = True
    db.session.add(Consulta(peso="N/A", sintomas="Alerta de Inmunización", diagnostico=f"Biológico: {alerta.tipo}", tratamiento=f"Vacuna aplicada.", canino_id=perro.id))
    db.session.delete(alerta); db.session.commit(); flash('Vacuna registrada en historial.', 'success'); return redirect(url_for('alertas'))

@app.route('/alertas/descartar/<int:id>')
@login_required
def descartar_alerta(id): db.session.delete(Vacuna.query.get_or_404(id)); db.session.commit(); return redirect(url_for('alertas'))

@app.route('/rescate/<int:id>', methods=['GET', 'POST'])
def rescate(id):
    p = Canino.query.get_or_404(id)
    if request.method == 'POST':
        d = request.get_json(silent=True) or request.form
        try:
            p.latitud = float(d.get('lat') or d.get('latitud') or 0); p.longitud = float(d.get('lon') or d.get('longitud') or 0)
            p.situacion = '¡ALERTA QR!'; db.session.commit(); return jsonify({"status": "exito"})
        except Exception as e: db.session.rollback(); return jsonify({"status": "error"}), 400
    return render_template('rescate.html', perro=p)

@app.route('/usuarios')
@login_required
def gestion_usuarios():
    if current_user.rol != 'Admin': flash('Acceso denegado.', 'danger'); return redirect(url_for('inicio'))
    return render_template('usuarios.html', usuarios=Usuario.query.all())

@app.route('/usuarios/cambiar_clave/<int:id>', methods=['POST'])
@login_required
def cambiar_clave_usuario(id):
    if current_user.rol != 'Admin': return redirect(url_for('inicio'))
    u = Usuario.query.get_or_404(id); u.password = generate_password_hash(request.form.get('nueva_password') or '123456'); db.session.commit(); return redirect(url_for('gestion_usuarios'))

@app.route('/inventario', methods=['GET', 'POST'])
@login_required
def inventario():
    if request.method == 'POST':
        db.session.add(Medicamento(nombre=request.form.get('nombre'), stock=int(request.form.get('stock') or 0), unidad=request.form.get('unidad')))
        db.session.commit(); flash('Insumo registrado.', 'success'); return redirect(url_for('inventario'))
    return render_template('inventario.html', medicamentos=Medicamento.query.all())

@app.route('/inventario/actualizar/<int:id>', methods=['POST'])
@login_required
def actualizar_inventario(id): med = Medicamento.query.get_or_404(id); med.stock += int(request.form.get('cantidad_sumar') or 0); db.session.commit(); return redirect(url_for('inventario'))

@app.route('/inventario/eliminar/<int:id>')
@login_required
def eliminar_medicamento(id): db.session.delete(Medicamento.query.get_or_404(id)); db.session.commit(); return redirect(url_for('inventario'))

@app.route('/historial/<int:id>', methods=['GET', 'POST'])
@login_required
def historial(id):
    p = Canino.query.get_or_404(id)
    if request.method == 'POST':
        t_base = request.form.get('tratamiento'); m_id = request.form.get('medicamento_id'); cant = int(request.form.get('cantidad_usada') or 0)
        if m_id and cant > 0:
            med = Medicamento.query.get(m_id)
            if med and med.stock >= cant: med.stock -= cant; t_base += f"\n[FARMACIA]: Se extrajeron {cant} {med.unidad} de {med.nombre}."
        db.session.add(Consulta(peso=request.form.get('peso'), sintomas=request.form.get('sintomas'), diagnostico=request.form.get('diagnostico'), tratamiento=t_base, canino_id=p.id))
        db.session.commit(); flash('Consulta guardada.', 'success'); return redirect(url_for('historial', id=p.id))
    return render_template('historial.html', perro=p, medicamentos=Medicamento.query.filter(Medicamento.stock > 0).all())

@app.route('/historial/eliminar/<int:id>')
@login_required
def eliminar_consulta(id): c = Consulta.query.get_or_404(id); c_id = c.canino_id; db.session.delete(c); db.session.commit(); return redirect(url_for('historial', id=c_id))

@app.route('/receta/<int:consulta_id>')
@login_required
def receta_medica(consulta_id): return render_template('receta.html', consulta=Consulta.query.get_or_404(consulta_id))

@app.route('/reportes')
@login_required
def reportes():
    v_c = [Canino.query.filter_by(vacuna_parvovirus=True).count(), Canino.query.filter_by(vacuna_moquillo=True).count(), Canino.query.filter_by(vacuna_triple=True).count(), Canino.query.filter_by(vacuna_sextuple=True).count(), Canino.query.filter_by(vacuna_antirrabica=True).count()]
    return render_template('reportes.html', total_perros=Canino.query.count(), total_consultas=Consulta.query.count(), citas_pendientes=Cita.query.filter_by(estado='Pendiente').count(), sano_count=Canino.query.filter_by(estado_salud='Sano').count(), enfermo_count=Canino.query.filter_by(estado_salud='Enfermo').count(), tratamiento_count=Canino.query.filter_by(estado_salud='En Tratamiento').count(), macho_count=Canino.query.filter_by(sexo='Macho').count(), hembra_count=Canino.query.filter_by(sexo='Hembra').count(), vacunas_labels=['Parvovirus', 'Moquillo', 'Triple', 'Sextuple', 'Antirrábica'], vacunas_counts=v_c)

@app.route('/exportar')
@login_required
def exportar():
    output = io.StringIO(); output.write('\ufeff'); writer = csv.writer(output, delimiter=';')
    writer.writerow(['ID', 'Nombre', 'Raza', 'Sector', 'Salud', 'Propietario', 'WhatsApp'])
    for p in Canino.query.all(): writer.writerow([p.id, p.nombre, p.raza, p.sector, p.estado_salud, p.nombre_propietario, p.whatsapp_propietario])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=censo.csv"})

@app.route('/descargar_pdf')
@login_required
def descargar_pdf(): return render_template('pdf.html', caninos=Canino.query.order_by(Canino.id.asc()).all())

@app.route('/mapa_general')
@login_required
def mapa_general(): return render_template('mapa.html', perros=Canino.query.filter(Canino.latitud != 0).all())

@app.route('/carnet/<int:id>')
@login_required
def carnet(id): return render_template('carnet.html', dog=Canino.query.get_or_404(id), perro=Canino.query.get_or_404(id))

@app.route('/videos')
@login_required
def videos(): return render_template('videos.html', video=Video.query.first())

@app.route('/subir_video', methods=['POST'])
@login_required
def subir_video():
    f = request.files.get('video_archivo')
    if f and f.filename:
        nom = secure_filename(f.filename); f.save(os.path.join(app.config['UPLOAD_FOLDER'], nom)); v_v = Video.query.first()
        if v_v: db.session.delete(v_v)
        db.session.add(Video(archivo=nom)); db.session.commit()
    return redirect(url_for('videos'))

@app.route('/manual')
@login_required
def manual(): return render_template('manual.html', documento=ManualDoc.query.first())

@app.route('/subir_manual', methods=['POST'])
@login_required
def subir_manual():
    f = request.files.get('manual_archivo')
    if f and f.filename:
        nom = secure_filename(f.filename); f.save(os.path.join(app.config['UPLOAD_FOLDER'], nom)); m_v = ManualDoc.query.first()
        if m_v: db.session.delete(m_v)
        db.session.add(ManualDoc(archivo=nom)); db.session.commit()
    return redirect(url_for('manual'))

if __name__ == '__main__': app.run(debug=True)