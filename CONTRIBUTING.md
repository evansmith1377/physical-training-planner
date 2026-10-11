# Contributing

Thanks for helping improve the planner. It's a small project, so the process is light.

1. **Open an issue first** for anything bigger than a fix, so we can agree on the approach.
2. **Work on a branch** and open a pull request into `main`. The PR template lists the checks.
3. **Keep the page dependency-free.** No frameworks, CDNs, trackers or network requests; see [CLAUDE.md](CLAUDE.md) for the full set of rules and conventions.
4. **Run the tests** before pushing:

   ```sh
   pip install -r requirements-dev.txt
   python -m playwright install chromium
   pytest -q
   ```

5. If you edit the inline `<script>`, run `python scripts/csp_hash.py` so the Content Security Policy still allows it. CI fails if you forget.

Merging to `main` deploys the site automatically after the tests pass.

Training advice in the planner should stay conservative and effort-first. If you change plan rules, safety warnings or nutrition text, explain the reasoning and cite a source in the PR, and say how the change holds up through the coach, sports-medicine and dietitian lenses. [CLAUDE.md → Review lenses](CLAUDE.md#review-lenses) lists the perspectives and personas to check a change against.

By contributing you agree your work is released under [the Unlicense](LICENSE).
