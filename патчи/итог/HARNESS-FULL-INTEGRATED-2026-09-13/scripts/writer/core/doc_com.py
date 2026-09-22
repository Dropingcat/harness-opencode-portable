# -*- coding: utf-8 -*-
"""writer_core.doc_com — извлечение текста из .doc (legacy binary) через Word COM.

Причина: python-docx не читает .doc; прямой `$doc.SaveAs` в PowerShell 5.1 COM
нестабилен («Ошибка метода»). Надёжный путь — `$doc.Content.Text` / `Range.Text`
→ UTF-8. Обёртка на win32com (доступен в venv) с fail-closed.
"""
from __future__ import annotations

import os
from typing import Optional

try:
    import win32com.client  # type: ignore
    import pythoncom  # type: ignore
    _HAS_COM = True
except Exception:  # pragma: no cover
    _HAS_COM = False


def available() -> bool:
    """Есть ли Word COM (win32com) в среде."""
    return _HAS_COM


def _is_doc(path: str) -> bool:
    return str(path).lower().endswith(".doc")


def extract_doc_text(path: str, timeout_s: int = 60) -> str:
    """Извлечь текст из .doc через Word COM (Content.Text -> str).

    Raises:
        RuntimeError — если win32com нет, Word недоступен, файл не читается.
    """
    if not _HAS_COM:
        raise RuntimeError("win32com не установлен (pip install pywin32) — .doc извлечь нельзя")
    if not os.path.exists(path):
        raise RuntimeError(f"файл не найден: {path}")
    if not _is_doc(path):
        raise RuntimeError(f"не .doc файл: {path}")

    pythoncom.CoInitialize()
    word = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        # Open(FileName, ConfirmConversions=False, ReadOnly=True)
        doc = word.Documents.Open(os.path.abspath(path), False, True)
        try:
            # Content.Text возвращает текст документа (с табличными разделителями \r\a)
            text = doc.Content.Text
        finally:
            doc.Close(False)
        return text
    except Exception as e:
        raise RuntimeError(f"Word COM извлечение .doc не удалось: {type(e).__name__}: {e}") from e
    finally:
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()


def try_extract_doc_text(path: str) -> Optional[str]:
    """fail-closed версия: вернуть текст или None (без исключения наружу)."""
    try:
        return extract_doc_text(path)
    except Exception:
        return None