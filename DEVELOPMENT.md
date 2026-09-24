# Development Guide & Git Flow Workflow

## Git Flow Workflow

This project follows **Git Flow** branching model:

### Branch Structure
| Branch | Purpose |
|--------|---------|
| `master` | Production-ready code (protected) |
| `develop` | Integration branch for features |
| `feature/*` | New features (branch from `develop`) |
| `bugfix/*` | Bug fixes for `develop` |
| `release/*` | Release preparation |
| `hotfix/*` | Emergency fixes for `master` |

### Branching Strategy

```
master (production)
  │
  └── develop (integration)
       │
       ├── feature/improve-mcp-resolver  ← current
       ├── feature/xxx
       └── bugfix/xxx
```

## Branch Naming Conventions
| Type | Prefix | Example |
|------|--------|---------|
| Feature | `feature/` | `feature/improve-mcp-resolver` |
| Bugfix | `bugfix/` | `bugfix/fix-resolve-scihub` |
| Release | `release/` | `release/v1.2.0` |
| Hotfix | `hotfix/` | `hotfix/fix-critical-bug` |

## Workflow

### Starting a Feature
```bash
# From develop branch
git flow feature start my-new-feature
# or manually:
git checkout develop
git pull origin develop
git checkout -b feature/my-feature
```

### During Development
```bash
# Work on feature, commit often
git add .
git commit -m "feat: descriptive message"

# Push feature branch to remote
git push -u origin feature/my-feature
```

### Finishing a Feature
```bash
# Option 1: Git Flow (recommended)
git flow feature finish my-feature

# Or manually:
git checkout develop
git pull origin develop
git merge --no-ff feature/my-feature
git push origin develop
git push origin --delete feature/my-feature
git branch -d feature/my-feature
```

### Pull Request Process
1. Push feature branch: `git push -u origin feature/my-feature`
2. Create PR on GitHub: `feature/my-feature` → `develop`
3. CI checks must pass
4. Code review required
4. Squash and merge (prefer squash for clean history)
5. Delete feature branch after merge

### Release Process
```bash
git flow release start v1.2.0
# test, version bump, changelog
git flow release finish v1.2.0
```

### Hotfix Process
```bash
git flow hotfix start critical-fix
# fix, test
git flow hotfix finish critical-fix
```

## Branch Protection Rules (GitHub)
- `master`: Require PR, 2 approvals, status checks, linear history
- `develop`: Require PR, 1 approval, status checks

## Commit Message Convention
```
type(scope): subject

body (optional)

footer (optional)
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`, `build`

Examples:
```
feat(mcp): add resolve cascade with local corpus
fix(downloader): handle sci-hub URL normalization
docs(deps): update mcp to 1.26.0
```

## Commit Signing
- Sign commits: `git commit -S -m "message"`
- GPG key configured in GitHub settings

## Code Review Checklist
- [ ] Tests pass (CI green)
- [ ] Code follows style guide
- [ ] Tests added for new functionality
- [ ] Documentation updated
- [ ] No breaking changes (or noted in PR)
- [ ] Changelog entry if user-facing

## Release Process
1. `git flow release start v1.x.x`
2. Update version, CHANGELOG.md
3. `git flow release finish v1.x.x`
4. Creates tag, merges to master & develop
4. GitHub Release with changelog

## Hotfix Process
```bash
git flow hotfix start critical-bug
# fix
git flow hotfix finish critical-bug
# merges to master + develop, creates tag
```

## Useful Commands
```bash
# Start feature
git flow feature start my-feature
# or manually:
git checkout develop && git pull && git checkout -b feature/my-feature

# Finish feature
git flow feature finish my-feature

# Start release
git flow release start v1.2.0

# Finish release
git flow release finish v1.2.0

# Hotfix
git flow hotfix start critical-fix
git flow hotfix finish critical-fix
```

## Useful Aliases (add to ~/.gitconfig)
```ini
[alias]
    feature = flow feature
    release = flow release
    hotfix = flow hotfix
    finish = flow feature finish
    start = flow feature start
    pub = push -u origin HEAD
```