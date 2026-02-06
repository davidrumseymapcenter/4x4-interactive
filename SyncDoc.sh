# Copy folder from source repo to destination repo
cp -R '/Users/lyzniu/Library/Mobile Documents/iCloud~md~obsidian/Documents/ObsidianVault/Documentations/DRMCwebmapDoc' /Users/lyzniu/GitHubProjects/4x4-interactive

# Go to destination repo
cd /Users/lyzniu/GitHubProjects/4x4-interactive/DavidRumseyMapCenter

# Add, commit, and push changes
git checkout main
git add .
git commit -m "Update notes: $(date '+%Y-%m-%d %H:%M:%S')"
git push origin main