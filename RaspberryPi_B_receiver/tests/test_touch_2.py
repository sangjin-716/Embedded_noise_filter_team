import RPi.GPIO as GPIO
import time

# --- 설정 ---
TOUCH_PIN = 17
COOLDOWN_TIME = 0.5
last_touch_time = 0

# --- 초기화 ---
GPIO.setmode(GPIO.BCM)

# [수정] setup을 먼저 해야 cleanup이든 remove든 할 수 있습니다.
GPIO.setup(TOUCH_PIN, GPIO.IN) 

# --- [핵심 수정] 기존 이벤트 제거 ---
try:
    GPIO.remove_event_detect(TOUCH_PIN)
except:
    pass

# --- 콜백 함수 ---
def touch_callback(channel):
    global last_touch_time
    current_time = time.time()
    
    if current_time - last_touch_time < COOLDOWN_TIME:
        return 
    
    last_touch_time = current_time
    print(f"👉 Touch Detected! (GPIO {channel})")

# --- 이벤트 등록 ---
try:
    GPIO.add_event_detect(TOUCH_PIN, GPIO.RISING, 
                          callback=touch_callback, 
                          bouncetime=200)
    print("✅ 센서 설정 완료. 터치해 보세요!")

except RuntimeError as e:
    print(f"❌ Error Occured: {e}")
    print("TIP: 'sudo reboot' and try again.")

# --- 루프 ---
try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\nCleaning up...")
    GPIO.cleanup()