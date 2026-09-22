#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClaimeAI Service Wrapper — чёрный ящик для извлечения и верификации claims.

ВХОД:
  - Текст (строка) ИЛИ путь к файлу (.txt, .md, .pdf)
  - Опционально: metadata (строка)

ВЫХОД:
  - JSON файл с результатами:
    - validated_claims: список валидных утверждений
    - discarded_claims: отброшенные утверждения
    - statistics: статистика обработки
    - errors: ошибки (если есть)

ГРАНИЦЫ ПРИМЕНИМОСТИ:
  ✅ Работает: научные тексты, статьи, диссертации, отчёты
  ⚠️  Ограничения:
     - Не работает с формулами LaTeX (игнорирует)
     - Не понимает таблицы и графики
     - Требует явные утверждения (не работает с поэзией, художественными текстами)
     - Максимум ~10K токенов за раз (разбивать на части)

ПЛОХОЕ ПОВЕДЕНИЕ:
  - Может разбивать сложные утверждения слишком агрессивно
  - Теряет контекст при дисамбигуации местоимений
  - Не проверяет фактическую достоверность (только формат)

Использование:
  python claimeai_wrapper.py input/abstract.txt output/result.json
"""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import os
import json
import asyncio
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

# Настройка окружения
os.environ['PYTHONSAFEPATH'] = '1'

# Путь к ClaimeAI
CLAIMEAI_PATH = '/home/orangepi/projects/ClaimeAI/apps/agent'
sys.path.insert(0, CLAIMEAI_PATH)

# ── Polza (OpenAI-совместимый провайдер) вместо хардкода секрета ──────
# Секрет НЕ зашит в код: POLZA_API_KEY читается из env-переменной или
# центрального env-файла (ai-provider-keys.env).
POLZA_BASE_URL = "https://polza.ai/api/v1"
POLZA_MODEL = os.environ.get("CLAIMEAI_MODEL", "deepseek/deepseek-v4-flash-0731")
_ENV_FILE_CANDIDATES = (
    "/home/orangepi/Документы/ai-provider-keys.env",
    "/home/orangepi/.hermes/profiles/resercher/.env",
)


def _load_polza_key():
    key = os.environ.get("POLZA_API_KEY")
    if key:
        return key
    for path in _ENV_FILE_CANDIDATES:
        p = Path(path)
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("POLZA_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


POLZA_API_KEY = _load_polza_key()
if not POLZA_API_KEY:
    raise RuntimeError(
        "POLZA_API_KEY не найден: задайте env-переменную POLZA_API_KEY "
        "или добавьте её в ai-provider-keys.env"
    )

# Провайдер подключается КОДОМ к LLM-фабрике ClaimeAI: get_llm/get_default_llm
# патчатся ДО импорта графа, чтобы все узлы агента (`from utils import get_llm`)
# получили Polza (base_url + ключ), а не aitunnel.
from langchain_openai import ChatOpenAI

# P2-фикс: extractor_guard — санитизация JSON (control chars / двойное кодирование),
# retry + таймаут, детерминированный fallback.
from extractor_guard import (
    RetryExhausted,
    deterministic_extract,
    run_with_retry,
    sanitize_llm_json,
)

# P2-фикс: таймаут одной попытки и число попыток extractor (настраиваются env).
EXTRACT_TIMEOUT = float(os.environ.get("CLAIMEAI_TIMEOUT", "100"))
EXTRACT_MAX_RETRIES = int(os.environ.get("CLAIMEAI_MAX_RETRIES", "3"))


class _SanitizingChatOpenAI(ChatOpenAI):
    """ChatOpenAI, санитизирующий JSON-выдачу ПЕРЕД парсингом в pydantic.

    Исправляет "Invalid JSON: control character ..." и вложенное кодирование JSON,
    которое роняет with_structured_output (SelectionOutput и др.).
    """

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        result = super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        for generation in result.generations:
            if getattr(generation, "text", None):
                generation.text = sanitize_llm_json(generation.text)
            msg = getattr(generation, "message", None)
            if msg is None:
                continue
            ak = getattr(msg, "additional_kwargs", {}) or {}
            fc = ak.get("function_call")
            if fc and isinstance(fc.get("arguments"), str):
                fc["arguments"] = sanitize_llm_json(fc["arguments"])
            for tc in ak.get("tool_calls") or []:
                fn = tc.get("function") or {}
                if isinstance(fn.get("arguments"), str):
                    fn["arguments"] = sanitize_llm_json(fn["arguments"])
            for tc in getattr(msg, "tool_calls", None) or []:
                fn = tc.get("function") or {}
                if isinstance(fn.get("arguments"), str):
                    fn["arguments"] = sanitize_llm_json(fn["arguments"])
        return result


def _polza_llm(model_name: str = POLZA_MODEL, temperature: float = 0.0, completions: int = 1):
    if completions > 1 and temperature == 0.0:
        temperature = 0.2
    return _SanitizingChatOpenAI(
        model=model_name,
        api_key=POLZA_API_KEY,
        base_url=POLZA_BASE_URL,
        temperature=temperature,
    )


import utils
import utils.models as _models
try:
    from utils import settings as _settings
    _settings.openai_api_key = POLZA_API_KEY
except Exception:
    pass
_models.get_llm = _polza_llm
_models.get_default_llm = _polza_llm
utils.get_llm = _polza_llm
utils.get_default_llm = _polza_llm

from claim_extractor.agent import graph as extractor_graph


class ClaimeAIWrapper:
    """Инкапсулированный wrapper для ClaimeAI."""

    def __init__(self, model_name: str = POLZA_MODEL):
        self.model_name = model_name
        self.llm = None
        self._init_llm()

    def _init_llm(self):
        """Инициализация LLM (Polza, base_url polza.ai)."""
        try:
            self.llm = _polza_llm(model_name=self.model_name, temperature=0.0)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize LLM: {e}")
    
    def _read_input(self, input_source: Union[str, Path]) -> str:
        """Чтение входа: файл или строка."""
        if isinstance(input_source, (str, Path)):
            path = Path(input_source)
            if not path.exists():
                raise FileNotFoundError(f"Input file not found: {path}")
            
            if path.suffix == '.pdf':
                # PDF пока не поддерживается
                raise NotImplementedError("PDF support not yet implemented")
            elif path.suffix in ['.txt', '.md', '.json']:
                return path.read_text(encoding='utf-8')
            else:
                # Пытаемся прочитать как текст
                return path.read_text(encoding='utf-8')
        else:
            # Предполагаем, что это строка
            return str(input_source)
    
    async def _extract_claims(self, text: str, metadata: str = "") -> Dict[str, Any]:
        """Извлечение claims из текста."""
        result = await extractor_graph.ainvoke({
            'answer_text': text,
            'metadata': metadata
        })
        return result
    
    def _format_output(self, raw_result: Dict[str, Any], input_source: str) -> Dict[str, Any]:
        """Форматирование выхода в стандартный JSON."""
        validated = []
        discarded = []
        
        # Извлекаем валидные claims
        if 'validated_claims' in raw_result:
            for claim in raw_result['validated_claims']:
                if hasattr(claim, 'claim_text'):
                    validated.append({
                        'text': claim.claim_text,
                        'original_sentence': getattr(claim, 'original_sentence', ''),
                        'original_index': getattr(claim, 'original_index', -1)
                    })
        
        # Извлекаем отброшенные claims (разница между potential и validated)
        if 'potential_claims' in raw_result:
            validated_texts = {v['text'] for v in validated}
            for claim in raw_result['potential_claims']:
                if hasattr(claim, 'claim_text'):
                    if claim.claim_text not in validated_texts:
                        discarded.append({
                            'text': claim.claim_text,
                            'reason': 'validation_failed'
                        })
        
        # Статистика
        stats = {
            'input_source': input_source,
            'input_length': len(raw_result.get('answer_text', '')),
            'sentences_detected': len(raw_result.get('contextual_sentences', [])),
            'claims_extracted': len(raw_result.get('potential_claims', [])),
            'claims_validated': len(validated),
            'claims_discarded': len(discarded),
            'validation_rate': len(validated) / max(len(raw_result.get('potential_claims', [])), 1)
        }
        
        return {
            'status': 'success',
            'claims': {
                'validated': validated,
                'discarded': discarded
            },
            'statistics': stats,
            'raw_keys': list(raw_result.keys())
        }
    
    def process(self, input_source: Union[str, Path], 
                output_path: Optional[Union[str, Path]] = None,
                metadata: str = "") -> Dict[str, Any]:
        """
        Основной метод обработки.
        
        Args:
            input_source: Путь к файлу или текст
            output_path: Путь для сохранения JSON (опционально)
            metadata: Метаданные (источник, автор, etc.)
        
        Returns:
            Dict с результатами
        """
        start_time = time.time()
        
        # 1. Чтение входа
        try:
            text = self._read_input(input_source)
        except Exception as e:
            return {
                'status': 'error',
                'error_type': 'input_error',
                'message': str(e)
            }
        
        # 2. Извлечение claims (P2-фикс: retry + таймаут, fallback на детерминированное)
        try:
            raw_result = run_with_retry(
                lambda: self._extract_claims(text, metadata),
                max_retries=EXTRACT_MAX_RETRIES,
                timeout=EXTRACT_TIMEOUT,
            )
        except (RetryExhausted, Exception) as e:
            print(f"⚠ ClaimeAI нестабилен ({e}) — fallback: детерминированное извлечение")
            output = deterministic_extract(text, metadata=str(input_source))
            output["processing_time_sec"] = round(time.time() - start_time, 2)
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(output, f, ensure_ascii=False, indent=2)
            return output
        
        # 3. Форматирование выхода
        output = self._format_output(raw_result, str(input_source))
        output['processing_time_sec'] = round(time.time() - start_time, 2)
        
        # 4. Сохранение (если указан путь)
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
        
        return output


def main():
    """CLI интерфейс."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    input_source = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    metadata = sys.argv[3] if len(sys.argv) > 3 else ""
    
    print(f"🔍 ClaimeAI Service Wrapper")
    print(f"   Input: {input_source}")
    print(f"   Output: {output_path or 'stdout'}")
    print()
    
    wrapper = ClaimeAIWrapper()
    result = wrapper.process(input_source, output_path, metadata)

    if result['status'] in ('success', 'fallback_deterministic'):
        if result['status'] == 'success':
            print(f"✅ Обработка завершена за {result['processing_time_sec']}с")
            print(f"   Найдено claims: {result['statistics']['claims_extracted']}")
            print(f"   Валидно: {result['statistics']['claims_validated']}")
            print(f"   Отброшено: {result['statistics']['claims_discarded']}")
            print(f"   % валидации: {result['statistics']['validation_rate']:.1%}")
        else:
            print(f"⚠ Детерминированный fallback за {result['processing_time_sec']}с: "
                  f"{result.get('fallback_reason', '')}")
            print(f"   Валидно (предложения-тезисы): "
                  f"{result['statistics']['claims_validated']}")
        
        if output_path:
            print(f"\n💾 Результат сохранён: {output_path}")
        else:
            print("\n📄 Результат (первые 5 claims):")
            for i, claim in enumerate(result['claims']['validated'][:5], 1):
                print(f"   [{i}] {claim['text'][:100]}")
    else:
        print(f"❌ Ошибка: {result['error_type']}")
        print(f"   {result['message']}")
        sys.exit(1)


if __name__ == '__main__':
    main()
