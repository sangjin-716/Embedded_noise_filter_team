import RPi.GPIO as GPIO
import time

TOUCH_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(TOUCH_PIN, GPIO.IN)

print("👉 Touch the sensor! (Ctrl+C : quit)")

try:
    while True:
        if GPIO.input(TOUCH_PIN):
            print("⭕ touched!")
        else:
            # 너무 도배되면 보기 힘들어서 터치 안 될 땐 출력 생략하거나 가끔 출력
            pass
        time.sleep(0.1)

except KeyboardInterrupt:
    GPIO.cleanup()
