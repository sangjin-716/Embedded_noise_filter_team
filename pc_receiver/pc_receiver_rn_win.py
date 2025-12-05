import socket
import sounddevice as sd
import numpy as np
from collections import deque
import math
import threading
from pyrnnoise import RNNoise  # 윈도우용 RNNoise 래퍼

# ===== 네트워크 설정 =====
LISTEN_IP = "0.0.0.0"   # 모든 인터페이스에서 받기
LISTEN_PORT = 54321
# =======================

# ===== 오디오 설정 =====
SAMPLE_RATE = 48000
CHANNELS = 1
CHUNK = 480          # 10ms @ 48kHz
DTYPE = "int16"
BYTES_PER_CHUNK = CHUNK * CHANNELS * 2
# =======================

# ===== 인위적 딜레이 설정 =====
DELAY_SEC = 0.5
DELAY_FRAMES = int(np.ceil(DELAY_SEC * SAMPLE_RATE / CHUNK))
print(f"[PC] delay: {DELAY_SEC}s ≒ {DELAY_FRAMES} frames")
# ===========================

# 0: raw, 1: HPF, 2: RNN, 3: HPF+RNN
MODE = 0
MODE_NAME = {0: "RAW", 1: "HPF", 2: "RNN", 3: "BOTH"}


class HighPassFilter:
    def __init__(self, fs: float, fc: float):
        self.fs = fs
        self.fc = fc
        self.prev_x = 0.0
        self.prev_y = 0.0
        self._update_alpha()

    def _update_alpha(self):
        dt = 1.0 / self.fs
        rc = 1.0 / (2.0 * math.pi * self.fc)
        self.alpha = rc / (rc + dt)

    def process(self, x: np.ndarray) -> np.ndarray:
        # x: float32 1D
        y = np.empty_like(x, dtype=np.float32)
        prev_x = self.prev_x
        prev_y = self.prev_y
        a = self.alpha

        for i, sample in enumerate(x):
            v = a * (prev_y + sample - prev_x)
            y[i] = v
            prev_y = v
            prev_x = sample

        self.prev_x = prev_x
        self.prev_y = prev_y
        return y


# HPF 설정 (100Hz)
hpf = HighPassFilter(fs=SAMPLE_RATE, fc=100.0)

# RNNoise 인스턴스 (48kHz 기준)
# ⚠ channels 인자 쓰지 말 것. sample_rate 만 넘김.
denoiser = RNNoise(sample_rate=SAMPLE_RATE)


def mode_input_thread():
    global MODE
    print("\nmode: 0=RAW, 1=HPF, 2=RNN, 3=HPF+RNN")
    print(f"[PC] start mode: {MODE} ({MODE_NAME[MODE]})")

    while True:
        try:
            s = input("mode (0/1/2/3): ").strip()
        except EOFError:
            break

        if s in ("0", "1", "2", "3"):
            MODE = int(s)
            print(f"[PC] mode -> {MODE} ({MODE_NAME[MODE]})")
        else:
            print("0/1/2/3 only")


def apply_filter(frames: np.ndarray) -> np.ndarray:
    """
    frames: int16, 길이 CHUNK(480)
    RNNoise 프레임 사이즈도 480이라, 호출당 1프레임 처리.
    """
    assert frames.shape[0] == CHUNK

    # 항상 int16 기준으로 처리
    x = frames.astype(np.int16)

    # RAW
    if MODE == 0:
        return x

    # HPF
    if MODE in (1, 3):
        xf = hpf.process(x.astype(np.float32))  # HPF는 float32에서
        x = np.clip(xf, -32768, 32767).astype(np.int16)

    # RNNoise
    if MODE in (2, 3):
        # pyrnnoise 권장 방식: [num_channels, num_samples]로 chunk 처리
        mono = x.reshape(1, -1)  # (1, 480)

        # denoise_chunk는 frame마다 (speech_prob, denoised_audio) yield
        for _, denoised in denoiser.denoise_chunk(mono):
            # mono 1채널이니까 [0]만 사용
            x = denoised[0].astype(np.int16)
            break  # 이번 프레임(480 샘플)만 쓰면 되니까 바로 탈출

    return x


def main():
    # 모드 입력 스레드
    t = threading.Thread(target=mode_input_thread, daemon=True)
    t.start()

    # 소켓 서버 열기
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    sock.listen(1)
    print(f"[PC] listen {LISTEN_IP}:{LISTEN_PORT}... (Pi가 접속할 때까지 대기)")

    conn, addr = sock.accept()
    print(f"[PC] Pi connected: {addr}")

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
                    print("[PC] recv end")
                    break

                buffer += data

                while len(buffer) >= BYTES_PER_CHUNK:
                    frame_bytes = buffer[:BYTES_PER_CHUNK]
                    buffer = buffer[BYTES_PER_CHUNK:]

                    frames = np.frombuffer(frame_bytes, dtype=np.int16)
                    filtered = apply_filter(frames)

                    delay_buffer.append(filtered)

                    if len(delay_buffer) < DELAY_FRAMES:
                        continue

                    delayed_frames = delay_buffer.popleft()
                    stream.write(delayed_frames)

        except KeyboardInterrupt:
            print("\n[PC] interrupted")
        finally:
            conn.close()
            sock.close()
            print("[PC] socket closed")


if __name__ == "__main__":
    main()
