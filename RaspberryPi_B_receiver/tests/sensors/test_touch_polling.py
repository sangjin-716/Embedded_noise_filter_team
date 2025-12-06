import RPi.GPIO as GPIO
import time

# --- 설정 ---
TOUCH_PIN = 17
MUTE_STATE = False
LAST_STATE = 0  # 이전 터치 상태 기억

# --- 초기화 ---
GPIO.setmode(GPIO.BCM)
# TTP223은 신호를 확실하게(0V/3.3V) 주므로 풀다운/풀업 설정 불필요 (기본 상태)
GPIO.setup(TOUCH_PIN, GPIO.IN)

print(f"👉 Touch Sensor Test (Polling) - GPIO {TOUCH_PIN}")
print("Ctrl+C: quit")

try:
    while True:
        # 1. 현재 센서 상태 읽기 (0 또는 1)
        current_val = GPIO.input(TOUCH_PIN)

        # 2. 상태 변화 감지 (버튼 누르는 순간: 0 -> 1)
        if current_val == 1 and LAST_STATE == 0:
            MUTE_STATE = not MUTE_STATE # 토글
            status = "🔇 MUTED" if MUTE_STATE else "🔊 LIVE"
            print(f"👉 Touch Detected! State Transition: {status}")
            
            # 디바운싱 (중복 입력 방지)
            time.sleep(0.3) 

        # 3. 상태 저장
        LAST_STATE = current_val
        
        # CPU 점유율 낮추기 위한 미세 대기
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\n종료합니다.")
    GPIO.cleanup()