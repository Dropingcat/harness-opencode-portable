#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Безопасный тест ClaimeAI с aitunnel.ru (DeepSeek V4 Flash)
Запускается в изолированном окружении (/tmp), не влияет на основные процессы.

Использование:
    cd /tmp/claimeai_test
    PYTHONSAFEPATH=1 /home/orangepi/projects/ClaimeAI/apps/agent/.venv/bin/python3 test_claimeai_safe.py
"""
import sys
import os
import asyncio
import time

# Переход в тестовую директорию
os.chdir('/tmp/claimeai_test')
os.environ['PYTHONSAFEPATH'] = '1'
os.environ['OPENAI_API_KEY'] = 'sk-aitunnel-f6HQbzAFWH48SS8IyP6IRwo85HOCp4gH'
os.environ['OPENAI_BASE_URL'] = 'https://api.aitunnel.ru/v1'

# Добавляем путь к ClaimeAI
sys.path.insert(0, '/home/orangepi/projects/ClaimeAI/apps/agent')

print("=" * 70)
print("🧪 CLAIMEAI ТЕСТ (DeepSeek V4 Flash через aitunnel.ru)")
print("=" * 70)

# === Тест 1: Импорт модулей ===
print("\n[1/6] Импорт модулей ClaimeAI...")
try:
    from claim_extractor.agent import graph as extractor_graph
    from claim_extractor.schemas import State
    from utils.models import get_llm
    print("✅ Все модули импортированы")
except Exception as e:
    print(f"❌ Ошибка импорта: {e}")
    sys.exit(1)

# === Тест 2: Создание LLM ===
print("\n[2/6] Создание LLM (deepseek-v4-flash)...")
try:
    llm = get_llm(model_name="deepseek-v4-flash", temperature=0.0)
    print(f"✅ LLM создан: {type(llm).__name__}")
    print(f"   Модель: {llm.model_name}")
    # Проверяем атрибут по-разному (зависит от версии langchain)
    base_url = getattr(llm, 'api_base', None) or getattr(llm, 'base_url', None) or 'N/A'
    print(f"   Base URL: {base_url}")
except Exception as e:
    print(f"❌ Ошибка создания LLM: {e}")
    sys.exit(1)

# === Тест 3: Простой запрос к LLM ===
print("\n[3/6] Тестовый запрос к LLM...")
try:
    t0 = time.time()
    response = llm.invoke("Ответь одним числом: 2+2=?")
    t1 = time.time()
    print(f"✅ Ответ за {t1-t0:.2f}с: {response.content.strip()}")
except Exception as e:
    print(f"❌ Ошибка запроса: {e}")
    sys.exit(1)

# === Тест 4: Извлечение claims (async) ===
print("\n[4/6] Извлечение claims из текста...")
test_text = """
Apollo 11 was a spaceflight mission launched by NASA on July 16, 1969.
It was the first mission to land humans on the Moon.
Neil Armstrong became the first human to walk on the lunar surface on July 20, 1969.
Buzz Aldrin joined him shortly after.
They spent about 2.5 hours outside the spacecraft.
The mission collected 21.5 kg of lunar samples and returned them to Earth.
"""

async def test_extractor():
    try:
        t0 = time.time()
        result = await extractor_graph.ainvoke({
            'answer_text': test_text,
            'metadata': 'NASA Apollo 11 Test'
        })
        t1 = time.time()
        
        print(f"✅ Извлечение завершено за {t1-t0:.2f}с")
        print(f"   Ключи результата: {list(result.keys())}")
        
        # Показываем извлечённые claims
        if 'validated_claims' in result and result['validated_claims']:
            claims = result['validated_claims']
            print(f"   Найдено claims: {len(claims)}")
            for i, claim in enumerate(claims[:5], 1):
                if hasattr(claim, 'claim_text'):
                    print(f"   [{i}] {claim.claim_text[:100]}")
        elif 'potential_claims' in result and result['potential_claims']:
            claims = result['potential_claims']
            print(f"   Найдено potential_claims: {len(claims)}")
            for i, claim in enumerate(claims[:5], 1):
                if hasattr(claim, 'claim_text'):
                    print(f"   [{i}] {claim.claim_text[:100]}")
        elif 'contextual_sentences' in result and result['contextual_sentences']:
            sentences = result['contextual_sentences']
            print(f"   Найдено sentences: {len(sentences)}")
            for i, sent in enumerate(sentences[:5], 1):
                if hasattr(sent, 'original_sentence'):
                    print(f"   [{i}] {sent.original_sentence[:100]}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка извлечения: {e}")
        import traceback
        traceback.print_exc()
        return False

# Запуск async теста
success = asyncio.run(test_extractor())

# === Тест 5: Проверка памяти ===
print("\n[5/6] Проверка потребления памяти...")
import subprocess
result = subprocess.run(
    ['free', '-h'],
    capture_output=True, text=True, timeout=5
)
print(result.stdout)

# === Тест 6: Итог ===
print("\n[6/6] ИТОГИ ТЕСТА")
print("=" * 70)
if success:
    print("✅ ClaimeAI работает корректно с aitunnel.ru (DeepSeek V4 Flash)")
    print("\n📝 Для полного запуска:")
    print("   cd /home/orangepi/projects/ClaimeAI/apps/agent")
    print("   source .venv/bin/activate")
    print("   PYTHONSAFEPATH=1 python scripts/run_claim_extractor.py")
    print("\n⚠️  Требуется LangGraph Server для production использования")
else:
    print("⚠️  Тест выявил проблемы (см. выше)")
    print("\n💡 Возможные решения:")
    print("   - Проверить API ключ aitunnel.ru")
    print("   - Увеличить таймауты для медленных запросов")
    print("   - Проверить сеть (proxy/DPI)")

print("=" * 70)
