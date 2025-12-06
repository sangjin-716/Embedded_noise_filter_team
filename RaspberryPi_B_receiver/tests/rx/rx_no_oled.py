import socket
import struct
import sounddevice as sd
import numpy as np
import time
import subprocess
import sys
import threading

# 라이브러리 임포트 (OLED 관련 라이브러리가 없어도 돌아가도록 처리)
try:
    from rpi_ws281x import PixelStrip, Color
    from gpiozero import Button
except ImportError as e:
    print(f"❌ Error: Missing Libraries! -> {e}")
    sys.exit(1)

# OLED 라이브러리는 선택사항으로 처리
try:
    import board
    import busio
    import adafruit_ssd1306
    from PIL import Image, ImageDraw, ImageFont
    OLED_AVAILABLE = True
except ImportError:
    OLED_AVAILABLE = False
    print("⚠️ OLED libraries not found. Running without Display.")

# ==========================================
# 1. 설정 (Configuration)
# ==========================================
HOST = '0.0.0.0'
PORT = 54321

# 오디오 설정
SAMPLE_RATE = 48000
CHANNELS = 2         # 하드웨어 출력 (스테레오)
CHUNK = 3840         # 480 * 8
DTYPE = "int16"
PAYLOAD_SIZE = CHUNK * 2

# GPIO
TOUCH_PIN = 17
LED_PIN = 12
LED_COUNT = 16
RMS_SENSITIVITY = 10000  # neo pixel 감도 조절

# 상태 변수
MUTE_STATE = False
CURRENT_RMS = 0
CURRENT_MODE = 0
last_touch_time = 0
TOUCH_COOLDOWN = 0.5

# UI 변수
current_led_level = 0

# ==========================================
# 2. 하드웨어 초기화
# ==========================================
# 터치
try:
    touch_sensor = Button(TOUCH_PIN, pull_up=False, bounce_time=0.1)
except: touch_sensor = None

# OLED (연결 시도하되 실패하면 무시)
oled = None
if OLED_AVAILABLE:
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        oled = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)
        try: font = ImageFont.truetype("DejaVuSans.ttf", 13)
        except: font = ImageFont.load_default()
        print("Initialize: OLED OK")
    except: 
        print("Initialize: OLED Failed (Skipping)")
        oled = None

# NeoPixel
strip = None
try:
    strip = PixelStrip(LED_COUNT, LED_PIN, 800000, 10, False, 50, 0)
    strip.begin()
    print("Initialize: NeoPixel OK")
except: pass

def get_ip():
    try: return subprocess.check_output(['hostname', '-I']).decode().split()[0]
    except: return "No IP"
MY_IP = get_ip()

# ==========================================
# 3. 기능 함수
# ==========================================
def touch_handler():
    global MUTE_STATE, last_touch_time
    curr = time.time()
    if curr - last_touch_time < TOUCH_COOLDOWN: return
    last_touch_time = curr
    MUTE_STATE = not MUTE_STATE
    print(f"⚡ Touch! Mute: {MUTE_STATE}")

if touch_sensor:
    touch_sensor.when_pressed = touch_handler

# UI 스레드
def ui_thread_func():
    global current_led_level
    
    # 로그 출력을 위한 이전 상태 기억 (도배 방지)
    last_log_time = 0
    
    while True:
        rms = CURRENT_RMS
        mode = CURRENT_MODE
        mute = MUTE_STATE
        
        # 1. LED 목표 레벨 계산
        target_level = min(int((rms / RMS_SENSITIVITY) * LED_COUNT), LED_COUNT)
        
        # 2. 부드러운 움직임
        if target_level > current_led_level:
            current_led_level = target_level
        elif target_level < current_led_level:
            current_led_level -= 1
        if current_led_level < 0: current_led_level = 0

        # 3. ★ [추가] 터미널 로그 출력 (1초에 한 번만)
        if time.time() - last_log_time > 1.0:
            mode_names = ["RAW", "HPF", "RNN", "BOTH"]
            m_str = mode_names[mode] if mode < 4 else "UNK"
            s_str = "🔇 MUTE" if mute else "🔊 LIVE"
            # RMS를 막대그래프로 표현
            bar = "#" * int(current_led_level)
            print(f"[{s_str}] Mode:{m_str} | RMS:{rms} | {bar}")
            last_log_time = time.time()

        # 4. OLED (있으면 그리고, 없으면 패스)
        if oled:
            try:
                oled.fill(0)
                img = Image.new("1", (128, 32))
                draw = ImageDraw.Draw(img)
                
                state_str = "State: MUTE" if mute else "State: RESUME"
                info_str = f"IP: {MY_IP}"
                
                draw.text((0, 0), state_str, font=font, fill=255)
                draw.text((0, 16), info_str, font=font, fill=255)
                
                bar_w = int((current_led_level / 16) * 30)
                draw.rectangle((90, 4, 90+bar_w, 12), outline=255, fill=255)
                
                oled.image(img); oled.show()
            except: pass

        # 5. NeoPixel
        if strip:
            try:
                if mute:
                    for i in range(LED_COUNT): strip.setPixelColor(i, 0)
                    strip.setPixelColor(0, Color(255, 0, 0))
                else:
                    for i in range(LED_COUNT):
                        if i < current_led_level:
                            if i < 10: col = Color(0, 255, 0)
                            elif i < 14: col = Color(255, 80, 0)
                            else: col = Color(255, 0, 0)
                            strip.setPixelColor(i, col)
                        else:
                            strip.setPixelColor(i, 0)
                strip.show()
            except: pass
            
        time.sleep(0.03)

# ==========================================
# 4. 메인 루프
# ==========================================
def main():
    global CURRENT_RMS, CURRENT_MODE

    ui_thread = threading.Thread(target=ui_thread_func, daemon=True)
    ui_thread.start()
    print("UI Thread Started")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen(1)
    
    print(f"Waiting for Sender on {PORT}...")
    
    conn, addr = sock.accept()
    print(f"Connected: {addr}")
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    try:
        stream = sd.OutputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE, blocksize=CHUNK)
        stream.start()
        print(f"Audio Stream Started ({SAMPLE_RATE}Hz, Stereo)")
    except Exception as e:
        print(f"❌ Audio Error: {e}")
        return

    data_buffer = b""
    header_size = struct.calcsize('!II')
    payload_size = PAYLOAD_SIZE

    try:
        while True:
            while len(data_buffer) < (header_size + payload_size):
                packet = conn.recv(4096)
                if not packet: raise ConnectionResetError
                data_buffer += packet
            
            header = data_buffer[:header_size]
            mode, rms = struct.unpack('!II', header)
            audio_bytes = data_buffer[header_size : header_size + payload_size]
            data_buffer = data_buffer[header_size + payload_size:]

            CURRENT_RMS = rms
            CURRENT_MODE = mode

            if not MUTE_STATE:
                audio_np = np.frombuffer(audio_bytes, dtype=DTYPE)
                stereo_audio = np.column_stack((audio_np, audio_np))
                stream.write(stereo_audio)

    except Exception as e:
        print(f"Disconnected: {e}")
    finally:
        print("Shutdown...")
        if strip: 
            try:
                for i in range(LED_COUNT): strip.setPixelColor(i, 0)
                strip.show()
            except: pass
        
        # OLED 끄기 (연결되어 있다면)
        if oled: 
            try: oled.fill(0); oled.show()
            except: pass
        
        try: stream.stop(); stream.close()
        except: pass
        sock.close()

if __name__ == "__main__":
    main()