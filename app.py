from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from datetime import datetime, date
import json, os, io
from functools import wraps
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import requests

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'cartera-mora-secret-2024'

# --- Config ---
APP_PASSWORD = os.environ.get('APP_PASSWORD', 'admin123')
EMAIL_DESTINO = os.environ.get('EMAIL_DESTINO', '')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
EMAIL_FROM = os.environ.get('EMAIL_FROM', 'onboarding@resend.dev')

DATA_DIR = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
DATA_FILE = os.path.join(DATA_DIR, 'cartera.json')

ESTADOS = ['PREJUDICIAL', 'JUICIO', 'SENTENCIA', 'EJECUCION', 'COBRADO/CERRADO']
PERSPECTIVAS = ['Alta', 'Media', 'Baja', 'Incobrable', '']

# --- Calculo de intereses ---
def calcular_interes_factura(monto, fecha_mora_str, tasa_anual):
    """Interés simple: monto * tasa_diaria * dias"""
    if not fecha_mora_str or not monto or not tasa_anual:
        return 0
    try:
        fecha_mora = datetime.strptime(fecha_mora_str, '%Y-%m-%d').date()
        hoy = date.today()
        dias = (hoy - fecha_mora).days
        if dias <= 0:
            return 0
        tasa_diaria = tasa_anual / 365 / 100
        return round(monto * tasa_diaria * dias)
    except Exception:
        return 0

def calcular_totales_cliente(cliente, tasa_anual):
    """Calcula monto_original e intereses sumando todas las facturas"""
    facturas = cliente.get('facturas', [])
    if not facturas:
        return cliente.get('monto_original', 0) or 0, cliente.get('intereses', 0) or 0
    monto_total = sum(f.get('monto', 0) or 0 for f in facturas)
    intereses_total = sum(calcular_interes_factura(f.get('monto', 0), f.get('fecha_mora', ''), tasa_anual) for f in facturas)
    return monto_total, intereses_total

# --- Persistencia ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Migracion: agregar campos nuevos si no existen
            if 'tasa_bna' not in data:
                data['tasa_bna'] = 60.0
            if 'facturas' not in data:
                data['facturas'] = {}
            return data
    return cargar_datos_iniciales()

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def cargar_datos_iniciales():
    clientes = [
        {"id": 1, "razon_social": "SAVEDRA NATALIA", "monto_original": 9318447, "intereses": 0, "estado": "PREJUDICIAL", "sub_estado": "ACTUAL", "fecha_gestion": "", "observaciones": "", "perspectiva": "Alta"},
        {"id": 2, "razon_social": "TRANSPORTES LUNA", "monto_original": 1600000, "intereses": 0, "estado": "PREJUDICIAL", "sub_estado": "ACTUAL", "fecha_gestion": "", "observaciones": "", "perspectiva": "Alta"},
        {"id": 3, "razon_social": "LA MARTINA AGROSERVICIOS", "monto_original": 11837000, "intereses": 0, "estado": "JUICIO", "sub_estado": "SENTENCIA", "fecha_gestion": "", "observaciones": "", "perspectiva": "Media"},
        {"id": 4, "razon_social": "TRES DECIMA SAS", "monto_original": 17000000, "intereses": 0, "estado": "PREJUDICIAL", "sub_estado": "ACTUAL", "fecha_gestion": "", "observaciones": "", "perspectiva": "Alta"},
        {"id": 5, "razon_social": "LA COLO AGROPECUARIA", "monto_original": 46167077, "intereses": 0, "estado": "JUICIO", "sub_estado": "PENAL", "fecha_gestion": "", "observaciones": "", "perspectiva": "Incobrable"},
        {"id": 6, "razon_social": "KANCHEFF ALFREDO", "monto_original": 11747356, "intereses": 0, "estado": "JUICIO", "sub_estado": "PENAL", "fecha_gestion": "", "observaciones": "", "perspectiva": "Media"},
        {"id": 7, "razon_social": "INDUSTRIAS SANTA BARBARA", "monto_original": 0, "intereses": 0, "estado": "PREJUDICIAL", "sub_estado": "", "fecha_gestion": "", "observaciones": "23.000 LITROS", "perspectiva": ""},
        {"id": 8, "razon_social": "MARTINEZ SANTAMARINA SEBASTIAN", "monto_original": 31304298, "intereses": 0, "estado": "JUICIO", "sub_estado": "SENTENCIA", "fecha_gestion": "", "observaciones": "", "perspectiva": "Incobrable"},
        {"id": 9, "razon_social": "AGUABLANCA SAS", "monto_original": 31304298, "intereses": 0, "estado": "JUICIO", "sub_estado": "SENTENCIA", "fecha_gestion": "", "observaciones": "", "perspectiva": "Incobrable"},
        {"id": 10, "razon_social": "ARIEL GARCIA", "monto_original": 1500000, "intereses": 0, "estado": "MEDIACION", "sub_estado": "MEDIACION CON ACUERDO", "fecha_gestion": "", "observaciones": "", "perspectiva": "Baja"},
        {"id": 11, "razon_social": "NOBEN SRL", "monto_original": 71200000, "intereses": 0, "estado": "PREJUDICIAL", "sub_estado": "", "fecha_gestion": "", "observaciones": "", "perspectiva": ""},
        {"id": 12, "razon_social": "MONTEROS LEMON SAS", "monto_original": 69299410, "intereses": 0, "estado": "PREJUDICIAL", "sub_estado": "", "fecha_gestion": "", "observaciones": "", "perspectiva": ""},
        {"id": 13, "razon_social": "VISION EMPRESARIAL NOROESTE SRL", "monto_original": 27623401, "intereses": 0, "estado": "JUICIO", "sub_estado": "EJECUCION DE SENTENCIA", "fecha_gestion": "", "observaciones": "", "perspectiva": "Media"},
        {"id": 14, "razon_social": "NIEVAS NELSON", "monto_original": 3827682, "intereses": 0, "estado": "JUICIO", "sub_estado": "SENTENCIA", "fecha_gestion": "", "observaciones": "", "perspectiva": "Media"},
    ]
    data = {"clientes": clientes, "historial": {}, "facturas": {}, "tasa_bna": 60.0, "next_id": 15}
    save_data(data)
    return data

# --- Auth ---
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# --- Email ---
def enviar_email_cambio_estado(cliente, estado_anterior, estado_nuevo):
    if not RESEND_API_KEY or not EMAIL_DESTINO:
        return
    try:
        fecha = datetime.now().strftime('%d/%m/%Y %H:%M')
        requests.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {RESEND_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'from': EMAIL_FROM,
                'to': [EMAIL_DESTINO],
                'subject': f'[Cartera Mora] Cambio de estado: {cliente["razon_social"]}',
                'html': f"""
                <h2>Cambio de estado en cartera</h2>
                <p><strong>Cliente:</strong> {cliente['razon_social']}</p>
                <p><strong>Estado anterior:</strong> {estado_anterior}</p>
                <p><strong>Estado nuevo:</strong> {estado_nuevo}</p>
                <p><strong>Fecha:</strong> {fecha}</p>
                """
            },
            timeout=10
        )
    except Exception:
        pass

# --- Rutas ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == APP_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        error = 'Contraseña incorrecta'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    data = load_data()
    return render_template('index.html', clientes=data['clientes'], estados=ESTADOS, perspectivas=PERSPECTIVAS)

@app.route('/api/config', methods=['GET'])
@login_required
def get_config():
    data = load_data()
    return jsonify({'tasa_bna': data.get('tasa_bna', 60.0)})

@app.route('/api/config', methods=['PUT'])
@login_required
def update_config():
    data = load_data()
    body = request.json
    if 'tasa_bna' in body:
        data['tasa_bna'] = float(body['tasa_bna'])
    save_data(data)
    return jsonify({'tasa_bna': data['tasa_bna']})

@app.route('/api/clientes', methods=['GET'])
@login_required
def get_clientes():
    data = load_data()
    tasa = data.get('tasa_bna', 60.0)
    clientes = []
    for c in data['clientes']:
        c2 = dict(c)
        facturas = data.get('facturas', {}).get(str(c['id']), [])
        c2['facturas'] = facturas
        if facturas:
            mo, int_ = calcular_totales_cliente({'facturas': facturas}, tasa)
            c2['monto_original'] = mo
            c2['intereses'] = int_
        clientes.append(c2)
    return jsonify(clientes)

@app.route('/api/clientes', methods=['POST'])
@login_required
def add_cliente():
    data = load_data()
    nuevo = request.json
    nuevo['id'] = data['next_id']
    nuevo.setdefault('monto_original', 0)
    nuevo.setdefault('intereses', 0)
    nuevo.setdefault('estado', 'PREJUDICIAL')
    nuevo.setdefault('sub_estado', '')
    nuevo.setdefault('fecha_gestion', '')
    nuevo.setdefault('observaciones', '')
    nuevo.setdefault('perspectiva', '')
    data['clientes'].append(nuevo)
    data['next_id'] += 1
    data['historial'][str(nuevo['id'])] = []
    data['facturas'][str(nuevo['id'])] = []
    save_data(data)
    return jsonify(nuevo)

@app.route('/api/clientes/<int:cid>', methods=['PUT'])
@login_required
def update_cliente(cid):
    data = load_data()
    updates = request.json
    for i, c in enumerate(data['clientes']):
        if c['id'] == cid:
            estado_anterior = c.get('estado', '')
            estado_nuevo = updates.get('estado', estado_anterior)
            data['clientes'][i].update(updates)
            save_data(data)
            if estado_anterior != estado_nuevo:
                enviar_email_cambio_estado(data['clientes'][i], estado_anterior, estado_nuevo)
            return jsonify(data['clientes'][i])
    return jsonify({'error': 'No encontrado'}), 404

@app.route('/api/clientes/<int:cid>', methods=['DELETE'])
@login_required
def delete_cliente(cid):
    data = load_data()
    data['clientes'] = [c for c in data['clientes'] if c['id'] != cid]
    data['historial'].pop(str(cid), None)
    data['facturas'].pop(str(cid), None)
    save_data(data)
    return jsonify({'ok': True})

@app.route('/api/historial/<int:cid>', methods=['GET'])
@login_required
def get_historial(cid):
    data = load_data()
    return jsonify(data['historial'].get(str(cid), []))

@app.route('/api/historial/<int:cid>', methods=['POST'])
@login_required
def add_historial(cid):
    data = load_data()
    entrada = request.json
    entrada['fecha'] = datetime.now().strftime('%d/%m/%Y %H:%M')
    if str(cid) not in data['historial']:
        data['historial'][str(cid)] = []
    data['historial'][str(cid)].insert(0, entrada)
    for c in data['clientes']:
        if c['id'] == cid:
            c['fecha_gestion'] = datetime.now().strftime('%d/%m/%Y')
            break
    save_data(data)
    return jsonify(entrada)

# --- Facturas ---
@app.route('/api/facturas/<int:cid>', methods=['GET'])
@login_required
def get_facturas(cid):
    data = load_data()
    tasa = data.get('tasa_bna', 60.0)
    facturas = data.get('facturas', {}).get(str(cid), [])
    # Agregar interes calculado a cada factura
    for f in facturas:
        f['interes_calculado'] = calcular_interes_factura(f.get('monto', 0), f.get('fecha_mora', ''), tasa)
        f['total'] = (f.get('monto', 0) or 0) + f['interes_calculado']
    return jsonify(facturas)

@app.route('/api/facturas/<int:cid>', methods=['POST'])
@login_required
def add_factura(cid):
    data = load_data()
    tasa = data.get('tasa_bna', 60.0)
    factura = request.json
    factura['id'] = datetime.now().strftime('%Y%m%d%H%M%S%f')
    factura.setdefault('numero', '')
    factura.setdefault('monto', 0)
    factura.setdefault('fecha_mora', '')
    factura.setdefault('descripcion', '')
    if str(cid) not in data.get('facturas', {}):
        data.setdefault('facturas', {})[str(cid)] = []
    data['facturas'][str(cid)].append(factura)
    # Recalcular totales del cliente
    facturas = data['facturas'][str(cid)]
    mo, int_ = calcular_totales_cliente({'facturas': facturas}, tasa)
    for c in data['clientes']:
        if c['id'] == cid:
            c['monto_original'] = mo
            c['intereses'] = int_
            break
    save_data(data)
    factura['interes_calculado'] = calcular_interes_factura(factura['monto'], factura['fecha_mora'], tasa)
    factura['total'] = factura['monto'] + factura['interes_calculado']
    return jsonify(factura)

@app.route('/api/facturas/<int:cid>/<fid>', methods=['DELETE'])
@login_required
def delete_factura(cid, fid):
    data = load_data()
    tasa = data.get('tasa_bna', 60.0)
    facturas = data.get('facturas', {}).get(str(cid), [])
    data['facturas'][str(cid)] = [f for f in facturas if f.get('id') != fid]
    # Recalcular totales
    facturas_new = data['facturas'][str(cid)]
    mo, int_ = calcular_totales_cliente({'facturas': facturas_new}, tasa)
    for c in data['clientes']:
        if c['id'] == cid:
            c['monto_original'] = mo
            c['intereses'] = int_
            break
    save_data(data)
    return jsonify({'ok': True})

@app.route('/api/resumen', methods=['GET'])
@login_required
def get_resumen():
    data = load_data()
    tasa = data.get('tasa_bna', 60.0)
    resumen = {}
    todos = ESTADOS + ['MEDIACION']
    for estado in todos:
        cs = [c for c in data['clientes'] if c['estado'] == estado]
        monto_total = 0
        adeudado_total = 0
        for c in cs:
            facturas = data.get('facturas', {}).get(str(c['id']), [])
            if facturas:
                mo, int_ = calcular_totales_cliente({'facturas': facturas}, tasa)
            else:
                mo = c.get('monto_original', 0) or 0
                int_ = c.get('intereses', 0) or 0
            monto_total += mo
            adeudado_total += mo + int_
        resumen[estado] = {'cantidad': len(cs), 'monto_original': monto_total, 'total_adeudado': adeudado_total}
    return jsonify(resumen)

@app.route('/exportar/pdf')
@login_required
def exportar_pdf():
    data = load_data()
    tasa = data.get('tasa_bna', 60.0)
    clientes = data['clientes']

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('titulo', parent=styles['Title'],
                                   fontSize=16, textColor=colors.HexColor('#1a2e4a'), spaceAfter=4)
    subtitulo_style = ParagraphStyle('sub', parent=styles['Normal'],
                                      fontSize=9, textColor=colors.HexColor('#64748b'), spaceAfter=12)
    cell_style = ParagraphStyle('cell', fontSize=7.5, leading=10)

    def fmt(v): return f"$ {v:,.0f}".replace(',', '.') if v else '-'

    elements = []
    elements.append(Paragraph("INFORME DE ESTADO DE DEUDA — CARTERA EN MORA", titulo_style))
    elements.append(Paragraph(f"Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')} hs · Tasa BNA: {tasa}% anual · Montos en ARS", subtitulo_style))

    headers = ['N°', 'Cliente / Razón Social', 'Monto Original', 'Intereses', 'Total Adeudado', 'Estado', 'Última Gestión', 'Perspectiva', 'Observaciones']
    filas = [headers]
    total_mo = total_int = 0
    for i, c in enumerate(clientes):
        facturas = data.get('facturas', {}).get(str(c['id']), [])
        if facturas:
            mo, int_ = calcular_totales_cliente({'facturas': facturas}, tasa)
        else:
            mo = c.get('monto_original', 0) or 0
            int_ = c.get('intereses', 0) or 0
        total = mo + int_
        total_mo += mo
        total_int += int_
        filas.append([
            str(i + 1),
            Paragraph(c.get('razon_social', ''), cell_style),
            fmt(mo), fmt(int_), fmt(total),
            c.get('estado', ''),
            c.get('fecha_gestion', '') or '-',
            c.get('perspectiva', '') or '-',
            Paragraph(c.get('observaciones', '') or '-', cell_style),
        ])

    filas.append(['', 'TOTALES', fmt(total_mo), fmt(total_int), fmt(total_mo + total_int), '', '', '', ''])

    col_widths = [1*cm, 5.5*cm, 3*cm, 2.5*cm, 3*cm, 3*cm, 2.8*cm, 2.2*cm, 4.5*cm]
    tabla = Table(filas, colWidths=col_widths, repeatRows=1)
    color_header = colors.HexColor('#1a2e4a')
    color_alt = colors.HexColor('#f0f4f8')
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), color_header),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 7.5),
        ('ROWBACKGROUND', (0, 1), (-1, -2), [colors.white, color_alt]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('ALIGN', (2, 1), (4, -1), 'RIGHT'),
    ]))
    elements.append(tabla)

    doc.build(elements)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True,
                     download_name=f'cartera_mora_{datetime.now().strftime("%Y%m%d")}.pdf')

if __name__ == '__main__':
    app.run(debug=True)
