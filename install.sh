#!/usr/bin/env bash
# install_ubuntu.sh - Install all scanner dependencies on Ubuntu / WSL
set -euo pipefail

echo "  HubAudit - Ubuntu/WSL Dependency Installer"


# ── System packages ────────────────────────────────────────────────────────────
echo ""
echo "[1/4] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    curl wget ca-certificates

# ── Python packages ───────────────────────────────────────────────────────────
echo ""
echo "[2/4] Installing Python packages..."

python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
echo "  * Packages installed (activate with: source venv/bin/activate)"

# ── Trivy ─────────────────────────────────────────────────────────────────────
echo ""
echo "[3/4] Installing Trivy..."
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
    | sudo sh -s -- -b /usr/local/bin
trivy --version && echo "  * Trivy installed"

# ── Opengrep ──────────────────────────────────────────────────────────────────
echo ""
echo "[4/4] Installing Opengrep..."
OPENGREP_VERSION="v1.16.5"
OPENGREP_URL="https://github.com/opengrep/opengrep/releases/download/${OPENGREP_VERSION}/opengrep_manylinux_x86"
sudo curl -fsSL "$OPENGREP_URL" -o /usr/local/bin/opengrep
sudo chmod +x /usr/local/bin/opengrep
opengrep --version && echo "  * Opengrep installed"

