#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ROOM_ROOT = ROOT / 'Game2' / 'runtime' / 'room_matches'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_late_probe_results.md'
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_late_probe_results.json'
DEFAULT_LABELS = [
    'n574c',
    'n576a', 'n576b', 'n576c',
    'n577a', 'n577b', 'n577c', 'n577d', 'n577e',
    'n578a', 'n578b', 'n578c', 'n578d', 'n578e', 'n578f',
    'n579a', 'n579b', 'n579c', 'n579d',
    'n580a', 'n580b', 'n580c', 'n580d',
    'n581a', 'n581b', 'n581c', 'n581d',
    'n582a', 'n582b', 'n582c', 'n582d',
    'n583a', 'n583b', 'n583c', 'n583d',
    'n584a', 'n584b', 'n584c', 'n584d',
    'n585a', 'n585b', 'n585c', 'n585d',
    'n586a', 'n586b', 'n586c', 'n586d',
    'n587a', 'n587b', 'n587c', 'n587d',
    'n588a', 'n588b', 'n588c', 'n588d',
    'n589a', 'n589b', 'n589c', 'n589d',
    'n590a', 'n590b', 'n590c', 'n590d',
    'n591a', 'n591b', 'n591c', 'n591d',
    'n592a', 'n592b', 'n592c', 'n592d',
    'n593a', 'n593b', 'n593c', 'n593d',
    'n594a', 'n594b', 'n594c', 'n594d',
    'n595a', 'n595b', 'n595c', 'n595d',
    'n596a', 'n596b', 'n596c', 'n596d', 'n596e', 'n596f', 'n596g', 'n596h',
    'n597a', 'n597b', 'n597c', 'n597d', 'n597e',
    'n598a', 'n598b', 'n598c', 'n598d', 'n598e',
    'n599a', 'n599b', 'n599c', 'n599d', 'n599e', 'n599f',
    'n600a', 'n600b', 'n600c', 'n600d', 'n600e',
    'n601a', 'n601b', 'n601c', 'n601d', 'n601e', 'n601f',
    'n602a', 'n602b', 'n602c', 'n602d', 'n602e', 'n602f',
    'n603a', 'n603b', 'n603c', 'n603d',
    'n604a', 'n604b', 'n604c', 'n604d', 'n604e', 'n604f',
    'n605a', 'n605b', 'n605c', 'n605d', 'n605e',
    'n606a', 'n606b', 'n606c',
    'n607a', 'n607b', 'n607c',
    'n608a', 'n608b', 'n608c',
    'n609a', 'n609b', 'n609c',
    'n610b', 'n610c',
    'n611a', 'n611b', 'n611c',
    'n612a', 'n612b', 'n612c',
    'n613a', 'n613b', 'n613c',
    'n614a', 'n614b',
    'n615a', 'n615b', 'n615c', 'n615d',
    'n616a', 'n616b',
    'n617a', 'n617b', 'n617c', 'n617d', 'n617e',
    'n618a', 'n618b', 'n618c', 'n618d',
    'n619a', 'n619b', 'n619c',
    'n620a', 'n620b', 'n620c',
    'n621a', 'n621b', 'n621c',
    'n622a', 'n622b', 'n622c',
    'n623a', 'n623b', 'n623c', 'n623d',
    'sk548e0910pzb',
    'sk548e0910pzt', 'sk548e0910pzu', 'sk548e0910pzv', 'sk548e0910pzw', 'sk548e0910pzx', 'sk548e0910pzy', 'sk548e0910pzz',
    'sk548e0910qaa', 'sk548e0910qab', 'sk548e0910qac', 'sk548e0910qad', 'sk548e0910qae',
    'sk548e0910qaf', 'sk548e0910qag', 'sk548e0910qah', 'sk548e0910qai', 'sk548e0910qaj', 'sk548e0910qak', 'sk548e0910qal', 'sk548e0910qam', 'sk548e0910qan', 'sk548e0910qao',
    'sk548e0910qap', 'sk548e0910qaq', 'sk548e0910qar', 'sk548e0910qas', 'sk548e0910qat',
    'sk548e0910qau', 'sk548e0910qav', 'sk548e0910qaw', 'sk548e0910qax', 'sk548e0910qay', 'sk548e0910qaz', 'sk548e0910qba', 'sk548e0910qbb', 'sk548e0910qbc', 'sk548e0910qbd',
    'sk548e0910qbe', 'sk548e0910qbf', 'sk548e0910qbg', 'sk548e0910qbh', 'sk548e0910qbi', 'sk548e0910qbj', 'sk548e0910qbk', 'sk548e0910qbl', 'sk548e0910qbm', 'sk548e0910qbn',
]
INTERESTING_EVIDENCE = {
    '401', '402', '404', '405', '501', '502', '503', '504',
    '505',
    '601', '602', '603', '604', '605', '606', '607', '608',
    '701', '702', '703', '704', '705', '706', '707', '708',
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def label_from_dir(path: Path, labels: list[str]) -> str:
    name = path.name
    for label in sorted(labels, key=len, reverse=True):
        if f'_{label}_' in name or name.endswith(f'_{label}_room') or name == label:
            return label
    return ''


def evidence_sets(analysis: dict[str, Any]) -> list[str]:
    found: set[str] = set()
    for rec in analysis.get('decoded_stdin_records') or []:
        if not isinstance(rec, dict):
            continue
        for ev in rec.get('evidences') or []:
            if not isinstance(ev, dict):
                continue
            eid = str(ev.get('id', ''))
            if eid in INTERESTING_EVIDENCE:
                found.add(eid)
    return sorted(found)


def collect(labels: list[str]) -> dict[str, Any]:
    rows_by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in sorted(ROOM_ROOT.glob('*_room')):
        label = label_from_dir(d, labels)
        if not label:
            continue
        for analysis_path in sorted(d.glob('matches/*/analysis.json')):
            analysis = load_json(analysis_path)
            player = (analysis.get('players') or [{}])[0]
            score = player.get('score')
            row = {
                'label': label,
                'room_dir': str(d.relative_to(ROOT)),
                'match_id': analysis_path.parent.name,
                'end_state': player.get('end_state'),
                'score': score if isinstance(score, int) else None,
                'evidence': evidence_sets(analysis),
            }
            rows_by_label[label].append(row)

    summary: dict[str, Any] = {}
    for label in labels:
        rows = rows_by_label.get(label, [])
        valid_scores = [row['score'] for row in rows if isinstance(row.get('score'), int) and row.get('score', 0) > 0]
        evidence_counter: Counter[str] = Counter()
        for row in rows:
            evidence_counter.update(row.get('evidence') or [])
        summary[label] = {
            'samples': len(rows),
            'valid_samples': len(valid_scores),
            'score_distribution': dict(sorted(Counter(valid_scores).items())),
            'min_score': min(valid_scores) if valid_scores else None,
            'max_score': max(valid_scores) if valid_scores else None,
            'avg_score': (sum(valid_scores) / len(valid_scores)) if valid_scores else None,
            'evidence_counts': dict(sorted(evidence_counter.items())),
            'rows': rows,
        }
    return {'labels': labels, 'summary': summary}


def write_outputs(data: dict[str, Any]) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    lines = ['# Game2 Late Probe Results', '']
    lines.append('| label | valid | distribution | min | max | avg | evidence |')
    lines.append('| --- | ---: | --- | ---: | ---: | ---: | --- |')
    for label in data['labels']:
        item = data['summary'][label]
        dist = ', '.join(f'{score}x{count}' for score, count in item['score_distribution'].items()) or '-'
        evid = ', '.join(f'{eid}x{count}' for eid, count in item['evidence_counts'].items()) or '-'
        avg = item['avg_score']
        avg_text = f'{avg:.1f}' if isinstance(avg, float) else '-'
        lines.append(
            f"| `{label}` | {item['valid_samples']} | {dist} | "
            f"{item['min_score'] if item['min_score'] is not None else '-'} | "
            f"{item['max_score'] if item['max_score'] is not None else '-'} | "
            f"{avg_text} | {evid} |"
        )
    lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='Summarize neutral Game2 late Poker/Yuan probe room results')
    parser.add_argument('--labels', nargs='*', default=DEFAULT_LABELS)
    args = parser.parse_args()
    labels = [str(label).strip() for label in args.labels if str(label).strip()]
    data = collect(labels)
    write_outputs(data)
    print(json.dumps({'out_md': str(OUT_MD), 'out_json': str(OUT_JSON)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
