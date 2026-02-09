import streamlit as st
import logic
import auth
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
</style>""", unsafe_allow_html=True)

# 3. САЙДБАР
with st.sidebar:
    st.title("VYUD AI 🎓")
    st.markdown("### ⚙️ Настройки")
    logo_file = st.file_uploader("Логотип компании", type=[png, jpg, jpeg], key="logo_upload")
    signature_file = st.file_uploader("Подпись руководителя", type=[png, jpg, jpeg], key="sig_upload")
    if logo_file: st.image(logo_file, width=150)
    if signature_file: st.image(signature_file, width=100)
    st.markdown("---")

# 4. АВТОРИЗАЦИЯ
if user not in st.session_state: st.session_state[user] = None

if not st.session_state[user]:
    t1, t2 = st.tabs(["Вход", "Регистрация"])
    with t1:
        e = st.text_input("Email", key="l_e"); p = st.text_input("Пароль", type="password", key="l_p")
        if st.button("Войти", key="login_btn"):
            if auth.login_user(e, p): st.session_state[user]=e; st.rerun()
            else: st.error("Ошибка входа")
    with t2:
        e2 = st.text_input("Email", key="r_e"); p2 = st.text_input("Пароль", type="password", key="r_p")
        if st.button("Создать", key="reg_btn"):
            if auth.register_user(e2, p2): st.success("Аккаунт создан! Войдите."); 
            else: st.error("Ошибка")
else:
    # 5. САЙДБАР ДЛЯ АВТОРИЗОВАННЫХ
    with st.sidebar:
        st.write(f"Вы: **{st.session_state[user]}**")
        try: cr = auth.get_user_credits(st.session_state[user])
        except: cr = 0
        
        col_b1, col_b2 = st.columns([2, 1])
        with col_b1: st.metric("Баланс", cr)
        with col_b2: st.write("")
        
        st.link_button("💎 Тарифы", "https://vyud.online/#pricing", type="primary", use_container_width=True)

        if st.button("Выход", use_container_width=True, key="logout_btn"): 
            st.session_state[user]=None; st.rerun()

        # ПРОМО CRM
        st.markdown("---")
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 20px; 
                    border-radius: 10px; 
                    margin: 10px 0;">
            <h3 style="color: white; margin: 0 0 10px 0;">💼 VYUD CRM</h3>
            <p style="color: white; margin: 0 0 15px 0; font-size: 14px;">
                Управляйте клиентами<br>в визуальной воронке
            </p>
            <a href="https://crm.vyud.online" target="_blank" 
               style="background: white; 
                      color: #667eea; 
                      padding: 10px 20px; 
                      border-radius: 5px; 
                      text-decoration: none; 
                      font-weight: 600;
                      display: inline-block;">
                Попробовать бесплатно →
            </a>
            <p style="color: rgba(255,255,255,0.8); margin: 10px 0 0 0; font-size: 12px;">
                ⚡ 10 лидов бесплатно
            </p>
        </div>
        """, unsafe_allow_html=True)

    # 6. ГЛАВНОЕ МЕНЮ С ТАБАМИ
    st.title("VYUD AI 🎓")
    
    # Определяем табы в зависимости от роли
    is_admin = st.session_state[user] == "vatyutovd@gmail.com"
    
    if is_admin:
        tabs = st.tabs(["🚀 Генератор", "📚 Мои курсы", "📊 Аналитика", "📈 Статистика", "🛡️ Админ"])
        tab_generator, tab_my_courses, tab_analytics, tab_statistics, tab_admin = tabs
    else:
        tabs = st.tabs(["🚀 Генератор", "📚 Мои курсы", "📊 Аналитика"])
        tab_generator, tab_my_courses, tab_analytics = tabs

    # ============================================================
    # TAB 1: ГЕНЕРАТОР (текущий функционал)
    # ============================================================
    with tab_generator:
        st.header("Генератор Обучения AI 🧠")
        
        uf = st.file_uploader("Загрузите файл (PDF, Video, Audio, DOCX...)", 
                             type=[pdf,docx,pptx,txt,xlsx,csv,mp4,mov,mp3,wav,mpeg4,mkv,avi,webm,wmv],
                             key="file_uploader_main")

        if uf:
            st.success(f"Файл: {uf.name}")
            c1, c2, c3 = st.columns(3)
            with c1: diff = st.radio("Сложность", ["Easy", "Medium", "Hard"], key="diff_radio")
            with c2: lang = st.selectbox("Язык", ["Russian", "English", "Kazakh", "Uzbek", "Kyrgyz", "Turkish"], key="lang_select")
            with c3: cnt = st.slider("Вопросы", 1, 20, 5, key="cnt_slider")

            if st.button("🚀 Создать тест", type="primary", key="create_test_btn"):
                if auth.get_user_credits(st.session_state[user]) > 0:
                    with st.spinner("Анализ..."):
                        try:
                            txt = logic.process_file_to_text(uf, st.secrets["OPENAI_API_KEY"])
                            st.session_state[q] = logic.generate_quiz_ai(txt, cnt, diff, lang)
                            st.session_state[h] = logic.generate_methodologist_hints(txt, lang)
                            st.session_state[fn] = uf.name
                            st.session_state[done] = False
                            st.session_state[score] = 0
                            
                            # Сохраняем тест в БД
                            questions_json = [
                                {
                                    "question": q.scenario,
                                    "options": q.options,
                                    "correct_option_id": q.correct_option_id,
                                    "explanation": q.explanation
                                }
                                for q in st.session_state[q].questions
                            ]
                            test_id = auth.save_quiz(
                                st.session_state[user],
                                uf.name,
                                questions_json,
                                st.session_state.get(h, [])
                            )
                            st.session_state[current_test_id] = test_id
                            
                            auth.deduct_credit(st.session_state[user])
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")
                else: st.error("Недостаточно кредитов! Пополните баланс в меню слева.")

        if st.session_state.get(q):
            st.divider()
            if st.session_state.get(h):
                with st.expander("💡 Подсказки Методолога", expanded=True): st.info(st.session_state[h])

            q = st.session_state[q]
            if not st.session_state.get(done):
                with st.form("qz"):
                    s = 0; ans = {}
                    for i, qu in enumerate(q.questions):
                        st.markdown(f"**{i+1}. {qu.scenario}**")
                        ans[i] = st.radio("Ответ:", qu.options, key=f"q{i}")
                        st.divider()
                    if st.form_submit_button("Завершить"):
                        for i, qu in enumerate(q.questions):
                            if ans.get(i) == qu.options[qu.correct_option_id]: s+=1
                        st.session_state[score] = s
                        if s >= len(q.questions)*0.7: st.session_state[done] = True; st.rerun()
                        else: st.error(f"Не сдал: {s}/{len(q.questions)}")
            else:
                st.success(f"Сдано! Результат: {st.session_state[score]}")
                st.subheader("📜 Сертификат / Экспорт")
                c_n, c_c = st.columns(2)
                with c_n: 
                    d_n = st.session_state[user].split(@)[0]
                    name = st.text_input("ФИО Студента", value=d_n, key="cert_name")
                with c_c: 
                    d_c = st.session_state[fn].split(.)[0]
                    course = st.text_input("Название курса", value=d_c, key="cert_course")
                
                try:
                    pdf = logic.create_certificate(name, course, logo_file, signature_file)
                    st.download_button("📥 Скачать Сертификат (PDF)", pdf, "cert.pdf", "application/pdf", type="primary", key="download_cert")
                except Exception as e: st.error(f"Ошибка PDF: {e}")
                
                try: st.download_button("🌐 Скачать Тест (HTML Offline)", logic.create_html_quiz(q, st.session_state[fn]), "quiz.html", "text/html", key="download_html")
                except: pass

                if st.button("Заново", key="restart_btn"): st.session_state[done]=False; st.rerun()

        st.divider()
        st.markdown("""<div style="background-color:#f0f9ff; padding:15px; border-radius:10px; border:1px solid #bae6fd">
        <h4>🤖 Обучение на бегу</h4>
        <p>Используйте Telegram Бота: <a href="https://t.me/VyudAiBot" target="_blank">@VyudAiBot</a></p></div>""", unsafe_allow_html=True)

    # ============================================================
    # TAB 2: МОИ КУРСЫ
    # ============================================================
    with tab_my_courses:
        st.header("📚 Мои курсы")
        
        try:
            quizzes = auth.get_user_quizzes(st.session_state[user])
            
            if not quizzes:
                st.info("У вас пока нет созданных курсов. Создайте первый в разделе Генератор!")
            else:
                st.success(f"Всего курсов: {len(quizzes)}")
                
                # Фильтры
                search = st.text_input("🔍 Поиск по названию", key="search_courses")
                
                # Фильтруем курсы
                filtered_quizzes = quizzes
                if search:
                    filtered_quizzes = [q for q in quizzes if search.lower() in q.get(title, ).lower()]
                
                # Отображаем курсы
                for idx, quiz in enumerate(filtered_quizzes):
                    with st.expander(f"📝 {quiz.get(title, Без названия)} - {quiz.get(created_at, )[:10]}", expanded=False):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            st.write(f"**ID:** `{quiz.get(id, N/A)}`")
                            st.write(f"**Вопросов:** {len(quiz.get(questions, []))}")
                            st.write(f"**Создан:** {quiz.get(created_at, N/A)[:16]}")
                        
                        with col2:
                            if st.button("👁️ Просмотр", key=f"view_{idx}"):
                                st.session_state[viewing_quiz] = quiz
                                st.rerun()
                        
                        with col3:
                            # Кнопка удаления (если нужна)
                            pass
                
                # Просмотр выбранного курса
                if st.session_state.get(viewing_quiz):
                    st.divider()
                    st.subheader("📖 Просмотр курса")
                    quiz = st.session_state[viewing_quiz]
                    
                    st.write(f"**Название:** {quiz.get(title)}")
                    st.write(f"**Вопросов:** {len(quiz.get(questions, []))}")
                    
                    for i, q in enumerate(quiz.get(questions, []), 1):
                        st.markdown(f"**{i}. {q.get(question)}**")
                        for opt_idx, opt in enumerate(q.get(options, [])):
                            if opt_idx == q.get(correct_option_id):
                                st.success(f"✅ {opt}")
                            else:
                                st.write(f"   {opt}")
                        if q.get(explanation):
                            st.info(f"💡 {q.get(explanation)}")
                        st.divider()
                    
                    if st.button("◀️ Назад к списку", key="back_to_list"):
                        st.session_state.pop(viewing_quiz)
                        st.rerun()
        
        except Exception as e:
            st.error(f"Ошибка загрузки курсов: {e}")

    # ============================================================
    # TAB 3: АНАЛИТИКА
    # ============================================================
    with tab_analytics:
        st.header("📊 Аналитика прохождений")
        
        try:
            # Получаем данные о прохождениях
            # Предполагаем, что в БД есть таблица с результатами
            # Если нет - показываем заглушку
            
            st.info("📈 Раздел в разработке: здесь будет статистика по прохождениям ваших курсов студентами")
            
            # Пример структуры (закомментировано до реализации в БД):
            # results = auth.get_user_quiz_results(st.session_state[user])
            # if results:
            #     df = pd.DataFrame(results)
            #     st.dataframe(df)
            #     
            #     # Графики
            #     st.bar_chart(df[score])
            # else:
            #     st.info("Пока нет данных о прохождениях")
            
        except Exception as e:
            st.error(f"Ошибка: {e}")

    # ============================================================
    # TAB 4: СТАТИСТИКА (только для админа)
    # ============================================================
    if is_admin:
        with tab_statistics:
            st.header("📈 Общая статистика платформы")
            
            try:
                # Статистика пользователей
                users_data = auth.supabase.table(users_credits).select("*").execute()
                
                if users_data.data:
                    df_users = pd.DataFrame(users_data.data)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Всего пользователей", len(df_users))
                    with col2:
                        total_credits = df_users[credits].sum() if credits in df_users.columns else 0
                        st.metric("Всего кредитов", total_credits)
                    with col3:
                        premium_users = df_users[df_users.get(telegram_premium, False) == True].shape[0] if telegram_premium in df_users.columns else 0
                        st.metric("Premium пользователей", premium_users)
                    
                    st.divider()
                    
                    # Таблица пользователей
                    st.subheader("👥 Список пользователей")
                    st.dataframe(df_users, use_container_width=True)
                    
                    # Статистика по тарифам
                    if tariff in df_users.columns:
                        st.divider()
                        st.subheader("💎 Распределение по тарифам")
                        tariff_counts = df_users[tariff].value_counts()
                        st.bar_chart(tariff_counts)
                
                else:
                    st.info("Нет данных о пользователях")
                    
            except Exception as e:
                st.error(f"Ошибка загрузки статистики: {e}")

    # ============================================================
    # TAB 5: АДМИН ПАНЕЛЬ (только для админа)
    # ============================================================
    if is_admin:
        with tab_admin:
            st.header("🛡️ Админ Панель")
            
            if st.button("🔴 ПЕРЕЗАГРУЗИТЬ СЕРВЕР (Update Code)", key="restart_server_btn"): 
                os.system("pkill -9 -f streamlit")
            
            st.divider()
            st.subheader("💰 Управление кредитами")
            
            c_a1, c_a2, c_a3 = st.columns(3)
            with c_a1: 
                t_e = st.text_input("Email пользователя", key="admin_email_input")
            with c_a2:
                credit_amount = st.number_input("Количество кредитов", min_value=1, max_value=1000, value=50, key="admin_credit_amount")
            with c_a3:
                if st.button("💰 Начислить", key="add_credits_btn"):
                    try:
                        res = auth.supabase.table(users_credits).select("*").eq(email, t_e).execute()
                        if res.data:
                            current_credits = res.data[0].get(credits, 0)
                            new_credits = current_credits + credit_amount
                            auth.supabase.table(users_credits).update({credits: new_credits}).eq(email, t_e).execute()
                            st.success(f"✅ Начислено {credit_amount} кредитов! Новый баланс: {new_credits}")
                        else:
                            st.error("❌ Пользователь не найден")
                    except Exception as e:
                        st.error(f"❌ Ошибка: {e}")
