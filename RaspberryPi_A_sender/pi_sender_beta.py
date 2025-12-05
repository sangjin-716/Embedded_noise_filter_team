import socket
import sounddevice as sd
import numpy as np

# ===== PC IP / PORT 설정 =====
PC_IP = "192.168.0.35"  # 예: "192.168.0.10"
PC_PORT = 54321
# ============================

SAMPLE_RATE = 48000
CHANNELS = 1
CHUNK = 480          # 10ms @ 48kHz
DTYPE = "int16"


def main():
    # 소켓 생성 및 PC로 연결
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"[Pi_SENDER] PC {PC_IP}:{PC_PORT} 에 연결 시도...")
    sock.connect((PC_IP, PC_PORT))
    print("[Pi_SENDER] 연결 성공. 마이크 스트리밍 시작.")

    # 마이크 입력 스트림 열기
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        blocksize=CHUNK,
    ) as stream:
        try:
            while True:
                frames, overflowed = stream.read(CHUNK)
                if overflowed:
                    print("[Pi_SENDER] Warning: input overflow", flush=True)

                # int16 → bytes 로 변환해서 전송
                data = frames.astype(np.int16).tobytes()
                sock.sendall(data)

        except KeyboardInterrupt:
            print("\n[Pi_SENDER] Ctrl+C로 종료.")
        finally:
            sock.close()
            print("[Pi_SENDER] 소켓 닫힘.")


if __name__ == "__main__":
    main()
