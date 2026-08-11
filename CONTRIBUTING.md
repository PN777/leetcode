# Contributing

## Overview

- LeetSync automatically synchronizes accepted LeetCode solutions into this repository.
- Do **not** manually edit auto-generated README statistics.

## Expected Repository Structure

This repository is designed to keep LeetSync-generated solution folders at the root while reserving infrastructure files for tracking:

- `README.md` (manual + auto-generated sections)
- `scripts/update_stats.py` (stats generator)
- `.github/workflows/update-stats.yml` (automation)
- LeetSync-generated solution directories/files

The stats script supports different LeetSync naming patterns and handles missing metadata gracefully.

## How Statistics Are Generated

Statistics are derived from repository content (not fabricated):

1. Recursively scan likely solution files.
2. Infer language from file extension.
3. Infer problem number/title from path names when possible.
4. Infer difficulty only when detectable from path text.
5. Update only the section between:
   - `<!-- LEETCODE-STATS:START -->`
   - `<!-- LEETCODE-STATS:END -->`

## Run Locally

From repository root:

```bash
python scripts/update_stats.py
```

## Trigger GitHub Action Manually

- Go to **Actions** → **Update LeetCode Stats**
- Click **Run workflow**

## Important Rules

- Keep LeetSync solution sync behavior unchanged.
- Avoid manual edits to the generated stats section.
- If markers are missing in `README.md`, restore them before running the script.
