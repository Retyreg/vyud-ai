import streamlit as st
import openai
import os
import tempfile
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_parse import LlamaParse
from dotenv import load_dotenv
from supabase import create_client, Client
import moviepy.editor as mp  # Для видео

# --- 1. НАСТРОЙКИ И КЛЮЧИ ---
st.set_page_config(page_title="Vyud AI - Генератор Курсов", page_icon="🎓", layout="wide")

# Загрузка секретов (Приоритет: .streamlit/secrets.toml)
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    LLAMA_CLOUD_API_KEY = st.secrets["LLAMA_CLOUD_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error("❌ Не найдены API ключи в secrets.toml!")
    st.stop()

# Инициализация клиентов
openai.api_key = OPENAI_API_KEY
os.environ["LLAMA_CLOUD_API_KEY"] = LLAMA_CLOUD_API_KEY
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. ФУНКЦИИ (Supabase, HTML, Video) ---

def login_user(email):
    """Вход или регистрация через Supabase"""
    email = email.lower().strip()
    # Проверка юзера
    try:
        response = supabase.table('users_credits').select("*").eq('email', email).execute()
        if len(response.data) > 0:
            # Юзер есть
            user = response.data[0]
            st.session_state['user_id'] = user['id']
            st.session_state['credits'] = user['credits']
            st.session_state['email'] = email
            st.success(f"С возвращением! Баланс: {user['credits']} кредитов.")
        else:
            # Регистрация нового
            new_user = {"email": email, "credits": 3}
            data = supabase.table('users_credits').insert(new_user).execute()
            if len(data.data) > 0:
                user = data.data[0]
                st.session_state['user_id'] = user['id']
                st.session_state['credits'] = user['credits']
                st.session_state['email'] = email
                st.success("Регистрация успешна! Вам начислено 3 кредита.")
    except Exception as e:
        st.error(f"Ошибка подключения к базе: {e}")

def decrement_credit():
    """Списание кредита"""
    if st.session_state.get('user_id'):
        uid = st.session_state['user_id']
        current = st.session_state['credits']
        if current > 0:
            new_val = current - 1
            supabase.table('users_credits').update({'credits': new_val}).eq('id', uid).execute()
            st.session_state['credits'] = new_val
            return True
    return False

def generate_html_quiz(quiz_data):
    """Генерация HTML файла с тестом"""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Интерактивный Тест</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f4f4f9; }}
            .quiz-container {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; }}
            .question {{ margin-bottom: 20px; padding: 15px; border-bottom: 1px solid #eee; }}
            .options {{ display: flex; flex-direction: column; gap: 10px; margin-top: 10px; }}
            button {{ padding: 10px 15px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; text-align: left; }}
            button:hover {{ background-color: #0056b3; }}
            button.correct {{ background-color: #28a745 !important; }}
            button.wrong {{ background-color: #dc3545 !important; }}
            .feedback {{ margin-top: 10px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="quiz-container">
            <h1>🎓 Тест по материалу</h1>
            <div id="quiz"></div>
        </div>

        <script>
            const quizData = {quiz_data};

            const quizContainer = document.getElementById('quiz');

            function loadQuiz() {{
                let html = '';
                quizData.forEach((item, index) => {{
                    html += `<div class="question">
                        <h3>Вопрос ${{index + 1}}: ${{item.question}}</h3>
                        <div class="options">`;
                    
                    item.options.forEach(option => {{
                        html += `<button onclick="checkAnswer(this, '${{item.answer}}')">${{option}}</button>`;
                    }});

                    html += `</div><div class="feedback"></div></div>`;
                }});
                quizContainer.innerHTML = html;
            }}

            function checkAnswer(btn, correctAnswer) {{
                const parent = btn.parentElement;
                const feedback = parent.nextElementSibling;
                const selected = btn.innerText;

                // Блокируем кнопки
                const buttons = parent.querySelectorAll('button');
                buttons.forEach(b => b.disabled = true);

                if (selected.includes(correctAnswer) || selected === correctAnswer) {{
                    btn.classList.add('correct');
                    feedback.style.color = 'green';
                    feedback.innerText = "Верно! 🎉";
                }} else {{
                    btn.classList.add('wrong');
                    buttons.forEach(b => {{
                        if (b.innerText.includes(correctAnswer) || b.innerText === correctAnswer) {{
                            b.classList.add('correct');
                        }}
                    }});
                    feedback.style.color = 'red';
                    feedback.innerText = "Ошибка. Правильный ответ: " + correctAnswer;
                }}
            }}

            loadQuiz();
        </script>
    </body>
    </html>
    """
    return html_content

def process_video_audio(file_path):
    """Извлечение текста из Видео/Аудио через OpenAI Whisper"""
    try:
        # Если это видео, вытаскиваем аудио
        if file_path.endswith(('.mp4', '.mov', '.avi', '.mkv')):
            audio_path = file_path.replace(file_path.split('.')[-1], 'mp3')
            video = mp.VideoFileClip(file_path)
            video.audio.write_audiofile(audio_path)
            file_to_transcribe = audio_path
        else:
            file_to_transcribe = file_path

        # Транскрибация
        with open(file_to_transcribe, "rb") as audio_file:
            transcript = openai.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
        return transcript.text
    except Exception as e:
        st.error(f"Ошибка обработки медиа: {e}")
        return None

# --- 3. ИНТЕРФЕЙС ---

# Сайдбар - Вход
with st.sidebar:
    st.title("🔐 Профиль")
    if 'email' not in st.session_state:
        email_input = st.text_input("Ваш Email")
        if st.button("Войти / Регистрация"):
            if "@" in email_input:
                login_user(email_input)
            else:
                st.warning("Некорректный Email")
        st.caption("Новым пользователям: 3 генерации бесплатно.")
    else:
        st.write(f"👤 **{st.session_state['email']}**")
        st.write(f"💳 Кредитов: **{st.session_state['credits']}**")
        if st.button("Выйти"):
            del st.session_state['email']
            del st.session_state['credits']
            st.rerun()

    st.markdown("---")
    st.header("⚙️ Настройки")
    language = st.selectbox("Язык теста:", ["Русский", "English", "Español", "Deutsch"])
    difficulty = st.radio("Сложность:", ["Easy (Факты)", "Medium (Понимание)", "Hard (Кейсы)"])
    num_questions = st.slider("Количество вопросов:", 3, 10, 5)

# Основной экран
st.title("🎓 Vyud AI")
st.markdown("### Загрузи материал (PDF, Видео, Аудио) и получи готовый тест.")

# Логика доступа
if 'credits' not in st.session_state or st.session_state['credits'] <= 0:
    st.warning("⚠️ Для генерации войдите в систему и убедитесь, что есть кредиты.")
    access_granted = False
else:
    access_granted = True

uploaded_file = st.file_uploader("Перетащите файл сюда", type=['pdf', 'mp4', 'mov', 'avi', 'mp3'])

if uploaded_file and access_granted:
    if st.button(f"🚀 Создать Тест (1 кредит)"):
        with st.spinner("⏳ Обработка..."):
            try:
                # 1. Списание кредита
                if not decrement_credit():
                    st.error("Не удалось списать кредит. Попробуйте снова.")
                    st.stop()
                
                # 2. Сохранение файла
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name

                # 3. Извлечение текста
                extracted_text = ""
                
                # Если PDF
                if uploaded_file.type == "application/pdf":
                    st.caption("📄 Читаю PDF документ (LlamaParse)...")
                    documents = LlamaParse(result_type="markdown").load_data(tmp_path)
                    extracted_text = "\n\n".join([doc.text for doc in documents])
                
                # Если Видео/Аудио
                else:
                    st.caption("🎬 Обрабатываю Видео/Аудио (Whisper)...")
                    extracted_text = process_video_audio(tmp_path)

                if not extracted_text:
                    st.error("Не удалось извлечь текст.")
                    st.stop()

                # 4. Генерация теста (OpenAI)
                st.caption("🤖 Генерирую вопросы (GPT-4o)...")
                prompt = f"""
                Создай тест на языке: {language}.
                Сложность: {difficulty}.
                Количество вопросов: {num_questions}.
                Текст материала:
                {extracted_text[:50000]} 

                Формат ответа JSON список:
                [
                    {{"question": "Текст вопроса?", "options": ["Вариант А", "Вариант Б", "Вариант В"], "answer": "Правильный вариант"}}
                ]
                """
                
                response = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                
                import json
                result = json.loads(response.choices[0].message.content)
                quiz_data = result.get("questions", result.get("quiz", [])) # Попытка найти список внутри JSON
                
                # Если вернулся просто список, а не dict
                if not quiz_data and isinstance(result, list):
                    quiz_data = result
                elif not quiz_data: # Если ключ не угадали, пробуем values
                     for key, value in result.items():
                         if isinstance(value, list):
                             quiz_data = value
                             break

                # 5. Вывод результатов
                st.success("✅ Тест готов! Кредит списан.")
                
                # Отображение на экране
                for i, q in enumerate(quiz_data):
                    st.subheader(f"{i+1}. {q['question']}")
                    st.radio(f"Варианты ответа {i+1}:", q['options'], key=f"q{i}")
                    with st.expander(f"Показать ответ"):
                        st.write(f"Правильный: **{q['answer']}**")

                # 6. КНОПКИ СКАЧИВАНИЯ
                col1, col2 = st.columns(2)
                
                # HTML
                html_file = generate_html_quiz(quiz_data)
                with col1:
                    st.download_button(
                        label="📥 Скачать Интерактивный HTML",
                        data=html_file,
                        file_name="quiz.html",
                        mime="text/html"
                    )

                # PDF (Текстовый) - простая версия
                import reportlab
                # (Тут можно добавить логику PDF, но пока оставим HTML как основной)

                st.balloons()

            except Exception as e:
                st.error(f"Произошла ошибка: {e}")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

if not uploaded_file:
    st.info("👈 Сначала войдите в аккаунт слева, затем загрузите файл.")
