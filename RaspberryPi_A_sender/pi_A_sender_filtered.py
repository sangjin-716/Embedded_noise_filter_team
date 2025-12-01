# pi_a_sender_filtered.py

import socket
import sounddevice as sd
import numpy as np
from collections import deque
import math
import threading
from pyrnnoise import RNNoise  # 라즈베리파이에 rnnoise 라이브러리 설치되어 있어야 함

# ===== 수신측(Pi_B) IP / PORT 설정 =====
RECEIVER_IP = "192.168.0.3" 
RECEIVER_PORT = 54321
# =====================================

# ===== 오디오 설정 =====
SAMPLE_RATE = 48000
CHANNELS = 1
CHUNK = 480          # 10ms @ 48kHz
DTYPE = "int16"
# =======================

# 0: raw, 1: HPF, 2: RNN, 3: HPF+RNN
MODE = 0
MODE_NAME = {0: "RAW", 1: "HPF", 2: "RNN", 3: "BOTH"}

# ===== RNN 필터 강도 (0.0 ~ 1.0) =====
# 1.0 = RNNoise 100% 적용
# 0.5 = 원본(dry) 50% + RNNoise 50%
# 0.0 = RNNoise 효과 없음 (실질적으로 dry만 전송)
RNN_MIX = 0.7
# =====================================


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
    """
    터미널에서:
      0 / 1 / 2 / 3  → 필터 모드 변경
      r 0.5          → RNNoise 50% 믹스
    """
    global MODE, RNN_MIX
    print("\nmode: 0=RAW, 1=HPF, 2=RNN, 3=HPF+RNN")
    print("mix:  r <0.0~1.0>  (예: r 0.5 → RNNoise 50%)")
    print(f"[Pi_A] start mode: {MODE} ({MODE_NAME[MODE]}), RNN_MIX={RNN_MIX}")

    while True:
        try:
            s = input("> ").strip()
        except EOFError:
            break

        # --- 모드 변경 (0/1/2/3) ---
        if s in ("0", "1", "2", "3"):
            MODE = int(s)
            print(f"[Pi_A] mode -> {MODE} ({MODE_NAME[MODE]})")
            continue

        # --- RNN 강도 변경: r 0.7 이런 식 ---
        if s.startswith("r "):
            parts = s.split()
            if len(parts) != 2:
                print("사용법: r 0.7  (0.0 ~ 1.0)")
                continue

            try:
                v = float(parts[1])
            except ValueError:
                print("숫자로 입력해라. 예: r 0.5")
                continue

            # 0.0 ~ 1.0 범위로 클램프
            v = max(0.0, min(1.0, v))
            RNN_MIX = v
            print(f"[Pi_A] RNN_MIX -> {RNN_MIX}")
            continue

        print("명령어:  0/1/2/3  또는  r <0.0~1.0>")


def apply_filter(frames: np.ndarray) -> np.ndarray:
    """
    frames: int16, 길이 CHUNK(480)
    RNNoise 프레임 사이즈도 480이라, 호출당 1프레임 처리.
    """
    assert frames.shape[0] == CHUNK

    # 항상 int16 기준으로 처리
    x = frames.astype(np.int16)

    # RAW 기준 신호(dry) 보관
    dry = x.copy()

    # RAW
    if MODE == 0:
        return x

    # HPF
    if MODE in (1, 3):
        xf = hpf.process(x.astype(np.float32))  # HPF는 float32에서
        x = np.clip(xf, -32768, 32767).astype(np.int16)

        # MODE=3에서는 HPF 결과를 dry로 사용 (HPF-only vs HPF+RNN 믹스)
        if MODE == 3:
            dry = x.copy()

    # RNNoise
    if MODE in (2, 3):
        # pyrnnoise 권장 방식: [num_channels, num_samples]로 chunk 처리
        mono = x.reshape(1, -1)  # (1, 480)

        denoised_int16 = x  # fallback
        # denoise_chunk는 frame마다 (speech_prob, denoised_audio) yield
        for _, denoised in denoiser.denoise_chunk(mono):
            # mono 1채널이니까 [0]만 사용
            denoised_int16 = denoised[0].astype(np.int16)
            break  # 이번 프레임(480 샘플)만 쓰면 되니까 바로 탈출

        # === RNNoise 강도 믹스 ===
        mix = max(0.0, min(1.0, RNN_MIX))  # 혹시 실수로 범위 벗어나도 클램프

        if mix >= 1.0:
            # RNNoise 100%
            x = denoised_int16
        elif mix <= 0.0:
            # RNNoise 0% (dry만 사용)
            x = dry
        else:
            dry_f = dry.astype(np.float32)
            wet_f = denoised_int16.astype(np.float32)
            mixed_f = (1.0 - mix) * dry_f + mix * wet_f
            x = np.clip(mixed_f, -32768, 32767).astype(np.int16)
        # ========================

    return x


def main():
    # 모드 입력 스레드 시작
    t = threading.Thread(target=mode_input_thread, daemon=True)
    t.start()

    # 소켓 생성 및 Pi_B로 연결
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"[Pi_A] receiver {RECEIVER_IP}:{RECEIVER_PORT} 에 연결 시도...")
    sock.connect((RECEIVER_IP, RECEIVER_PORT))
    print("[Pi_A] 연결 성공. 마이크 + 필터 스트리밍 시작.")

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
                    print("[Pi_A] Warning: input overflow", flush=True)

                # frames shape: (CHUNK, CHANNELS)
                if frames.ndim == 2 and frames.shape[1] == 1:
                    frames_mono = frames[:, 0]
                else:
                    frames_mono = frames.reshape(-1)

                # 필터 적용
                filtered = apply_filter(frames_mono)

                # int16 → bytes 로 변환해서 전송
                data = filtered.astype(np.int16).tobytes()
                sock.sendall(data)

        except KeyboardInterrupt:
            print("\n[Pi_A] Ctrl+C로 종료.")
        finally:
            sock.close()
            print("[Pi_A] 소켓 닫힘.")


if __name__ == "__main__":
    main()

