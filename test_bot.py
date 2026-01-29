"""
Тесты критичного функционала VYUD AI Bot
Запуск: cd /var/www/vyud_app && source venv/bin/activate && python -m pytest test_bot.py -v
"""

import sys
import inspect
sys.path.insert(0, '/var/www/vyud_app')

class TestModels:
    """Проверка моделей данных"""
    
    def test_quiz_question_has_scenario(self):
        """QuizQuestion должен иметь поле scenario, не question"""
        from logic import QuizQuestion
        q = QuizQuestion(scenario="Test?", options=["A", "B"], correct_option_id=0)
        assert hasattr(q, 'scenario'), "QuizQuestion должен иметь поле 'scenario'"
        assert not hasattr(q, 'question'), "QuizQuestion НЕ должен иметь поле 'question'"
    
    def test_quiz_question_fields(self):
        """Все обязательные поля присутствуют"""
        from logic import QuizQuestion
        q = QuizQuestion(scenario="Test?", options=["A", "B", "C", "D"], correct_option_id=1, explanation="Because")
        assert q.scenario == "Test?"
        assert q.options == ["A", "B", "C", "D"]
        assert q.correct_option_id == 1
        assert q.explanation == "Because"


class TestAuthFunctions:
    """Проверка что auth.py функции синхронные"""
    
    def test_deduct_credit_is_sync(self):
        """deduct_credit должна быть синхронной"""
        from auth import deduct_credit
        assert not inspect.iscoroutinefunction(deduct_credit), \
            "deduct_credit должна быть СИНХРОННОЙ (вызывать через asyncio.to_thread)"
    
    def test_get_user_credits_is_sync(self):
        """get_user_credits должна быть синхронной"""
        from auth import get_user_credits
        assert not inspect.iscoroutinefunction(get_user_credits), \
            "get_user_credits должна быть СИНХРОННОЙ"
    
    def test_save_quiz_is_sync(self):
        """save_quiz должна быть синхронной"""
        from auth import save_quiz
        assert not inspect.iscoroutinefunction(save_quiz), \
            "save_quiz должна быть СИНХРОННОЙ"


class TestBotCode:
    """Проверка кода bot.py"""
    
    def test_send_poll_exists_for_audio(self):
        """send_poll должен быть в обработчике аудио"""
        with open('/var/www/vyud_app/bot.py', 'r') as f:
            content = f.read()
        assert content.count('send_poll') >= 2, \
            "Должно быть минимум 2 вызова send_poll (аудио и документы)"
    
    def test_no_await_deduct_credit_direct(self):
        """Не должно быть прямого await deduct_credit"""
        with open('/var/www/vyud_app/bot.py', 'r') as f:
            content = f.read()
        assert 'await deduct_credit(' not in content, \
            "deduct_credit синхронная! Использовать await asyncio.to_thread(deduct_credit, ...)"
    
    def test_scenario_not_question_in_bot(self):
        """В bot.py должен использоваться q.scenario, не q.question"""
        with open('/var/www/vyud_app/bot.py', 'r') as f:
            content = f.read()
        assert 'q.question' not in content, \
            "Использовать q.scenario вместо q.question"


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])


class TestLanguageSupport:
    """Проверка поддержки русского языка"""
    
    def test_russian_language_in_generate_calls(self):
        """Генерация квизов должна вызываться с Russian"""
        with open('/var/www/vyud_app/bot.py', 'r') as f:
            content = f.read()
        assert 'generate_quiz_struct' in content
        assert '"Russian"' in content or "'Russian'" in content, \
            "Генерация должна вызываться с языком Russian"


class TestTelegramPolls:
    """Проверка отправки квизов в Telegram"""
    
    def test_send_poll_for_documents(self):
        """send_poll должен быть в обработчике документов (после строки 250)"""
        with open('/var/www/vyud_app/bot.py', 'r') as f:
            lines = f.readlines()
        # Ищем send_poll после строки 250 (обработчик документов)
        found_after_250 = False
        for i, line in enumerate(lines):
            if i > 250 and 'send_poll' in line:
                found_after_250 = True
                break
        assert found_after_250, "send_poll должен быть в обработчике документов"
    
    def test_send_poll_uses_scenario(self):
        """send_poll должен использовать q.scenario"""
        with open('/var/www/vyud_app/bot.py', 'r') as f:
            content = f.read()
        # Находим все строки с send_poll
        import re
        poll_lines = re.findall(r'.*send_poll.*', content)
        for line in poll_lines:
            assert 'scenario' in line, f"send_poll должен использовать q.scenario: {line}"


class TestCreditSystem:
    """Проверка системы кредитов"""
    
    def test_deduct_credit_with_asyncio_to_thread(self):
        """deduct_credit должен вызываться через asyncio.to_thread"""
        with open('/var/www/vyud_app/bot.py', 'r') as f:
            content = f.read()
        assert 'asyncio.to_thread(deduct_credit' in content, \
            "deduct_credit должен вызываться через asyncio.to_thread"


class TestWebKeyboard:
    """Проверка клавиатуры с кнопками"""
    
    def test_create_web_keyboard_exists(self):
        """Функция create_web_keyboard должна существовать"""
        with open('/var/www/vyud_app/bot.py', 'r') as f:
            content = f.read()
        assert 'def create_web_keyboard' in content, \
            "Функция create_web_keyboard должна быть определена"
    
    def test_keyboard_used_after_quiz(self):
        """Клавиатура должна показываться после создания квиза"""
        with open('/var/www/vyud_app/bot.py', 'r') as f:
            content = f.read()
        assert 'reply_markup=create_web_keyboard(test_id)' in content, \
            "После создания квиза должна показываться клавиатура с test_id"
