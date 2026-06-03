from flask import Flask, render_template, request, redirect, url_for, Response, jsonify, flash
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

app = Flask(__name__)
app.secret_key = 'clave_secreta_censo_master_v6'

# Forzamos la creación automática de una estructura limpia y unificada
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///censo_v6.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Sesión requerida."
login_manager.login_message_category = "danger"

# ==========================================
# MODELOS DE BASE DE DATOS COMPLETOS
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
    id = db.Column(db.Integer, primary_key=True)
    imagen = db.Column(db.String(200), nullable=False)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    archivo = db.Column(db.String(200), nullable=False)

class ManualDoc(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    archivo = db.Column(db.String(200), nullable=False)

class Consulta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    peso = db.Column(db.String(20))
    sintomas = db.Column(db.Text)
    diagnostico = db.Column(db.Text)
    tratamiento = db.Column(db.Text)
    canino_id = db.Column(db.Integer, db.ForeignKey('canino.id'), nullable=False)

class Cita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha_hora = db.Column(db.DateTime, nullable=False)
    motivo = db.Column(db.String(200), nullable=False)
    estado = db.Column(db.String(20), default='Pendiente') # Pendiente, Aceptada, Rechazada
    canino_id = db.Column(db.Integer, db.ForeignKey('canino.id'), nullable=False)

class Vacuna(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(100), nullable=False)
    fecha_aplicacion = db.Column(db.Date, nullable=False)
    fecha_proxima = db.Column(db.Date, nullable=False)
    canino_id = db.Column(db.Integer, db.ForeignKey('canino.id'), nullable=False)

class Canino(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    consultas = db.relationship('Consulta', backref='paciente', lazy=True, cascade="all, delete-orphan")
    citas = db.relationship('Cita', backref='paciente', lazy=True, cascade="all, delete-orphan")
    vacunas_historial = db.relationship('Vacuna', backref='paciente', lazy=True, cascade="all, delete-orphan")
    
    foto = db.Column(db.String(200)); nombre = db.Column(db.String(100)); raza = db.Column(db.String(100))
    edad = db.Column(db.String(50)); sexo = db.Column(db.String(20)); estado_tenencia = db.Column(db.String(50))
    nombre_propietario = db.Column(db.String(100)); estado_salud = db.Column(db.String(100)); sector = db.Column(db.String(100))
    latitud = db.Column(db.Float); longitud = db.Column(db.Float)
    situacion = db.Column(db.String(100), default='Censo Normal')
    reportado_por = db.Column(db.String(100))
    
    esterilizado = db.Column(db.Boolean, default=False); desparasitado = db.Column(db.Boolean, default=False)
    vacuna_parvovirus = db.Column(db.Boolean, default=False); vacuna_moquillo = db.Column(db.Boolean, default=False)
    vacuna_triple = db.Column(db.Boolean, default=False); vacuna_sextuple = db.Column(db.Boolean, default=False)
    vacuna_antirrabica = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(username='admin').first():
        db.session.add(Usuario(username='admin', password=generate_password_hash('admin123'), rol='Admin', nombre='Administrador Principal', apellido='Censo', cedula='0000', whatsapp='0000', direccion='Sede Sinergia'))
        db.session.commit()

# ==========================================
# RUTAS DE SISTEMA DE ACCESO Y AUTENTICACIÓN
# ==========================================

@app.route('/registro', methods=['GET', 'POST'])
def registro_publico():
    if request.method == 'POST':
        user = request.form.get('username')
        if Usuario.query.filter_by(username=user).first():
            flash('Ese usuario o correo ya está registrado.', 'danger'); return redirect(url_for('registro_publico'))
        nuevo = Usuario(
            username=user, password=generate_password_hash(request.form.get('password')),
            nombre=request.form.get('nombre'), apellido=request.form.get('apellido'),
            cedula=request.form.get('cedula'), whatsapp=request.form.get('whatsapp'),
            direccion=request.form.get('direccion'), rol='Ciudadano'
        )
        db.session.add(nuevo); db.session.commit()
        flash('Cuenta creada con éxito. Ya puedes iniciar sesión.', 'success'); return redirect(url_for('login'))
    return render_template('registro_publico.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('inicio'))
    if request.method == 'POST':
        user = Usuario.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user); return redirect(url_for('inicio'))
        flash('Credenciales de acceso incorrectas.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))

# ==========================================
# GESTIÓN CENTRAL (PANEL PRINCIPAL / CRUD)
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
        
        nuevo = Canino(
            foto=n_f, nombre=request.form.get('nombre'), raza=request.form.get('raza'), edad=request.form.get('edad'), 
            sexo=request.form.get('sexo'), estado_tenencia=request.form.get('estado_tenencia'), nombre_propietario=request.form.get('nombre_propietario'), 
            estado_salud=request.form.get('estado_salud'), sector=request.form.get('sector'), latitud=lat, longitud=lon,
            situacion=request.form.get('situacion', 'Censo Normal'), reportado_por=current_user.nombre,
            esterilizado=request.form.get('esterilizado')=='on', desparasitado=request.form.get('desparasitado')=='on', 
            vacuna_parvovirus=request.form.get('vacuna_parvovirus')=='on', vacuna_moquillo=request.form.get('vacuna_moquillo')=='on', 
            vacuna_triple=request.form.get('vacuna_triple')=='on', vacuna_sextuple=request.form.get('vacuna_sextuple')=='on', 
            vacuna_antirrabica=request.form.get('vacuna_antirrabica')=='on'
        )
        db.session.add(nuevo); db.session.commit()
        flash('Registro guardado correctamente.', 'success'); return redirect(url_for('inicio'))
    
    p = request.args.get('page', 1, type=int); b = request.args.get('buscar')
    q = Canino.query.filter(Canino.nombre.contains(b) | Canino.nombre_propietario.contains(b) | Canino.sector.contains(b)) if b else Canino.query
    paginacion = q.order_by(Canino.id.desc()).paginate(page=p, per_page=10, error_out=False)
    return render_template('index.html', caninos=paginacion, busqueda=b, carrusel=Carrusel.query.all())

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    if current_user.rol != 'Admin': flash('Acceso denegado.', 'danger'); return redirect(url_for('inicio'))
    p = Canino.query.get_or_404(id)
    if request.method == 'POST':
        f = request.files.get('foto')
        if f and f.filename: p.foto = secure_filename(f.filename); f.save(os.path.join(app.config['UPLOAD_FOLDER'], p.foto))
        p.nombre = request.form.get('nombre'); p.raza = request.form.get('raza'); p.edad = request.form.get('edad')
        p.sexo = request.form.get('sexo'); p.estado_tenencia = request.form.get('estado_tenencia'); p.nombre_propietario = request.form.get('nombre_propietario')
        p.estado_salud = request.form.get('estado_salud'); p.sector = request.form.get('sector'); p.situacion = request.form.get('situacion')
        try: p.latitud = float(request.form.get('latitud') or 0)
        except: p.latitud = 0
        try: p.longitud = float(request.form.get('longitud') or 0)
        except: p.longitud = 0
        p.esterilizado = request.form.get('esterilizado')=='on'; p.desparasitado = request.form.get('desparasitado')=='on'
        p.vacuna_parvovirus = request.form.get('vacuna_parvovirus')=='on'; p.vacuna_moquillo = request.form.get('vacuna_moquillo')=='on'
        p.vacuna_triple = request.form.get('vacuna_triple')=='on'; p.vacuna_sextuple = request.form.get('vacuna_sextuple')=='on'; p.vacuna_antirrabica = request.form.get('vacuna_antirrabica')=='on'
        db.session.commit(); flash('Expediente actualizado.', 'success'); return redirect(url_for('inicio'))
    return render_template('editar.html', perro=p)

@app.route('/eliminar/<int:id>')
@login_required
def eliminar(id):
    if current_user.rol != 'Admin': flash('Acceso denegado.', 'danger'); return redirect(url_for('inicio'))
    db.session.delete(Canino.query.get_or_404(id)); db.session.commit(); flash('Canino eliminado.', 'success'); return redirect(url_for('inicio'))

# ==========================================
# REQUERIMIENTO 4: GESTIÓN DE USUARIOS (ADMIN)
# ==========================================

@app.route('/usuarios')
@login_required
def gestion_usuarios():
    if current_user.rol != 'Admin': flash('Acceso denegado.', 'danger'); return redirect(url_for('inicio'))
    lista_usuarios = Usuario.query.all()
    return render_template('usuarios.html', usuarios=lista_usuarios)

@app.route('/usuarios/cambiar_clave/<int:id>', methods=['POST'])
@login_required
def cambiar_clave_usuario(id):
    if current_user.rol != 'Admin': flash('Acceso denegado.', 'danger'); return redirect(url_for('inicio'))
    u = Usuario.query.get_or_404(id)
    nueva_clave = request.form.get('nueva_password')
    if nueva_clave:
        u.password = generate_password_hash(nueva_clave)
        db.session.commit()
        flash(f'Contraseña de {u.username} restablecida con éxito.', 'success')
    return redirect(url_for('gestion_usuarios'))

# ==========================================
# REQUERIMIENTO 2: MODULO DE ALERTAS MEJORADO
# ==========================================

@app.route('/alertas', methods=['GET', 'POST'])
@login_required
def alertas():
    hoy = date.today()
    if request.method == 'POST':
        t = request.form.get('tipo'); can_id = request.form.get('canino_id'); f_ap = datetime.strptime(request.form.get('fecha_aplicacion'), '%Y-%m-%d').date()
        db.session.add(Vacuna(tipo=t, fecha_aplicacion=f_ap, fecha_proxima=f_ap + timedelta(days=21 if 'Cachorro' in t else 365), canino_id=can_id))
        db.session.commit(); flash('Alerta programada.', 'success'); return redirect(url_for('alertas'))
    return render_template('alertas.html', alertas=Vacuna.query.filter(Vacuna.fecha_proxima <= hoy + timedelta(days=30)).all(), hoy=hoy, perros=Canino.query.all())

@app.route('/alertas/aceptar/<int:id>')
@login_required
def aceptar_alerta(id):
    if current_user.rol != 'Admin': flash('Acceso denegado.', 'danger'); return redirect(url_for('alertas'))
    alerta = Vacuna.query.get_or_404(id); perro = Canino.query.get(alerta.canino_id)
    if 'Parvovirus' in alerta.tipo: perro.vacuna_parvovirus = True
    elif 'Antirrábica' in alerta.tipo: perro.vacuna_antirrabica = True
    db.session.delete(alerta); db.session.commit(); flash('Alerta aceptada y expediente actualizado.', 'success')
    return redirect(url_for('alertas'))

@app.route('/alertas/descartar/<int:id>')
@login_required
def descartar_alerta(id):
    if current_user.rol != 'Admin': flash('Acceso denegado.', 'danger'); return redirect(url_for('alertas'))
    db.session.delete(Vacuna.query.get_or_404(id)); db.session.commit(); flash('Alerta rechazada y removida.', 'info')
    return redirect(url_for('alertas'))

# ==========================================
# REQUERIMIENTO 3: MODULO DE CITAS MEJORADO
# ==========================================

@app.route('/citas', methods=['GET', 'POST'])
@login_required
def gestion_citas():
    if request.method == 'POST':
        db.session.add(Cita(fecha_hora=datetime.strptime(request.form.get('fecha_hora'), '%Y-%m-%dT%H:%M'), motivo=request.form.get('motivo'), canino_id=request.form.get('canino_id')))
        db.session.commit(); flash('Cita solicitada/agendada.', 'success'); return redirect(url_for('gestion_citas'))
    return render_template('citas.html', citas=Cita.query.order_by(Cita.fecha_hora.asc()).all(), perros=Canino.query.all())

@app.route('/citas/aceptar/<int:id>')
@login_required
def aceptar_cita(id):
    if current_user.rol != 'Admin': flash('Acceso denegado.', 'danger'); return redirect(url_for('gestion_citas'))
    c = Cita.query.get_or_404(id); c.estado = 'Aceptada'; db.session.commit(); flash('Cita aceptada y confirmada.', 'success')
    return redirect(url_for('gestion_citas'))

@app.route('/citas/rechazar/<int:id>')
@login_required
def rechazar_cita(id):
    if current_user.rol != 'Admin': flash('Acceso denegado.', 'danger'); return redirect(url_for('gestion_citas'))
    c = Cita.query.get_or_404(id); c.estado = 'Rechazada'; db.session.commit(); flash('Cita rechazada.', 'warning')
    return redirect(url_for('gestion_citas'))

# ==========================================
# RUTAS MULTIMEDIA Y DOCUMENTOS
# ==========================================

@app.route('/subir_carrusel', methods=['POST'])
@login_required
def subir_carrusel():
    if current_user.rol != 'Admin': return redirect(url_for('inicio'))
    for f in request.files.getlist('foto_carrusel'):
        if f and f.filename:
            nom = secure_filename(f.filename); f.save(os.path.join(app.config['UPLOAD_FOLDER'], nom))
            db.session.add(Carrusel(imagen=nom))
    db.session.commit(); flash('Banner actualizado.', 'success'); return redirect(url_for('inicio'))

@app.route('/eliminar_carrusel/<int:id>')
@login_required
def eliminar_carrusel(id):
    if current_user.rol != 'Admin': return redirect(url_for('inicio'))
    db.session.delete(Carrusel.query.get_or_404(id)); db.session.commit(); flash('Imagen eliminada.', 'success')
    return redirect(url_for('inicio'))

@app.route('/videos')
@login_required
def videos(): return render_template('videos.html', video=Video.query.first())

@app.route('/subir_video', methods=['POST'])
@login_required
def subir_video():
    if current_user.rol != 'Admin': return redirect(url_for('inicio'))
    f = request.files.get('video_archivo')
    if f and f.filename:
        nom = secure_filename(f.filename); f.save(os.path.join(app.config['UPLOAD_FOLDER'], nom))
        v_v = Video.query.first()
        if v_v: db.session.delete(v_v)
        db.session.add(Video(archivo=nom)); db.session.commit(); flash('Video actualizado.', 'success')
    return redirect(url_for('videos'))

@app.route('/manual')
@login_required
def manual(): return render_template('manual.html', documento=ManualDoc.query.first())

@app.route('/subir_manual', methods=['POST'])
@login_required
def subir_manual():
    if current_user.rol != 'Admin': return redirect(url_for('inicio'))
    f = request.files.get('manual_archivo')
    if f and f.filename:
        nom = secure_filename(f.filename); f.save(os.path.join(app.config['UPLOAD_FOLDER'], nom))
        m_v = ManualDoc.query.first()
        if m_v: db.session.delete(m_v)
        db.session.add(ManualDoc(archivo=nom)); db.session.commit(); flash('Manual publicado.', 'success')
    return redirect(url_for('manual'))

# ==========================================
# REPORTES Y EXPORTACIÓN A EXCEL / PDF
# ==========================================

@app.route('/reportes')
@login_required
def reportes():
    total = Canino.query.count()
    v_c = [Canino.query.filter_by(vacuna_parvovirus=True).count(), Canino.query.filter_by(vacuna_moquillo=True).count(), Canino.query.filter_by(vacuna_triple=True).count(), Canino.query.filter_by(vacuna_sextuple=True).count(), Canino.query.filter_by(vacuna_antirrabica=True).count()]
    return render_template('reportes.html', total_perros=total, total_consultas=Consulta.query.count(), total_citas=Cita.query.count(), macho_count=Canino.query.filter_by(sexo='Macho').count(), hembra_count=Canino.query.filter_by(sexo='Hembra').count(), sano_count=Canino.query.filter_by(estado_salud='Sano').count(), enfermo_count=Canino.query.filter_by(estado_salud='Enfermo').count(), tratamiento_count=Canino.query.filter_by(estado_salud='En Tratamiento').count(), vacunas_labels=['Parvovirus', 'Moquillo', 'Triple', 'Sextuple', 'Antirrábica'], vacunas_counts=v_c, citas_pendientes=Cita.query.filter_by(estado='Pendiente').count(), citas_completadas=Cita.query.filter_by(estado='Aceptada').count())

@app.route('/exportar')
@login_required
def exportar():
    if current_user.rol != 'Admin': return redirect(url_for('inicio'))
    output = io.StringIO(); output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['ID', 'Nombre', 'Raza', 'Edad', 'Sexo', 'Situacion', 'Sector', 'Salud', 'Propietario', 'Antirrabica', 'ReportadoPor'])
    for p in Canino.query.all():
        writer.writerow([p.id, p.nombre, p.raza, p.edad, p.sexo, p.situacion, p.sector, p.estado_salud, p.nombre_propietario, 'Si' if p.vacuna_antirrabica else 'No', p.reportado_por])
    return Response(output.getvalue(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment;filename=censo_completo.csv"})

@app.route('/descargar_pdf')
@login_required
def descargar_pdf(): return render_template('pdf.html', caninos=Canino.query.all())

@app.route('/mapa_general')
@login_required
def mapa_general(): return render_template('mapa.html', perros=Canino.query.filter(Canino.latitud != 0).all())

@app.route('/carnet/<int:id>')
@login_required
def carnet(id): return render_template('carnet.html', perro=Canino.query.get_or_404(id))

@app.route('/historial/<int:id>', methods=['GET', 'POST'])
@login_required
def historial(id):
    p = Canino.query.get_or_404(id)
    if request.method == 'POST':
        db.session.add(Consulta(peso=request.form.get('peso'), sintomas=request.form.get('sintomas'), diagnostico=request.form.get('diagnostico'), tratamiento=request.form.get('tratamiento'), canino_id=p.id))
        db.session.commit(); flash('Consulta guardada.', 'success'); return redirect(url_for('historial', id=p.id))
    return render_template('historial.html', perro=p)

@app.route('/historial/eliminar/<int:id>')
@login_required
def eliminar_consulta(id):
    c = Consulta.query.get_or_404(id); c_id = c.canino_id
    db.session.delete(c); db.session.commit(); flash('Consulta eliminada.', 'success'); return redirect(url_for('historial', id=c_id))

if __name__ == '__main__': app.run(debug=True)