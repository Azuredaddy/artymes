#!/bin/bash
# Artymes - Raspberry Pi First Boot Installer
# Runs automatically when Pi boots for the first time
# Place this in /boot/firstboot.sh and enable via /etc/rc.local

INSTALL_DIR="/home/pi/artymes"
LOG="/boot/arty_install.log"
DONE_FLAG="/boot/arty_installed"

exec > >(tee -a $LOG) 2>&1

# Only run once
if [ -f "$DONE_FLAG" ]; then
    exit 0
fi

echo "========================================"
echo " Artymes - ARTY First Boot Setup"
echo " $(date)"
echo "========================================"

# ── Wait for network ──────────────────────────────────────────────────────────
echo "[1/8] Waiting for network..."
for i in $(seq 1 30); do
    if ping -c1 google.com &>/dev/null; then
        echo "  Network ready."
        break
    fi
    sleep 2
done

# ── System packages ───────────────────────────────────────────────────────────
echo "[2/8] Updating system packages..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    ffmpeg portaudio19-dev \
    git curl wget \
    espeak-ng \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    fonts-dejavu

# ── Clone / copy Artymes ──────────────────────────────────────────────────────
echo "[3/8] Installing Artymes..."
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

# Pull from GitHub if repo set, otherwise copy from USB if present
USB_MOUNT="/media/pi"
GITHUB_REPO="Azuredaddy/artymes"

if [ -f "$USB_MOUNT/artymes.zip" ]; then
    echo "  Found artymes.zip on USB — installing from USB..."
    unzip -o "$USB_MOUNT/artymes.zip" -d /home/pi/
elif [ "$GITHUB_REPO" != "YOUR_GITHUB_USERNAME/artymes" ]; then
    echo "  Cloning from GitHub..."
    git clone "https://github.com/$GITHUB_REPO.git" $INSTALL_DIR
fi

# ── Copy .env from USB if present ────────────────────────────────────────────
echo "[4/8] Checking for config..."
if [ -f "$USB_MOUNT/arty.env" ]; then
    echo "  Found arty.env on USB — copying config..."
    cp "$USB_MOUNT/arty.env" "$INSTALL_DIR/.env"
elif [ -f "/boot/arty.env" ]; then
    echo "  Found arty.env in /boot — copying config..."
    cp "/boot/arty.env" "$INSTALL_DIR/.env"
else
    echo "  No .env found — copying example (manual setup needed)"
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
fi

# ── Python virtual environment ────────────────────────────────────────────────
echo "[5/8] Creating Python environment..."
python3 -m venv $INSTALL_DIR/venv

# ── Install PyTorch for ARM (Pi 5) ───────────────────────────────────────────
echo "[6/8] Installing PyTorch for Raspberry Pi..."
$INSTALL_DIR/venv/bin/pip install --upgrade pip --quiet
$INSTALL_DIR/venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu --quiet

# ── Install requirements ──────────────────────────────────────────────────────
echo "[7/8] Installing ARTY requirements..."
$INSTALL_DIR/venv/bin/pip install -r $INSTALL_DIR/requirements.txt --quiet

# ── Autostart on boot ────────────────────────────────────────────────────────
echo "[8/8] Setting up autostart..."
cat > /etc/systemd/system/arty.service << EOF
[Unit]
Description=ARTY AI Employee
After=network.target sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python main.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl enable arty.service

# ── Fix permissions ───────────────────────────────────────────────────────────
chown -R pi:pi $INSTALL_DIR
usermod -a -G audio pi

# ── Mark complete ─────────────────────────────────────────────────────────────
touch $DONE_FLAG
echo ""
echo "========================================"
echo " ARTY install complete! Rebooting..."
echo "========================================"
reboot
