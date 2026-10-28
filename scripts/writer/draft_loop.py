#!/usr/bin/env python3
"""Read-only by default: ingest one exact, claim-constrained paragraph."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import tempfile

from citation_trace import Parser, InputError, error_report, inventory, load_dom, run


def ingest(text, dom, paragraph_id):
    claims, sources, sections, paragraphs, titles = inventory(dom)
    if paragraph_id not in paragraphs:
        raise InputError('paragraph-id does not resolve exactly')
    # Entire input is the selected paragraph, never a positional guess in a document.
    if not text.strip() or re.search(r'\n[ \t]*\n', text.strip()) or any(l.lstrip().startswith('#') for l in text.splitlines()):
        raise InputError('input must contain only one selected paragraph (no headings/blank blocks)')
    candidate = text.strip()
    selected = paragraphs[paragraph_id]
    result = run(candidate, dom, strict=False)
    if result['verdict'] != 'PASS': return result, None
    from citation_trace import MARKER
    cited = {i for i in MARKER.findall(candidate) if i in claims}
    if cited != set(selected['claims']):
        raise InputError('input claim IDs must equal selected paragraph claims; no reassignment permitted')
    updated = copy.deepcopy(dom)
    inventory(updated)[3][paragraph_id]['text'] = candidate
    result.update({'paragraph_id': paragraph_id, 'changed': selected['text'] != candidate, 'applied': False})
    return result, updated


def main(argv=None):
    temporary = None
    try:
        ap = Parser(description=__doc__)
        ap.add_argument('--text', required=True); ap.add_argument('--dom', required=True)
        ap.add_argument('--paragraph-id', required=True); ap.add_argument('--apply', action='store_true')
        args = ap.parse_args(argv)
        path = Path(args.dom)
        if path.resolve() == Path(args.text).resolve() or path.is_symlink():
            raise InputError('DOM must be a separate regular nonsymlink file')
        original = path.read_bytes()
        dom = load_dom(path)
        result, updated = ingest(Path(args.text).read_text(encoding='utf-8-sig'), dom, args.paragraph_id)
        if updated is not None and args.apply:
            if path.suffix.lower() == '.json': payload = json.dumps(updated, ensure_ascii=False, indent=2)
            else:
                import yaml
                payload = yaml.safe_dump(updated, allow_unicode=True, sort_keys=False)
            fd, temporary = tempfile.mkstemp(prefix='.draft-loop-', dir=path.parent)
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
                f.write(payload); f.flush(); os.fsync(f.fileno())
            if path.read_bytes() != original:
                raise InputError('DOM changed during ingestion; refusing overwrite')
            os.replace(temporary, path); temporary = None
            result['applied'] = True
    except Exception as exc:
        result = error_report(exc)
        result['applied'] = False
    finally:
        if temporary is not None: os.unlink(temporary)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
