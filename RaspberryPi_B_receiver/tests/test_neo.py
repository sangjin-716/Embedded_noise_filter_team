import time
from rpi_ws281x import PixelStrip, Color

# 설정
LED_COUNT = 16      # 스틱 1개면 8, 2개면 16
LED_PIN = 12       # ★ Pi B는 GPIO 12번 사용
LED_BRIGHTNESS = 50

strip = PixelStrip(LED_COUNT, LED_PIN, 800000, 10, False, LED_BRIGHTNESS, 0)
strip.begin()

print("🌈 네오픽셀 테스트 (Ctrl+C 종료)")

try:
    while True:
        # 빨강 채우기
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(255, 0, 0))
        strip.show()
        time.sleep(0.5)
        
        # 초록 채우기
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 255, 0))
        strip.show()
        time.sleep(0.5)

        # 끄기
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()
        time.sleep(0.5)

except KeyboardInterrupt:
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0,0,0))
    strip.show()