# Milestone Manager

`milestone_manager.py` saves and restores Python-file snapshots of this project.

## What It Does

- `create` copies current project `.py` files into a timestamped milestone folder.
- `list` shows saved milestones from `index.json`.
- `restore` copies `.py` files from a selected milestone back into the project.

Milestones are stored inside the `milestones/` folder with:

- `metadata.json`: milestone metadata and tracked files
- `project/`: copied snapshot of project Python files

## Commands

### Create a milestone

```bash
python milestones/milestone_manager.py create -d "short description"
```

Example:

```bash
python milestones/milestone_manager.py create -d "before heap rewrite"
```

### List milestones

```bash
python milestones/milestone_manager.py list
```

### Restore a milestone

```bash
python milestones/milestone_manager.py restore -i <milestone_id>
```

Example:

```bash
python milestones/milestone_manager.py restore -i 20260325_123836_ai-2
```

## Fuzzy Restore Behavior

`restore` supports more than exact IDs.

If the provided ID is not an exact match:

- it first looks for partial matches in milestone IDs and descriptions
- then it tries fuzzy matches
- if still nothing matches, it shows the latest milestones for manual selection

When matches are shown, enter the printed number to choose one milestone.
Press Enter with no selection to cancel.

The number of fuzzy or fallback candidates is controlled by:

```python
DEFAULT_MATCH_LIMIT
```

inside [milestone_manager.py](/c:/Users/JasonLi/OneDrive/Desktop/script/nlp_0326/milestones/milestone_manager.py).

## Help

To print the full help for all commands:

```bash
python milestones/milestone_manager.py -h
```

## Notes

- Only `.py` files are included in milestone snapshots.
- The `milestones/` folder itself is excluded from snapshot copying.
- Restore overwrites current project `.py` files with the selected snapshot.
