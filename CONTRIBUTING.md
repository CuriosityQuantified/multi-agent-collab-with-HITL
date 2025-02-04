# Contributing Guide

## Repository Structure
```
two-agent-collab-with-HITL/
├── main.py              # Main application code
├── helper_functions.py  # Utility functions
├── README.md           # Project documentation
├── .gitignore          # Git ignore rules
└── conversation_logs/   # Directory for conversation logs (not tracked)
```

## Step-by-Step Guide for Updates

### 1. Initial Setup (First Time Only)
```bash
# Clone the repository
git clone https://github.com/CuriosityQuantified/two-agent-collab-with-HITL.git
cd two-agent-collab-with-HITL

# Set up git configuration (if not already done)
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Set rebase as the default pull strategy
git config pull.rebase true
```

### 2. Before Making Changes
```bash
# Make sure you're on the main branch
git checkout main

# Get the latest changes
git pull origin main
```

### 3. Making Changes
1. Make your code changes
2. Test your changes thoroughly
3. Ensure no sensitive data (API keys, etc.) is included
4. Check that no conversation logs or temporary files are being tracked

### 4. Committing Changes
```bash
# Check what files have changed
git status

# Add your changes
git add <changed_files>
# Example: git add main.py helper_functions.py README.md

# Create a commit
git commit -m "[Cursor] Brief description of changes"
```

### 5. Pushing Changes
```bash
# Pull latest changes with rebase
git pull origin main

# Push your changes
git push origin main
```

## Important Notes

### Files to Never Commit
- `.env` files containing sensitive data
- `conversation_log_*.csv` files
- `__pycache__` directories
- Temporary development files (e.g., `agent_collab_v*.py`)

### Commit Message Format
- Always prefix commits with "[Cursor] "
- Use clear, descriptive messages
- For complex changes, use a multi-line commit message:
  ```bash
  git commit -m "[Cursor] Main change description

  - Detailed point 1
  - Detailed point 2
  - Detailed point 3"
  ```

### Troubleshooting

#### If Push is Rejected
```bash
# 1. Pull with rebase
git pull origin main

# 2. If there are conflicts, resolve them and then:
git add <resolved_files>
git rebase --continue

# 3. Push your changes
git push origin main
```

#### If Things Go Wrong
```bash
# To check current status
git status

# To discard all local changes
git reset --hard origin/main

# To start fresh
git fetch origin
git reset --hard origin/main
```

## Best Practices
1. Always pull before starting new work
2. Keep commits focused and atomic
3. Test changes before committing
4. Use meaningful commit messages
5. Don't commit temporary or generated files
6. Regularly check `git status` to ensure you're not committing unwanted files 