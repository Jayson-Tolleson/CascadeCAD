#!/bin/bash
set -e

echo "Stopping CascadeCAD services..."
sudo systemctl stop cascade-cad.service cascade-cad-worker.service || true

echo "Cleaning up storage directory (/var/lib/cascade-cad)..."
if [ -d "/var/lib/cascade-cad" ]; then
    # Remove contents of jobs, projects, and top-level json files while keeping directory structure
    sudo rm -rf /var/lib/cascade-cad/jobs/*
    sudo rm -rf /var/lib/cascade-cad/projects/*
    sudo rm -f /var/lib/cascade-cad/*.json
    echo "Storage cleaned successfully."
else
    echo "Directory /var/lib/cascade-cad does not exist."
fi

echo "Restarting CascadeCAD services..."
sudo systemctl start cascade-cad.service cascade-cad-worker.service

echo "CascadeCAD has been reset and services are back online."
