#!/usr/bin/env python3
"""content_verdict.py — слой оценки контента: предикат + уверенность + цитата
(инкапсулированный модуль, ядро Perplexity-класс модуля).

Для КАЖДОГО источника, найденного каскадом (cascade.py), определяет:
  - предикат: supports / refutes / neutral / irrelevant;
  - уверенность 0–1;
  - цитату-основание (фрагмент текста источника, на который опирается).

Структура — схема ClaimeAI (claim → verifier → typed verdict); движок
уверенности — принцип FIRE (верификация с уверенностью; LLM — свидетельство).

Алгоритм по одному источнику:
  1. анти-циркулярность: origin=document_derived → irrelevant
     (самоподтверждение текстом документа, circularity.py) — НЕ участвует в evidence.
  2. детерминированная оценка (кодом):
       - gap-claim: маркеры пробела → supports(gap); маркеры решения → refutes;
       - отрицание (CONTRADICTION_MARKERS / «не <глагол claim>») → refutes;
       - >= 2 опорных термина claim в тексте (stem-match, RU+EN) → supports;
       - 1 терм + overlap >= 0.4  → supports-weak (неоднозначный → LLM);
       - маркеры claim есть, но нет опоры → neutral;
       - нет совпадений → irrelevant.
  3. LLM-валидатор ТОЛЬКО для неоднозначных (4+LLM): подтверждает/нет + цитата.
     Принцип №0: LLM уточняет/умаляет, НЕ переворачивает жёсткий вердикт кода
     (refutes от негации, gap-논борщения, не подтверждает без опоры).
  4. цитата-основание — окно вокруг первой опоры claim в тексте.

Агрегация:
  - в evidence входят ТОЛЬКО supports/refutes; neutral/irrelevant отбрасываются;
  - вердикт claim и неопределённость выносятся КОДОМ по числу evidence.

Модуль самодостаточен (cascade — внешний, передаётся результатом каскада).
Тестируется отдельно (test_content_verdict.py).

CLI:
  python3 content_verdict.py "claim" --sources sources.json [--document]
  python3 content_verdict.py --pipeline "claim" [--json]   # каскад + слой
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from claim_classifier import classify
from gap_rules import decide_gap_verdict

# ── Предикаты ──────────────────────────────────────────────────────────────
SUPPORTS = "supports"
REFUTES = "refutes"
NEUTRAL = "neutral"
IRRELEVANT = "irrelevant"
_PREDICATES = {SUPPORTS, REFUTES, NEUTRAL, IRRELEVANT}

# ── Пороги детерминированного слоя ────────────────────────────────────────
MIN_HITS_STRONG = 2        # >=2 опорных термина → сильное подтверждение
MIN_OVERLAP_STRONG = 0.25  # доля терминов claim в тексте для сильного подтверждения
OVERLAP_WEAK = 0.40        # 1 термина + overlap >= этого → weak support
MIN_HITS_WEAK = 1
CONTRADICTION_CONF = 0.82  # уверенность при детерминированной негации
BASE_SUPP_CONF = 0.60      # база для supports
CONF_PER_HIT = 0.08        # прирост на каждый доп. опорный терм
CONF_CAP = 0.92
GAP_SUPP_CONF = 0.72
GAP_REF_CONF = 0.85
NEUTRAL_CONF = 0.35
# неоднозначные зоны: детерминированный supports/neutral с conf здесь → LLM
LLM_CONF_LO = 0.45
LLM_CONF_HI = 0.78
MAX_LLM_CALLS = 8           # бюджет LLM-свидетельств на один claim (FIRE: cost-bound)

LLM_MODEL = os.environ.get("CONTENT_LLM_MODEL", "deepseek/deepseek-v4-flash-0731")
LLM_TIMEOUT = float(os.environ.get("CONTENT_LLM_TIMEOUT", "60"))
POLZA_BASE = "https://polza.ai/api/v1"
_ENV_FILES = (
    "/home/orangepi/Документы/ai-provider-keys.env",
    "/home/orangepi/.hermes/profiles/resercher/.env",
)

# ── Маркеры ────────────────────────────────────────────────────────────────
CONTRADICTION_MARKERS = (
    "не подтвержда", "противореч", "опроверг", "не обнаруж", "не установлено",
    "невозможно", "вопреки", "противополож", "не приводит", "не влияет",
    "не увеличивает", "не пов", "не ускочит", "не ускоря", "не наблюдается",
    "нет ускор", "не происходит", "подавлен", "замедлив", "препятств",
)
NEGATIVE_VERBS = ("ускоря", "повыш", "увелич", "улучш", "интенсиф", "замедл")

GAP_SUPPORT_MARKERS = (
    "остаётся нерешённ", "остается нерешенн", "нерешённой задачей",
    "нерешенной задачей", "остаётся открыт", "остается открыт", "не изучен",
    "не изучено", "неизвестн", "нет данных", "данные отсутствуют",
    "требует дальнейших", "недостаточно", "малоизучен", "не решено",
    "не решена", "требует исследования",
)
GAP_CONTRADICT_MARKERS = (
    "решена", "решается", "разрешена", "разрешён", "установлено", "установлена",
    "известно", "показано", "доказано", "не является пробелом", "исследован",
    "данные получены", "решено",
)

_STOP = {
    "the", "and", "for", "that", "this", "with", "which", "при", "для", "что",
    "это", "как", "не", "и", "в", "на", "по", "из", "от", "однако", "таких",
    "также", "причём", "если", "работах", "работы",
}


def norm(text):
    return re.sub(r"\s+", " ", (text or "").lower().strip())


def significant_terms(text, min_len=4):
    t = re.sub(r"[^a-zа-яё0-9\s-]", " ", norm(text))
    return [w for w in t.split() if len(w) >= min_len and w not in _STOP]


def _glossary():
    """RU→EN глоссарий для билингвального сравнения (совпадает с cascade.py)."""
    try:
        from cascade import RU_EN_GLOSSARY
        return RU_EN_GLOSSARY
    except Exception:
        return {}


def claim_terms_bilingual(claim_text):
    """Опорные термины claim (RU + EN через глоссарий), отсортированы по длине.

    Возвращает список {name, stem} — достаточно список строк (для stem_match).
    """
    ru = significant_terms(claim_text)
    en = []
    glo = _glossary()
    for w in ru:
        for stem, enw in glo.items():
            if w.startswith(stem):
                en.extend(enw.split())
                break
    terms = ru + en
    seen, out = set(), []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return sorted(out, key=len, reverse=True)


def stem_in(text, term, min_stem=5):
    """Терм или его стем/окончания присутствуют в тексте."""
    if not term:
        return False
    if term in text:
        return True
    stem = term[:min_stem]
    if len(stem) >= min_stem and stem in text:
        return True
    for suf in ("ing", "ation", "ировани", "ния", "ние"):
        if term.endswith(suf) and len(term) - len(suf) >= min_stem:
            if term[: len(term) - len(suf)] in text:
                return True
    return False


def _source_text(source):
    return source.get("text") or source.get("excerpt") or source.get("title") or ""


def _quote(hay, terms=None, markers=None, width=340):
    """Цитата-основание: окно вокруг первой опоры (терм claim или маркер)."""
    terms = terms or []
    markers = markers or []
    pos = [hay.find(t) for t in list(terms) + list(markers) if hay.find(t) != -1]
    text = hay.strip()
    if pos:
        p = min(pos)
        lo = max(0, p - width // 3)
        hi = min(len(text), p + (2 * width) // 3)
        return text[lo:hi].strip()
    return text[:width].strip()


def _negated_by_text(hay, terms):
    """Прямое отрицание claim-термина («не ускоряет», «does not accelerate»…)."""
    for t in terms[:8]:
        p = hay.find(t)
        if p == -1:
            continue
        chunk = hay[max(0, p - 40): p + 80]
        for v in NEGATIVE_VERBS:
            if f"не {v}" in chunk or f"not {v}" in chunk or f"no {v}" in chunk:
                return True
        if any(m in chunk for m in (" не ", "nicht", "без", "не показ", "не обнаруж",
                                    "not ", "no increase", "no acceleration")):
            return True
    # глобальные маркеры отрицания в любом месте текста
    for m in CONTRADICTION_MARKERS:
        if m in hay:
            return True
    for m in ("does not accelerate", "not accelerate", "no acceleration",
              "failed to", "did not", "rather than", "reduced", "decreased"):
        if m in hay:
            return True
    return False


def _markers_appear(hay, terms):
    """В тексте есть хотя бы один опорный терм claim (иначе — чужой ресурс)."""
    return any(stem_in(hay, t) for t in terms)


_ABSOLUTE_QUALIFIERS = ("однозначн", "всегда", "никогда", "полностью опреде",
                        "непосредственно опреде", "автоматически")


def _absolute_qualifier(claim_text_or_cls, text):
    """Абсолютный квантор в claim (кроме покрытия в тексте) — для cap уверенности."""
    q = any(m in (claim_text_or_cls or "") for m in _ABSOLUTE_QUALIFIERS)
    if q and any(m in text for m in _ABSOLUTE_QUALIFIERS):
        return False  # источник сам повторяет абсолютность → подтверждает сильнее
    return q


# ── Детерминированная оценка источника ─────────────────────────────────────
def _det_eval(text_hay, terms, claim_class, claim_text=""):
    """Детерминированный предикат + уверенность (до LLM).

    Возвращает (pred, conf, hits, overlap, marker).
    """
    hay = norm(text_hay)
    hits = [t for t in terms if stem_in(hay, t)]
    overlap = len(hits) / len(terms) if terms else 0.0
    marker = "entail"
    phrase_cov = _phrase_coverage(norm(claim_text), hay)

    # gap
    if claim_class == "gap":
        gs = any(m in hay for m in GAP_SUPPORT_MARKERS)
        gc = any(m in hay for m in GAP_CONTRADICT_MARKERS)
        if gc and not gs:
            return REFUTES, GAP_REF_CONF, hits, overlap, "gap_contradict"
        if gs and not gc:
            return SUPPORTS, GAP_SUPP_CONF, hits, overlap, "gap_support"

    # негация
    if _negated_by_text(hay, terms) and hits:
        conf = min(CONF_CAP, CONTRADICTION_CONF + 0.03 * min(3, len(hits)))
        return REFUTES, conf, hits, overlap, "negation"

    # подтверждение: достаточно терминов + фразовое покрытие claim или
    # высокий overlap. Для EN-источников по RU-claim фразовое покрытие ~0,
    # поэтому перекрёст терминов (bilingual) — основной сигнал.
    strong = (len(hits) >= MIN_HITS_STRONG and overlap >= MIN_OVERLAP_STRONG) and (
        phrase_cov >= 0.10 or overlap >= 0.24)
    if strong:
        conf = min(CONF_CAP, BASE_SUPP_CONF + CONF_PER_HIT * (len(hits) - MIN_HITS_STRONG))
        if _absolute_qualifier(claim_text, hay):
            # абсолютный квантор («однозначно») без его повторения в источнике —
            # сужает утверждение до «жёсткого», поэтому ниже уверенность
            conf = min(conf, BASE_SUPP_CONF)  # cap для абсолютных
            return SUPPORTS, conf, hits, overlap, "strong_entail_abs"
        return SUPPORTS, conf, hits, overlap, "strong_entail"

    # слабое подтверждение (1 опорный термин + покрытие контекста)
    if len(hits) == 1 and (phrase_cov >= 0.20 or overlap >= OVERLAP_WEAK):
        return SUPPORTS, BASE_SUPP_CONF - 0.05, hits, overlap, "weak_entail"

    # маркеры claim есть, но нет опоры → нейтрально
    if _markers_appear(hay, terms):
        return NEUTRAL, NEUTRAL_CONF, hits, overlap, "markers_no_entail"

    return IRRELEVANT, 0.0, [], 0.0, "no_entail"


def _phrase_coverage(short, long):
    """Доля биграмм short в long (покрытие смысловых связок claim)."""
    ts = [w for w in short.split() if len(w) >= 3]
    tl = [w for w in long.split() if len(w) >= 3]
    bs = set(zip(ts[:-1], ts[1:]))
    bl = set(zip(tl[:-1], tl[1:]))
    if not bs:
        return 0.0
    return len(bs & bl) / len(bs)


# ── LLM-валидатор (свидетельство, не решение) ──────────────────────────────
def _load_polza_key():
    key = os.environ.get("POLZA_API_KEY")
    if key:
        return key
    for path in _ENV_FILES:
        p = Path(path)
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("POLZA_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def llm_available():
    return bool(_load_polza_key())


def llm_validate(claim_text, evidence_text, claim_type=None):
    """Свидетельство LLM: подтверждает ли фрагмент тезис.

    Возвращает {"confirmed": bool, "confidence": float, "quote": str} | None.
    При отсутствии ключа/сбое — None (без падений).
    """
    key = _load_polza_key()
    if not key:
        return None
    prompt = (
        "Ты — научный ревьюер по материаловедению (физика конденсированного "
        "состояния: азотирование, нитридные фазы, диффузия, микродеформации).\n\n"
        f"ТЕЗИС: {claim_text}\n\n"
        f"ФРАГМЕНТ ИСТОЧНИКА:\n{evidence_text[:1800]}\n\n"
        "Отвечай СТРОГО в JSON: {\"confirmed\": true|false, "
        "\"confidence\": 0.0-1.0, \"quote\": \"фраза из фрагмента, "
        "подтверждающая тезис\"}. Если фрагмент не подтверждает — "
        "confirmed:false. Только JSON."
    )
    body = json.dumps({
        "model": LLM_MODEL, "temperature": 0.0, "max_tokens": 250,
        "messages": [
            {"role": "system", "content": "Только JSON, без пояснений."},
            {"role": "user", "content": prompt},
        ],
    }).encode()
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{POLZA_BASE}/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
            j = json.loads(resp.read().decode("utf-8"))
        msg = j["choices"][0]["message"]["content"] or ""
        msg = msg.strip()
        if msg.startswith("```"):
            msg = msg.split("```")[1].strip()
            if msg.lower().startswith("json"):
                msg = msg[4:].strip()
        conf = 0.5
        try:
            parsed = json.loads(msg)
        except (ValueError, TypeError):
            parsed = {"confirmed": msg.startswith("true"), "confidence": 0.5,
                      "quote": ""}
        conf = float(parsed.get("confidence", 0.5) or 0.5)
        return {
            "confirmed": bool(parsed.get("confirmed")),
            "confidence": min(1.0, max(0.0, conf)),
            "quote": (parsed.get("quote") or "")[:400],
        }
    except Exception:
        return None


def _need_llm(pred, conf):
    """Когда вызывать LLM-валидатор (режим 4+LLM): неоднозначная зона."""
    if conf >= LLM_CONF_HI or conf <= 0.15:
        return False
    if pred == REFUTES:
        return False  # от стабильной негации не откупаемся
    if pred == SUPPORTS:
        return conf < LLM_CONF_HI  # неоднозначное слабое/среднее подтверждение
    if pred == NEUTRAL:
        # нейтральный источник без узнанных терминов, но без явного отсева —
        # тоже неоднозначный (например, 1-hit entailment с phrase-покрытием)
        return True
    return False


# ── Оценка одного источника ────────────────────────────────────────────────
def evaluate_source(source, claim_text, claim_class=None, document_text=None,
                    use_llm=True, llm_fn=None):
    """Оценка одного источника → обогащает source["_content"].

    source["_content"] = {
      predicate, confidence, quote, marker, hits, overlap, reason, llm, circular
    }
    """
    text = _source_text(source)
    # анти-циркулярность
    cyc = None
    if document_text is not None or source.get("origin") is None:
        try:
            from circularity import detect_origin
            cyc = detect_origin(text, claim_text, document_text,
                                source.get("found_via"))
        except Exception:
            cyc = None
    if cyc is not None and (cyc.get("origin") == "document_derived"
                            or "paraphrase" in " ".join(cyc.get("markers") or [])
                            or cyc.get("doc_coverage", 0.0) >= 0.4):
        source["_content"] = {
            "predicate": IRRELEVANT, "confidence": 0.0, "quote": "",
            "marker": "circularity", "hits": [], "overlap": 0.0,
            "reason": f"источник цитирует/пересказывает документ: {cyc['reason']}",
            "llm": None, "circular": True,
        }
        return source
    if cyc is not None:
        source["origin"] = cyc.get("origin") or source.get("origin", "external")
        source["overlap_claim"] = cyc.get("overlap", 0.0)

    claim_cls = classify(claim_text)["claim_class"]
    terms = claim_terms_bilingual(claim_text)
    # приём поисковой выдачи: неорганизованные/слаборелевантные записи не образуют
    # evidence (поисковый шум по стоп-словам), кроме явных циркулярных.
    accepted = bool(source.get("accepted")) or (source.get("relevance") or 0.0) >= 0.5
    if not accepted and not source.get("error"):
        pred, conf, hits, overlap, marker = (IRRELEVANT, 0.0, [], 0.0, "not_accepted")
        llm = None
        src_content = {
            "predicate": pred, "confidence": conf, "quote": "",
            "marker": marker, "hits": [], "overlap": 0.0,
            "reason": "источник не принят каскадом (поисковый шум)",
            "llm": None, "circular": False,
        }
        source["_content"] = src_content
        return source

    pred, conf, hits, overlap, marker = _det_eval(_source_text(source), terms, claim_cls, claim_text)

    llm = None
    if use_llm and _need_llm(pred, conf):
        if llm_fn is None:
            llm = llm_validate(claim_text, _source_text(source), claim_cls) or None
        else:
            # единый контракт шаклера: принимает и (claim, text), и (claim, text, cls)
            try:
                llm = llm_fn(claim_text, _source_text(source))
            except TypeError:
                llm = llm_fn(claim_text, _source_text(source), claim_cls)
        if llm:
            if not llm.get("confirmed"):
                # принцип №0: LLM может понизить уверенность, не переворачивает
                # жёсткий вердикт кода, но может отозвать слабый supports/neutral
                if pred == SUPPORTS and conf < 0.55:
                    pred, marker = NEUTRAL, "llm_no_confirm"
                elif pred == NEUTRAL:
                    conf = max(0.30, conf - 0.05)
            else:
                # LLM подтверждает неоднозначный источник → усиливаем поддержку
                if pred == NEUTRAL and llm.get("confidence", 0.5) >= 0.7 and conf < 0.6:
                    pred, marker = SUPPORTS, "llm_upgrade"
                    conf = min(0.72, 0.45 + 0.10 * len(hits))
                else:
                    conf = max(conf, 0.5)
    conf = min(1.0, max(0.0, conf))

    source["_content"] = {
        "predicate": pred, "confidence": round(conf, 3),
        "quote": _quote(norm(_source_text(source)), terms if pred != REFUTES else [],
                        CONTRADICTION_MARKERS if pred == REFUTES else []),
        "marker": marker, "hits": hits, "overlap": round(overlap, 3),
        "reason": _explain(pred, marker, len(hits)),
        "llm": llm, "circular": False,
    }
    return source


def _explain(pred, marker, nhits):
    if pred == REFUTES:
        return f"отрицание claim в тексте ({marker})"
    if pred == SUPPORTS:
        return f"опорных терминов claim: {nhits} ({marker})"
    if pred == NEUTRAL:
        return "маркер без опоры — нейтральный контекст"
    return "совпадения с claim нет"


# Ключевые «специфичные» термины claim (не общие справочники): для установления,
# что источник реально говорит о ПРЕДМЕТЕ claim, а не об общем свойстве.
_COMMON_TERMS = {
    "сталь", "стали", "сталей", "твердост", "твёрдост", "износостойк",
    "свойств", "прочност", "слоя", "слой", "слою", "поверхност",
    "hardness", "wear", "surface", "steel", "properties", "impact", "load",
    "resistance", "diffusion", "homprob", "состояние", "structur",
}

# Претенденты-маркеры/глаголы в claim — не предмет утверждения.
_CLAIM_MARKER_STOP = {
    "однозначно", "определяет", "определяет", "определяется", "позволяет",
    "улучшает", "обеспечивает", "является", "играет", "представляет",
    "наблюдается", "происходит", "оказывает", "приводит",
}


def _specificity_terms(claim_text):
    ts = significant_terms(claim_text) + _en_glossary_terms(claim_text)
    return [t for t in ts
            if t not in _COMMON_TERMS and t not in _CLAIM_MARKER_STOP]


def _en_glossary_terms(claim_text):
    """Английские варианты RU-терминов claim (глоссарий каскада)."""
    try:
        from cascade import RU_EN_GLOSSARY
    except Exception:
        return []
    out = []
    ru = significant_terms(claim_text)
    for w in ru:
        for stem, en in RU_EN_GLOSSARY.items():
            if w.startswith(stem):
                out.extend(en.split())
                break
    return out


def _source_specific_enough(source, claim_text, term_hits):
    """Источник должен покрывать хотя бы один специфичный терм claim
    (не общий справочный контекст). Позволяет отсеить «Лахтин про твёрдость»
    для claims про диффузионную зону."""
    spec = _specificity_terms(claim_text)
    if not spec:
        return True
    hay = norm(_source_text(source))
    return any(stem_in(hay, t) for t in spec)


def _subject_terms(claim_text):
    """Ядро claim — существительные ПРЕДМЕТА, не маркеры/предикат/качество.

    Например для «Структурное состояние диффузионной зоны однозначно определяет
    твёрдость...» вернёт {структурное, диффузионной(→зоны)} — предмет определения,
    но НЕ «твёрдость/износостойкость» (предикат, который может встречаться и в
    общих справочниках про твёрдость). Порог «первая половина» + позиция глагола.
    """
    ru = significant_terms(claim_text)
    stop = set(_COMMON_TERMS) | _CLAIM_MARKER_STOP | {
        "твёрдость", "твердост", "износостойк", "слой", "слоя", "слою",
        "вкладов", "задачей", "обработ", "обработке", "кинетику", "свойств",
        "улучшен", "повышени", "данных", "исследован", "моделей",
    }
    # обрезаем по маркеру-предикату: первый глагол/связка после существительных
    cut = len(ru)
    for i, w in enumerate(ru):
        if i and (w in ("определяет", "устанавливает", "является", "позволяет",
                        "обеспечивает", "равен", "составляет", "повышает",
                        "зависит", "происходит", "остаётся", "представляет",
                        "влияет", "приводит")):
            cut = i
            break
    subj = [t for t in ru[:cut] if t not in stop and len(t) >= 5][:6]
    # билингвальные эквиваленты через глоссарий каскада
    for w in ru[:cut]:
        for stem, en in _glossary().items():
            if w.startswith(stem):
                subj.extend([x for x in en.split() if len(x) >= 4])
    seen, out = set(), []
    for t in subj:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:8]


# ── Агрегация ──────────────────────────────────────────────────────────────
def evaluate_claim(claim_text, sources, document_text=None, use_llm=True,
                   llm_fn=None, claim_id=None):
    """Слой оценки: claim + список источников каскада → evidence + вердикт.

    Возвращает dict с ключами: claim_id, claim_text, claim_class, verdict,
    confidence, uncertainty, reason, stats, evidence, per_source, sources.
    """
    claim_class = classify(claim_text)["claim_class"]
    ev_list = []
    llm_budget = {"used": 0}
    for i, s in enumerate(sources):
        if s.get("error"):
            continue
        if use_llm and not llm_fn:
            def wrapper(c, txt, _cls=None):
                if llm_budget["used"] >= MAX_LLM_CALLS:
                    return {"confirmed": False, "confidence": 0.0, "quote": "",
                            "budget_exhausted": True}
                r = llm_validate(c, txt, _cls)
                if r is not None:
                    llm_budget["used"] += 1
                return r
            evaluate_source(s, claim_text, claim_class, document_text, use_llm, wrapper)
        else:
            evaluate_source(s, claim_text, claim_class, document_text, use_llm, llm_fn)
        ev_list.append(s)

    supports = [s for s in ev_list if s.get("_content", {}).get("predicate") == SUPPORTS]
    refutes = [s for s in ev_list if s.get("_content", {}).get("predicate") == REFUTES]
    neutral = [s for s in ev_list if s.get("_content", {}).get("predicate") == NEUTRAL]
    irrelevant = [s for s in ev_list if s.get("_content", {}).get("predicate") == IRRELEVANT]

    stats = {"supports": len(supports), "refutes": len(refutes),
             "neutral": len(neutral), "irrelevant": len(irrelevant),
             "total_non_error": len(ev_list)}

    evidence = supports + refutes
    verdict, confidence, reason, caveats = _verdict_plain(
        supports, refutes, len(ev_list), claim_class, claim_text)

    unc = _uncertainty(confidence, len(evidence), verdict)
    return {
        "claim_id": claim_id,
        "claim_text": claim_text,
        "claim_class": claim_class,
        "verdict": verdict,
        "confidence": round(confidence, 3),
        "uncertainty": unc,
        "reason": reason,
        "caveats": caveats,
        "evidence": [_evidence_record(s) for s in evidence],
        "per_source": [_per_source_record(s) for s in ev_list],
        "stats": stats,
        "sources": ev_list,
        "llm_calls": llm_budget["used"],
    }


def _evidence_record(s):
    c = s.get("_content", {})
    return {
        "predicate": c.get("predicate"), "confidence": c.get("confidence"),
        "quote": c.get("quote"), "title": s.get("title"),
        "url": s.get("url"), "doi": s.get("doi"),
        "found_via": s.get("found_via"), "year": s.get("year"),
        "marker": c.get("marker"), "reason": c.get("reason"),
    }


def _per_source_record(s):
    c = s.get("_content", {})
    return {
        "title": s.get("title"), "found_via": s.get("found_via"),
        "predicate": c.get("predicate"), "confidence": c.get("confidence"),
        "quote": c.get("quote"), "marker": c.get("marker"),
        "circular": c.get("circular", False),
        "origin": s.get("origin"), "relevance": s.get("relevance"),
    }


def _verdict_plain(supports, refutes, _total, claim_class, claim_text=""):
    caveats = []
    # Caveats-механизм: абсолютный квантор в claim, не повторённый источниками,
    # переводит SUPPORTED → AMBIGUOUS (как в референсном прогоне: 2 caveats → AMBIGUOUS).
    def _source_has_subject(source, spec):
        hay = norm(_source_text(source))
        return any(stem_in(hay, t) for t in spec)

    subject_terms = _subject_terms(claim_text)
    subject_covered = any(_source_has_subject(s, subject_terms) for s in supports)
    if claim_class == "gap":
        res = decide_gap_verdict(
            [s for s in supports + refutes],
            gap_support_hits=len(supports),
            gap_contradictions=len(refutes),
        )
        return res["verdict"], res["confidence"], res["reason"], []
    if refutes and len(refutes) >= len(supports):
        conf = min(0.9, CONTRADICTION_CONF + 0.05 * len(refutes))
        return "CONTRADICTED", conf, f"{len(refutes)} источн. опровергают", []
    if refutes and supports and len(supports) > len(refutes):
        # противоречивые свидетельства при перевесе поддержки → AMBIGUOUS
        return ("AMBIGUOUS", 0.55,
                f"{len(supports)} подтвержд. и {len(refutes)} опроверг. — конфликт",
                [{"severity": "warning",
                  "text": "имеются и поддерживающие, и опровергающие источники"}])
    if len(supports) >= 2:
        conf = min(CONF_CAP, 0.55 + 0.12 * len(supports))
        reason = f"{len(supports)} независимых подтверждений"
        if any(m in (claim_text or "") for m in _ABSOLUTE_QUALIFIERS):
            caveats.append({
                "severity": "warning",
                "text": "абсолютный квантор в claim («однозначно») не покрыт "
                        "подтверждающим контекстом — вердикт умеряется",
            })
        if not subject_covered:
            caveats.append({
                "severity": "warning",
                "text": "источники не покрывают предмет claim — подтверждение "
                        "общее (справочный контекст)",
            })
        if len(caveats) >= 1:
            # общее/обобщённое подтверждение при не покрытом предмете и без
            # абсолютного квантора — остаётся SUPPORTED, но с пониженной
            # уверенностью; если есть и квантор — AMBIGUOUS (2 caveat-предупреждения)
            if len(caveats) >= 2:
                return "AMBIGUOUS", min(0.62, conf), reason + " (2 caveat → AMBIGUOUS)", caveats
            conf = min(0.65, conf)
        return "SUPPORTED", conf, reason, caveats
    if len(supports) == 1:
        return "AMBIGUOUS", 0.62, "одно независимое подтверждение", []
    if supports or refutes:
        return "AMBIGUOUS", 0.5, "внешние источники есть, но evidence не сформирован", []
    return "UNSUPPORTED", 0.35, "нет независимых подтверждений/опровержений", []


def _uncertainty(conf, n_evidence, verdict):
    numeric = round(1.0 - conf, 2)
    if verdict == "GAP-UNVERIFIED":
        return {"level": "high", "value": numeric,
                "note": "gap не подтверждён и не опровергнуть — отсутствие данных"}
    if verdict == "UNSUPPORTED":
        return {"level": "high", "value": numeric,
                "note": "нет независимых внешних подтверждений"}
    if n_evidence < 2:
        return {"level": "medium", "value": numeric,
                "note": "мало независимых источников"}
    if conf >= 0.8:
        return {"level": "low", "value": numeric,
                "note": "несколько независимых внешних подтверждений"}
    return {"level": "medium", "value": numeric, "note": ""}


# ── CLI ‑ реальный прогон: каскад → слой оценки ────────────────────────────
def run_content_pipeline(claim_text, document_text=None, layers=None,
                         use_llm=True, llm_fn=None, claim_id=None):
    """Полный прогон: каскад (cascade.py) + circularity + слой оценки.

    Возвращает результат evaluate_claim.
    """
    from cascade import build_queries, run_cascade
    cls = classify(claim_text)["claim_class"]
    ru_q, en_q = build_queries(claim_text, cls)
    layers = layers or ["local_corpus", "openalex", "arxiv", "web_ddg"]
    all_sources = []
    for q in (ru_q, en_q):
        if not q.strip():
            continue
        res = run_cascade(q, layers=layers, max_iterations=2)
        all_sources.extend(res["sources"])
    # дедуп по doi/url
    seen = set()
    deduped = []
    for s in all_sources:
        if s.get("error"):
            continue
        key = s.get("doi") or s.get("url") or s.get("title", "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(s)
    return evaluate_claim(claim_text, deduped, document_text, use_llm, None,
                          claim_id=claim_id)


def run_all_claims(claims, layers=None, document_text=None, use_llm=True,
                   out_path=None):
    """Прогон слоя оценки по списку claims + сохранение артефакта.

    Возвращает dict {claim_id|индекс: результат}. Используется для воспроизведения
    `workspace/content_verdict_results.json` из отчёта.
    """
    out = {}
    for c in claims:
        text = c.get("text") or c.get("claim_text") or str(c)
        cid = c.get("claim_id", c.get("original_index"))
        out[str(cid)] = run_content_pipeline(
            text, document_text, layers=layers or ["local_corpus", "openalex",
                                                   "arxiv", "web_ddg"],
            use_llm=use_llm, claim_id=cid)
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("claim", nargs="?", help="claim-текст")
    ap.add_argument("--sources", help="sources.json (результат каскада)")
    ap.add_argument("--document", help="текст документа (анти-циркулярность)")
    ap.add_argument("--run", action="store_true",
                    help="прогнать каскад реально и оценить")
    ap.add_argument("--no-llm", action="store_true", help="отключить LLM-валидатор")
    ap.add_argument("--json", dest="as_json", action="store_true")
    args = ap.parse_args()

    if args.run and args.claim:
        doc = None
        if args.document and Path(args.document).is_file():
            doc = Path(args.document).read_text(encoding="utf-8")
        res = run_content_pipeline(args.claim, doc,
                                   use_llm=not args.no_llm)
        _print(res, args.as_json)
        return
    if args.claim and args.sources:
        sources = json.loads(Path(args.sources).read_text(encoding="utf-8"))
        if isinstance(sources, dict) and "sources" in sources:
            sources = sources["sources"]
        doc = None
        if args.document and Path(args.document).is_file():
            doc = Path(args.document).read_text(encoding="utf-8")
        res = evaluate_claim(args.claim, sources, doc, use_llm=not args.no_llm)
        _print(res, args.as_json)
        return
    ap.print_help()
    sys.exit(2)


def _print(res, as_json):
    if as_json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return
    print(f"Claim: {res['claim_text'][:80]}")
    print(f"Вердикт: {res['verdict']} (conf={res['confidence']}) "
          f"неопределённость={res['uncertainty']['level']}")
    print(f"Жизнь: {res['reason']}")
    print(f"stats: {res['stats']}")
    for e in res["evidence"]:
        print(f"  [{e['predicate']}] conf={e['confidence']} via={e['found_via']} "
              f"{e['title'][:64]}\n      quote: {e['quote'][:100]}")


if __name__ == "__main__":
    main()