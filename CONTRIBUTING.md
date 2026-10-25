# Contributing to Maia

Thanks for taking the time to contribute. Maia is a fork of CowAgent
(Copyright (c) 2022 zhayujie, © 2026 dubhagen, MIT).
Contributions of all sizes are welcome.

## Language policy

To keep the project accessible to a global community, **please write issues,
pull requests, code comments, and commit messages in English.** Imperfect
English is fine. Clear is enough, and machine translation is welcome.

## Reporting issues

Found a bug or have an idea? [Open an issue](https://github.com/dubhagen/Maia/issues/new).

Before opening one, please search existing issues (including closed ones) to
avoid duplicates, and make sure you're on the latest version.

## Submitting a pull request

1. **Fork** the repo and create a branch from `master`
   (e.g. `feat/web-search`, `fix/console-reconnect`).
2. Make your change. Keep it focused — one logical change per PR.
3. Follow the existing code style. Write comments and docstrings in English.
4. Run the app locally to confirm your change works.
5. Open a PR with a clear title and a short description of **what** and **why**.

We keep the bar friendly: clear, focused, and working is enough. Maintainers are
happy to help polish details during review.

### Commit & PR titles

Use a short, imperative summary. The [Conventional Commits](https://www.conventionalcommits.org/)
style is preferred but not required:

```
feat: add web search tool
fix: keep the web console connected after a proxy timeout
docs: clarify Docker setup
```

## Development setup

See [docs/guide/manual-install.md](docs/guide/manual-install.md). In short:

```bash
git clone https://github.com/dubhagen/Maia.git
cd Maia
pip install -r requirements.txt
pip install -e .
maia start
```

## Code of conduct

Be respectful and constructive.
