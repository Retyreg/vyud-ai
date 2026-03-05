"""
SCORM 1.2 Export Module для VYUD AI
Генерирует SCORM-совместимые ZIP-пакеты тестов с поддержкой 4 типов вопросов.
"""
import json
import uuid
from io import BytesIO
from zipfile import ZipFile
from datetime import datetime


def generate_scorm_package(quiz_title: str, questions_json: list) -> bytes:
    """
    Генерирует SCORM 1.2 пакет (ZIP в памяти).
    
    Args:
        quiz_title: Название теста
        questions_json: Список вопросов в формате [{"question": "...", "options": [...], ...}]
    
    Returns:
        bytes: ZIP-архив SCORM-пакета
    """
    # Создаём ZIP в памяти
    zip_buffer = BytesIO()
    
    with ZipFile(zip_buffer, 'w') as zipf:
        # 1. Манифест SCORM 1.2
        manifest = _generate_manifest(quiz_title)
        zipf.writestr('imsmanifest.xml', manifest)
        
        # 2. HTML с квизом
        html_content = _generate_html_quiz(quiz_title, questions_json)
        zipf.writestr('index.html', html_content)
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def _generate_manifest(title: str) -> str:
    """Генерирует imsmanifest.xml для SCORM 1.2"""
    identifier = f"VYUD_SCORM_{uuid.uuid4().hex[:12]}"
    
    manifest = f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="{identifier}" version="1.0"
          xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
          xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd
                              http://www.imsglobal.org/xsd/imsmd_rootv1p2p1 imsmd_rootv1p2p1.xsd
                              http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
  
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>1.2</schemaversion>
  </metadata>
  
  <organizations default="ORG-{identifier}">
    <organization identifier="ORG-{identifier}">
      <title>{_escape_xml(title)}</title>
      <item identifier="ITEM-{identifier}" identifierref="RES-{identifier}">
        <title>{_escape_xml(title)}</title>
        <adlcp:masteryscore>70</adlcp:masteryscore>
      </item>
    </organization>
  </organizations>
  
  <resources>
    <resource identifier="RES-{identifier}" type="webcontent" adlcp:scormtype="sco" href="index.html">
      <file href="index.html"/>
    </resource>
  </resources>
  
</manifest>"""
    
    return manifest


def _generate_html_quiz(title: str, questions: list) -> str:
    """Генерирует самодостаточный HTML с квизом и SCORM API"""
    
    # Нормализуем вопросы (backward compatibility)
    normalized_questions = []
    for q in questions:
        # Унифицируем поле "question" или "scenario"
        question_text = q.get("question", q.get("scenario", "Question?"))
        
        q_type = q.get("question_type", "single_choice")
        
        normalized = {
            "question": question_text,
            "type": q_type,
            "options": q.get("options", []),
            "correct_option_id": q.get("correct_option_id", 0),
            "explanation": q.get("explanation", "")
        }
        
        # Для multiple_choice
        if q_type == "multiple_choice":
            normalized["correct_option_ids"] = q.get("correct_option_ids", [q.get("correct_option_id", 0)])
        
        # Для matching
        if q_type == "matching":
            normalized["matching_pairs"] = q.get("matching_pairs", [])
        
        normalized_questions.append(normalized)
    
    quiz_json = json.dumps(normalized_questions, ensure_ascii=False)
    
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_escape_html(title)}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #1a202c;
        }}
        
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            color: #4F46E5;
            font-size: 2em;
            margin-bottom: 10px;
        }}
        
        .scorm-warning {{
            background: #FEF3C7;
            border: 2px solid #F59E0B;
            color: #92400E;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: none;
        }}
        
        .scorm-warning.show {{
            display: block;
        }}
        
        .progress-bar {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        }}
        
        .progress-bar-fill {{
            height: 8px;
            background: linear-gradient(90deg, #4F46E5, #7C3AED);
            border-radius: 10px;
            transition: width 0.3s ease;
        }}
        
        .progress-text {{
            margin-top: 10px;
            color: #6B7280;
            font-size: 14px;
        }}
        
        .quiz-card {{
            background: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        
        .question-type-badge {{
            display: inline-block;
            background: #E0E7FF;
            color: #4F46E5;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 15px;
        }}
        
        .question-title {{
            font-size: 1.4em;
            color: #1a202c;
            margin-bottom: 25px;
            line-height: 1.6;
        }}
        
        .options {{
            margin-bottom: 25px;
        }}
        
        .option {{
            background: #F9FAFB;
            border: 2px solid #E5E7EB;
            padding: 15px 20px;
            border-radius: 10px;
            margin-bottom: 12px;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
        }}
        
        .option:hover {{
            border-color: #4F46E5;
            background: #EEF2FF;
        }}
        
        .option input[type="radio"],
        .option input[type="checkbox"] {{
            margin-right: 12px;
            width: 20px;
            height: 20px;
            cursor: pointer;
        }}
        
        .option.selected {{
            border-color: #4F46E5;
            background: #EEF2FF;
        }}
        
        .option.correct {{
            border-color: #059669;
            background: #D1FAE5;
        }}
        
        .option.incorrect {{
            border-color: #DC2626;
            background: #FEE2E2;
        }}
        
        .matching-container {{
            display: grid;
            gap: 15px;
        }}
        
        .matching-row {{
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            gap: 15px;
            align-items: center;
            background: #F9FAFB;
            padding: 15px;
            border-radius: 10px;
        }}
        
        .matching-left {{
            font-weight: 500;
        }}
        
        .matching-arrow {{
            color: #4F46E5;
            font-size: 20px;
        }}
        
        .matching-select {{
            width: 100%;
            padding: 10px;
            border: 2px solid #E5E7EB;
            border-radius: 8px;
            font-size: 14px;
            background: white;
        }}
        
        .navigation {{
            display: flex;
            gap: 15px;
            justify-content: space-between;
        }}
        
        .btn {{
            padding: 15px 30px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            flex: 1;
        }}
        
        .btn-primary {{
            background: linear-gradient(135deg, #4F46E5, #7C3AED);
            color: white;
        }}
        
        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(79, 70, 229, 0.3);
        }}
        
        .btn-secondary {{
            background: #E5E7EB;
            color: #4B5563;
        }}
        
        .btn-secondary:hover {{
            background: #D1D5DB;
        }}
        
        .btn:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}
        
        .results {{
            text-align: center;
        }}
        
        .score-circle {{
            width: 200px;
            height: 200px;
            margin: 30px auto;
            border-radius: 50%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            font-size: 3em;
            font-weight: bold;
            color: white;
        }}
        
        .score-circle.passed {{
            background: linear-gradient(135deg, #059669, #10B981);
        }}
        
        .score-circle.failed {{
            background: linear-gradient(135deg, #DC2626, #EF4444);
        }}
        
        .score-label {{
            font-size: 0.3em;
            margin-top: 5px;
        }}
        
        .explanation {{
            background: #EFF6FF;
            border-left: 4px solid #3B82F6;
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            font-size: 14px;
            color: #1E40AF;
        }}
        
        .review-item {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 20px;
            border-left: 4px solid #E5E7EB;
        }}
        
        .review-item.correct {{
            border-left-color: #059669;
        }}
        
        .review-item.incorrect {{
            border-left-color: #DC2626;
        }}
        
        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 1.5em;
            }}
            
            .quiz-card {{
                padding: 25px;
            }}
            
            .matching-row {{
                grid-template-columns: 1fr;
                text-align: center;
            }}
            
            .matching-arrow {{
                transform: rotate(90deg);
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{_escape_html(title)}</h1>
            <p>Интерактивный тест VYUD AI</p>
        </div>
        
        <div class="scorm-warning" id="scormWarning">
            ⚠️ Тест открыт вне LMS. Результаты не будут сохранены в системе обучения.
        </div>
        
        <div class="progress-bar" id="progressBar" style="display:none;">
            <div class="progress-bar-fill" id="progressFill"></div>
            <div class="progress-text" id="progressText"></div>
        </div>
        
        <div class="quiz-card" id="quizContainer"></div>
    </div>

    <script>
        // ==================== SCORM 1.2 API WRAPPER ====================
        const SCORM = {{
            API: null,
            isAvailable: false,
            
            init() {{
                this.API = this.findAPI(window);
                if (this.API) {{
                    const result = this.API.LMSInitialize("");
                    this.isAvailable = (result === "true");
                    
                    if (this.isAvailable) {{
                        this.setValue("cmi.core.lesson_status", "incomplete");
                        this.setValue("cmi.core.score.min", "0");
                        this.setValue("cmi.core.score.max", "100");
                        this.commit();
                        console.log("✅ SCORM API инициализирован");
                    }}
                }} else {{
                    console.warn("⚠️ SCORM API не найден");
                    document.getElementById('scormWarning').classList.add('show');
                }}
            }},
            
            findAPI(win) {{
                let attempts = 0;
                while ((!win.API) && (win.parent) && (win.parent != win) && (attempts < 10)) {{
                    attempts++;
                    win = win.parent;
                }}
                
                if (win.API) return win.API;
                
                // Проверяем opener
                if (win.opener && win.opener.API) return win.opener.API;
                
                return null;
            }},
            
            setValue(key, value) {{
                if (this.API) {{
                    return this.API.LMSSetValue(key, value);
                }}
                return "false";
            }},
            
            getValue(key) {{
                if (this.API) {{
                    return this.API.LMSGetValue(key);
                }}
                return "";
            }},
            
            commit() {{
                if (this.API) {{
                    return this.API.LMSCommit("");
                }}
                return "false";
            }},
            
            finish(score, passed) {{
                if (!this.isAvailable) return;
                
                this.setValue("cmi.core.score.raw", score.toString());
                this.setValue("cmi.core.lesson_status", passed ? "passed" : "failed");
                this.commit();
                this.API.LMSFinish("");
                
                console.log(`✅ SCORM результат отправлен: ${{score}}% - ${{passed ? 'PASSED' : 'FAILED'}}`);
            }}
        }};

        // ==================== QUIZ DATA ====================
        const quizData = {quiz_json};
        let currentQuestion = 0;
        let userAnswers = {{}};
        let quizCompleted = false;

        // ==================== QUIZ ENGINE ====================
        class QuizEngine {{
            constructor() {{
                SCORM.init();
                this.render();
            }}
            
            render() {{
                if (quizCompleted) {{
                    this.renderResults();
                }} else {{
                    this.renderQuestion();
                }}
            }}
            
            renderQuestion() {{
                const q = quizData[currentQuestion];
                const container = document.getElementById('quizContainer');
                
                // Progress bar
                const progress = ((currentQuestion + 1) / quizData.length) * 100;
                document.getElementById('progressBar').style.display = 'block';
                document.getElementById('progressFill').style.width = progress + '%';
                document.getElementById('progressText').textContent = `Вопрос ${{currentQuestion + 1}} из ${{quizData.length}}`;
                
                // Question type badges
                const typeBadges = {{
                    'single_choice': '🔘 Один ответ',
                    'multiple_choice': '☑️ Несколько ответов',
                    'true_false': '✅❌ Верно/Неверно',
                    'matching': '🔗 Соответствие'
                }};
                
                const badge = typeBadges[q.type] || '🔘 Один ответ';
                
                let html = `
                    <span class="question-type-badge">${{badge}}</span>
                    <h2 class="question-title">${{q.question}}</h2>
                `;
                
                // Render options based on type
                if (q.type === 'matching') {{
                    html += this.renderMatching(q);
                }} else if (q.type === 'multiple_choice') {{
                    html += this.renderMultipleChoice(q);
                }} else {{
                    html += this.renderSingleChoice(q);
                }}
                
                // Navigation
                html += `
                    <div class="navigation">
                        <button class="btn btn-secondary" onclick="quiz.prevQuestion()" ${{currentQuestion === 0 ? 'disabled' : ''}}>
                            ← Назад
                        </button>
                        <button class="btn btn-primary" onclick="quiz.nextQuestion()">
                            ${{currentQuestion === quizData.length - 1 ? 'Завершить тест →' : 'Далее →'}}
                        </button>
                    </div>
                `;
                
                container.innerHTML = html;
            }}
            
            renderSingleChoice(q) {{
                let html = '<div class="options">';
                q.options.forEach((opt, idx) => {{
                    const checked = userAnswers[currentQuestion] === idx ? 'checked' : '';
                    const selectedClass = checked ? 'selected' : '';
                    html += `
                        <label class="option ${{selectedClass}}">
                            <input type="radio" name="q${{currentQuestion}}" value="${{idx}}" ${{checked}}
                                   onchange="quiz.saveAnswer(${{idx}})">
                            <span>${{opt}}</span>
                        </label>
                    `;
                }});
                html += '</div>';
                return html;
            }}
            
            renderMultipleChoice(q) {{
                const selected = userAnswers[currentQuestion] || [];
                let html = '<div class="options">';
                html += '<p style="color: #6B7280; margin-bottom: 15px; font-size: 14px;">Выберите все правильные ответы:</p>';
                q.options.forEach((opt, idx) => {{
                    const checked = selected.includes(idx) ? 'checked' : '';
                    const selectedClass = checked ? 'selected' : '';
                    html += `
                        <label class="option ${{selectedClass}}">
                            <input type="checkbox" value="${{idx}}" ${{checked}}
                                   onchange="quiz.saveMultipleAnswer(${{idx}}, this.checked)">
                            <span>${{opt}}</span>
                        </label>
                    `;
                }});
                html += '</div>';
                return html;
            }}
            
            renderMatching(q) {{
                const pairs = q.matching_pairs || [];
                const rightOptions = pairs.map(p => p.right);
                const selected = userAnswers[currentQuestion] || {{}};
                
                let html = '<div class="matching-container">';
                pairs.forEach((pair, idx) => {{
                    html += `
                        <div class="matching-row">
                            <div class="matching-left">${{pair.left}}</div>
                            <div class="matching-arrow">→</div>
                            <select class="matching-select" onchange="quiz.saveMatchingAnswer(${{idx}}, this.value)">
                                <option value="">Выберите...</option>
                                ${{rightOptions.map(opt => `
                                    <option value="${{opt}}" ${{selected[idx] === opt ? 'selected' : ''}}>${{opt}}</option>
                                `).join('')}}
                            </select>
                        </div>
                    `;
                }});
                html += '</div>';
                return html;
            }}
            
            saveAnswer(idx) {{
                userAnswers[currentQuestion] = idx;
                // Update UI
                document.querySelectorAll('.option').forEach(opt => opt.classList.remove('selected'));
                document.querySelectorAll('input[type="radio"]')[idx].closest('.option').classList.add('selected');
            }}
            
            saveMultipleAnswer(idx, checked) {{
                if (!userAnswers[currentQuestion]) userAnswers[currentQuestion] = [];
                if (checked) {{
                    if (!userAnswers[currentQuestion].includes(idx)) {{
                        userAnswers[currentQuestion].push(idx);
                    }}
                }} else {{
                    userAnswers[currentQuestion] = userAnswers[currentQuestion].filter(i => i !== idx);
                }}
                // Update UI
                const option = document.querySelector(`input[type="checkbox"][value="${{idx}}"]`).closest('.option');
                option.classList.toggle('selected', checked);
            }}
            
            saveMatchingAnswer(pairIdx, value) {{
                if (!userAnswers[currentQuestion]) userAnswers[currentQuestion] = {{}};
                userAnswers[currentQuestion][pairIdx] = value;
            }}
            
            nextQuestion() {{
                if (currentQuestion < quizData.length - 1) {{
                    currentQuestion++;
                    this.render();
                }} else {{
                    this.completeQuiz();
                }}
            }}
            
            prevQuestion() {{
                if (currentQuestion > 0) {{
                    currentQuestion--;
                    this.render();
                }}
            }}
            
            completeQuiz() {{
                quizCompleted = true;
                this.render();
            }}
            
            calculateScore() {{
                let correct = 0;
                
                quizData.forEach((q, idx) => {{
                    const answer = userAnswers[idx];
                    
                    if (q.type === 'matching') {{
                        const pairs = q.matching_pairs || [];
                        let allCorrect = true;
                        pairs.forEach((pair, pairIdx) => {{
                            if (answer && answer[pairIdx] !== pair.right) {{
                                allCorrect = false;
                            }}
                        }});
                        if (allCorrect && answer && Object.keys(answer).length === pairs.length) {{
                            correct++;
                        }}
                    }} else if (q.type === 'multiple_choice') {{
                        const correctIds = q.correct_option_ids || [q.correct_option_id];
                        const userIds = answer || [];
                        if (JSON.stringify([...correctIds].sort()) === JSON.stringify([...userIds].sort())) {{
                            correct++;
                        }}
                    }} else {{
                        if (answer === q.correct_option_id) {{
                            correct++;
                        }}
                    }}
                }});
                
                return correct;
            }}
            
            renderResults() {{
                const correctCount = this.calculateScore();
                const total = quizData.length;
                const percentage = Math.round((correctCount / total) * 100);
                const passed = percentage >= 70;
                
                // Отправляем в SCORM
                SCORM.finish(percentage, passed);
                
                const container = document.getElementById('quizContainer');
                document.getElementById('progressBar').style.display = 'none';
                
                let html = `
                    <div class="results">
                        <h2>Тест завершён!</h2>
                        <div class="score-circle ${{passed ? 'passed' : 'failed'}}">
                            ${{percentage}}%
                            <div class="score-label">${{correctCount}} из ${{total}}</div>
                        </div>
                        <h3 style="margin: 20px 0;">${{passed ? '🎉 Поздравляем! Тест пройден!' : '😔 Тест не пройден'}}</h3>
                        <p style="color: #6B7280; margin-bottom: 30px;">
                            Для успешного прохождения требуется ${{Math.ceil(total * 0.7)}} правильных ответов (70%)
                        </p>
                `;
                
                // Показываем разбор неправильных ответов
                let hasIncorrect = false;
                quizData.forEach((q, idx) => {{
                    const answer = userAnswers[idx];
                    const isCorrect = this.isAnswerCorrect(q, answer, idx);
                    
                    if (!isCorrect && q.explanation) {{
                        hasIncorrect = true;
                    }}
                }});
                
                if (hasIncorrect) {{
                    html += '<h3 style="margin: 30px 0 20px 0; text-align: left;">📖 Разбор ошибок:</h3>';
                    
                    quizData.forEach((q, idx) => {{
                        const answer = userAnswers[idx];
                        const isCorrect = this.isAnswerCorrect(q, answer, idx);
                        
                        if (!isCorrect && q.explanation) {{
                            html += `
                                <div class="review-item incorrect">
                                    <strong>Вопрос ${{idx + 1}}:</strong> ${{q.question}}
                                    <div class="explanation">
                                        💡 ${{q.explanation}}
                                    </div>
                                </div>
                            `;
                        }}
                    }});
                }}
                
                html += `
                        <button class="btn btn-primary" onclick="location.reload()">
                            🔄 Пройти заново
                        </button>
                    </div>
                `;
                
                container.innerHTML = html;
            }}
            
            isAnswerCorrect(q, answer, idx) {{
                if (q.type === 'matching') {{
                    const pairs = q.matching_pairs || [];
                    let allCorrect = true;
                    pairs.forEach((pair, pairIdx) => {{
                        if (!answer || answer[pairIdx] !== pair.right) {{
                            allCorrect = false;
                        }}
                    }});
                    return allCorrect && answer && Object.keys(answer).length === pairs.length;
                }} else if (q.type === 'multiple_choice') {{
                    const correctIds = q.correct_option_ids || [q.correct_option_id];
                    const userIds = answer || [];
                    return JSON.stringify([...correctIds].sort()) === JSON.stringify([...userIds].sort());
                }} else {{
                    return answer === q.correct_option_id;
                }}
            }}
        }}

        // ==================== INITIALIZE ====================
        const quiz = new QuizEngine();
    </script>
</body>
</html>"""
    
    return html


def _escape_xml(text: str) -> str:
    """Экранирует специальные символы для XML"""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))


def _escape_html(text: str) -> str:
    """Экранирует специальные символы для HTML"""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
