import socket
import sounddevice as sd
import numpy as np
from collections import deque
import ctypes
import atexit
import math
import threading  # 모드 변경용 입력 스레드

# ===== 네트워크 / 오디오 설정 =====
LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 54321

SAMPLE_RATE = 48000      # RNNoise는 48kHz 기준
CHANNELS = 1
CHUNK = 480              # 10ms @ 48kHz
DTYPE = "int16"
BYTES_PER_CHUNK = CHUNK * CHANNELS * 2
# ================================

# ===== 인위적 딜레이 설정 =====
DELAY_SEC = 0.5
DELAY_FRAMES = int(np.ceil(DELAY_SEC * SAMPLE_RATE / CHUNK))
print(f"[Pi_B] 인위적 딜레이: {DELAY_SEC}초 ≒ {DELAY_FRAMES} 프레임")
# ==============================

# ===== 필터 모드 (0~3) =====
# 0: RAW      (필터 없음, 완전 생)
# 1: HPF      (고역통과 필터만)
# 2: RNN      (RNNoise만)
# 3: BOTH     (HPF + RNNoise)
MODE = 0  # 시작은 RAW
MODE_NAME = {
    0: "RAW",
    1: "HPF",
    2: "RNN",
    3: "BOTH",
}
# ==========================


# ===== RNNoise 로드 =====
def load_rnnoise():
    """librnnoise.so.0 또는 librnnoise.so 로드"""
    libnames = ["librnnoise.so.0", "librnnoise.so"]
    last_err = None
    for name in libnames:
        try:
            lib = ctypes.CDLL(name)
            print(f"[Pi_B] RNNoise 라이브러리 로드: {name}")
            return lib
        except OSError as e:
            last_err = e
    raise OSError(f"RNNoise 라이브러리 로드 실패: {last_err}")


rn = load_rnnoise()

# C 시그니처:
# DenoiseState *rnnoise_create(RNNModel *model);
# float rnnoise_process_frame(DenoiseState *st, float *out, const float *in);
# void rnnoise_destroy(DenoiseState *st);

rn.rnnoise_create.argtypes = [ctypes.c_void_p]   # RNNModel* (또는 NULL)
rn.rnnoise_create.restype = ctypes.c_void_p

rn.rnnoise_process_frame.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_float),
    ctypes.POINTER(ctypes.c_float),
]
rn.rnnoise_process_frame.restype = ctypes.c_float

rn.rnnoise_destroy.argtypes = [ctypes.c_void_p]
rn.rnnoise_destroy.restype = None

# RNNoise 상태 하나 만들기 (기본 모델 사용 → NULL 전달)
_rn_state = rn.rnnoise_create(None)
if not _rn_state:
    raise RuntimeError("rnnoise_create(NULL) 실패")


def _cleanup_rnnoise():
    global _rn_state
    if _rn_state:
        rn.rnnoise_destroy(_rn_state)
        _rn_state = None


atexit.register(_cleanup_rnnoise)
# ========================


# ===== 1차 HPF 클래스 =====
class HighPassFilter:
    """
    y[n] = alpha * (y[n-1] + x[n] - x[n-1])
    """
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
        alpha = self.alpha

        for i, sample in enumerate(x):
            y_i = alpha * (prev_y + sample - prev_x)
            y[i] = y_i
            prev_y = y_i
            prev_x = sample

        self.prev_x = prev_x
        self.prev_y = prev_y
        return y


# HPF 컷오프 
hpf = HighPassFilter(fs=SAMPLE_RATE, fc=100.0) #hpf 설정
# ========================


# ===== 모드 입력 스레드 =====
def mode_input_thread():
    global MODE
    print("\n=== 필터 모드 변경 가능 (실행 중 아무 때나 숫자 + Enter) ===")
    print("0: RAW   (필터 없음)")
    print("1: HPF   (고역통과 필터만)")
    print("2: RNN   (RNNoise만)")
    print("3: BOTH  (HPF + RNNoise)")
    print(f"[Pi_B] 초기 모드: {MODE} ({MODE_NAME[MODE]})")

    while True:
        try:
            s = input("모드 번호 (0/1/2/3): ").strip()
        except EOFError:
            # 입력 스트림 끊겨도 오디오 루프는 계속 돌게 놔둠
            break

        if s in ("0", "1", "2", "3"):
            MODE = int(s)
            print(f"[Pi_B] 모드 변경: {MODE} ({MODE_NAME[MODE]})")
        else:
            print("0, 1, 2, 3 중 하나만 입력.")
# =========================


# ===== HPF + RNNoise 필터 함수 =====
def apply_filter(frames: np.ndarray) -> np.ndarray:
    """
    frames: int16 1D 배열 (길이 = CHUNK=480)
    MODE에 따라 필터 적용 후 int16 1D 배열 반환
    """
    assert frames.shape[0] == CHUNK, "프레임 길이는 CHUNK와 같아야 함"

    # 0) RAW 모드: 아무것도 안 하고 바로 리턴
    if MODE == 0:
        return frames

    # int16 -> float32
    x = frames.astype(np.float32)

    # 1) HPF만 또는 HPF+RNN
    if MODE in (1, 3):
        x = hpf.process(x)

    # 2) RNN만 또는 HPF+RNN
    if MODE in (2, 3):
        in_buf = x.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        out = np.empty_like(x, dtype=np.float32)
        out_buf = out.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        rn.rnnoise_process_frame(_rn_state, out_buf, in_buf)
        x = out  # RNNoise 출력으로 교체

    # float -> int16
    y = np.clip(x, -32768.0, 32767.0).astype(np.int16)
    return y
# ================================


def main():
    # 모드 변경용 입력 스레드 시작
    t = threading.Thread(target=mode_input_thread, daemon=True)
    t.start()

    # 소켓 준비
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    sock.listen(1)
    print(f"[Pi_B] {LISTEN_IP}:{LISTEN_PORT} 에서 대기 중...")

    conn, addr = sock.accept()
    print(f"[Pi_B] Pi_A 연결됨: {addr}")

    buffer = b""
    delay_buffer = deque()

    # 오디오 출력 스트림
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
                    print("[Pi_B] 데이터 수신 종료.")
                    break

                buffer += data

                # CHUNK 단위로 자르기
                while len(buffer) >= BYTES_PER_CHUNK:
                    frame_bytes = buffer[:BYTES_PER_CHUNK]
                    buffer = buffer[BYTES_PER_CHUNK:]

                    # bytes -> int16 배열 (480 샘플)
                    frames = np.frombuffer(frame_bytes, dtype=np.int16)

                    # 선택된 모드대로 필터 적용
                    filtered = apply_filter(frames)

                    # 딜레이 버퍼에 쌓기
                    delay_buffer.append(filtered)

                    # 아직 딜레이 프레임 수만큼 안 쌓였으면 재생하지 않음
                    if len(delay_buffer) < DELAY_FRAMES:
                        continue

                    # 딜레이만큼 쌓인 뒤부터는 제일 오래된 것부터 재생
                    delayed_frames = delay_buffer.popleft()
                    stream.write(delayed_frames)

        except KeyboardInterrupt:
            print("\n[Pi_B] Ctrl+C로 종료.")
        finally:
            conn.close()
            sock.close()
            print("[Pi_B] 소켓 닫힘.")


if __name__ == "__main__":
    main()