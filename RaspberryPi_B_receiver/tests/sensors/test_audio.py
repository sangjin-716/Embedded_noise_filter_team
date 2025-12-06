import pyaudio
import numpy as np
import time

# --- 설정 (Configuration) ---
RATE = 48000       # 샘플링 레이트 (Hz)
DURATION = 3       # 재생 시간 (초)
FREQ = 440.0       # 주파수 (440Hz = '라' 음)
VOLUME = 0.5       # 볼륨 (0.0 ~ 1.0)

def main():
    # 1. 사인파 생성 (Generate Sine Wave)
    # 시간 축 생성
    t = np.linspace(0, DURATION, int(RATE * DURATION), endpoint=False)
    # 사인파 계산 (최대값 32767 for 16-bit PCM)
    wave = (VOLUME * np.sin(2 * np.pi * FREQ * t) * 32767).astype(np.int16)
    
    # 2. 스테레오 데이터로 변환 (Stereo Mixing)
    # I2S 앰프는 보통 스테레오 신호를 받아서 믹싱하거나 한쪽만 출력하므로 스테레오로 보냄
    stereo_wave = np.column_stack((wave, wave)).flatten()

    # 3. PyAudio 초기화
    p = pyaudio.PyAudio()

    print(f"Sound Device Count: {p.get_device_count()}")
    
    try:
        # 스트림 열기 (Card 0번 강제 지정)
        # output_device_index=0 : aplay -l 에서 확인한 I2S 앰프 번호
        stream = p.open(format=pyaudio.paInt16,
                        channels=2,
                        rate=RATE,
                        output=True,
                        output_device_index=0)

        print(f"▶ Playing {FREQ}Hz Tone for {DURATION} seconds...")
        
        # 4. 데이터 쓰기 (재생)
        stream.write(stereo_wave.tobytes())
        
        print("✅ Playback Finished")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        # 리소스 정리
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    main()