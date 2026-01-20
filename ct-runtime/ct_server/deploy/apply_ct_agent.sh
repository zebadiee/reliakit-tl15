#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DIR/../.." && pwd)"
SERVICE_SRC="$DIR/ct-agent-register.service"
ENV_SRC="$DIR/ct-agent-register.env"
LOGROTATE_SRC="$DIR/logrotate.ct-agent"

dry_run() {
  echo "DRY RUN - planned actions:"
  echo "  Copy $SERVICE_SRC -> /etc/systemd/system/ct-agent-register.service"
  echo "  Copy $ENV_SRC -> /etc/ct-agent/ct-agent-register.env"
  echo "  Copy $LOGROTATE_SRC -> /etc/logrotate.d/ct-agent"
  echo "  Ensure user/group 'ct' exists (create if missing)"
  echo "  Create /var/log/ct-agent (owner ct:ct)"
  echo "  systemctl daemon-reload && systemctl enable --now ct-agent-register"
  exit 0
}

_apply() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: apply requires root. Rerun with sudo." >&2
    exit 2
  fi

  mkdir -p /etc/ct-agent
  install -m 644 "$SERVICE_SRC" /etc/systemd/system/ct-agent-register.service
  install -m 644 "$ENV_SRC" /etc/ct-agent/ct-agent-register.env
  # Fill runtime-specific values if missing
  if ! grep -q '^CT_RUNTIME_DIR=' /etc/ct-agent/ct-agent-register.env 2>/dev/null; then
    echo "CT_RUNTIME_DIR=$REPO_ROOT" >> /etc/ct-agent/ct-agent-register.env
  else
    sed -i "s|^CT_RUNTIME_DIR=.*$|CT_RUNTIME_DIR=$REPO_ROOT|" /etc/ct-agent/ct-agent-register.env || true
  fi
  VENV_BIN="$REPO_ROOT/.venv/bin/uvicorn"
  if ! grep -q '^CT_RUNTIME_VENV=' /etc/ct-agent/ct-agent-register.env 2>/dev/null; then
    echo "CT_RUNTIME_VENV=$VENV_BIN" >> /etc/ct-agent/ct-agent-register.env
  else
    sed -i "s|^CT_RUNTIME_VENV=.*$|CT_RUNTIME_VENV=$VENV_BIN|" /etc/ct-agent/ct-agent-register.env || true
  fi

  install -m 644 "$LOGROTATE_SRC" /etc/logrotate.d/ct-agent

  if ! id -u ct >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin ct || true
  fi

  mkdir -p /var/log/ct-agent
  chown ct:ct /var/log/ct-agent
  chmod 0750 /var/log/ct-agent

  systemctl daemon-reload
  systemctl enable --now ct-agent-register
  echo "APPLY complete."
}

case "${1:-}" in
  --apply)
    echo "You are about to apply changes to this host."
    read -p "Type 'yes' to proceed: " CONFIRM
    if [ "$CONFIRM" = "yes" ]; then
      _apply
    else
      echo "Aborted by user."
      exit 0
    fi
    ;;
  *)
    dry_run
    ;;
esac
