import streamlit as st
import logic
import auth
import db
import os
import pandas as pd
from datetime import datetime

# 1. КОНФИГУРАЦИЯ
st.set_page_config(page_title="VYUD AI", page_icon="🎓", layout="wide")

# 2. CSS
st.markdown("""
<style>
    .stApp {background-color:#FFFFFF!important}
    [data-testid="stSidebar"] {background-color:#F8F9FA!important; border-right:1px solid #E6E6E6}
    h1,h2,h3,h4,h5,h6,p,li,span,div,label, .stMarkdown {color:#262730!important}
    details {background-color:#FFFFFF!important; border:1px solid #d1d5db!important; border-radius:5px; margin-bottom:10px}
    summary {background-color:#fcfcfc!important; color:black!important; font-weight:600}
    input, textarea {background-color:white!important; color:black!important; border:1px solid #ccc!important}
    button[kind="primary"] {background-color:#FF4B4B!important; color:white!important; border:none!important}
    .stAlert {background-color: #f0f2f6 !important; color: #000000 !important;}
    .stat-card {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; color: white; text-align: center; margin: 5px;}
    .stat-number {font-size: 32px; font-weight: bold;}
    .stat-label {font-size: 14px; opacity: 0.9;}
    .share-link {background-color: #e8f4f8; padding: 10px; border-radius: 5px; font-family: monospace; word-break: break-all;}
</style>""", unsafe_allow_html=True)

# ==================== ПРОВЕРКА ПУБЛИЧНОГО ТЕСТА ====================
query_params = st.query_params
public_slug = query_params.get("test", None)

if public_slug:
    # Режим прохождения публичного теста
    public_test = db.get_public_test(public_slug)
    
    if not public_test:
        st.error("❌ Тест не найден или недоступен")
        st.stop()
    
    st.title(f"📝 {public_test['title']}")
    st.caption(f"Автор: {public_test['owner_email'].split('@')[0]}")
    
    # Запрос имени если требуется
    if public_test.get('require_name', True):
        if 'guest_name' not in st.session_state:
            st.session_state['guest_name'] = None
        
        if not st.session_state['guest_name']:
            st.markdown("### Введите ваше имя для начала теста")
            guest_name = st.text_input("Ваше имя", key="guest_name_input")
            if st.button("Начать тест", type="primary", key="btn_start_public"):
                if guest_name.strip():
                    st.session_state['guest_name'] = guest_name.strip()
                    st.session_state['public_test_start'] = datetime.now()
                    st.rerun()
                else:
                    st.error("Введите имя")
            st.stop()
        
        guest_email = f"guest_{st.session_state['guest_name']}@public"
    else:
        guest_email = "anonymous@public"
        if 'public_test_start' not in st.session_state:
            st.session_state['public_test_start'] = datetime.now()
    
    # Прохождение теста
    questions = public_test['questions']
    
    if not st.session_state.get('public_done'):
        with st.form("public_quiz_form"):
            ans = {}
            for i, q in enumerate(questions):
                st.markdown(f"**{i+1}. {q['scenario']}**")
                ans[i] = st.radio("Ответ:", q['options'], key=f"pub_q_{i}")
                st.divider()
            
            if st.form_submit_button("Завершить тест", type="primary"):
                score = 0
                answers_data = []
                for i, q in enumerate(questions):
                    selected_idx = q['options'].index(ans.get(i)) if ans.get(i) in q['options'] else -1
                    is_correct = selected_idx == q['correct_option_id']
                    if is_correct:
                        score += 1
                    answers_data.append({
                        "question_id": i,
                        "selected": selected_idx,
                        "correct": is_correct
                    })
                
                total = len(questions)
                passed = score >= total * 0.7
                
                # Время прохождения
                time_spent = None
                if st.session_state.get('public_test_start'):
                    time_spent = int((datetime.now() - st.session_state['public_test_start']).total_seconds())
                
                # Сохраняем результат
                db.save_attempt(
                    test_id=public_test['id'],
                    user_email=guest_email,
                    score=score,
                    total_questions=total,
                    passed=passed,
                    answers=answers_data,
                    time_spent_seconds=time_spent
                )
                
                st.session_state['public_score'] = score
                st.session_state['public_total'] = total
                st.session_state['public_passed'] = passed
                st.session_state['public_done'] = True
                st.rerun()
    else:
        # Результаты
        score = st.session_state['public_score']
        total = st.session_state['public_total']
        passed = st.session_state['public_passed']
        
        if passed:
            st.success(f"🎉 Поздравляем! Вы сдали тест: {score}/{total}")
            st.balloons()
        else:
            st.error(f"😔 К сожалению, тест не сдан: {score}/{total}. Нужно минимум {int(total * 0.7)} правильных.")
        
        # Показываем правильные ответы
        with st.expander("📖 Посмотреть правильные ответы"):
            for i, q in enumerate(questions):
                correct_ans = q['options'][q['correct_option_id']]
                st.markdown(f"**{i+1}. {q['scenario']}**")
                st.markdown(f"✅ Правильный ответ: **{correct_ans}**")
                if q.get('explanation'):
                    st.caption(f"💡 {q['explanation']}")
                st.divider()
        
        if st.button("🔄 Пройти ещё раз", key="btn_retry_public"):
            st.session_state['public_done'] = False
            st.session_state['public_test_start'] = datetime.now()
            st.rerun()
        
        st.markdown("---")
        st.markdown("**Хотите создавать свои тесты?**")
        st.link_button("🚀 Зарегистрироваться в VYUD AI", "https://app.vyud.online", type="primary")
    
    st.stop()  # Останавливаем выполнение — не показываем основной интерфейс

# ==================== ОСНОВНОЙ ИНТЕРФЕЙС ====================

# 3. САЙДБАР
with st.sidebar:
    st.title("VYUD AI 🎓")
    st.markdown("### ⚙️ Настройки")
    logo_file = st.file_uploader("Логотип компании", type=['png', 'jpg', 'jpeg'], key="logo_uploader")
    signature_file = st.file_uploader("Подпись руководителя", type=['png', 'jpg', 'jpeg'], key="sig_uploader")
    if logo_file: st.image(logo_file, width=150)
    if signature_file: st.image(signature_file, width=100)
    st.markdown("---")

# 4. АВТОРИЗАЦИЯ
if 'user' not in st.session_state: st.session_state['user'] = None

if not st.session_state['user']:
    t1, t2 = st.tabs(["Вход", "Регистрация"])
    with t1:
        e = st.text_input("Email", key="login_email")
        p = st.text_input("Пароль", type="password", key="login_pass")
        if st.button("Войти", key="btn_login"):
            if auth.login_user(e, p): 
                st.session_state['user'] = e
                st.rerun()
            else: 
                st.error("Ошибка входа")
    with t2:
        e2 = st.text_input("Email", key="reg_email")
        p2 = st.text_input("Пароль", type="password", key="reg_pass")
        if st.button("Создать", key="btn_register"):
            if auth.register_user(e2, p2): 
                st.success("Аккаунт создан! Войдите.")
            else: 
                st.error("Ошибка")
else:
    # 5. ПРИЛОЖЕНИЕ (авторизованный пользователь)
    with st.sidebar:
        st.write(f"Вы: **{st.session_state['user']}**")
        try: 
            cr = auth.get_user_credits(st.session_state['user'])
        except: 
            cr = 0
        
        col_b1, col_b2 = st.columns([2, 1])
        with col_b1: 
            st.metric("Баланс", cr)
        with col_b2: 
            st.write("")
        
        st.link_button("💎 Тарифы", "https://vyud.online/#pricing", type="primary", use_container_width=True)

        if st.button("Выход", use_container_width=True, key="btn_logout"): 
            st.session_state['user'] = None
            st.rerun()

    # ГЛАВНЫЕ ВКЛАДКИ
    main_tab1, main_tab2, main_tab3 = st.tabs(["🧠 Создать тест", "📚 Мои тесты", "📊 Статистика"])
    
    # ==================== ВКЛАДКА 1: СОЗДАНИЕ ТЕСТА ====================
    with main_tab1:
        st.title("Генератор Обучения AI 🧠")
        
        uf = st.file_uploader(
            "Загрузите файл (PDF, Video, Audio, DOCX...)", 
            type=['pdf','docx','pptx','txt','xlsx','csv','mp4','mov','mp3','wav','mpeg4','mkv','avi','webm','wmv'],
            key="file_uploader_main"
        )

        if uf:
            st.success(f"Файл: {uf.name}")
            c1, c2, c3 = st.columns(3)
            with c1: 
                diff = st.radio("Сложность", ["Easy", "Medium", "Hard"], key="difficulty_radio")
            with c2: 
                lang = st.selectbox("Язык", ["Russian", "English", "Kazakh", "Uzbek", "Kyrgyz", "Turkish"], key="lang_select")
            with c3: 
                cnt = st.slider("Вопросы", 1, 20, 5, key="questions_slider")

            if st.button("🚀 Создать тест", type="primary", key="btn_create_test"):
                if auth.get_user_credits(st.session_state['user']) > 0:
                    with st.spinner("Анализ..."):
                        try:
                            txt = logic.process_file_to_text(uf, st.secrets["OPENAI_API_KEY"])
                            quiz = logic.generate_quiz_ai(txt, cnt, diff, lang)
                            hints = logic.generate_methodologist_hints(txt, lang)
                            
                            # Конвертируем Quiz объект в JSON для сохранения
                            questions_json = [
                                {
                                    "scenario": q.scenario,
                                    "options": q.options,
                                    "correct_option_id": q.correct_option_id,
                                    "explanation": q.explanation
                                }
                                for q in quiz.questions
                            ]
                            
                            # Сохраняем тест в БД
                            test_title = uf.name.rsplit('.', 1)[0]
                            test_id = db.save_test(
                                owner_email=st.session_state['user'],
                                title=test_title,
                                questions=questions_json,
                                source_filename=uf.name,
                                difficulty=diff,
                                language=lang
                            )
                            
                            st.session_state['q'] = quiz
                            st.session_state['q_json'] = questions_json
                            st.session_state['h'] = hints
                            st.session_state['fn'] = uf.name
                            st.session_state['current_test_id'] = test_id
                            st.session_state['done'] = False
                            st.session_state['score'] = 0
                            st.session_state['test_start_time'] = datetime.now()
                            
                            auth.deduct_credit(st.session_state['user'])
                            st.rerun()
                        except Exception as e: 
                            st.error(f"Error: {e}")
                else: 
                    st.error("Недостаточно кредитов! Пополните баланс в меню слева.")

        # Отображение теста после генерации
        if st.session_state.get('q'):
            st.divider()
            if st.session_state.get('h'):
                with st.expander("💡 Подсказки Методолога", expanded=True): 
                    st.info(st.session_state['h'])

            q = st.session_state['q']
            if not st.session_state.get('done'):
                with st.form("quiz_form"):
                    ans = {}
                    for i, qu in enumerate(q.questions):
                        st.markdown(f"**{i+1}. {qu.scenario}**")
                        ans[i] = st.radio("Ответ:", qu.options, key=f"quiz_q_{i}")
                        st.divider()
                    
                    if st.form_submit_button("Завершить тест"):
                        s = 0
                        answers_data = []
                        for i, qu in enumerate(q.questions):
                            selected_idx = qu.options.index(ans.get(i)) if ans.get(i) in qu.options else -1
                            is_correct = ans.get(i) == qu.options[qu.correct_option_id]
                            if is_correct: 
                                s += 1
                            answers_data.append({
                                "question_id": i,
                                "selected": selected_idx,
                                "correct": is_correct
                            })
                        
                        st.session_state['score'] = s
                        total = len(q.questions)
                        passed = s >= total * 0.7
                        
                        # Сохраняем результат в БД
                        time_spent = None
                        if st.session_state.get('test_start_time'):
                            time_spent = int((datetime.now() - st.session_state['test_start_time']).total_seconds())
                        
                        if st.session_state.get('current_test_id'):
                            db.save_attempt(
                                test_id=st.session_state['current_test_id'],
                                user_email=st.session_state['user'],
                                score=s,
                                total_questions=total,
                                passed=passed,
                                answers=answers_data,
                                time_spent_seconds=time_spent
                            )
                        
                        if passed: 
                            st.session_state['done'] = True
                            st.rerun()
                        else: 
                            st.error(f"Не сдал: {s}/{total}. Нужно минимум {int(total * 0.7)} правильных.")
            else:
                st.success(f"✅ Сдано! Результат: {st.session_state['score']}/{len(q.questions)}")
                st.subheader("📜 Сертификат / Экспорт")
                c_n, c_c = st.columns(2)
                with c_n: 
                    d_n = st.session_state['user'].split('@')[0]
                    name = st.text_input("ФИО Студента", value=d_n, key="cert_name")
                with c_c: 
                    d_c = st.session_state['fn'].split('.')[0]
                    course = st.text_input("Название курса", value=d_c, key="cert_course")
                
                try:
                    pdf = logic.create_certificate(name, course, logo_file, signature_file)
                    st.download_button("📥 Скачать Сертификат (PDF)", pdf, "cert.pdf", "application/pdf", type="primary", key="btn_download_cert")
                except Exception as e: 
                    st.error(f"Ошибка PDF: {e}")
                
                try: 
                    st.download_button("🌐 Скачать Тест (HTML Offline)", logic.create_html_quiz(q, st.session_state['fn']), "quiz.html", "text/html", key="btn_download_html")
                except: 
                    pass

                if st.button("Заново", key="btn_retry"): 
                    st.session_state['done'] = False
                    st.session_state['test_start_time'] = datetime.now()
                    st.rerun()

        st.divider()
        st.markdown("""<div style="background-color:#f0f9ff; padding:15px; border-radius:10px; border:1px solid #bae6fd">
        <h4>🤖 Обучение на бегу</h4>
        <p>Используйте Telegram Бота: <a href="https://t.me/VyudAiBot" target="_blank">@VyudAiBot</a></p></div>""", unsafe_allow_html=True)

    # ==================== ВКЛАДКА 2: МОИ ТЕСТЫ ====================
    with main_tab2:
        st.title("📚 Мои тесты")
        
        tests = db.get_user_tests(st.session_state['user'])
        
        if not tests:
            st.info("У вас пока нет сохранённых тестов. Создайте первый тест на вкладке 'Создать тест'!")
        else:
            for test in tests:
                with st.expander(f"📝 {test['title']} ({test['questions_count']} вопросов)", expanded=False):
                    # Первый ряд кнопок
                    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
                    with col1:
                        st.caption(f"📅 Создан: {test['created_at'][:10]}")
                        st.caption(f"📁 Файл: {test.get('source_filename', 'N/A')}")
                        st.caption(f"🎯 Сложность: {test.get('difficulty', 'N/A')} | 🌐 Язык: {test.get('language', 'N/A')}")
                    
                    with col2:
                        if st.button("▶️ Пройти", key=f"take_{test['id']}", type="primary"):
                            st.session_state['taking_test_id'] = test['id']
                            st.session_state['taking_test_start'] = datetime.now()
                            st.rerun()
                    
                    with col3:
                        if st.button("🔗 Поделиться", key=f"share_{test['id']}"):
                            st.session_state['sharing_test_id'] = test['id']
                            st.rerun()
                    
                    with col4:
                        if st.button("✏️ Редактировать", key=f"edit_{test['id']}"):
                            st.session_state['editing_test_id'] = test['id']
                            st.rerun()
                    
                    with col5:
                        if st.button("🗑️ Удалить", key=f"del_{test['id']}"):
                            if db.delete_test(test['id']):
                                st.success("Тест удалён")
                                st.rerun()
                    
                    # Показываем статистику теста
                    stats = db.get_test_stats(test['id'])
                    if stats and stats['total_attempts'] > 0:
                        st.markdown("---")
                        st.markdown("**📊 Статистика прохождений:**")
                        mcol1, mcol2, mcol3, mcol4 = st.columns(4)
                        with mcol1:
                            st.metric("Прохождений", stats['total_attempts'])
                        with mcol2:
                            st.metric("Сдали", stats['passed_count'])
                        with mcol3:
                            st.metric("Не сдали", stats['failed_count'])
                        with mcol4:
                            st.metric("Средний %", f"{stats['avg_percentage']}%")
                        
                        # Кнопка истории
                        if st.button("📜 История попыток", key=f"history_{test['id']}"):
                            st.session_state['history_test_id'] = test['id']
                            st.session_state['history_test_title'] = test['title']
                            st.rerun()
        
        # РЕЖИМ ПРОХОЖДЕНИЯ ТЕСТА
        if st.session_state.get('taking_test_id'):
            st.divider()
            test_data = db.get_test(st.session_state['taking_test_id'])
            
            if test_data:
                st.subheader(f"▶️ Прохождение: {test_data['title']}")
                
                questions = test_data['questions']
                
                if not st.session_state.get('taking_done'):
                    with st.form("take_test_form"):
                        ans = {}
                        for i, q in enumerate(questions):
                            st.markdown(f"**{i+1}. {q['scenario']}**")
                            ans[i] = st.radio("Ответ:", q['options'], key=f"take_q_{i}")
                            st.divider()
                        
                        col_submit, col_cancel = st.columns(2)
                        with col_submit:
                            submitted = st.form_submit_button("✅ Завершить тест", type="primary")
                        with col_cancel:
                            cancelled = st.form_submit_button("❌ Отмена")
                        
                        if submitted:
                            score = 0
                            answers_data = []
                            for i, q in enumerate(questions):
                                selected_idx = q['options'].index(ans.get(i)) if ans.get(i) in q['options'] else -1
                                is_correct = selected_idx == q['correct_option_id']
                                if is_correct:
                                    score += 1
                                answers_data.append({
                                    "question_id": i,
                                    "selected": selected_idx,
                                    "correct": is_correct
                                })
                            
                            total = len(questions)
                            passed = score >= total * 0.7
                            
                            # Время
                            time_spent = None
                            if st.session_state.get('taking_test_start'):
                                time_spent = int((datetime.now() - st.session_state['taking_test_start']).total_seconds())
                            
                            # Сохраняем результат
                            db.save_attempt(
                                test_id=st.session_state['taking_test_id'],
                                user_email=st.session_state['user'],
                                score=score,
                                total_questions=total,
                                passed=passed,
                                answers=answers_data,
                                time_spent_seconds=time_spent
                            )
                            
                            st.session_state['taking_score'] = score
                            st.session_state['taking_total'] = total
                            st.session_state['taking_passed'] = passed
                            st.session_state['taking_done'] = True
                            st.rerun()
                        
                        if cancelled:
                            del st.session_state['taking_test_id']
                            if 'taking_done' in st.session_state:
                                del st.session_state['taking_done']
                            st.rerun()
                else:
                    # Результаты
                    score = st.session_state['taking_score']
                    total = st.session_state['taking_total']
                    passed = st.session_state['taking_passed']
                    
                    if passed:
                        st.success(f"🎉 Поздравляем! Тест сдан: {score}/{total}")
                        st.balloons()
                    else:
                        st.error(f"😔 Тест не сдан: {score}/{total}. Нужно минимум {int(total * 0.7)} правильных.")
                    
                    # Показываем правильные ответы
                    with st.expander("📖 Посмотреть правильные ответы"):
                        for i, q in enumerate(questions):
                            correct_ans = q['options'][q['correct_option_id']]
                            st.markdown(f"**{i+1}. {q['scenario']}**")
                            st.markdown(f"✅ Правильный ответ: **{correct_ans}**")
                            if q.get('explanation'):
                                st.caption(f"💡 {q['explanation']}")
                            st.divider()
                    
                    col_r1, col_r2 = st.columns(2)
                    with col_r1:
                        if st.button("🔄 Пройти ещё раз", key="btn_retake"):
                            st.session_state['taking_done'] = False
                            st.session_state['taking_test_start'] = datetime.now()
                            st.rerun()
                    with col_r2:
                        if st.button("📚 Вернуться к тестам", key="btn_back_tests"):
                            del st.session_state['taking_test_id']
                            del st.session_state['taking_done']
                            st.rerun()
        
        # РЕЖИМ ИСТОРИИ ПОПЫТОК
        if st.session_state.get('history_test_id'):
            st.divider()
            st.subheader(f"📜 История попыток: {st.session_state.get('history_test_title', 'Тест')}")
            
            attempts = db.get_test_attempts_history(st.session_state['history_test_id'], st.session_state['user'])
            
            if not attempts:
                st.info("Вы ещё не проходили этот тест")
            else:
                # График прогресса
                if len(attempts) > 1:
                    st.markdown("**📈 График прогресса:**")
                    import pandas as pd
                    chart_data = pd.DataFrame({
                        'Попытка': list(range(1, len(attempts) + 1)),
                        'Результат (%)': [a['percentage'] for a in reversed(attempts)]
                    })
                    st.line_chart(chart_data.set_index('Попытка'))
                
                # Таблица попыток
                st.markdown("**📋 Все попытки:**")
                for i, a in enumerate(attempts):
                    status = "✅ Сдано" if a['passed'] else "❌ Не сдано"
                    time_str = f"{a['time_spent']}с" if a.get('time_spent') else "N/A"
                    date_str = a['date'][:16].replace('T', ' ') if a.get('date') else "N/A"
                    
                    st.markdown(f"""
                    **Попытка {len(attempts) - i}** | {status} | {a['score']}/{a['total']} ({a['percentage']}%) | ⏱️ {time_str} | 📅 {date_str}
                    """)
                    st.progress(a['percentage'] / 100)
            
            if st.button("◀️ Назад", key="btn_back_history"):
                del st.session_state['history_test_id']
                if 'history_test_title' in st.session_state:
                    del st.session_state['history_test_title']
                st.rerun()
        
        # РЕЖИМ ШАРИНГА
        if st.session_state.get('sharing_test_id'):
            st.divider()
            st.subheader("🔗 Поделиться тестом")
            
            sharing_info = db.get_test_sharing_info(st.session_state['sharing_test_id'])
            
            if sharing_info:
                is_public = sharing_info.get('is_public', False)
                current_slug = sharing_info.get('public_slug')
                
                if is_public and current_slug:
                    public_url = f"https://app.vyud.online/?test={current_slug}"
                    st.success("✅ Тест доступен по публичной ссылке")
                    st.markdown(f'<div class="share-link">{public_url}</div>', unsafe_allow_html=True)
                    st.code(public_url, language=None)
                    
                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        if st.button("🔒 Сделать приватным", key="btn_make_private"):
                            if db.make_test_private(st.session_state['sharing_test_id']):
                                st.success("Тест теперь приватный")
                                st.rerun()
                    with col_s2:
                        if st.button("❌ Закрыть", key="btn_close_share"):
                            del st.session_state['sharing_test_id']
                            st.rerun()
                else:
                    st.info("Тест пока приватный. Создайте публичную ссылку, чтобы ученики могли проходить тест без регистрации.")
                    
                    require_name = st.checkbox("Запрашивать имя перед тестом", value=True, key="share_require_name")
                    
                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        if st.button("🔓 Создать публичную ссылку", type="primary", key="btn_make_public"):
                            slug = db.make_test_public(st.session_state['sharing_test_id'], require_name=require_name)
                            if slug:
                                st.success("Ссылка создана!")
                                st.rerun()
                    with col_s2:
                        if st.button("❌ Отмена", key="btn_cancel_share"):
                            del st.session_state['sharing_test_id']
                            st.rerun()
        
        # РЕЖИМ РЕДАКТИРОВАНИЯ
        if st.session_state.get('editing_test_id'):
            st.divider()
            st.subheader("✏️ Редактирование теста")
            
            test_data = db.get_test(st.session_state['editing_test_id'])
            if test_data:
                # Редактирование названия
                new_title = st.text_input("Название теста", value=test_data['title'], key="edit_title")
                
                st.markdown("### Вопросы:")
                
                # Храним изменённые вопросы
                if 'edited_questions' not in st.session_state or st.session_state.get('edit_test_loaded') != test_data['id']:
                    st.session_state['edited_questions'] = test_data['questions'].copy()
                    st.session_state['edit_test_loaded'] = test_data['id']
                
                questions = st.session_state['edited_questions']
                
                for i, q in enumerate(questions):
                    with st.expander(f"Вопрос {i+1}: {q['scenario'][:50]}...", expanded=False):
                        # Редактирование вопроса
                        new_scenario = st.text_area(
                            "Текст вопроса", 
                            value=q['scenario'], 
                            key=f"edit_scenario_{i}",
                            height=100
                        )
                        
                        st.markdown("**Варианты ответов:**")
                        new_options = []
                        for j, opt in enumerate(q['options']):
                            new_opt = st.text_input(
                                f"Вариант {j+1}", 
                                value=opt, 
                                key=f"edit_opt_{i}_{j}"
                            )
                            new_options.append(new_opt)
                        
                        new_correct = st.selectbox(
                            "Правильный ответ",
                            options=list(range(len(new_options))),
                            index=q['correct_option_id'],
                            format_func=lambda x: f"Вариант {x+1}: {new_options[x][:30]}...",
                            key=f"edit_correct_{i}"
                        )
                        
                        new_explanation = st.text_area(
                            "Объяснение",
                            value=q.get('explanation', ''),
                            key=f"edit_expl_{i}",
                            height=80
                        )
                        
                        # Обновляем в session_state
                        questions[i] = {
                            "scenario": new_scenario,
                            "options": new_options,
                            "correct_option_id": new_correct,
                            "explanation": new_explanation
                        }
                
                # Кнопки сохранения/отмены
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.button("💾 Сохранить изменения", type="primary", key="btn_save_edit"):
                        if db.update_test(test_data['id'], questions=questions, title=new_title):
                            st.success("✅ Тест обновлён!")
                            del st.session_state['editing_test_id']
                            del st.session_state['edited_questions']
                            del st.session_state['edit_test_loaded']
                            st.rerun()
                
                with col_cancel:
                    if st.button("❌ Отмена", key="btn_cancel_edit"):
                        del st.session_state['editing_test_id']
                        if 'edited_questions' in st.session_state:
                            del st.session_state['edited_questions']
                        if 'edit_test_loaded' in st.session_state:
                            del st.session_state['edit_test_loaded']
                        st.rerun()

    # ==================== ВКЛАДКА 3: СТАТИСТИКА ====================
    with main_tab3:
        st.title("📊 Моя статистика")
        
        user_stats = db.get_user_stats(st.session_state['user'])
        
        if not user_stats or user_stats['total_attempts'] == 0:
            st.info("Пока нет данных. Пройдите хотя бы один тест!")
        else:
            # Карточки со статистикой
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-number">{user_stats['total_attempts']}</div>
                    <div class="stat-label">Всего попыток</div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div class="stat-card" style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);">
                    <div class="stat-number">{user_stats['tests_passed']}</div>
                    <div class="stat-label">Сдано</div>
                </div>
                """, unsafe_allow_html=True)
            with col3:
                st.markdown(f"""
                <div class="stat-card" style="background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);">
                    <div class="stat-number">{user_stats['tests_failed']}</div>
                    <div class="stat-label">Не сдано</div>
                </div>
                """, unsafe_allow_html=True)
            with col4:
                st.markdown(f"""
                <div class="stat-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                    <div class="stat-number">{user_stats['avg_percentage']}%</div>
                    <div class="stat-label">Средний балл</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.divider()
            
            # Таблица последних попыток
            st.subheader("📜 История прохождений")
            if user_stats['recent_attempts']:
                df_data = []
                for a in user_stats['recent_attempts']:
                    df_data.append({
                        "Тест": a['test_title'],
                        "Результат": f"{a['score']}/{a['total']}",
                        "Процент": f"{a['percentage']}%",
                        "Статус": "✅ Сдано" if a['passed'] else "❌ Не сдано",
                        "Дата": a['date'][:10] if a['date'] else "N/A"
                    })
                st.dataframe(pd.DataFrame(df_data), use_container_width=True, hide_index=True)

    # ==================== АДМИН ПАНЕЛЬ ====================
    user_role = auth.get_user_role(st.session_state['user'])
    
    if user_role == 'admin':
        st.divider()
        st.subheader("🛡️ Админ Панель")
        
        admin_tab1, admin_tab2, admin_tab3, admin_tab4 = st.tabs([
            "📊 Дашборд", "📚 Все тесты", "📈 Все результаты", "👥 Пользователи"
        ])
        
        # --- ДАШБОРД ---
        with admin_tab1:
            global_stats = db.get_global_stats()
            if global_stats:
                st.markdown("### 🌍 Статистика платформы")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Всего тестов", global_stats['total_tests'], f"+{global_stats['tests_today']} сегодня")
                with col2:
                    st.metric("Всего прохождений", global_stats['total_attempts'], f"+{global_stats['attempts_today']} сегодня")
                with col3:
                    st.metric("Средний % сдачи", f"{global_stats['avg_pass_rate']}%")
                
                st.metric("Пользователей с тестами", global_stats['total_users_with_tests'])
            
            st.markdown("---")
            if st.button("🔴 ПЕРЕЗАГРУЗИТЬ СЕРВЕР", key="btn_admin_restart"): 
                os.system("pkill -9 -f streamlit")
        
        # --- ВСЕ ТЕСТЫ ---
        with admin_tab2:
            st.markdown("### 📚 Все тесты на платформе")
            all_tests = db.get_all_tests()
            
            if not all_tests:
                st.info("Тестов пока нет")
            else:
                # Фильтр по владельцу
                owners = list(set(t['owner_email'] for t in all_tests))
                selected_owner = st.selectbox("Фильтр по владельцу", ["Все"] + owners, key="filter_owner")
                
                filtered_tests = all_tests if selected_owner == "Все" else [t for t in all_tests if t['owner_email'] == selected_owner]
                
                for test in filtered_tests:
                    with st.expander(f"📝 {test['title']} | 👤 {test['owner_email']}", expanded=False):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            st.caption(f"📅 Создан: {test['created_at'][:10]}")
                            st.caption(f"📁 Файл: {test.get('source_filename', 'N/A')}")
                            st.caption(f"❓ Вопросов: {test['questions_count']}")
                        
                        with col2:
                            if st.button("✏️ Редактировать", key=f"admin_edit_{test['id']}"):
                                st.session_state['editing_test_id'] = test['id']
                                st.rerun()
                        
                        with col3:
                            if st.button("🗑️ Удалить", key=f"admin_del_{test['id']}"):
                                if db.delete_test(test['id']):
                                    st.success("Тест удалён")
                                    st.rerun()
                        
                        # Статистика теста
                        stats = db.get_test_stats(test['id'])
                        if stats and stats['total_attempts'] > 0:
                            st.markdown("**Статистика:**")
                            mcol1, mcol2, mcol3 = st.columns(3)
                            with mcol1:
                                st.metric("Прохождений", stats['total_attempts'])
                            with mcol2:
                                st.metric("Сдали", stats['passed_count'])
                            with mcol3:
                                st.metric("Средний %", f"{stats['avg_percentage']}%")
        
        # --- ВСЕ РЕЗУЛЬТАТЫ ---
        with admin_tab3:
            st.markdown("### 📈 История всех прохождений")
            all_attempts = db.get_all_attempts(limit=100)
            
            if not all_attempts:
                st.info("Прохождений пока нет")
            else:
                # Фильтры
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    users = list(set(a['user_email'] for a in all_attempts))
                    selected_user = st.selectbox("Фильтр по ученику", ["Все"] + users, key="filter_user")
                with col_f2:
                    status_filter = st.selectbox("Статус", ["Все", "Сдано", "Не сдано"], key="filter_status")
                
                filtered = all_attempts
                if selected_user != "Все":
                    filtered = [a for a in filtered if a['user_email'] == selected_user]
                if status_filter == "Сдано":
                    filtered = [a for a in filtered if a['passed']]
                elif status_filter == "Не сдано":
                    filtered = [a for a in filtered if not a['passed']]
                
                # Таблица
                df_data = []
                for a in filtered:
                    time_str = f"{a['time_spent_seconds']}с" if a.get('time_spent_seconds') else "N/A"
                    df_data.append({
                        "Ученик": a['user_email'],
                        "Тест": a['test_title'],
                        "Автор теста": a['test_owner'],
                        "Результат": f"{a['score']}/{a['total_questions']}",
                        "Процент": f"{a['percentage']}%",
                        "Статус": "✅ Сдано" if a['passed'] else "❌ Не сдано",
                        "Время": time_str,
                        "Дата": a['passed_at'][:10] if a['passed_at'] else "N/A"
                    })
                
                st.dataframe(pd.DataFrame(df_data), use_container_width=True, hide_index=True)
                st.caption(f"Показано {len(filtered)} из {len(all_attempts)} записей")
        
        # --- ПОЛЬЗОВАТЕЛИ ---
        with admin_tab4:
            st.markdown("### 👥 Управление пользователями")
            
            users = auth.get_all_users()
            if users:
                df_users = pd.DataFrame(users)
                st.dataframe(df_users, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.markdown("#### Действия")
            
            col_a1, col_a2, col_a3 = st.columns(3)
            with col_a1:
                t_e = st.text_input("Email пользователя", key="admin_email_input")
            with col_a2:
                credit_amount = st.number_input("Кредиты", min_value=1, value=50, key="admin_credit_amount")
                if st.button("💰 Начислить", key="btn_admin_credits"):
                    if t_e and auth.add_credits(t_e, credit_amount):
                        st.success(f"Начислено {credit_amount} кредитов!")
                    else:
                        st.error("Ошибка")
            with col_a3:
                new_role = st.selectbox("Роль", ["user", "moderator", "admin"], key="admin_role_select")
                if st.button("👑 Изменить роль", key="btn_admin_role"):
                    if t_e and auth.set_user_role(t_e, new_role):
                        st.success(f"Роль изменена на {new_role}!")
                        st.rerun()
                    else:
                        st.error("Ошибка")
