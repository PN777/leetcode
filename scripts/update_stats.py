#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

README_PATH = "README.md"
START_MARKER = "<!-- LEETCODE-STATS:START -->"
END_MARKER = "<!-- LEETCODE-STATS:END -->"

IGNORED_DIRS = {
    ".git",
    ".github",
    "scripts",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
}

CODE_EXTENSIONS = {
    ".java": "Java",
    ".py": "Python",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".c": "C",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".cs": "C#",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".rb": "Ruby",
    ".php": "PHP",
    ".scala": "Scala",
    ".sql": "SQL",
}

PROBLEM_NUMBER_RE = re.compile(r"(?<!\d)(\d{1,5})(?!\d)")
DIFFICULTY_RE = re.compile(r"\b(easy|medium|hard)\b", re.IGNORECASE)
TITLE_SEP_RE = re.compile(r"[-_.]+")


@dataclass
class SolutionRecord:
    file_path: Path
    language: str
    problem_key: str
    problem_number: Optional[int]
    problem_title: Optional[str]
    difficulty: Optional[str]
    solved_date: Optional[str]


def looks_like_solution_file(rel_path: Path) -> bool:
    if rel_path.name.lower() in {"readme.md", "contributing.md"}:
        return False
    if rel_path.suffix.lower() not in CODE_EXTENSIONS:
        return False
    if len(rel_path.parts) < 2:
        return False
    if not any(PROBLEM_NUMBER_RE.search(part) for part in rel_path.parts):
        return False
    return True


def extract_number_and_title(candidate: str) -> tuple[Optional[int], Optional[str]]:
    match = PROBLEM_NUMBER_RE.search(candidate)
    number = int(match.group(1)) if match else None

    title = None
    if match:
        raw = candidate[match.end() :]
        raw = raw.strip(" -_./")
        if raw:
            cleaned = TITLE_SEP_RE.sub(" ", raw).strip()
            if cleaned:
                title = " ".join(word.capitalize() for word in cleaned.split())

    if not title:
        cleaned = TITLE_SEP_RE.sub(" ", candidate).strip()
        cleaned = re.sub(r"\b\d{1,5}\b", "", cleaned).strip()
        if cleaned:
            title = " ".join(word.capitalize() for word in cleaned.split())

    return number, title


def extract_problem_metadata(rel_path: Path) -> tuple[Optional[int], Optional[str], str]:
    candidates = list(rel_path.parent.parts[::-1]) + [rel_path.stem]

    for candidate in candidates:
        number, title = extract_number_and_title(candidate)
        if number is not None:
            key = f"#{number}:{title or 'Unknown'}"
            return number, title, key

    fallback_title = " ".join(word.capitalize() for word in TITLE_SEP_RE.sub(" ", rel_path.stem).split())
    key = f"path:{str(rel_path.parent).lower()}"
    return None, (fallback_title or None), key


def extract_difficulty(rel_path: Path) -> Optional[str]:
    path_text = "/".join(rel_path.parts)
    match = DIFFICULTY_RE.search(path_text)
    if not match:
        return None
    return match.group(1).capitalize()


def git_date_for_file(repo_root: Path, rel_path: Path, cache: dict[str, Optional[str]]) -> Optional[str]:
    cache_key = str(rel_path)
    if cache_key in cache:
        return cache[cache_key]

    try:
        completed = subprocess.run(
            ["git", "log", "-1", "--date=short", "--format=%ad", "--", str(rel_path)],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        cache[cache_key] = None
        return None

    if completed.returncode != 0:
        cache[cache_key] = None
        return None

    date_str = completed.stdout.strip() or None
    cache[cache_key] = date_str
    return date_str


def scan_solutions(repo_root: Path) -> list[SolutionRecord]:
    records: list[SolutionRecord] = []
    date_cache: dict[str, Optional[str]] = {}

    for current_root, dirnames, filenames in os.walk(repo_root):
        rel_root = Path(current_root).relative_to(repo_root)

        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]

        if any(part in IGNORED_DIRS for part in rel_root.parts):
            continue

        for filename in filenames:
            if filename.startswith("."):
                continue

            rel_path = rel_root / filename if rel_root != Path(".") else Path(filename)
            if not looks_like_solution_file(rel_path):
                continue

            language = CODE_EXTENSIONS[rel_path.suffix.lower()]
            number, title, problem_key = extract_problem_metadata(rel_path)
            difficulty = extract_difficulty(rel_path)
            solved_date = git_date_for_file(repo_root, rel_path, date_cache)

            records.append(
                SolutionRecord(
                    file_path=rel_path,
                    language=language,
                    problem_key=problem_key,
                    problem_number=number,
                    problem_title=title,
                    difficulty=difficulty,
                    solved_date=solved_date,
                )
            )

    return records


def render_bar_chart(language_counter: Counter[str]) -> str:
    if not language_counter:
        return "_No detected solution files yet._"

    max_count = max(language_counter.values())
    lines = []
    for language, count in sorted(language_counter.items(), key=lambda item: (-item[1], item[0])):
        blocks = max(1, round((count / max_count) * 20))
        lines.append(f"- {language:<10} {'█' * blocks} ({count})")
    return "\n".join(lines)


def parse_date(value: Optional[str]) -> Optional[dt.date]:
    if not value:
        return None
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def build_problem_summary(records: list[SolutionRecord]) -> dict[str, dict]:
    summary: dict[str, dict] = {}
    for record in records:
        data = summary.setdefault(
            record.problem_key,
            {
                "number": record.problem_number,
                "title": record.problem_title,
                "difficulty": None,
                "languages": set(),
                "latest_date": None,
            },
        )

        if not data["title"] and record.problem_title:
            data["title"] = record.problem_title
        if not data["difficulty"] and record.difficulty:
            data["difficulty"] = record.difficulty
        data["languages"].add(record.language)

        candidate_date = parse_date(record.solved_date)
        existing_date = parse_date(data["latest_date"])
        if candidate_date and (existing_date is None or candidate_date > existing_date):
            data["latest_date"] = record.solved_date

    return summary


def calc_current_streak(latest_dates: list[dt.date]) -> Optional[int]:
    if not latest_dates:
        return None

    unique_dates = sorted(set(latest_dates), reverse=True)
    today = dt.date.today()
    if unique_dates[0] not in {today, today - dt.timedelta(days=1)}:
        return 0

    streak = 1
    for idx in range(1, len(unique_dates)):
        if unique_dates[idx - 1] - unique_dates[idx] == dt.timedelta(days=1):
            streak += 1
        else:
            break
    return streak


def render_solution_index(problem_summary: dict[str, dict], max_rows: int = 200) -> str:
    if not problem_summary:
        return "_No solved problems detected yet._"

    rows = sorted(
        problem_summary.values(),
        key=lambda item: (
            item["number"] is None,
            item["number"] if item["number"] is not None else 10**9,
            (item["title"] or "").lower(),
        ),
    )

    displayed = rows[:max_rows]
    table_lines = [
        "| # | Problem | Difficulty | Language(s) |",
        "| - | ------- | ---------- | ----------- |",
    ]

    for row in displayed:
        number = row["number"] if row["number"] is not None else "—"
        title = row["title"] or "Unknown"
        difficulty = row["difficulty"] or "Unknown"
        languages = ", ".join(sorted(row["languages"])) if row["languages"] else "Unknown"
        table_lines.append(f"| {number} | {title} | {difficulty} | {languages} |")

    if len(rows) > max_rows:
        table_lines.append("")
        table_lines.append(f"_Showing first {max_rows} of {len(rows)} detected solved problems._")

    return "\n".join(table_lines)


def render_recent(problem_summary: dict[str, dict], limit: int = 10) -> str:
    dated = []
    for item in problem_summary.values():
        date_obj = parse_date(item["latest_date"])
        if not date_obj:
            continue
        dated.append((date_obj, item))

    if not dated:
        return "_No reliable solved dates available from git history yet._"

    dated.sort(key=lambda pair: pair[0], reverse=True)
    lines = []
    for date_obj, item in dated[:limit]:
        num = f"#{item['number']}" if item["number"] is not None else "#—"
        title = item["title"] or "Unknown"
        diff = item["difficulty"] or "Unknown"
        lines.append(f"- {date_obj.isoformat()} — {num} {title} ({diff})")
    return "\n".join(lines)


def render_milestones(total_solved: int) -> str:
    milestones = [25, 50, 100, 150, 200, 250, 300, 500, 750, 1000]
    lines = []
    for milestone in milestones:
        status = "✅" if total_solved >= milestone else "🔒"
        lines.append(f"- {milestone} problems → {status}")
    return "\n".join(lines)


def build_stats_markdown(records: list[SolutionRecord]) -> str:
    language_counter = Counter(record.language for record in records)
    problem_summary = build_problem_summary(records)
    total_solved = len(problem_summary)

    difficulty_counter = Counter()
    solved_dates: list[dt.date] = []

    for item in problem_summary.values():
        difficulty = item["difficulty"]
        if difficulty in {"Easy", "Medium", "Hard"}:
            difficulty_counter[difficulty] += 1
        parsed = parse_date(item["latest_date"])
        if parsed:
            solved_dates.append(parsed)

    total_submissions = len(records)
    acceptance_rate = "N/A"
    current_streak = calc_current_streak(solved_dates)
    current_streak_text = str(current_streak) if current_streak is not None else "N/A"

    generated_at = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M UTC")

    return "\n".join(
        [
            START_MARKER,
            f"_Last updated: {generated_at}_",
            "",
            "### Snapshot",
            f"- Total solved: **{total_solved}**",
            f"- Easy: **{difficulty_counter.get('Easy', 0)}**",
            f"- Medium: **{difficulty_counter.get('Medium', 0)}**",
            f"- Hard: **{difficulty_counter.get('Hard', 0)}**",
            f"- Total detected solution files (submissions proxy): **{total_submissions}**",
            f"- Acceptance rate: **{acceptance_rate}**",
            f"- Current streak (from git-dated solves): **{current_streak_text}**",
            "",
            "### Languages",
            render_bar_chart(language_counter),
            "",
            "### Recently Solved",
            render_recent(problem_summary),
            "",
            "### Milestones (Auto)",
            render_milestones(total_solved),
            "",
            "### Solution Index (Auto)",
            render_solution_index(problem_summary),
            END_MARKER,
        ]
    )


def update_readme(readme_path: Path, stats_block: str) -> bool:
    content = readme_path.read_text(encoding="utf-8")

    if START_MARKER not in content or END_MARKER not in content:
        raise RuntimeError(
            "README markers not found. Ensure both markers exist before running the stats updater."
        )

    pattern = re.compile(re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL)
    updated = pattern.sub(stats_block, content, count=1)

    if updated == content:
        return False

    readme_path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    readme_path = repo_root / README_PATH

    if not readme_path.exists():
        print("ERROR: README.md not found.", file=sys.stderr)
        return 1

    records = scan_solutions(repo_root)
    stats_block = build_stats_markdown(records)

    changed = update_readme(readme_path, stats_block)
    if changed:
        print("README statistics updated.")
    else:
        print("README statistics already up to date.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
