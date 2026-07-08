import pandas as pd

class Nutrition:
    def __init__(self):
        # Membaca file CSV database gizi
        self.data = pd.read_csv("database/nutrition.csv")

    def get_food(self, food_name):
        # Mengubah ke huruf kecil untuk menghindari case-sensitive
        food_name_lower = food_name.lower()

        # Gunakan pencarian parsial (apakah nama di CSV mengandung kata dari AI atau sebaliknya)
        hasil = self.data[self.data["name"].str.lower().str.contains(food_name_lower, na=False)]

        # Jika tidak ketemu, coba pencarian balik kata per kata
        if hasil.empty:
            for word in food_name_lower.split():
                hasil = self.data[self.data["name"].str.lower().str.contains(word, na=False)]
                if not hasil.empty:
                    break

        if hasil.empty:
            return None

        # Ambil baris pertama hasil pencarian dan ubah ke Dictionary
        return hasil.iloc[0].to_dict()