import os
from PIL import Image
from dotenv import load_dotenv
from google import genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

def detect_food(image_path):
    """
    Mengirim gambar makanan ke Gemini AI
    """
    image = Image.open(image_path)

    # Prompt dioptimalkan agar output string-nya bersih dan pas dengan database
    prompt = """
    Kamu adalah AI pendeteksi makanan.
    Lihat gambar berikut.
    Jawab HANYA nama makanannya saja secara singkat dan umum dalam bahasa Indonesia tanpa tanda baca tambahan.
    
    Contoh:
    Ayam
    Nasi Goreng
    Bakso
    Soto Ayam
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt, image]
    )

    return response.text.strip()