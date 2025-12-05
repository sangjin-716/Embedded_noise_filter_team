import socket
import sounddevice as sd
import numpy as np
import math
import threading
import time
import RPi.GPIO as GPIO
from rnnoise_wrapper import RNNoise  

# ===== 수신측(Pi_B) IP / PORT 설정 =====
RECEIVER_IP = "172.30.1.93"
RECEIVER_PORT = 54321
# =====================================

# ===== 오디오 설정 =====
SAMPLE_RATE = 48000
CHANNELS = 1
CHUNK = 3840          # 10ms @ 48kHz, RNNoise 프레임과 동일
DTYPE = "int16"
# =======================

# ===== 모드 정의 =====
# 항상 HPF + RNNoise
# 0: RNN 0.0 (HPF only)
# 1: RNN 0.3
# 2: RNN 0.7
# 3: RNN 1.0
MODE = 0
MODE_NAME = {
    0: "HPF + RNN 0.0",
    1: "HPF + RNN 0.3",
    2: "HPF + RNN 0.7",
    3: "HPF + RNN 1.0",
}
MODE_RNN_MIX = {
    0: 0.0,
    1: 0.3,
    2: 0.7,
    3: 1.0,
}
# =======================

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

# ===== HPF 설정 =====
# 컷오프 150Hz, 1차 HPF 2개 직렬 → 2차(12 dB/oct) 정도 효과
HPF_FC = 150.0
HPF_ORDER = 2
hpf_list = [HighPassFilter(fs=SAMPLE_RATE, fc=HPF_FC) for _ in range(HPF_ORDER)]
# =====================

# RNNoise 인스턴스 (우리 래퍼, 480샘플 고정)
denoiser = RNNoise()

# ===== GPIO 핀 매핑 (BCM 번호) =====
# 4-버튼 모듈 (한쪽 GND, 한쪽 GPIO, 풀업 사용)
BTN_PINS = [17, 27, 22, 5]   # 물리핀: 11, 13, 15, 29

# 초음파 센서 HC-SR04
TRIG_PIN = 23                # 물리핀 16
ECHO_PIN = 24                # 물리핀 18  (반드시 저항분배 등으로 3.3V로 낮출 것)

PERSON_THRESHOLD_CM = 80.0   # 이 거리보다 가까우면 "사람 있음"
ULTRA_INTERVAL = 0.2         # 거리 측정 주기(초)
# ===============================

person_present = False
running = True

def gpio_setup():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    # 버튼 입력: 풀업, GND로 눌리는 구조
    for pin in BTN_PINS:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    # 초음파 센서
    GPIO.setup(TRIG_PIN, GPIO.OUT)
    GPIO.setup(ECHO_PIN, GPIO.IN)
    GPIO.output(TRIG_PIN, False)

    print("[GPIO] 초기화 완료.")
    print(f"[GPIO] 버튼 핀(BCM) = {BTN_PINS}")
    print(f"[GPIO] HC-SR04 TRIG={TRIG_PIN}, ECHO={ECHO_PIN}")
    print(f"[GPIO] 사람 감지 임계 거리 = {PERSON_THRESHOLD_CM} cm")

def button_poll_thread():
    """
    이벤트 인터럽트 대신, 50ms마다 버튼을 읽어서
    눌린 순간(High → Low 변 transition)만 MODE 변경하는 스레드.
    """
    global MODE, running

    # 풀업이니까 기본값 1, 눌리면 0
    last_state = [GPIO.input(pin) for pin in BTN_PINS]

    print("[BTN] 버튼 폴링 스레드 시작.")

    while running:
        for idx, pin in enumerate(BTN_PINS):
            cur = GPIO.input(pin)
            # HIGH → LOW 변화 감지 (버튼 눌림)
            if last_state[idx] == 1 and cur == 0:
                MODE = idx  # 0~3
                mix = MODE_RNN_MIX.get(MODE, 0.0)
                print(f"[BTN] Button {idx+1} (GPIO{pin}) 눌림 → MODE={MODE} ({MODE_NAME[MODE]}), RNN_MIX={mix}")
            last_state[idx] = cur

        time.sleep(0.05)  # 50ms 폴링 + 디바운스 효과

def measure_distance_cm():
    """HC-SR04 한 번 측정 (cm). 실패 시 None."""
    # 트리거 펄스
    GPIO.output(TRIG_PIN, False)
    time.sleep(0.000002)
    GPIO.output(TRIG_PIN, True)
    time.sleep(0.00001)  # 10us
    GPIO.output(TRIG_PIN, False)

    timeout = 0.02  # 20ms
    start = time.perf_counter()

    # Echo 핀 HIGH 시작 대기
    while GPIO.input(ECHO_PIN) == 0:
        if time.perf_counter() - start > timeout:
            return None
    pulse_start = time.perf_counter()

    # Echo 핀 LOW 될 때까지 대기
    while GPIO.input(ECHO_PIN) == 1:
        if time.perf_counter() - pulse_start > timeout:
            return None
    pulse_end = time.perf_counter()

    pulse_duration = pulse_end - pulse_start  # 초
    # 음속 34300 cm/s, 왕복이므로 /2
    distance_cm = pulse_duration * 34300.0 / 2.0
    return distance_cm

def ultrasonic_thread():
    global person_present, running
    last_state = None
    while running:
        dist = measure_distance_cm()
        if dist is not None:
            person_present = dist < PERSON_THRESHOLD_CM
        else:
            person_present = False

        if person_present != last_state:
            if person_present and dist is not None:
                print(f"[ULTRA] 사람 감지 (≈{dist:.1f} cm). 송신 ON.")
            else:
                print("[ULTRA] 사람 미감지. 송신 OFF.")
            last_state = person_present

        time.sleep(ULTRA_INTERVAL)

def apply_filter(frames: np.ndarray) -> np.ndarray:
    """
    frames: int16, 길이 CHUNK(480)
    파이프라인:
        mic(int16) → HPF(2차) → RNNoise → 모드별 믹스
    """
    assert frames.shape[0] == CHUNK

    # int16 → float32
    x = frames.astype(np.int16)

    # ----- 1) HPF (항상 적용) -----
    xf = x.astype(np.float32)
    for hpf in hpf_list:
        xf = hpf.process(xf)
    hpf_out = np.clip(xf, -32768, 32767).astype(np.int16)

    # ----- 2) RNNoise 처리 -----
    denoised_int16 = denoiser.process_int16(hpf_out)

    # ----- 3) 모드별 RNNoise 믹스 -----
    mix = MODE_RNN_MIX.get(MODE, 0.0)  # default: 0.0

    if mix <= 0.0:
        # RNNoise 0% → HPF만
        return hpf_out
    elif mix >= 1.0:
        # RNNoise 100%
        return denoised_int16
    else:
        dry_f = hpf_out.astype(np.float32)
        wet_f = denoised_int16.astype(np.float32)
        mixed_f = (1.0 - mix) * dry_f + mix * wet_f
        return np.clip(mixed_f, -32768, 32767).astype(np.int16)

def main():
    global running
    gpio_setup()

    # 초음파 스레드 시작 (사람 감지용)
    th_ultra = threading.Thread(target=ultrasonic_thread, daemon=True)
    th_ultra.start()

    # 버튼 폴링 스레드 시작 (모드 변경용)
    th_btn = threading.Thread(target=button_poll_thread, daemon=True)
    th_btn.start()

    # 소켓 생성 및 Pi_B로 연결
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"[Pi_A] receiver {RECEIVER_IP}:{RECEIVER_PORT} 에 연결 시도...")
    sock.connect((RECEIVER_IP, RECEIVER_PORT))
    print("[Pi_A] 연결 성공. 마이크 + 필터 스트리밍 준비.")

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

                # 사람 없으면 읽기만 하고 버림 (송신/필터 X)
                if not person_present:
                    continue

                # frames shape: (CHUNK, CHANNELS)
                if frames.ndim == 2 and frames.shape[1] == 1:
                    frames_mono = frames[:, 0]
                else:
                    frames_mono = frames.reshape(-1)

                # 필터 적용 (HPF + RNNoise mix)
                filtered = apply_filter(frames_mono)

                # int16 → bytes 로 변환해서 전송
                data = filtered.astype(np.int16).tobytes()
                sock.sendall(data)

        except KeyboardInterrupt:
            print("\n[Pi_A] Ctrl+C로 종료.")
        finally:
            running = False
            sock.close()
            GPIO.cleanup()
            print("[Pi_A] 소켓 닫힘, GPIO 정리 완료.")

if __name__ == "__main__":
    main()
