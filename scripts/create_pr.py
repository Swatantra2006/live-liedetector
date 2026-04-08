#!/usr/bin/env python3

import subprocess
import os
import sys
import glob as glob_module

# Find the project root by looking for .git directory
current_dir = os.getcwd()
print(f"[v0] Initial working directory: {current_dir}")

# Search for .git directory in current or parent directories
project_root = None
search_dir = current_dir
for _ in range(5):
    if os.path.isdir(os.path.join(search_dir, '.git')):
        project_root = search_dir
        break
    search_dir = os.path.dirname(search_dir)

if not project_root:
    # Try to find vercel.json or app.py files
    files = glob_module.glob('**/app.py', recursive=True)
    if files:
        project_root = os.path.dirname(os.path.abspath(files[0]))

if not project_root:
    print("[v0] Error: Could not find project root")
    sys.exit(1)

os.chdir(project_root)
print(f"[v0] Project root: {os.getcwd()}")

# Create a new branch for Vercel deployment
branch_name = "vercel-deployment-config"

try:
    # Check current branch
    result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                          capture_output=True, text=True, check=True)
    current_branch = result.stdout.strip()
    print(f"[v0] Current branch: {current_branch}")
    
    # Try to checkout existing branch or create new one
    try:
        subprocess.run(['git', 'checkout', branch_name], capture_output=True, check=True)
        print(f"[v0] Switched to existing branch: {branch_name}")
    except subprocess.CalledProcessError:
        subprocess.run(['git', 'checkout', '-b', branch_name], check=True)
        print(f"[v0] Created new branch: {branch_name}")
    
    # Add the changes
    print("[v0] Adding files...")
    subprocess.run(['git', 'add', 'requirements.txt', 'vercel.json', 'app.py'], check=True)
    
    # Commit the changes
    try:
        print("[v0] Committing changes...")
        subprocess.run([
            'git', 'commit', 
            '-m', 
            """Add Vercel deployment configuration

- Create requirements.txt with all Python dependencies
- Add vercel.json for serverless function configuration
- Update app.py to handle missing webcam gracefully for Vercel environment"""
        ], check=True)
        print("[v0] Commit successful")
    except subprocess.CalledProcessError:
        print("[v0] Nothing to commit")
    
    # Push to GitHub
    print("[v0] Pushing to GitHub...")
    subprocess.run(['git', 'push', '-u', 'origin', branch_name], check=True)
    
    print(f"\n✓ Changes committed and pushed to branch: {branch_name}")
    print(f"✓ Create a pull request at: https://github.com/Swatantra2006/live-liedetector/pull/new/{branch_name}")

except subprocess.CalledProcessError as e:
    print(f"Error executing git command: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
