# STUBS_LOG.md

Журнал найденных заглушек и параметров без конфига. Формат:
`## [дата] <файл>:<функция> - что - как - что нужно - статус`

## [2026-08-11] llm_client.py:llm_call / config_loader.py:llm_params
- fallback-дефолты температуры 0.3 и max_tokens 2048, когда роль/секция отсутствуют в writer_config.yaml
- это резервные значения для отсутствующих ключей, реальные параметры берутся из конфига
- можно вынести в llm.default_temperature / llm.default_max_tokens (+ ключ модели роли)
- статус: open

## [2026-08-11] regression_suite.py:_ks_critical_value
- коэффициент 0.5 в формуле критического значения KS: c(alpha) = sqrt(-0.5 * ln(alpha/2))
- математическая константа распределения Колмогорова-Смирнова, не тюнинг-параметр
- вынести в regression.ks_constant (низкий приоритет)
- статус: open

## [2026-08-11] writer_orchestrator.py:_build_suite_verdicts / _phase_regression
- fallback confidence = 0.5 и fallback-вердикт, когда свита не дала вердикта (нет wave_A/wave_B)
- фолбэк при отсутствии результатов свиты, работает только в degraded-режиме
- вынести в regression.fallback_confidence
- статус: open

## [2026-08-11] live_test.py:main
- числа в тестовых данных (confidence 0.2-0.95, «глубина слоя 0.3-0.6 мм»)
- это фикстуры живого теста, не параметры пайплайна
- ничего не требуется
- статус: closed (не параметр)
