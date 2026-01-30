#!/bin/bash
cp -R /Users/lyzniu/Library/Mobile Documents/iCloud~md~obsidian/Documents/ObsidianVault/Documentations/DavidRumseyMapCenter /Users/lyzniu/GitHubProjects/4x4-interactive/DavidRumseyMapCenter
cd /Users/lyzniu/GitHubProjects/4x4-interactive
git add .
git commit -m "Update documentations: $(date +'%Y-%m-%d %H:%M:%S')"
git push origin main 