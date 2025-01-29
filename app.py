from flask import Flask, render_template, request, jsonify
import qrcode
from io import BytesIO
import base64
import os
from werkzeug.utils import secure_filename

# Konfigurasi folder upload dan ekstensi file yang diizinkan
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Fungsi untuk memeriksa apakah file yang diunggah memiliki ekstensi yang diperbolehkan
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Data awal status kamar
tables = [
    {"id": i, "status": "kosong"} for i in range(1, 9)
]

@app.route('/')
def index():
    """
    Halaman utama yang menampilkan daftar kamar beserta QR Code untuk pemindaian.
    """
    table_data = []
    for table in tables:
        qr = qrcode.QRCode()
        qr_data = f"http://192.168.168.19:5000/update_status/{table['id']}"
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = BytesIO()
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_img.save(img, format="PNG")
        img_base64 = base64.b64encode(img.getvalue()).decode('utf-8')
        table_data.append({"table": table, "qr": img_base64})
    return render_template('index.html', table_data=table_data)

@app.route('/get_status', methods=['GET'])
def get_status():
    """
    API untuk mendapatkan status semua kamar.
    """
    for table in tables:
        table['show_button'] = table['status'] == 'terisi'
    return jsonify({"tables": tables})

@app.route('/update_status/<int:table_id>', methods=['GET', 'POST'])
def update_status(table_id):
    """
    Endpoint untuk memperbarui status kamar.
    - User biasa hanya bisa scan kamar yang kosong.
    - Admin dapat melihat detail dan mengosongkan kamar yang terisi.
    """
    table = next((t for t in tables if t['id'] == table_id), None)
    if not table:
        return jsonify({"success": False, "message": "Kamar tidak ditemukan"}), 404

    is_admin = request.args.get('is_admin', 'false').lower() == 'true'

    if table['status'] == 'terisi' and not is_admin:
        return jsonify({"success": False, "message": "Anda hanya dapat menscan kamar yang kosong"}), 403

    if request.method == 'POST':
        if is_admin and request.form.get('reset_kamar'):
            table['status'] = 'kosong'
            table.pop('pelanggan', None)
            return jsonify({"success": True, "message": f"Kamar {table_id} berhasil dikosongkan"}), 200

        nama_pelanggan = request.form.get('nama_pelanggan')
        nomor_telepon = request.form.get('nomor_telepon')
        check_in = request.form.get('check_in')
        check_out = request.form.get('check_out')
        metode_pembayaran = request.form.get('metode_pembayaran')
        file = request.files.get('bukti_pembayaran')

        if not all([nama_pelanggan, nomor_telepon, check_in, check_out, metode_pembayaran]):
            return jsonify({"success": False, "message": "Data tidak lengkap"}), 400

        if not file or not allowed_file(file.filename):
            return jsonify({"success": False, "message": "File tidak valid"}), 400

        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        table['status'] = 'terisi'
        table['pelanggan'] = {
            "nama": nama_pelanggan,
            "telepon": nomor_telepon,
            "check_in": check_in,
            "check_out": check_out,
            "metode_pembayaran": metode_pembayaran,
            "bukti_pembayaran": filename
        }

        return render_template('detail_pelanggan.html', table=table)

    pelanggan = table.get('pelanggan', {})
    return render_template('form_input.html', table=table, pelanggan=pelanggan, is_admin=is_admin)

@app.route('/get_table_details/<int:table_id>', methods=['GET'])
def get_table_details(table_id):
    """
    API untuk mendapatkan detail kamar berdasarkan ID.
    """
    table = next((t for t in tables if t['id'] == table_id), None)
    if not table or table['status'] == 'kosong':
        return jsonify({"success": False, "message": "Data tidak ditemukan"})

    return jsonify({"success": True, "table": table})

if __name__ == '__main__':
    app.run(host='192.168.168.19', port=5000, debug=True)
