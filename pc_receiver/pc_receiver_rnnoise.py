import socket
import sounddevice as sd
import numpy as np
from collections import deque
import ctypes
import atexit
import math
import threading

# ===== 네트워크 설정 =====
LISTEN_IP = "0.0.0.0"   # 모든 인터페이스에서 받기
LISTEN_PORT = 54321
# =======================

# ===== 오디오 설정 =====
SAMPLE_RATE = 48000
CHANNELS = 1
CHUNK = 480
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


def load_rnnoise():
    libnames = ["librnnoise.so.0", "librnnoise.so"]
    last_err = None
    for name in libnames:
        try:
            lib = ctypes.CDLL(name)
            print(f"[PC] RNNoise loaded: {name}")
            return lib
        except OSError as e:
            last_err = e
    raise OSError(f"RNNoise load failed: {last_err}")


rn = load_rnnoise()

rn.rnnoise_create.argtypes = [ctypes.c_void_p]
rn.rnnoise_create.restype = ctypes.c_void_p

rn.rnnoise_process_frame.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_float),
    ctypes.POINTER(ctypes.c_float),
]
rn.rnnoise_process_frame.restype = ctypes.c_float

rn.rnnoise_destroy.argtypes = [ctypes.c_void_p]
rn.rnnoise_destroy.restype = None

_rn_state = rn.rnnoise_create(None)
if not _rn_state:
    raise RuntimeError("rnnoise_create(NULL) failed")


def _cleanup_rnnoise():
    global _rn_state
    if _rn_state:
        rn.rnnoise_destroy(_rn_state)
        _rn_state = None


atexit.register(_cleanup_rnnoise)


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


def mode_input_thread():
    global MODE
    print("\nmode: 0=RAW, 1=HPF, 2=RNN, 3=BOTH")
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
    assert frames.shape[0] == CHUNK

    if MODE == 0:
        return frames

    x = frames.astype(np.float32)

    if MODE in (1, 3):
        x = hpf.process(x)

    if MODE in (2, 3):
        in_buf = x.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        out = np.empty_like(x, dtype=np.float32)
        out_buf = out.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        rn.rnnoise_process_frame(_rn_state, out_buf, in_buf)
        x = out

    y = np.clip(x, -32768.0, 32767.0).astype(np.int16)
    return y


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
