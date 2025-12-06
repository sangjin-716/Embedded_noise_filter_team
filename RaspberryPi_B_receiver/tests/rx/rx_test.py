import socket
import struct
import sounddevice as sd
import numpy as np
import time
import subprocess
import sys
import threading

# 라이브러리 임포트 (하드웨어 의존성 체크)
try:
    import board
    import busio
    import adafruit_ssd1306
    from PIL import Image, ImageDraw, ImageFont 
    from rpi_ws281x import PixelStrip, Color
    from gpiozero import Button
except ImportError as e:
    print(f"❌ Error: Missing Libraries! -> {e}")
    sys.exit(1)

# ==========================================
# 1. 설정 (Configuration)
# ==========================================
HOST = '0.0.0.0'
PORT = 54321

# 오디오 설정 (송신부와 일치시켜야 함)
SAMPLE_RATE = 48000
CHANNELS = 2         # 하드웨어 출력은 스테레오(2)
CHUNK = 3840         # ★ 핵심: 480 * 8 = 3840 (약 80ms) -> 오버플로우 방지 및 안정성 확보
DTYPE = "int16"
PAYLOAD_SIZE = CHUNK * 2

# GPIO
TOUCH_PIN = 17
LED_PIN = 12
LED_COUNT = 16
RMS_SENSITIVITY = 15000  # 감도 조절 (값이 클수록 둔감함)

# 상태 전역 변수 (스레드 간 공유)
MUTE_STATE = False
CURRENT_RMS = 0
CURRENT_MODE = 0
last_touch_time = 0
TOUCH_COOLDOWN = 0.5

# UI 애니메이션 변수
current_led_level = 0

# ==========================================
# 2. 하드웨어 초기화
# ==========================================
# 터치 센서
try:
    touch_sensor = Button(TOUCH_PIN, pull_up=False, bounce_time=0.1)
except: touch_sensor = None

# OLED
oled = None
try:
    i2c = busio.I2C(board.SCL, board.SDA)
    oled = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)
    try: font = ImageFont.truetype("DejaVuSans.ttf", 13)
    except: font = ImageFont.load_default()
    print("Initialize: OLED OK")
except: pass

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

# ★ UI 스레드: 화면과 LED만 전담해서 그림 ★
def ui_thread_func():
    global current_led_level
    
    while True:
        # 1. 최신 상태 읽기
        rms = CURRENT_RMS
        mode = CURRENT_MODE
        mute = MUTE_STATE
        
        # 2. 목표 LED 레벨 계산
        target_level = min(int((rms / RMS_SENSITIVITY) * LED_COUNT), LED_COUNT)
        
        # 3. 부드러운 감쇠 (Decay) 효과 적용
        if target_level > current_led_level:
            current_led_level = target_level # 커질 땐 즉시
        elif target_level < current_led_level:
            current_led_level -= 1           # 작아질 땐 천천히 (잔상 효과)
        if current_led_level < 0: current_led_level = 0

        # 4. OLED 업데이트
        if oled:
            try:
                oled.fill(0)
                img = Image.new("1", (128, 32))
                draw = ImageDraw.Draw(img)
                
                # 텍스트 표시
                status_str = "MUTED" if mute else "LIVE"
                mode_names = ["RAW", "HPF", "RNN", "BOTH"]
                mode_str = mode_names[mode] if mode < 4 else "UNK"
                
                draw.text((0, 0), f"[{status_str}] {mode_str}", font=font, fill=255)
                draw.text((0, 16), f"IP: {MY_IP}", font=font, fill=255)
                
                # 미니 RMS 바
                bar_w = int((current_led_level / 16) * 30)
                draw.rectangle((90, 4, 90+bar_w, 12), outline=255, fill=255)
                
                oled.image(img); oled.show()
            except: pass

        # 5. NeoPixel 업데이트
        if strip:
            try:
                if mute:
                    # Mute 상태: 빨간 점 하나
                    for i in range(LED_COUNT): strip.setPixelColor(i, 0)
                    strip.setPixelColor(0, Color(255, 0, 0))
                else:
                    # VU Meter: 초록 -> 주황 -> 빨강
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
            
        # 30FPS 유지 (CPU 절약)
        time.sleep(0.03)

# ==========================================
# 4. 메인 실행 (Audio Thread)
# ==========================================
def main():
    global CURRENT_RMS, CURRENT_MODE

    # UI 스레드 시작
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
        # 오디오 스트림 (스테레오 채널)
        stream = sd.OutputStream(
            samplerate=SAMPLE_RATE, 
            channels=CHANNELS, # 2 (Stereo)
            dtype=DTYPE, 
            blocksize=CHUNK
        )
        stream.start()
        print(f"Audio Stream Started ({SAMPLE_RATE}Hz, Stereo, Chunk={CHUNK})")
    except Exception as e:
        print(f"❌ Audio Error: {e}")
        return

    data_buffer = b""
    header_size = struct.calcsize('!II')
    payload_size = PAYLOAD_SIZE # 3840 * 2 bytes

    try:
        while True:
            # 1. 데이터 수신 (Blocking) - 오디오 끊김 방지 최우선
            while len(data_buffer) < (header_size + payload_size):
                packet = conn.recv(4096)
                if not packet: raise ConnectionResetError
                data_buffer += packet
            
            # 2. 헤더 파싱
            header = data_buffer[:header_size]
            mode, rms = struct.unpack('!II', header)
            
            # 3. 오디오 데이터 추출
            audio_bytes = data_buffer[header_size : header_size + payload_size]
            data_buffer = data_buffer[header_size + payload_size:]

            # 4. 정보 업데이트 (UI 스레드용)
            CURRENT_RMS = rms
            CURRENT_MODE = mode

            # 5. 소리 출력 (가장 중요)
            if not MUTE_STATE:
                audio_np = np.frombuffer(audio_bytes, dtype=DTYPE)
                # 모노 -> 스테레오 복사
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
        if oled: 
            try: oled.fill(0); oled.show()
            except: pass
        
        try: stream.stop(); stream.close()
        except: pass
        sock.close()

if __name__ == "__main__":
    main()