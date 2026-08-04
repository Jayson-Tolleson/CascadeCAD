#!/usr/bin/env bash
set -e

echo "=========================================="
echo " 1/3: Resetting File & Directory Permissions "
echo "=========================================="

# 1. Reset ownership of all files to the current non-root user
sudo chown -R $USER:$USER .

# 2. Set default directory permissions (755: rwxr-xr-x)
find . -type d -exec chmod 755 {} +

# 3. Set default file permissions (644: rw-r--r--)
find . -type f -exec chmod 644 {} +

# 4. Restore executable flag (755) for shell scripts and binaries
find . -type f \( -name "*.sh" -o -name "*.py" \) -exec chmod +x {} +

echo "Permissions reset successfully."
echo ""

echo "=========================================="
echo " 2/3: Launching Broadcast Service "
echo "=========================================="
if [ -f "./broadcast/broadcast.sh" ]; # Fallback check if script lives inside broadcast/
then
    ./broadcast/broadcast.sh
elif [ -f "./broadcast/install.sh" ]; # Adjust if broadcast uses install.sh
then
    ./broadcast/install.sh
else
    echo "Warning: Broadcast launcher not found at expected path."
fi

echo ""
echo "=========================================="
echo " 3/3: Launching CascadeCAD Installation "
echo "=========================================="
if [ -f "./Cascade/install.sh" ]; # Note: folder in repo is 'Cascade'
then
    ./Cascade/install.sh
elif [ -f "./CascadeCAD/install.sh" ];
then
    ./CascadeCAD/install.sh
else
    echo "Warning: CascadeCAD installer not found at expected path."
fi

echo ""
echo "=========================================="
echo " Master Deployment Sequence Completed! "
echo "=========================================="
