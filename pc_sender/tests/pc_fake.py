import socket
import struct
import sounddevice as sd
import numpy as np
import threading
import sys

# ==========================================
# 1. 설정 (Configuration)
# ==========================================
RECEIVER_IP = "172.30.1.60"  # ★ Pi B IP 주소 입력
RECEIVER_PORT = 54321

# 오디오 설정
SAMPLE_RATE = 48000
CHANNELS = 1
CHUNK = 3840         # 480 * 8 (수신부와 동일하게)
DTYPE = "int16"

# 상태 변수
CURRENT_MODE = 0     # 0:RAW, 1:HPF, 2:RNN, 3:BOTH

# 모드 이름
MODE_MAP = {
    0: "RAW (Send Raw, Flag 0)",
    1: "HPF (Send Raw, Flag 1)",
    2: "RNN (Send Raw, Flag 2)",
    3: "BOTH (Send Raw, Flag 3)"
}

# ==========================================
# 2. 키보드 입력 스레드
# ==========================================
def input_thread():
    global CURRENT_MODE
    print("\n[PC Sender] Library-Free Mode")
    print("Select Mode Flag to send (Real DSP is bypassed):")
    print(" 0 : RAW")
    print(" 1 : HPF Flag")
    print(" 2 : RNN Flag")
    print(" 3 : BOTH Flag")
    
    while True:
        try:
            cmd = input().strip()
            if cmd in ['0', '1', '2', '3']:
                CURRENT_MODE = int(cmd)
                print(f"✅ Sending Flag: {MODE_MAP[CURRENT_MODE]}")
        except: pass

# ==========================================
# 3. 메인 실행
# ==========================================
def main():
    t = threading.Thread(target=input_thread, daemon=True)
    t.start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"[PC] Connecting to {RECEIVER_IP}:{RECEIVER_PORT}...")
    
    try:
        sock.connect((RECEIVER_IP, RECEIVER_PORT))
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print("[PC] Connected! Streaming Started (Fake DSP Mode).")
    except Exception as e:
        print(f"[Error] Connection Failed: {e}")
        return

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE, blocksize=CHUNK) as stream:
            while True:
                # 1. 마이크 입력
                frames, overflowed = stream.read(CHUNK)
                if overflowed: print("!", end="", flush=True)
                
                audio_mono = frames.reshape(-1)

                # 2. 필터링 (생략 - 원본 그대로 사용)
                # PC에서 라이브러리 설치가 어려우므로 여기서는 Bypass 합니다.
                processed_audio = audio_mono

                # 3. RMS 계산 (수신부 LED용)
                rms = int(np.sqrt(np.mean(processed_audio.astype(np.float32)**2)))

                # 4. 패킷 전송 [Header(Mode, RMS) + Body]
                # ★ 핵심: 실제 처리는 안 했지만, 키보드로 선택한 'CURRENT_MODE' 값을 헤더에 담아 보냅니다.
                # 수신부(Pi B)는 이 헤더를 보고 OLED를 바꿀 것입니다.
                header = struct.pack('!II', CURRENT_MODE, rms)
                body = processed_audio.tobytes()
                
                sock.sendall(header + body)

    except KeyboardInterrupt:
        print("\n[PC] Stopped.")
    except Exception as e:
        print(f"[Error] {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    main()