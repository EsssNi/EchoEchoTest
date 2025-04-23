import sounddevice as sd
import numpy as np
import requests
import time
import threading
import wave
import io
import soundfile as sf
import urllib.request
import argparse
import json
import os
import subprocess

VOLUME_LEVELS = [75, 88, 100]

def download_audio(url):
    print("下载测试音频中...")
    with urllib.request.urlopen(url) as response:
        audio_data = response.read()
    audio_bytes = io.BytesIO(audio_data)
    data, samplerate = sf.read(audio_bytes)
    return data, samplerate

def record_input(duration, samplerate):
    print("开始录音...")
    recorded = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1)
    sd.wait()
    print("录音完成。")
    return recorded

def play_audio(data, samplerate):
    print("开始播放测试音频...")
    sd.play(data, samplerate=samplerate)
    sd.wait()
    print("播放结束。")

def play_and_record(audio_data, samplerate, duration):
    recorded = []

    def record_thread():
        nonlocal recorded
        recorded = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1)
        sd.wait()

    thread = threading.Thread(target=record_thread)
    thread.start()

    sd.play(audio_data[:samplerate * duration], samplerate=samplerate)
    sd.wait()
    thread.join()
    return recorded

def get_device_info():
    output_device = sd.query_devices(kind='output')
    input_device = sd.query_devices(kind='input')
    return {
        "output_device_name": output_device.get("name", "Unknown Output"),
        "input_device_name": input_device.get("name", "Unknown Input")
    }

def get_current_volume():
    try:
        result = subprocess.check_output(
            ["osascript", "-e", "output volume of (get volume settings)"]
        )
        return int(result.decode().strip())
    except Exception as e:
        print("获取当前音量失败：", e)
        return 50  # 默认假设为中音量

def set_output_volume(percent):
    print(f"设置系统音量为 {percent}%...")
    subprocess.run(["osascript", "-e", f"set volume output volume {percent}"])

def compute_metrics(playback, recorded, samplerate, device_info):
    playback_energy = np.sum(playback**2)
    recorded_energy = np.sum(recorded**2)

    erl = 10 * np.log10(playback_energy / recorded_energy) if recorded_energy != 0 else 100
    erle = erl + 5
    tail = np.argmax(np.abs(recorded[::-1]) > 0.001) / samplerate
    latency = np.argmax(np.abs(recorded) > 0.01) / samplerate
    tclw = max(0, 30 - erl)

    return {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ERL_dB": round(erl, 2),
        "ERLE_dB": round(erle, 2),
        "TCLw_dB": round(tclw, 2),
        "Echo_Tail_Length_s": round(tail, 3),
        "Latency_s": round(latency, 3),
        "Output_Device": device_info["output_device_name"],
        "Input_Device": device_info["input_device_name"]
    }

def get_system_info():
    import platform
    hostname = platform.node()
    try:
        sn = subprocess.check_output(
            "system_profiler SPHardwareDataType | awk '/Serial/ {print $4}'",
            shell=True
        ).decode().strip()
    except Exception:
        sn = "Unknown"
    return {
        "Hostname": hostname,
        "SerialNumber": sn,
        "os": platform.system(),
        "os_version": platform.version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "user": os.environ.get("USER") or os.environ.get("USERNAME", "")
    }

def send_results(metrics, webhook_url, headers=None, retries=3):
    print("📡 发送分析结果到 Webhook...")
    system_info = get_system_info()
    payload = {
        "event": "echo_test",
        "system": system_info,
        "data": metrics
    }
    print("📦 正在发送的 Webhook Payload：", json.dumps(payload, indent=2, ensure_ascii=False))
    for attempt in range(retries):
        try:
            response = requests.post(webhook_url, json=payload, headers=headers)
            print(f"Webhook 第 {attempt+1} 次请求，状态码：{response.status_code},{response.json()}")
            if response.ok:
                return True
        except Exception as e:
            print(f"发送失败：{e}")
        time.sleep(1)
    return False

def save_to_local(metrics, filename="echo_metrics_log.json"):
    os.makedirs("results", exist_ok=True)
    filepath = os.path.join("results", filename)
    with open(filepath, "a") as f:
        json.dump(metrics, f)
        f.write("\n")
    print(f"✅ 结果已保存至本地文件：{filepath}")

def run_test(audio_url, webhook_url, duration, sample_rate, webhook_headers):
    audio_data, sr = download_audio(audio_url)
    assert sr == sample_rate, f"采样率不一致（音频为 {sr}Hz，目标为 {sample_rate}Hz）"

    original_volume = get_current_volume()
    print(f"🔄 当前系统音量为：{original_volume}%")

    try:
        for vol in VOLUME_LEVELS:
            set_output_volume(vol)
            time.sleep(1)

            device_info = get_device_info()
            recorded = play_and_record(audio_data, sample_rate, duration)

            metrics = compute_metrics(audio_data[:len(recorded)], recorded, sample_rate, device_info)
            metrics["Volume_Percent"] = vol

            print(f"🔊 音量 {vol}% 测试结果：", metrics)
            save_to_local(metrics, filename=f"volume_{vol}_result.json")
            send_results(metrics, webhook_url, headers=webhook_headers)

            print("⏳ 等待 1.5 秒进入下一轮测试...")
            time.sleep(1.5)

    finally:
        print(f"🔁 恢复原始音量为 {original_volume}%...")
        set_output_volume(original_volume)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="macOS 外接硬件回声消除性能检测工具")
    parser.add_argument("--url", default="https://cdn.jsdelivr.net/gh/EsssNi/EchoEchoTest@main/-18.wav", help="公网音频流 URL（默认已填）")
    parser.add_argument("--webhook", default="https://bytedance.larkoffice.com/base/automation/webhook/event/J1JEa9qfwwTjLGhfUXbcGIy0nzd", help="Webhook 接收地址（默认已填）")
    parser.add_argument("--duration", type=int, default=10, help="测试音频时长（秒）")
    parser.add_argument("--rate", type=int, default=24000, help="采样率（Hz）")
    parser.add_argument("--token", default="1G9oNksO7ZS5OJjJ2AbznTqL")

    args = parser.parse_args()
    headers = {"Authorization": f"Bearer {args.token}"} if args.token else None
    headers['Content-Type'] = 'application/json'
    print(headers)

    run_test(
        audio_url=args.url,
        webhook_url=args.webhook,
        duration=args.duration,
        sample_rate=args.rate,
        webhook_headers=headers
    )