#!/bin/bash
# Quick start script for Ralph LLM integration

set -e

echo "================================================"
echo "  Ralph - MeshCore Bot LLM Tools Integration"
echo "================================================"
echo ""
echo "This will:"
echo "  1. Create branch: ralph/llm-tools-integration"
echo "  2. Run Ralph for 25 iterations"
echo "  3. Implement 15 user stories autonomously"
echo ""
echo "Features to be implemented:"
echo "  - LLM tool calling (commands as tools)"
echo "  - User mentions in responses"
echo "  - Universal command context tracking"
echo ""
echo "Estimated time: 3-5 hours"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Ensure we're in the right directory
cd ~/code/meshcore-bot

# Check current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"

# Create feature branch
echo "Creating branch: ralph/llm-tools-integration"
git checkout -b ralph/llm-tools-integration 2>/dev/null || git checkout ralph/llm-tools-integration

# Show the plan
echo ""
echo "Ralph will implement these 15 stories:"
jq -r '.userStories[] | "\(.id): \(.title)"' prd.json
echo ""

# Start Ralph
echo "Starting Ralph..."
echo ""
echo "Note: Ralph expects prd.json in the repo root"
echo "      progress.txt will be created to track execution"
echo ""
./scripts/ralph/ralph.sh --tool claude 25
