#!/usr/bin/env python3
"""stub_verifier.py — заглушка Node 2 (пилот).

Для каждого claim из claims.json формирует вердикт через промпт к
deepseek-v4-flash БЕЗ реальных источников. Показывает формат, не реальную
верификацию. Будет заменён на OpenAlex/CrossRef/arXiv в итерациях.

Usage:
    python3 stub_verifier.py <claims.json> <verdicts.json>
"""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
import time
import os
from pathlib import Path

def load_claims(claims_path: str) -> list[dict]:
    with open(claims_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    validated = data.get("claims", data).get("validated", data.get("validated_claims", []))
    if isinstance(validated, list):
        return validated
    return list(validated.values()) if validated else []

def verify_claim_llm(claim_text: str, claim_idx: int) -> dict:
    from openai import OpenAI
    # TD-114: провайдер из env (config.yaml: POLZA_API_KEY / SYNTHESIZER_BASE_URL)
    api_key = (os.environ.get("POLZA_API_KEY") or os.environ.get("AITUNNEL_KEY")
               or os.environ.get("OPENAI_API_KEY", ""))
    base_url = os.environ.get("SYNTHESIZER_BASE_URL", "https://api.aitunnel.ru/v1")
    client = OpenAI(api_key=api_key, base_url=base_url)
    prompt = (
        "Ты — физик-эксперт в области физики конденсированного состояния "
        "(азотирование, РФА, дифракция, нитридные фазы). "
        "Оцени следующее утверждение БЕЗ обращения к внешним источникам — "
        "только по физической правдоподобности и своим знаниям.\n\n"
        f"Утверждение: {claim_text}\n\n"
        "Ответь СТРОГО в JSON:\n"
        '{"verdict": "SUPPORTED|CONTRADICTED|UNSUPPORTED|AMBIGUOUS", '
        '"confidence": 0.0-1.0, "reason": "краткое объяснение"}\n\n'
        "Шкала:\n"
        "- SUPPORTED: физически правдоподобно\n"
        "- CONTRADICTED: противоречит известным физическим законам\n"
        "- UNSUPPORTED: недостаточно информации без источников\n"
        "- AMBIGUOUS: противоречивые данные\n"
        "Без источников confidence должен быть 0.2-0.5."
    )
    try:
        resp = client.chat.completions.create(
            model=os.environ.get("SYNTHESIZER_MODEL", "deepseek-v4-flash"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1000,
            timeout=90,
        )
        content = resp.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        return json.loads(content)
    except Exception as e:
        return {"verdict": "UNSUPPORTED", "confidence": 0.1, "reason": f"LLM error: {e}"}

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 stub_verifier.py <claims.json> <verdicts.json>", file=sys.stderr)
        sys.exit(1)
    claims_path, verdicts_path = sys.argv[1], sys.argv[2]
    claims = load_claims(claims_path)
    print(f"▶ Node 2: Stub-Verifier ({len(claims)} claims)")
    verdicts = []
    stats = {"total": len(claims), "supported": 0, "contradicted": 0, "unsupported": 0, "ambiguous": 0}
    t0 = time.time()
    for i, claim in enumerate(claims):
        text = claim.get("text") or claim.get("claim_text") or str(claim)
        v = verify_claim_llm(text, i)
        verdict = v.get("verdict", "UNSUPPORTED")
        stats[verdict.lower()] = stats.get(verdict.lower(), 0) + 1
        verdicts.append({
            "claim_id": i,
            "claim_text": text,
            "verdict": verdict,
            "confidence": v.get("confidence", 0.3),
            "reason": v.get("reason", ""),
        })
        print(f"  [{i+1}/{len(claims)}] {verdict} (conf={v.get('confidence',0.3)})")
    result = {
        "status": "success",
        "verdicts": verdicts,
        "statistics": stats,
        "processing_time_sec": round(time.time() - t0, 1),
    }
    Path(verdicts_path).parent.mkdir(parents=True, exist_ok=True)
    with open(verdicts_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ verdicts.json: {stats} ({result['processing_time_sec']}с)")

if __name__ == "__main__":
    main()