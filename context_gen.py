import os

# Файлы и папки, которые мы ИГНОРИРУЕМ (безопасность + мусор)
IGNORE_DIRS = {'.git', '__pycache__', 'venv', '.streamlit', 'env'}
IGNORE_FILES = {
    'poetry.lock', 'package-lock.json', '.DS_Store', 
    'context_gen.py', '_project_context.txt', # не включать сам себя и выходной файл
    'README.md', 'requirements.txt'
}
# Расширения файлов, которые нам нужны для контекста
INCLUDE_EXTS = {'.py', '.css', '.toml', '.sql', '.md'}

OUTPUT_FILE = "_project_context.txt"

def collect_code():
    with open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:
        outfile.write(f"# SNAPSHOT OF VYUD AI PROJECT\n")
        outfile.write(f"# Generated via context_gen.py\n\n")
        
        for root, dirs, files in os.walk("."):
            # Фильтрация папок
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file in files:
                if file in IGNORE_FILES:
                    continue
                
                _, ext = os.path.splitext(file)
                if ext in INCLUDE_EXTS or file == 'Dockerfile': # Если используем Docker
                    file_path = os.path.join(root, file)
                    
                    # Пропускаем секреты, если вдруг они не в .streamlit (на всякий случай)
                    if "secret" in file.lower() and "example" not in file.lower():
                        print(f"⚠️ SKIPPING potential secret file: {file_path}")
                        continue

                    outfile.write(f"\n{'='*20}\nFILE: {file_path}\n{'='*20}\n")
                    try:
                        with open(file_path, "r", encoding="utf-8") as infile:
                            outfile.write(infile.read())
                    except Exception as e:
                        outfile.write(f"# Error reading file: {e}")

    print(f"✅ Готово! Весь код собран в {OUTPUT_FILE}. Перетащи его в Gemini.")

if __name__ == "__main__":
    collect_code()