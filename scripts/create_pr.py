#!/usr/bin/env python3

import subprocess
import os
import sys

os.chdir('/vercel/share/v0-project')

# Create a new branch for Vercel deployment
branch_name = "vercel-deployment-config"

try:
    # Try to checkout existing branch or create new one
    subprocess.run(['git', 'checkout', branch_name], capture_output=True)
except:
    subprocess.run(['git', 'checkout', '-b', branch_name], check=True)

# Add the changes
subprocess.run(['git', 'add', 'requirements.txt', 'vercel.json', 'app.py'], check=True)

# Commit the changes
try:
    subprocess.run([
        'git', 'commit', 
        '-m', 
        """Add Vercel deployment configuration

- Create requirements.txt with all Python dependencies
- Add vercel.json for serverless function configuration
- Update app.py to handle missing webcam gracefully for Vercel environment"""
    ], check=True)
except subprocess.CalledProcessError:
    print("Nothing to commit")

# Push to GitHub
subprocess.run(['git', 'push', '-u', 'origin', branch_name], check=True)

print(f"\n✓ Changes committed and pushed to branch: {branch_name}")
print(f"✓ Create a pull request at: https://github.com/Swatantra2006/live-liedetector/pull/new/{branch_name}")
