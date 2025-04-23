#!/bin/bash

echo "📦 正在准备 Echo Test 环境..."

# 1. 安装 Homebrew（如果未安装）
if ! command -v brew &>/dev/null; then
  echo "🍺 安装 Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# 2. 安装 Python3 和依赖工具
brew install python3 portaudio

# 3. 安装 pip 包
pip3 install --upgrade pip
pip3 install sounddevice soundfile numpy requests

# 4. 拉取程序文件
mkdir -p ~/EchoTest && cd ~/EchoTest
curl -O https://raw.githubusercontent.com/EsssNi/EchoEchoTest/main/echo_test.py

# 5. 触发麦克风权限
echo "🎤 正在触发麦克风权限弹窗（若弹出，请点击 允许）..."
python3 -c "import sounddevice as sd; sd.rec(100, samplerate=44100, channels=1); sd.wait()"

# 6. 运行测试程序（自动用默认参数）
python3 echo_test.py