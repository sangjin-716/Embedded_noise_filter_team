# pi_b_receiver.py

import socket
import sounddevice as sd
import numpy as np
from collections import deque
import math

# ===== 네트워크 설정 (서버 역할) =====
LISTEN_IP = "0.0.0.0"   # 모든 인터페이스에서 받기
LISTEN_PORT = 54321
# ==================================

# ===== 오디오 설정 =====
SAMPLE_RATE = 48000
CHANNELS = 1
CHUNK = 480          # 10ms @ 48kHz
DTYPE = "int16"
BYTES_PER_CHUNK = CHUNK * CHANNELS * 2
# =======================

# ===== 인위적 딜레이 설정 =====
DELAY_SEC = 0.5
DELAY_FRAMES = int(math.ceil(DELAY_SEC * SAMPLE_RATE / CHUNK))
print(f"[Pi_B] delay: {DELAY_SEC}s ≒ {DELAY_FRAMES} frames")
# ===========================


def main():
    # 소켓 서버 열기
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    sock.listen(1)
    print(f"[Pi_B] listen {LISTEN_IP}:{LISTEN_PORT}... (Pi_A가 접속할 때까지 대기)")

    conn, addr = sock.accept()
    print(f"[Pi_B] Pi_A connected: {addr}")

    buffer = b""
    delay_buffer = deque()

    # 스피커 출력 스트림
    with sd.OutputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        blocksize=CHUNK,
    ) as stream:
        try:
            while True:
                data = conn.recv(4096)
                if not data:
                    print("[Pi_B] recv end")
                    break

                buffer += data

                while len(buffer) >= BYTES_PER_CHUNK:
                    frame_bytes = buffer[:BYTES_PER_CHUNK]
                    buffer = buffer[BYTES_PER_CHUNK:]

                    frames = np.frombuffer(frame_bytes, dtype=np.int16)

                    # 여기서는 필터 X, 그대로 딜레이 큐에 넣어서 출력
                    delay_buffer.append(frames.copy())

                    if len(delay_buffer) < DELAY_FRAMES:
                        # 딜레이 채우는 중
                        continue

                    delayed_frames = delay_buffer.popleft()
                    stream.write(delayed_frames)

        except KeyboardInterrupt:
            print("\n[Pi_B] interrupted")
        finally:
            conn.close()
            sock.close()
            print("[Pi_B] socket closed")


if __name__ == "__main__":
    main()
