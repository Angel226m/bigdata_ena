import chardet
import pandas as pd

file_path = "data/01_Cap100_1_0.csv"

# Detectar encoding
with open(file_path, "rb") as f:
    raw_data = f.read(100000)  # solo los primeros 100KB
    result = chardet.detect(raw_data)
    encoding_detected = result['encoding']
    print(f"Encoding detectado: {encoding_detected}")

# Cargar el CSV con el encoding correcto
try:
    df = pd.read_csv(file_path, encoding=encoding_detected, low_memory=False)
    print("✅ Archivo cargado correctamente")
    print("Columnas disponibles:", df.columns.tolist())
except Exception as e:
    print(f"❌ Error al leer CSV: {e}")
