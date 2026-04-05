# OpenGOAL Knowledge Base — Session Notes

## Repo
https://github.com/open-goal/jak-project (clone to VM as jak-project)

## Approach
- Use git grep and git ls-tree for cheap triage — never read full files unless needed
- Sparse checkout folders instead of full repo when needed
- Write knowledge to this repo, load at start of next session
- Push outputs to GitHub, share direct link — never render large files in chat

## What we know
- Repo: 555MB total, 4871 .gc files
- Useful dirs: goal_src/jak1/ (game logic), docs/ (sparse, 3MB)
- Ignore: third-party/ (200MB), test/ (93MB)
- Key tool: git grep -l to find files, git grep -n to extract lines
- raw.githubusercontent.com is BLOCKED on Claude VM — use git clone only
- api.github.com is also BLOCKED

## Documented so far
- [x] babak.md — full enemy documentation

## Next candidates
- [ ] nav-enemy system (parent of all enemies)
- [ ] process-drawable (parent of all game objects)
- [ ] jak player entity
- [ ] level loading / entity system
- [ ] how to spawn any entity generically
