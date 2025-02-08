from flask import Flask, render_template, request, jsonify, send_from_directory
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
    {"id": i, "status": "kosong", "count": 0} for i in range(201, 209)
]

@app.route('/')
def index():
    """
    Halaman utama yang menampilkan daftar kamar beserta QR Code untuk pemindaian.
    """
    table_data = []
    for table in tables:
        qr = qrcode.QRCode()
        qr_data = f"http://192.168.0.11:5000/update_status/{table['id']}"
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
        return f"""
            <script>
                alert("Anda hanya bisa mengscan kamar yang kosong!");
                window.location.href = "../";
            </script>
            """

    if request.method == 'POST':
        if is_admin and request.form.get('reset_kamar'):
            table['status'] = 'kosong'
            table.pop('pelanggan', None)

            return f"""
            <script>
                alert("Kamar {table_id} berhasil dikosongkan!");
                window.location.href = "/update_status/{table_id}?is_admin=true";
            </script>
            """

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

        if request.method == 'POST':
            table['status'] = 'terisi'
            table['count'] += 1  # Menambah jumlah penggunaan kamar

        return render_template('detail_pelanggan.html', table=table)

    pelanggan = table.get('pelanggan', {})
    return render_template('form_input.html', table=table, pelanggan=pelanggan, is_admin=is_admin)

@app.route('/cancel_menginap/<int:table_id>', methods=['GET'])
def cancel_menginap(table_id):
    """
    Endpoint untuk membatalkan menginap dan mengosongkan kamar.
    """
    table = next((t for t in tables if t['id'] == table_id), None)
    if not table:
        return jsonify({"success": False, "message": "Kamar tidak ditemukan"}), 404

    if table['status'] == 'kosong':
        return jsonify({"success": False, "message": "Kamar sudah kosong"}), 400

    table['status'] = 'kosong'
    table.pop('pelanggan', None)
    table['count'] = 0

    return f"""
            <script>
                alert("Kamar {table_id}, Order Berhasil Dibatalkan");
                window.location.href = "/update_status/{table_id}?is_admin=true";
            </script>
            """

@app.route('/get_table_details/<int:table_id>', methods=['GET'])
def get_table_details(table_id):
    """
    API untuk mendapatkan detail kamar berdasarkan ID.
    """
    table = next((t for t in tables if t['id'] == table_id), None)
    if not table or table['status'] == 'kosong':
        return jsonify({"success": False, "message": "Data tidak ditemukan"})

    return jsonify({"success": True, "table": table})

@app.route('/admin')
def admin():
    return render_template('admin.html', tables=tables)

@app.route('/room_usage_data', methods=['GET'])
def room_usage_data():
    """Mengirim data penggunaan kamar dalam format JSON"""
    data = [{"id": table["id"], "count": table["count"]} for table in tables]
    return jsonify(data)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Mengirim file gambar atau dokumen dari folder uploads."""
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except FileNotFoundError:
        abort(404)

@app.route('/uploads/')
def list_uploaded_files():
    """Menampilkan daftar file dalam folder uploads."""
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    file_urls = [f'<a href="/uploads/{file}">{file}</a>' for file in files]
    return "<h2>Daftar File Upload</h2>" + "<br>".join(file_urls)

if __name__ == '__main__':
    app.run(host='192.168.0.11', port=5000, debug=True)
