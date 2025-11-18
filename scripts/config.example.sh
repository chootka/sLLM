#!/bin/bash
# Example configuration file
# Copy this to config.sh and fill in your values
# config.sh is gitignored and won't be committed

PI_USER="your-pi-username"
PI_IP="your-pi-ip-or-hostname"
# PI_DIR: Location of the git repository on the Pi (where code is cloned/pulled)
PI_DIR="/home/your-username/sllm"
# DEPLOY_DIR: Web deployment directory where files are served from (default: /var/www/sllm)
DEPLOY_DIR="/var/www/sllm"
REPO_URL="git@github.com:yourusername/sLLM.git"

