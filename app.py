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

app = Flask(__name__)
app.secret_key = 'clave_secreta_censo_master_v8'

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Actualizamos a v8 para incluir el inventario
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///censo_v8.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Sesión requerida."
login_manager.login_message_category = "danger"

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
    id = db.Column(db.Integer, primary_key=True)
    imagen = db.Column(db.String(200), nullable=False)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    archivo = db.Column(db.String(200), nullable=False)

class ManualDoc(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    archivo = db.Column(db.String(200), nullable=False)

# NUEVO: Modelo de Inventario Farmacéutico
class Medicamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    stock = db.Column(db.Integer, default=0)
    unidad = db.Column(db.String(50), nullable=False) # ej: ml, tabletas, dosis

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
    estado = db.Column(db.String(20), default='Pendiente') 
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
    whatsapp_propietario = db.Column(db.String(20))
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
# RUTAS DE PWA Y AUTENTICACIÓN
# ==========================================
@app.route('/sw.js')
def sw():
    response = make_response(app.send_static_file('sw.js'))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Cache-Control'] = 'no-cache'
    return response

@app.route('/manifest.json')
def manifest(): return app.send_static_file('manifest.json')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('inicio'))
    if request.method == 'POST':
        user = Usuario.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user); return redirect(url_for('inicio'))
        flash('Credenciales incorrectas.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))

@app.route('/api/sincronizar_offline', methods=['POST'])
def sincronizar_offline():
    datos = request.get_json()
    if not datos: return jsonify({'status': 'error', 'message': 'JSON vacío'}), 400
    try:
        for item in datos:
            try: lat = float(item.get('latitud') or 0)
            except: lat = 0
            try: lon = float(item.get('longitud') or 0)
            except: lon = 0
            nuevo = Canino(
                nombre=item.get('nombre'), raza=item.get('raza'), edad=item.get('edad'),
                sexo=item.get('sexo'), estado_tenencia=item.get('estado_tenencia'),
                nombre_propietario=item.get('nombre_propietario'), whatsapp_propietario=item.get('whatsapp_propietario'),
                estado_salud=item.get('estado_salud'), sector=item.get('sector'), latitud=lat, longitud=lon,
                situacion=item.get('situacion', 'Censo Normal'), reportado_por="Sincronizado Offline", foto="",
                esterilizado=item.get('esterilizado') == 'on', desparasitado=item.get('desparasitado') == 'on',
                vacuna_parvovirus=item.get('vacuna_parvovirus') == 'on', vacuna_moquillo=item.get('vacuna_moquillo') == 'on',
                vacuna_triple=item.get('vacuna_triple') == 'on', vacuna_sextuple=item.get('vacuna_sextuple') == 'on',
                vacuna_antirrabica=item.get('vacuna_antirrabica') == 'on'
            )
            db.session.add(nuevo)
        db.session.commit()
        return jsonify({'status': 'exito'})
    except Exception as e:
        db.session.rollback(); return jsonify({'status': 'error', 'message': str(e)}), 500

# ==========================================
# RUTAS PRINCIPALES DEL SISTEMA
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
            whatsapp_propietario=request.form.get('whatsapp_propietario'), estado_salud=request.form.get('estado_salud'), sector=request.form.get('sector'), 
            latitud=lat, longitud=lon, situacion=request.form.get('situacion', 'Censo Normal'), reportado_por=current_user.nombre,
            esterilizado=request.form.get('esterilizado')=='on', desparasitado=request.form.get('desparasitado')=='on', 
            vacuna_parvovirus=request.form.get('vacuna_parvovirus')=='on', vacuna_moquillo=request.form.get('vacuna_moquillo')=='on', 
            vacuna_triple=request.form.get('vacuna_triple')=='on', vacuna_sextuple=request.form.get('vacuna_sextuple')=='on', 
            vacuna_antirrabica=request.form.get('vacuna_antirrabica')=='on'
        )
        db.session.add(nuevo); db.session.commit()
        flash('Registro guardado exitosamente.', 'success'); return redirect(url_for('inicio'))
    
    p = request.args.get('page', 1, type=int); b = request.args.get('buscar')
    q = Canino.query.filter(Canino.nombre.contains(b) | Canino.nombre_propietario.contains(b) | Canino.sector.contains(b)) if b else Canino.query
    paginacion = q.order_by(Canino.id.desc()).paginate(page=p, per_page=10, error_out=False)
    return render_template('index.html', caninos=paginacion, busqueda=b, carrusel=Carrusel.query.all())

# ==========================================
# NUEVO: MÓDULO KARDEX (INVENTARIO)
# ==========================================
@app.route('/inventario', methods=['GET', 'POST'])
@login_required
def inventario():
    if current_user.rol != 'Admin': return redirect(url_for('inicio'))
    
    if request.method == 'POST':
        # Registrar un nuevo medicamento en el sistema
        nuevo_med = Medicamento(
            nombre=request.form.get('nombre'),
            stock=int(request.form.get('stock') or 0),
            unidad=request.form.get('unidad')
        )
        db.session.add(nuevo_med)
        db.session.commit()
        flash('Medicamento registrado correctamente.', 'success')
        return redirect(url_for('inventario'))
        
    medicamentos = Medicamento.query.all()
    return render_template('inventario.html', medicamentos=medicamentos)

@app.route('/inventario/actualizar/<int:id>', methods=['POST'])
@login_required
def actualizar_inventario(id):
    if current_user.rol != 'Admin': return redirect(url_for('inicio'))
    med = Medicamento.query.get_or_404(id)
    cantidad = int(request.form.get('cantidad_sumar') or 0)
    med.stock += cantidad
    db.session.commit()
    flash(f'Stock de {med.nombre} actualizado.', 'success')
    return redirect(url_for('inventario'))

@app.route('/inventario/eliminar/<int:id>')
@login_required
def eliminar_medicamento(id):
    if current_user.rol != 'Admin': return redirect(url_for('inicio'))
    med = Medicamento.query.get_or_404(id)
    db.session.delete(med); db.session.commit()
    flash('Medicamento eliminado del sistema.', 'success')
    return redirect(url_for('inventario'))

# ==========================================
# RUTAS DE CONSULTA MÉDICA ACTUALIZADA
# ==========================================
@app.route('/historial/<int:id>', methods=['GET', 'POST'])
@login_required
def historial(id):
    p = Canino.query.get_or_404(id)
    
    if request.method == 'POST':
        tratamiento_base = request.form.get('tratamiento')
        
        # Logica del Kardex
        med_id = request.form.get('medicamento_id')
        cantidad_usada = int(request.form.get('cantidad_usada') or 0)
        
        if med_id and cantidad_usada > 0:
            med = Medicamento.query.get(med_id)
            if med:
                if med.stock >= cantidad_usada:
                    # Descontar del inventario
                    med.stock -= cantidad_usada
                    # Documentar automáticamente en el historial
                    tratamiento_base += f"\n[INVENTARIO]: Se aplicaron {cantidad_usada} {med.unidad} de {med.nombre}."
                else:
                    flash(f'Error: No hay suficiente stock de {med.nombre}. Quedan {med.stock} {med.unidad}.', 'danger')
                    return redirect(url_for('historial', id=p.id))

        nueva_consulta = Consulta(
            peso=request.form.get('peso'), 
            sintomas=request.form.get('sintomas'), 
            diagnostico=request.form.get('diagnostico'), 
            tratamiento=tratamiento_base, 
            canino_id=p.id
        )
        db.session.add(nueva_consulta)
        db.session.commit()
        flash('Consulta guardada y stock actualizado correctamente.', 'success')
        return redirect(url_for('historial', id=p.id))
        
    # Enviamos solo los medicamentos que tengan stock disponible
    medicamentos_disponibles = Medicamento.query.filter(Medicamento.stock > 0).all()
    return render_template('historial.html', perro=p, medicamentos=medicamentos_disponibles)

@app.route('/historial/eliminar/<int:id>')
@login_required
def eliminar_consulta(id):
    c = Consulta.query.get_or_404(id); c_id = c.canino_id; db.session.delete(c); db.session.commit(); return redirect(url_for('historial', id=c_id))

# ==========================================
# RESTO DE TUS RUTAS SIN MODIFICAR
# ==========================================
@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    p = Canino.query.get_or_404(id)
    if request.method == 'POST':
        p.nombre = request.form.get('nombre'); p.raza = request.form.get('raza'); db.session.commit(); return redirect(url_for('inicio'))
    return render_template('editar.html', perro=p)

@app.route('/eliminar/<int:id>')
@login_required
def eliminar(id): db.session.delete(Canino.query.get_or_404(id)); db.session.commit(); return redirect(url_for('inicio'))

@app.route('/alertas')
@login_required
def alertas(): return render_template('alertas.html', alertas=Vacuna.query.all(), hoy=date.today(), perros=Canino.query.all())

@app.route('/citas')
@login_required
def gestion_citas(): return render_template('citas.html', citas=Cita.query.all(), perros=Canino.query.all())

@app.route('/reportes')
@login_required
def reportes(): return render_template('reportes.html', total_perros=Canino.query.count(), vacunas_labels=[], vacunas_counts=[])

@app.route('/mapa_general')
@login_required
def mapa_general(): return render_template('mapa.html', perros=Canino.query.filter(Canino.latitud != 0).all())

@app.route('/carnet/<int:id>')
@login_required
def carnet(id): return render_template('carnet.html', perro=Canino.query.get_or_404(id))

@app.route('/rescate/<int:id>', methods=['GET', 'POST'])
def rescate(id):
    p = Canino.query.get_or_404(id)
    if request.method == 'POST':
        d = request.get_json(); p.latitud = d.get('lat'); p.longitud = d.get('lon'); p.situacion = '¡ALERTA QR!'; db.session.commit(); return jsonify({"status": "exito"})
    return render_template('rescate.html', perro=p)

if __name__ == '__main__': app.run(debug=True)