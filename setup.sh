#!/bin/bash
# Update system and install Playwright dependencies
apt-get update && apt-get install -y \
    libnss3 libatk1.0-0 libx11-xcb1 libxcomposite1 \
    libxrandr2 libxdamage1 libpango1.0-0 libgbm1 \
    libasound2 fonts-liberation libfontconfig1

# Force Playwright to install the browser binaries
python -m playwright install
