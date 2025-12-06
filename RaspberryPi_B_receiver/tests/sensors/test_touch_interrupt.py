from gpiozero import Button
from signal import pause
import time

# --- 설정 ---
TOUCH_PIN = 17
COOLDOWN = 0.5
last_touch_time = 0

# --- 핵심: gpiozero로 인터럽트 설정 ---
# pull_up=False: 내부 풀다운 저항 사용 (평소 0, 터치 시 1)
# bounce_time: 하드웨어 디바운싱 (초 단위) - RPi.GPIO보다 훨씬 잘 먹힘
sensor = Button(TOUCH_PIN, pull_up=False, bounce_time=0.1)

# --- 인터럽트 콜백 함수 ---
def touch_handler():
    global last_touch_time
    current_time = time.time()
    
    # 소프트웨어 쿨타임 체크 (이중 안전장치)
    if current_time - last_touch_time < COOLDOWN:
        return
    
    last_touch_time = current_time
    print("⚡ [Interrupt] Touch Detected! (Mute Toggle)")

# --- 이벤트 등록 ---
# when_pressed: 신호가 0 -> 1로 변할 때 (Rising Edge) 실행
sensor.when_pressed = touch_handler

print(f"👉 Touch Sensor Waiting for Interrupt.. (GPIO {TOUCH_PIN})")
print("Ctrl+C: quit")

# --- 메인 루프 ---
# pause()는 CPU를 쓰지 않고 신호를 기다리게 합니다. (무한 대기)
try:
    pause()
except KeyboardInterrupt:
    print("\ncleaning up...")