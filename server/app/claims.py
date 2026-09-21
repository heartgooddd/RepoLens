"""Verify model/stub references against immutable snapshot data; never overwrite facts."""
import hashlib
from .config import Settings
from .db import connect
from .import_policy import MAX_FILE


def verify_claims(settings: Settings, snapshot_id: str, data: dict) -> list[dict]:
    with connect(settings.database) as db:
        files = {r['path']: r['sha256'] for r in db.execute('SELECT * FROM snapshot_files WHERE snapshot_id = ?', (snapshot_id,))}
        folders = {r[0] for r in db.execute('SELECT path FROM folder_cards WHERE snapshot_id = ?', (snapshot_id,))}
    result = []
    claims = data.get('claims', []) if isinstance(data, dict) else []
    if not isinstance(claims, list):
        return []
    for claim in claims[:100]:
        if not isinstance(claim, dict):
            continue
        refs = claim.get('references', [])
        folder = claim.get('folder_path')
        valid = isinstance(folder, str) and folder in folders and isinstance(refs, list) and 0 < len(refs) <= 20
        checked = []
        for ref in refs[:20] if isinstance(refs, list) else []:
            matched = False
            try:
                path = ref['file_path']
                if path in files:
                    target = settings.data_dir / 'snapshots' / snapshot_id / path
                    if target.is_symlink() or any(p.is_symlink() for p in target.parents):
                        raise ValueError('link')
                    with target.open('rb') as stream:
                        raw = stream.read(MAX_FILE + 1)
                    start, end = ref['line_start'], ref['line_end']
                    lines = raw.decode('utf-8').splitlines()
                    matched = (type(start) is int and type(end) is int and 1 <= start <= end <= len(lines)
                               and hashlib.sha256(raw).hexdigest() == files[path]
                               and '\n'.join(lines[start - 1:end]) == ref['quote'])
            except (KeyError, TypeError, OSError, ValueError):
                pass
            valid = valid and matched
            checked.append({'file_path': ref.get('file_path') if isinstance(ref, dict) else None, 'matched': matched,
                            'line_start': ref.get('line_start') if isinstance(ref, dict) and type(ref.get('line_start')) is int else None,
                            'line_end': ref.get('line_end') if isinstance(ref, dict) and type(ref.get('line_end')) is int else None,
                            'quote': str(ref.get('quote', ''))[:4000] if isinstance(ref, dict) else ''})
        result.append({'folder_path': str(claim.get('folder_path', ''))[:700],
                       'description': str(claim.get('description', ''))[:2000],
                       'claim_type': 'inference' if valid else 'unverified',
                       'references': checked,
                       'note': '引用已匹配；仍属推断，未验证语义正确性。' if valid else '引用不匹配或缺失，职责待核实。'})
    return result
