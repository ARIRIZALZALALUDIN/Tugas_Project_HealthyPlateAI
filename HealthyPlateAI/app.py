import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from ai.detector import detect_food
from ai.nutrition import Nutrition

app = Flask(__name__)
app.secret_key = "kunci_rahasia_healthy_plate_ai" # Diperlukan untuk session login

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db_nutrition = Nutrition()

# ==========================================
# INISIALISASI DATABASE SQLITE
# ==========================================
def init_db():
    conn = sqlite3.connect("database/healthy_plate.db")
    cursor = conn.cursor()
    
    # Tabel User
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            weight REAL DEFAULT 0,
            height REAL DEFAULT 0,
            age INTEGER DEFAULT 25,
            gender TEXT DEFAULT 'Laki-laki',
            target_calories REAL DEFAULT 2000
        )
    """)
    
    # Tabel Riwayat Makanan
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            food_name TEXT,
            calories REAL,
            protein REAL,
            fat REAL,
            carbo REAL,
            image_path TEXT,
            date_added TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect("database/healthy_plate.db")
    conn.row_factory = sqlite3.Row
    return conn

# ==========================================
# ROUTE AUTHENTICATION (LOGIN & REGISTER)
# ==========================================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password)
        
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                         (name, email, hashed_password))
            conn.commit()
            flash("Pendaftaran berhasil! Silakan login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email sudah terdaftar!", "danger")
        finally:
            conn.close()
            
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("dashboard"))
        else:
            flash("Email atau password salah!", "danger")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# ==========================================
# ROUTE DASHBOARD & TARGET KALORI
# ==========================================
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
        
    user_id = session["user_id"]
    conn = get_db_connection()
    
    # Update Profil Fisik & Target Kalori
    if request.method == "POST":
        weight = float(request.form["weight"])
        height = float(request.form["height"])
        age = int(request.form["age"])
        gender = request.form["gender"]
        
        # Rumus Mifflin-St Jeor untuk BMR harian
        if gender == "Laki-laki":
            bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        else:
            bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
            
        target_calories = round(bmr * 1.375) # Asumsi aktivitas ringan
        
        conn.execute("""
            UPDATE users SET weight=?, height=?, age=?, gender=?, target_calories=? WHERE id=?
        """, (weight, height, age, gender, target_calories, user_id))
        conn.commit()
        flash("Profil fisik dan target kalori diperbarui!", "success")
        
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    
    # Ambil Riwayat Makanan beserta Laporan Bulanan (Total Kalori Bulan Ini)
    current_month = datetime.now().strftime("%Y-%m")
    history_rows = conn.execute("SELECT * FROM history WHERE user_id = ? ORDER BY date_added DESC", (user_id,)).fetchall()
    monthly_stats = conn.execute("SELECT SUM(calories) as total_cal, SUM(protein) as total_prot FROM history WHERE user_id = ? AND date_added LIKE ?", (user_id, f"{current_month}%")).fetchone()
    
    conn.close()
    return render_template("dashboard.html", user=user, history=history_rows, stats=monthly_stats)

# ==========================================
# UPLOAD DENGAN LOGIKA REKAM RIWAYAT
# ==========================================
@app.route("/upload", methods=["POST"])
def upload():
    if "image" not in request.files:
        return "Tidak ada gambar yang dipilih."

    file = request.files["image"]
    if file.filename == "":
        return "Silakan pilih gambar."

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    try:
        detected_name = detect_food(filepath)
        food_data = db_nutrition.get_food(detected_name)

        # Jika user sudah login, otomatis simpan ke tabel history database
        if "user_id" in session and food_data:
            conn = get_db_connection()
            conn.execute("""
                INSERT INTO history (user_id, food_name, calories, protein, fat, carbo, image_path, date_added)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session["user_id"], 
                food_data["name"], 
                food_data["calories"], 
                food_data["proteins"], 
                food_data["fat"], 
                food_data["carbohydrate"], 
                filename, 
                datetime.now().strftime("%Y-%m-%d %H:%M")
            ))
            conn.commit()
            conn.close()

        # Ambil batas kalori user (jika login), default 2000 jika guest
        user_target = 2000
        if "user_id" in session:
            conn = get_db_connection()
            u = conn.execute("SELECT target_calories FROM users WHERE id=?", (session["user_id"],)).fetchone()
            user_target = u["target_calories"] if u else 2000
            conn.close()

        return render_template(
            "result.html",
            image=filename,
            detected=detected_name,
            food=food_data,
            target_calories=user_target
        )
    except Exception as e:
        return f"Terjadi kesalahan saat memproses gambar: {str(e)}"

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

if __name__ == "__main__":
    app.run(debug=True)