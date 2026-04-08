#!/bin/bash

# Create PR for Vercel deployment configuration

set -e

cd /vercel/share/v0-project

# Create a new branch for Vercel deployment
BRANCH_NAME="vercel-deployment-config"
git checkout -b "$BRANCH_NAME" 2>/dev/null || git checkout "$BRANCH_NAME"

# Add the changes
git add requirements.txt vercel.json app.py

# Commit the changes
git commit -m "Add Vercel deployment configuration

- Create requirements.txt with all Python dependencies
- Add vercel.json for serverless function configuration
- Update app.py to handle missing webcam gracefully for Vercel environment" || echo "Nothing to commit"

# Push to GitHub
git push -u origin "$BRANCH_NAME"

echo "✓ Changes committed and pushed to branch: $BRANCH_NAME"
echo "✓ Create a pull request at: https://github.com/Swatantra2006/live-liedetector/pull/new/$BRANCH_NAME"
