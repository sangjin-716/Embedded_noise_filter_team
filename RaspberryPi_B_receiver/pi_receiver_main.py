import socket
import struct
import sounddevice as sd
import numpy as np
import board
import busio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
from rpi_ws281x import PixelStrip, Color
import time
import subprocess
import sys
from gpiozero import Button  # RPi.GPIO 대신 gpiozero 사용

# ==========================================
# 1. 설정 (Configuration)
# ==========================================
# 네트워크
HOST = '0.0.0.0'
PORT = 54321

# 오디오
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK = 1024
DTYPE = "int16"
PAYLOAD_SIZE = CHUNK * 2

# GPIO (네오픽셀)
LED_PIN = 12
LED_COUNT = 16

# 터치 센서 설정 (gpiozero)
TOUCH_PIN = 17
# pull_up=False : 평소에 0(Low), 누르면 1(High)로 인식 (TTP223 맞춤)
# bounce_time : 0.1초 디바운싱 (중복 입력 방지)
touch_sensor = Button(TOUCH_PIN, pull_up=False, bounce_time=0.1)

# 상태 변수
MUTE_STATE = False
last_touch_time = 0
TOUCH_COOLDOWN = 0.5

# UI 최적화용
last_ui_state = None 

# ==========================================
# 2. 하드웨어 초기화
# ==========================================

# --- OLED (128x32) ---
try:
    i2c = busio.I2C(board.SCL, board.SDA)
    oled = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 12)
    except IOError:
        font = ImageFont.load_default()
    print("Initialize: OLED OK")
except Exception as e:
    print(f"Error: OLED Setup Failed - {e}")

# --- NeoPixel ---
try:
    strip = PixelStrip(LED_COUNT, LED_PIN, 800000, 10, False, 50, 0)
    strip.begin()
    print("Initialize: NeoPixel OK")
except Exception as e:
    print(f"Error: NeoPixel Setup Failed - {e}")

# IP 주소 확인
def get_ip():
    try:
        return subprocess.check_output(['hostname', '-I']).decode().split()[0]
    except:
        return "No IP"
MY_IP = get_ip()

# ==========================================
# 3. 기능 함수
# ==========================================

def touch_handler():
    """
    gpiozero 인터럽트 콜백 함수
    """
    global MUTE_STATE, last_touch_time
    curr = time.time()
    
    # 소프트웨어 쿨타임 (이중 안전장치)
    if curr - last_touch_time < TOUCH_COOLDOWN:
        return
        
    last_touch_time = curr
    MUTE_STATE = not MUTE_STATE
    print(f"⚡ Touch Detected! Mute: {MUTE_STATE}")

# ★ 핵심: 이벤트 등록 (누르는 순간 실행)
touch_sensor.when_pressed = touch_handler

def update_ui(mode, rms):
    global last_ui_state
    
    # RMS -> LED Level (0~16)
    level = min(int((rms / 2000) * LED_COUNT), LED_COUNT)
    
    current_state = (mode, MUTE_STATE, level)
    if current_state == last_ui_state:
        return
    last_ui_state = current_state

    # --- 1. OLED ---
    oled.fill(0)
    img = Image.new("1", (128, 32))
    draw = ImageDraw.Draw(img)
    
    modes = ["RAW", "HPF", "RNN", "BOTH"]
    mode_str = modes[mode] if mode < 4 else "UNK"
    status_str = "MUTED" if MUTE_STATE else "LIVE"
    
    draw.text((0, 0), f"[{status_str}] {mode_str}", font=font, fill=255)
    draw.text((0, 16), f"IP: {MY_IP}", font=font, fill=255)
    
    # RMS 바
    bar_width = int((rms / 4000) * 40)
    draw.rectangle((85, 4, 85 + bar_width, 10), outline