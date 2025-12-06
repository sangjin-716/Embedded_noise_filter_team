# import board
# import busio
# from PIL import Image, ImageDraw, ImageFont
# import adafruit_ssd1306

# i2c = busio.I2C(board.SCL, board.SDA)
# oled = adafruit_ssd1306.SSD1306_I2C(128, 48, i2c)

# # 화면 지우기
# oled.fill(0)
# oled.show()

# # 이미지 그리기
# image = Image.new("1", (oled.width, oled.height))
# draw = ImageDraw.Draw(image)
# draw.text((10, 20), "Display OK!", fill=255)
# draw.text((10, 40), "Ready to Rock", fill=255)

# oled.image(image)
# oled.show()
# print("📺 OLED output complete.")

# --------------------------------






# import board
# import busio
# from PIL import Image, ImageDraw, ImageFont
# import adafruit_ssd1306

# # I2C 설정
# i2c = busio.I2C(board.SCL, board.SDA)

# # ★ 수정 1: 높이를 64 -> 32로 변경해야 합니다.
# # 0.91인치 와이드형은 높이가 32픽셀입니다.
# oled = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c) # 0.91인치 와이드 OLED

# def main():
#     try:
#         while True:
#             # 화면 지우기
#             oled.fill(0)
#             oled.show()

#             # 이미지 생성 (높이도 32로!)
#             image = Image.new("1", (oled.width, oled.height))
#             draw = ImageDraw.Draw(image)

#             # 폰트 설정 (기본 폰트 사용)
#             try:
#                 # 폰트 크기도 15는 너무 클 수 있습니다. 12 정도로 줄이거나 기본 폰트 사용
#                 # font = ImageFont.truetype("DejaVuSans.ttf", 12) 
#                 font = ImageFont.load_default()
#             except IOError:
#                 font = ImageFont.load_default()

#             # ★ 수정 2: y 좌표를 위로 올려야 합니다. (0 ~ 31 사이여야 함)
#             # 첫 번째 줄: y = 0
#             # 두 번째 줄: y = 16 (보통 폰트 높이가 10~15px 정도 되므로, 16이 적당합니다)
#             draw.text((0, 0), "Display OK!", font=font, fill=255)
#             draw.text((0, 16), "Ready to Print", font=font, fill=255)

#             # 출력
#             oled.image(image)
#             oled.show()

#             print("📺 OLED output complete.")

#             pass
    
#     except KeyboardInterrupt:
#             print("\nExiting...")

#     finally:
#         print("OLED Display cleanup...")
#         oled.fill(0)
#         oled.show()

#         # # 나머지 리소스 정리
#         # sock.close()
#         # stream.stop_stream()
#         # stream.close()
#         # p.terminate()   
#         # GPIO.cleanup()
#         print("Cleanup done.")

# if __name__ == "__main__":
#     main()

# --------------------------------





import board
import busio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
import time

# --- I2S 설정 ---
i2c = busio.I2C(board.SCL, board.SDA)

# 0.91인치 (128x32) 설정
oled = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)

def main():
    try:
        # 1. 화면 초기화 (지우기)
        oled.fill(0)
        oled.show()

        # 2. 이미지 생성
        image = Image.new("1", (oled.width, oled.height))
        draw = ImageDraw.Draw(image)

        # 3. 폰트 로드
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 12)
        except IOError:
            font = ImageFont.load_default()

        # 4. 텍스트 그리기
        draw.text((0, 0),  "Display Check!", font=font, fill=255)
        draw.text((0, 16), "128x32 Working", font=font, fill=255)

        # 5. 화면 출력
        oled.image(image)
        oled.show()
        
        print("📺 Printing OLED Display... (Ctrl+C: quit)")
        
        # 프로그램이 바로 안 꺼지게 대기 (테스트용)
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Detected KeyboardInterrupt!")

    finally:
        # 프로그램이 죽을 때 무조건 실행되는 구간 
        print("🧹 OLED Display off...")
        oled.fill(0)  # 검은색으로 채움
        oled.show()   # 화면에 반영
        print("✅ done")

if __name__ == "__main__":
    main()