#!/bin/bash

set -e

echo "\n📦 Initializing Echo Test environment (no Command Line Tools required)..."

# Check and install Homebrew if not present
if ! command -v brew &>/dev/null; then
  echo "🍺 Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
  echo "✅ Homebrew already installed"
fi

# Install precompiled dependencies
brew install python3 portaudio

# Install Python packages (disable build isolation to avoid CLT prompts)
pip3 install --no-build-isolation sounddevice soundfile numpy requests

# Download main program
mkdir -p ~/EchoTest && cd ~/EchoTest
curl -O https://github.com/EsssNi/EchoEchoTest/blob/main/echo_test.py

# Run test program (with default parameters)
echo "\n🚀 Running echo test..."
python3 echo_test.py
