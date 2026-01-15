send_private_review.sh — README

Purpose

This script uploads the private PDF to Hermes via Slack DM and posts a PR comment requesting public approval. It is intended to be run locally by an authorized user (no tokens or credentials stored in repo).

Requirements

- Linux/macOS environment
- curl, jq, gh installed
- SLACK_TOKEN environment variable (Bot token with users.list, files.upload, conversations.open, chat.postMessage scopes)
- HERMES_USERNAME environment variable (Slack username, e.g., "hermes")
- PR_URL environment variable (the PR URL where the public approval will be requested)

Usage

1. Export required environment variables:

   export SLACK_TOKEN="xoxb-your-token"
   export HERMES_USERNAME="hermes"
   export PR_URL="https://github.com/owner/repo/pull/123"

2. Run the script:

   ./scripts/send_private_review.sh

Notes

- The script will find Hermes' Slack user ID, open a DM channel, upload `docs/hermes_review/private/Hermes_Private_Review_Packet.pdf`, send the private message, and attempt to post a PR comment via `gh` if present.
- Do not store tokens in source control. Use environment variables or your local secret manager.
- The script is provided to automate the messaging step you requested; it will not push branches or create PRs.

Security

Keep your tokens private. This script intentionally avoids storing any secrets in the repo.
