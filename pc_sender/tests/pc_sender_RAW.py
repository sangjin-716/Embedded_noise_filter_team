import socket
import struct
import sounddevice as sd
import numpy as np
import time

# ==========================================
# 1. 설정 (Configuration)
# ==========================================
# ★ 수신부(라즈베리파이 B)의 IP 주소를 입력하세요
RECEIVER_IP = "172.30.1.60" 
RECEIVER_PORT = 54321

# 오디오 설정 (수신부와 반드시 일치해야 함)
SAMPLE_RATE = 48000  # 수신부와 동일
CHANNELS = 1         # 마이크는 1채널(Mono)
# ★ 중요: 수신부 코드의 CHUNK 사이즈와 똑같이 맞춰야 합니다.
# (수신부가 3840이면 3840, 1024면 1024)
CHUNK = 3840         
DTYPE = "int16"

# 테스트용 가상 모드 (PC에는 키패드가 없으므로)
CURRENT_MODE = 0 # 0:RAW 로 고정해서 보냄

# ==========================================
# 2. 메인 실행
# ==========================================
def main():
    # 소켓 생성
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"[PC] Connecting to {RECEIVER_IP}:{RECEIVER_PORT}...")
    
    try:
        sock.connect((RECEIVER_IP, RECEIVER_PORT))
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) # 지연 최소화
        print("[PC] Connected! Start Streaming...")
    except Exception as e:
        print(f"[Error] Connection Failed: {e}")
        return

    # 마이크 스트림 열기
    # (PC의 기본 녹음 장치를 사용합니다)
    try:
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE, 
            channels=CHANNELS, 
            dtype=DTYPE, 
            blocksize=CHUNK
        )
        stream.start()
    except Exception as e:
        print(f"[Error] Microphone Init Failed: {e}")
        print("Check your PC sound settings.")
        return

    try:
        while True:
            # 1. 마이크 입력 읽기
            frames, overflowed = stream.read(CHUNK)
            if overflowed:
                print("Warning: Input Overflow (PC CPU Busy)")
            
            # numpy 변환
            audio_data = frames.reshape(-1)

            # 2. RMS 계산 (수신부 LED 시각화용)
            # PC가 계산해서 보내주면 라즈베리파이가 편함
            rms = int(np.sqrt(np.mean(audio_data.astype(np.float32)**2)))

            # 3. 패킷 생성 (프로토콜 준수!)
            # [Header: Mode(4byte) + RMS(4byte)] + [Body: Audio]
            header = struct.pack('!II', CURRENT_MODE, rms)
            body = audio_data.tobytes()

            # 4. 전송
            sock.sendall(header + body)
            
            # (선택) 터미널에 상태 출력
            # print(f"Sent: RMS {rms}")

    except KeyboardInterrupt:
        print("\n[PC] Streaming Stopped by User.")
    except Exception as e:
        print(f"[Error] Sending Failed: {e}")
    finally:
        stream.stop()
        stream.close()
        sock.close()
        print("[PC] Closed.")

if __name__ == "__main__":
    main()