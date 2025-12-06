import time
from rpi_ws281x import PixelStrip, Color
import argparse

# --- 설정 ---
LED_COUNT = 16        # 스틱 2개 연결 (8 + 8)
LED_PIN = 12          # Pi B는 GPIO 12번 사용
LED_FREQ_HZ = 800000  # 주파수
LED_DMA = 10          # DMA 채널
LED_BRIGHTNESS = 50   # 밝기 (0~255)
LED_INVERT = False
LED_CHANNEL = 0

# --- 색상 정의 (Green, Orange, Red) ---
# 주황색은 LED 특성상 적색(R)을 많이, 녹색(G)을 적당히 섞어야 예쁘게 나옵니다.
COLOR_GREEN = Color(0, 255, 0)
COLOR_ORANGE = Color(255, 80, 0)  # (255, 165, 0)보다 붉은끼를 섞어야 노란색처럼 안보임
COLOR_RED = Color(255, 0, 0)
COLOR_OFF = Color(0, 0, 0)

# --- 픽셀 위치별 색상 결정 함수 ---
def get_color_for_index(index):
    # 0 ~ 9번 (10개): 초록색
    if index < 10:
        return COLOR_GREEN
    # 10 ~ 13번 (4개): 주황색
    elif index < 14:
        return COLOR_ORANGE
    # 14 ~ 15번 (2개): 빨간색
    else:
        return COLOR_RED

# --- 메인 실행 ---
if __name__ == '__main__':
    # 라이브러리 초기화
    strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
    strip.begin()

    print("🚀 네오픽셀 채우기 테스트 (Ctrl+C로 종료)")
    print("구성: [초록 10] -> [주황 4] -> [빨강 2]")

    try:
        while True:
            # 1. 하나씩 차오르기 (Fill Up)
            for i in range(strip.numPixels()):
                color = get_color_for_index(i)
                strip.setPixelColor(i, color)
                strip.show()
                time.sleep(0.05) # 올라가는 속도 조절

            time.sleep(0.5) # 꽉 찼을 때 잠깐 대기

            # 2. 하나씩 꺼지기 (Drain Down) - 옵션
            # 거꾸로(15 -> 0) 반복
            for i in range(strip.numPixels() - 1, -1, -1):
                strip.setPixelColor(i, COLOR_OFF)
                strip.show()
                time.sleep(0.03) # 내려가는 속도는 조금 빠르게
            
            time.sleep(0.5) # 다 꺼졌을 때 잠깐 대기

    except KeyboardInterrupt:
        # 종료 시 끄기
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, COLOR_OFF)
        strip.show()