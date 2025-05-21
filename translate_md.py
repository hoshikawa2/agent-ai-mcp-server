import requests
import os

# === CONFIGURAÇÕES ===
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY") or "475bc397-3d8d-4e57-8d01-cb9c30b5afce:fx"
INPUT_FILE = "./README.md"           # Caminho do arquivo de entrada
OUTPUT_FILE = "./README_en.md"       # Caminho do arquivo traduzido
SOURCE_LANG = "PT"                 # Idioma original: Português
TARGET_LANG = "EN"                 # Idioma alvo: Inglês

# === LÊ O ARQUIVO MARKDOWN ===
with open(INPUT_FILE, "r", encoding="utf-8") as file:
    content = file.read()

# === TRADUZ VIA API DEEPL ===
print("📤 Traduzindo via DeepL...")
response = requests.post(
    "https://api-free.deepl.com/v2/translate",
    data={
        "auth_key": DEEPL_API_KEY,
        "text": content,
        "source_lang": SOURCE_LANG,
        "target_lang": TARGET_LANG,
        "tag_handling": "xml"  # ajuda a preservar marcações
    }
)

if response.status_code == 200:
    translated_text = response.json()["translations"][0]["text"]
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out_file:
        out_file.write(translated_text)
    print(f"✅ Tradução concluída. Arquivo salvo em: {OUTPUT_FILE}")
else:
    print(f"❌ Erro na tradução: {response.status_code} - {response.text}")