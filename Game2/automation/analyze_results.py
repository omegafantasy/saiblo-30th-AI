#!/usr/bin/env python3
"""
Deep analysis of a completed iteration.
Reads iteration log directory, generates markdown report with:
- Score breakdown per case
- Question pattern analysis
- NPC visitation patterns
- Final answer correctness
- Comparison with admin baseline (if available)
- Comparison with previous iteration
- Concrete suggestions for next version

Usage:
  python analyze_results.py --iteration N
  python analyze_results.py --iteration-dir PATH
  python analyze_results.py --iteration N --compare-with M
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TOOLS_DIR = ROOT / 'Game2' / 'tools'
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from compare_match_runs import parse_final_answer

AUTO_DIR = Path(__file__).resolve().parent
LOGS_DIR = AUTO_DIR / 'logs'


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def load_iteration(iteration_dir: Path) -> dict[str, Any]:
    """Load all data for one iteration."""
    summary_path = iteration_dir / 'iteration_summary.json'
    summary = read_json(summary_path) or {}

    # Load individual match analyses
    matches_dir = iteration_dir / 'matches'
    match_analyses: list[dict[str, Any]] = []
    match_traces: dict[int, dict[str, Any]] = {}
    if matches_dir.is_dir():
        for match_dir in sorted(matches_dir.iterdir()):
            if not match_dir.is_dir():
                continue
            analysis = read_json(match_dir / 'analysis.json')
            if analysis:
                match_analyses.append(analysis)
                mid = analysis.get('match_id')
                trace = read_json(match_dir / 'match_download.json')
                if trace and mid:
                    match_traces[mid] = trace

    return {
        'dir': str(iteration_dir),
        'summary': summary,
        'match_analyses': match_analyses,
        'match_traces': match_traces,
    }


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def analyze_scores(data: dict[str, Any]) -> dict[str, Any]:
    """Breakdown of scores per match."""
    rows: list[dict[str, Any]] = []
    for analysis in data.get('match_analyses', []):
        match_id = analysis.get('match_id')
        players = analysis.get('players', [])
        my_score = None
        opp_score = None
        my_user = None
        opp_user = None
        for p in players:
            if not isinstance(p, dict):
                continue
            user = p.get('user', {}) if isinstance(p.get('user'), dict) else {}
            username = user.get('username', '')
            score = p.get('score')
            # Heuristic: first player listed is usually "us" in batch matches
            if my_score is None:
                my_score = score
                my_user = username
            else:
                opp_score = score
                opp_user = username
        rows.append({
            'match_id': match_id,
            'my_user': my_user,
            'my_score': my_score,
            'opp_user': opp_user,
            'opp_score': opp_score,
            'state': analysis.get('state'),
        })
    return {'score_rows': rows}


def analyze_cases(data: dict[str, Any]) -> dict[str, Any]:
    """Deep per-case analysis across all matches."""
    all_cases: list[dict[str, Any]] = []
    for analysis in data.get('match_analyses', []):
        match_id = analysis.get('match_id')
        for case in analysis.get('cases', []):
            if not isinstance(case, dict):
                continue
            result = case.get('final_result', {}) if isinstance(case.get('final_result'), dict) else {}
            parsed = parse_final_answer(str(case.get('final_answer', '')))
            correct_dims = [k for k, v in result.items() if v is True]
            incorrect_dims = [k for k, v in result.items() if v is False]
            all_cases.append({
                'match_id': match_id,
                'case_id': case.get('case_id'),
                'step_count': case.get('step_count', 0),
                'final_stage': case.get('final_stage'),
                'correct_dims': correct_dims,
                'incorrect_dims': incorrect_dims,
                'total_correct': len(correct_dims),
                'total_incorrect': len(incorrect_dims),
                'parsed_answer': parsed,
                'final_answer': case.get('final_answer', ''),
                'npc_question_counts': case.get('npc_question_counts', {}),
                'evidence_submission_counts': case.get('evidence_submission_counts', {}),
                'stage_transitions': case.get('stage_transitions', []),
            })
    return {'cases': all_cases}


def analyze_npc_patterns(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate NPC visitation patterns across cases."""
    npc_total: Counter[str] = Counter()
    npc_per_case: dict[str, list[int]] = defaultdict(list)
    for case in cases:
        npcs = case.get('npc_question_counts', {})
        for npc, count in npcs.items():
            npc_total[npc] += count
            npc_per_case[npc].append(count)
    return {
        'npc_total_questions': dict(npc_total.most_common()),
        'npc_case_frequency': {
            npc: len(counts) for npc, counts in sorted(npc_per_case.items(), key=lambda x: -sum(x[1]))
        },
        'npc_avg_per_case': {
            npc: round(sum(counts) / len(counts), 1)
            for npc, counts in sorted(npc_per_case.items(), key=lambda x: -sum(x[1]))
        },
    }


def analyze_question_patterns(data: dict[str, Any]) -> dict[str, Any]:
    """Extract and categorize question patterns."""
    all_questions: list[str] = []
    question_npc_map: dict[str, Counter[str]] = defaultdict(Counter)

    for analysis in data.get('match_analyses', []):
        for case in analysis.get('cases', []):
            if not isinstance(case, dict):
                continue
            for q_list_key in ('first_questions', 'last_questions'):
                for q_info in case.get(q_list_key, []):
                    if not isinstance(q_info, dict):
                        continue
                    q = q_info.get('question', '')
                    npc = q_info.get('npc', '')
                    if q and not q.startswith('提交最终答案:'):
                        all_questions.append(q)
                        question_npc_map[q][npc] += 1

    # Count question frequency
    q_counter = Counter(all_questions)

    # Categorize by pattern
    categories: dict[str, int] = defaultdict(int)
    for q in all_questions:
        if '证据' in q or 'evidence' in q.lower():
            categories['evidence_related'] += 1
        elif '嫌疑' in q or '凶手' in q or 'suspect' in q.lower():
            categories['suspect_related'] += 1
        elif '动机' in q or 'motive' in q.lower():
            categories['motive_related'] += 1
        elif '手法' in q or 'method' in q.lower():
            categories['method_related'] += 1
        elif '在哪' in q or '位置' in q or '地点' in q:
            categories['location_related'] += 1
        elif '时间' in q or '什么时候' in q:
            categories['time_related'] += 1
        elif '关系' in q or '认识' in q:
            categories['relationship_related'] += 1
        else:
            categories['other'] += 1

    return {
        'total_questions': len(all_questions),
        'unique_questions': len(q_counter),
        'top_questions': [{'question': q, 'count': c} for q, c in q_counter.most_common(15)],
        'categories': dict(categories),
    }


def analyze_stage_progression(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze how the AI progresses through stages."""
    stage_counts: Counter[str] = Counter()
    stage_step_counts: dict[str, list[int]] = defaultdict(list)
    for case in cases:
        final_stage = case.get('final_stage')
        if final_stage is not None:
            stage_counts[str(final_stage)] += 1
        stage_step_counts[str(final_stage)].append(case.get('step_count', 0))

    return {
        'final_stage_distribution': dict(stage_counts.most_common()),
        'avg_steps_by_final_stage': {
            stage: round(sum(steps) / len(steps), 1) if steps else 0
            for stage, steps in stage_step_counts.items()
        },
    }


def analyze_correctness(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate correctness per dimension across all cases."""
    dim_correct: Counter[str] = Counter()
    dim_incorrect: Counter[str] = Counter()
    dim_total: Counter[str] = Counter()

    total_cases = len(cases)
    total_fully_correct = 0
    total_partially_correct = 0
    total_all_wrong = 0

    for case in cases:
        for d in case.get('correct_dims', []):
            dim_correct[d] += 1
            dim_total[d] += 1
        for d in case.get('incorrect_dims', []):
            dim_incorrect[d] += 1
            dim_total[d] += 1
        tc = case.get('total_correct', 0)
        ti = case.get('total_incorrect', 0)
        if ti == 0 and tc > 0:
            total_fully_correct += 1
        elif tc > 0:
            total_partially_correct += 1
        elif ti > 0:
            total_all_wrong += 1

    dim_accuracy: dict[str, str] = {}
    for dim in dim_total:
        c = dim_correct.get(dim, 0)
        t = dim_total[dim]
        dim_accuracy[dim] = f'{c}/{t}'

    return {
        'total_cases': total_cases,
        'fully_correct': total_fully_correct,
        'partially_correct': total_partially_correct,
        'all_wrong': total_all_wrong,
        'no_answer': total_cases - total_fully_correct - total_partially_correct - total_all_wrong,
        'per_dimension_accuracy': dim_accuracy,
        'per_dimension_correct': dict(dim_correct),
        'per_dimension_incorrect': dict(dim_incorrect),
    }


def compare_iterations(
    current: dict[str, Any],
    previous: dict[str, Any],
) -> dict[str, Any]:
    """Compare two iteration datasets."""
    curr_case_data = analyze_cases(current)
    prev_case_data = analyze_cases(previous)
    curr_correct = analyze_correctness(curr_case_data['cases'])
    prev_correct = analyze_correctness(prev_case_data['cases'])

    curr_scores = analyze_scores(current)
    prev_scores = analyze_scores(previous)

    curr_my_scores = [r['my_score'] for r in curr_scores['score_rows'] if isinstance(r.get('my_score'), (int, float))]
    prev_my_scores = [r['my_score'] for r in prev_scores['score_rows'] if isinstance(r.get('my_score'), (int, float))]

    curr_avg = sum(curr_my_scores) / len(curr_my_scores) if curr_my_scores else 0
    prev_avg = sum(prev_my_scores) / len(prev_my_scores) if prev_my_scores else 0

    return {
        'score_change': {
            'previous_avg': round(prev_avg, 1),
            'current_avg': round(curr_avg, 1),
            'delta': round(curr_avg - prev_avg, 1),
            'previous_scores': prev_my_scores,
            'current_scores': curr_my_scores,
        },
        'correctness_change': {
            'previous': prev_correct,
            'current': curr_correct,
            'fully_correct_delta': curr_correct['fully_correct'] - prev_correct['fully_correct'],
            'all_wrong_delta': curr_correct['all_wrong'] - prev_correct['all_wrong'],
        },
    }


# ---------------------------------------------------------------------------
# Suggestion generation
# ---------------------------------------------------------------------------

def generate_suggestions(
    correctness: dict[str, Any],
    npc_patterns: dict[str, Any],
    question_patterns: dict[str, Any],
    stage_progression: dict[str, Any],
    cases: list[dict[str, Any]],
    comparison: dict[str, Any] | None,
) -> list[str]:
    """Generate concrete, actionable suggestions for the next version."""
    suggestions: list[str] = []

    # Check overall correctness
    if correctness.get('all_wrong', 0) > correctness.get('fully_correct', 0):
        suggestions.append(
            'HIGH PRIORITY: More cases are fully wrong than fully correct. '
            'Focus on basic information gathering before submitting answers.'
        )

    # Check per-dimension issues
    for dim, accuracy_str in correctness.get('per_dimension_accuracy', {}).items():
        parts = accuracy_str.split('/')
        if len(parts) == 2:
            correct_count = int(parts[0])
            total = int(parts[1])
            if total > 0 and correct_count / total < 0.5:
                suggestions.append(
                    f'Dimension "{dim}" has low accuracy ({accuracy_str}). '
                    f'Review the questioning strategy for this dimension.'
                )

    # Check stage progression
    stage_dist = stage_progression.get('final_stage_distribution', {})
    early_stages = sum(v for k, v in stage_dist.items() if k in ('0', '1', 'None', 'null'))
    total_stage_cases = sum(stage_dist.values()) if stage_dist else 0
    if total_stage_cases > 0 and early_stages / total_stage_cases > 0.3:
        suggestions.append(
            'Many cases end at early stages. The AI may be running out of steps '
            'or failing to progress. Consider optimizing question efficiency.'
        )

    # Check NPC diversity
    npc_freq = npc_patterns.get('npc_case_frequency', {})
    if npc_freq:
        top_npc = max(npc_freq, key=lambda x: npc_freq[x])
        total_npc_cases = sum(npc_freq.values())
        if npc_freq[top_npc] > total_npc_cases * 0.6:
            suggestions.append(
                f'NPC "{top_npc}" is queried disproportionately often. '
                f'Consider diversifying NPC visits to gather more varied information.'
            )

    # Check question diversity
    q_stats = question_patterns
    if q_stats.get('unique_questions', 0) < 5 and q_stats.get('total_questions', 0) > 10:
        suggestions.append(
            'Very few unique questions are being asked. '
            'The AI may be repeating the same questions. Add more question variety.'
        )

    # Check if evidence is being gathered
    categories = q_stats.get('categories', {})
    if categories.get('evidence_related', 0) == 0 and q_stats.get('total_questions', 0) > 5:
        suggestions.append(
            'No evidence-related questions detected. '
            'Consider adding questions that specifically ask about evidence or clues.'
        )

    # Step efficiency
    step_counts = [c.get('step_count', 0) for c in cases]
    if step_counts:
        avg_steps = sum(step_counts) / len(step_counts)
        if avg_steps > 40:
            suggestions.append(
                f'Average step count is high ({avg_steps:.0f}). '
                f'Consider more targeted questioning to reduce unnecessary steps.'
            )

    # Comparison-based suggestions
    if comparison:
        score_change = comparison.get('score_change', {})
        delta = score_change.get('delta', 0)
        if delta < 0:
            suggestions.append(
                f'Score regressed by {abs(delta):.1f} points vs previous iteration. '
                f'Review what changed and consider reverting problematic modifications.'
            )
        correct_delta = comparison.get('correctness_change', {}).get('fully_correct_delta', 0)
        if correct_delta < 0:
            suggestions.append(
                f'Fully correct cases decreased by {abs(correct_delta)}. '
                f'Check if recent changes broke previously working logic.'
            )

    if not suggestions:
        suggestions.append('No specific issues detected. Consider expanding test coverage with more opponents.')

    return suggestions


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def render_report(
    iteration_dir: Path,
    data: dict[str, Any],
    scores: dict[str, Any],
    case_analysis: dict[str, Any],
    correctness: dict[str, Any],
    npc_patterns: dict[str, Any],
    question_patterns: dict[str, Any],
    stage_progression: dict[str, Any],
    suggestions: list[str],
    comparison: dict[str, Any] | None,
) -> str:
    lines: list[str] = []

    summary = data.get('summary', {})
    lines.append(f'# Deep Analysis: Iteration {summary.get("iteration", "?")}')
    lines.append('')
    lines.append(f'- code_id: `{summary.get("code_id")}`')
    lines.append(f'- version: `{summary.get("version")}`')
    lines.append(f'- entity: `{summary.get("entity_name")}`')
    lines.append(f'- batch_id: `{summary.get("batch_id")}`')
    lines.append(f'- dir: `{iteration_dir}`')
    lines.append('')

    # ---- Scores ----
    lines.append('## Score Breakdown')
    lines.append('')
    for row in scores.get('score_rows', []):
        win_marker = ''
        if isinstance(row.get('my_score'), (int, float)) and isinstance(row.get('opp_score'), (int, float)):
            if row['my_score'] > row['opp_score']:
                win_marker = ' [WIN]'
            elif row['my_score'] < row['opp_score']:
                win_marker = ' [LOSS]'
            else:
                win_marker = ' [TIE]'
        lines.append(
            f'- match `{row.get("match_id")}` ({row.get("state")}): '
            f'my=`{row.get("my_score")}` vs opp=`{row.get("opp_score")}` '
            f'({row.get("my_user")} vs {row.get("opp_user")}){win_marker}'
        )
    lines.append('')

    # ---- Correctness ----
    lines.append('## Answer Correctness')
    lines.append('')
    lines.append(f'- total cases: `{correctness.get("total_cases")}`')
    lines.append(f'- fully correct: `{correctness.get("fully_correct")}`')
    lines.append(f'- partially correct: `{correctness.get("partially_correct")}`')
    lines.append(f'- all wrong: `{correctness.get("all_wrong")}`')
    lines.append(f'- no answer: `{correctness.get("no_answer")}`')
    lines.append('')
    lines.append('Per-dimension accuracy:')
    for dim, acc in correctness.get('per_dimension_accuracy', {}).items():
        lines.append(f'- `{dim}`: `{acc}`')
    lines.append('')

    # ---- Per-case detail ----
    lines.append('## Case Details')
    lines.append('')
    for case in case_analysis.get('cases', []):
        parsed = case.get('parsed_answer', {})
        lines.append(
            f'### Match {case.get("match_id")} / Case {case.get("case_id")}'
        )
        lines.append('')
        lines.append(f'- steps: `{case.get("step_count")}`')
        lines.append(f'- final_stage: `{case.get("final_stage")}`')
        lines.append(f'- correct: `{case.get("correct_dims")}` | incorrect: `{case.get("incorrect_dims")}`')
        lines.append(f'- murderer: `{parsed.get("murderer")}`')
        lines.append(f'- motivation: `{parsed.get("motivation")}`')
        lines.append(f'- method: `{parsed.get("method")}`')
        npcs = case.get('npc_question_counts', {})
        if npcs:
            lines.append(f'- NPC visits: `{dict(list(npcs.items())[:8])}`')
        evidence = case.get('evidence_submission_counts', {})
        if evidence:
            lines.append(f'- Evidence submitted: `{dict(list(evidence.items())[:8])}`')
        transitions = case.get('stage_transitions', [])
        if transitions:
            lines.append('- Stage transitions:')
            for t in transitions:
                lines.append(
                    f'  - step `{t.get("step_id")}`: '
                    f'`{t.get("from_stage")}` -> `{t.get("to_stage")}` '
                    f'(npc=`{t.get("npc")}`)'
                )
        lines.append('')

    # ---- NPC patterns ----
    lines.append('## NPC Visitation Patterns')
    lines.append('')
    lines.append('Total questions per NPC:')
    for npc, count in npc_patterns.get('npc_total_questions', {}).items():
        freq = npc_patterns.get('npc_case_frequency', {}).get(npc, 0)
        avg = npc_patterns.get('npc_avg_per_case', {}).get(npc, 0)
        lines.append(f'- `{npc}`: total=`{count}` cases=`{freq}` avg_per_case=`{avg}`')
    lines.append('')

    # ---- Question patterns ----
    lines.append('## Question Patterns')
    lines.append('')
    lines.append(f'- total questions: `{question_patterns.get("total_questions")}`')
    lines.append(f'- unique questions: `{question_patterns.get("unique_questions")}`')
    lines.append('')
    lines.append('Categories:')
    for cat, count in sorted(question_patterns.get('categories', {}).items(), key=lambda x: -x[1]):
        lines.append(f'- `{cat}`: `{count}`')
    lines.append('')
    lines.append('Top questions:')
    for item in question_patterns.get('top_questions', []):
        lines.append(f'- [{item.get("count")}x] `{str(item.get("question", ""))[:200]}`')
    lines.append('')

    # ---- Stage progression ----
    lines.append('## Stage Progression')
    lines.append('')
    lines.append('Final stage distribution:')
    for stage, count in stage_progression.get('final_stage_distribution', {}).items():
        avg_steps = stage_progression.get('avg_steps_by_final_stage', {}).get(stage, '?')
        lines.append(f'- stage `{stage}`: `{count}` cases (avg_steps=`{avg_steps}`)')
    lines.append('')

    # ---- Comparison ----
    if comparison:
        lines.append('## Comparison with Previous Iteration')
        lines.append('')
        sc = comparison.get('score_change', {})
        lines.append(f'- avg score: `{sc.get("previous_avg")}` -> `{sc.get("current_avg")}` (delta=`{sc.get("delta")}`)')
        lines.append(f'- previous scores: `{sc.get("previous_scores")}`')
        lines.append(f'- current scores: `{sc.get("current_scores")}`')
        cc = comparison.get('correctness_change', {})
        prev_c = cc.get('previous', {})
        curr_c = cc.get('current', {})
        lines.append(f'- fully correct: `{prev_c.get("fully_correct")}` -> `{curr_c.get("fully_correct")}`')
        lines.append(f'- all wrong: `{prev_c.get("all_wrong")}` -> `{curr_c.get("all_wrong")}`')
        lines.append('')

    # ---- Suggestions ----
    lines.append('## Action Items for Next Version')
    lines.append('')
    for i, s in enumerate(suggestions, 1):
        lines.append(f'{i}. {s}')
    lines.append('')

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_analysis(iteration_dir: Path, compare_dir: Path | None = None) -> str:
    """Run full analysis and return the markdown report."""
    data = load_iteration(iteration_dir)

    scores = analyze_scores(data)
    case_analysis = analyze_cases(data)
    cases = case_analysis['cases']
    correctness = analyze_correctness(cases)
    npc_patterns = analyze_npc_patterns(cases)
    question_patterns = analyze_question_patterns(data)
    stage_progression = analyze_stage_progression(cases)

    comparison = None
    if compare_dir and compare_dir.is_dir():
        prev_data = load_iteration(compare_dir)
        comparison = compare_iterations(data, prev_data)

    suggestions = generate_suggestions(
        correctness=correctness,
        npc_patterns=npc_patterns,
        question_patterns=question_patterns,
        stage_progression=stage_progression,
        cases=cases,
        comparison=comparison,
    )

    report = render_report(
        iteration_dir=iteration_dir,
        data=data,
        scores=scores,
        case_analysis=case_analysis,
        correctness=correctness,
        npc_patterns=npc_patterns,
        question_patterns=question_patterns,
        stage_progression=stage_progression,
        suggestions=suggestions,
        comparison=comparison,
    )

    # Save outputs
    report_path = iteration_dir / 'deep_analysis.md'
    report_path.write_text(report, encoding='utf-8')

    analysis_data = {
        'scores': scores,
        'correctness': correctness,
        'npc_patterns': npc_patterns,
        'question_patterns': question_patterns,
        'stage_progression': stage_progression,
        'suggestions': suggestions,
        'comparison': comparison,
    }
    analysis_path = iteration_dir / 'deep_analysis.json'
    analysis_path.write_text(json.dumps(analysis_data, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'Report written to: {report_path}', file=sys.stderr)
    print(f'Data written to: {analysis_path}', file=sys.stderr)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Deep analysis of a completed Game2 iteration')
    parser.add_argument('--iteration', type=int, default=0, help='Iteration number to analyze')
    parser.add_argument('--iteration-dir', type=str, default='', help='Direct path to iteration directory')
    parser.add_argument('--compare-with', type=int, default=0, help='Previous iteration number to compare with')
    parser.add_argument('--compare-dir', type=str, default='', help='Direct path to previous iteration for comparison')
    parser.add_argument('--print', action='store_true', help='Print report to stdout')
    args = parser.parse_args()

    # Resolve iteration directory
    if args.iteration_dir:
        iteration_dir = Path(args.iteration_dir).resolve()
    elif args.iteration > 0:
        iteration_dir = LOGS_DIR / f'iteration_{args.iteration}'
    else:
        # Find latest iteration
        candidates = sorted(LOGS_DIR.glob('iteration_*'), key=lambda p: p.name)
        if not candidates:
            print('No iteration directories found.', file=sys.stderr)
            return 1
        iteration_dir = candidates[-1]
        print(f'Using latest: {iteration_dir}', file=sys.stderr)

    if not iteration_dir.is_dir():
        print(f'Iteration directory not found: {iteration_dir}', file=sys.stderr)
        return 1

    # Resolve comparison directory
    compare_dir: Path | None = None
    if args.compare_dir:
        compare_dir = Path(args.compare_dir).resolve()
    elif args.compare_with > 0:
        compare_dir = LOGS_DIR / f'iteration_{args.compare_with}'
    else:
        # Auto-detect previous iteration
        match = re.search(r'iteration_(\d+)', iteration_dir.name)
        if match:
            prev_num = int(match.group(1)) - 1
            if prev_num >= 1:
                candidate = LOGS_DIR / f'iteration_{prev_num}'
                if candidate.is_dir():
                    compare_dir = candidate
                    print(f'Auto-comparing with: {compare_dir}', file=sys.stderr)

    report = run_analysis(iteration_dir, compare_dir)

    if args.print:
        print(report)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
