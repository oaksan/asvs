#!/usr/bin/env bash

# Diagnose docker-buildx plugin for this project
# Returns 0 if a valid plugin is present, 1 otherwise.

PLUGIN_PATH="$HOME/.docker/cli-plugins/docker-buildx"
MIN_SIZE=100  # bytes; a proper binary is much larger

if [ -f "$PLUGIN_PATH" ]; then
    SIZE=$(stat -c%s "$PLUGIN_PATH")
    if [ "$SIZE" -ge "$MIN_SIZE" ]; then
        echo "✅ Buildx plugin found (size=${SIZE} bytes)."
        exit 0
    else
        echo "⚠️ Buildx plugin exists but appears corrupted (size=${SIZE} bytes)."
        echo "Consider removing it and reinstalling as described in README."
        exit 1
    fi
else
    echo "❌ Buildx plugin not found at $PLUGIN_PATH."
    echo "Install it following the steps in the project's README."
    exit 1
fi

