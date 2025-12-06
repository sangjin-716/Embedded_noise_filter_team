import socket
import struct
import sounddevice as sd
import numpy as np
import threading
import math
import sys

# 라이브러리 체크
try:
    from rnnoise_wrapper import RNNoise
except ImportError:
    print("❌ Error: 'rnnoise-wrapper' not found.")
    print("Run: pip install rnnoise-wrapper")
    sys.exit(1)

# ==========================================
# 1. 설정 (Configuration)
# ==========================================
RECEIVER_IP = "172.30.1.60"  # ★ 수신부(Pi B) IP 입력 필수
RECEIVER_PORT = 54321

# 오디오 설정 (RNNoise는 48k 필수)
SAMPLE_RATE = 48000
CHANNELS = 1
CHUNK = 3840         # 480 * 8 (전송 효율 + AI 처리 최적화)
DTYPE = "int16"

# 상태 변수
CURRENT_MODE = 0     # 0:RAW, 1:HPF, 2:RNN, 3:BOTH
RNN_MIX = 1.0        # RNNoise 적용 강도 (0.0 ~ 1.0)

# 모드 이름
MODE_MAP = {
    0: "RAW (Bypass)",
    1: "HPF (Vibration Cut)",
    2: "RNN (AI Denoise)",
    3: "BOTH (Hybrid)"
}

# ==========================================
# 2. DSP 클래스 & 객체 초기화
# ==========================================

# --- HPF 클래스 (직접 구현) ---
class HighPassFilter:
    def __init__(self, fs, fc):
        dt = 1.0 / fs
        rc = 1.0 / (2.0 * math.pi * fc)
        self.alpha = rc / (rc + dt)
        self.prev_x = 0.0
        self.prev_y = 0.0

    def process(self, chunk):
        # float32로 변환하여 연산 정밀도 확보
        x = chunk.astype(np.float32)
        y = np.zeros_like(x)
        
        # 첫 샘플 처리 (이전 상태 연결)
        y[0] = self.alpha * (self.prev_y + x[0] - self.prev_x)
        
        # 나머지 샘플 처리 (벡터 연산 대신 순차 처리)
        for i in range(1, len(x)):
            y[i] = self.alpha * (y[i-1] + x[i] - x[i-1])
            
        # 상태 저장
        self.prev_x = x[-1]
        self.prev_y = y[-1]
        
        return y # float32 반환

# 필터 객체 생성
hpf = HighPassFilter(SAMPLE_RATE, 100) # 100Hz 컷오프
denoiser = RNNoise() # AI 노이즈 제거기

# ==========================================
# 3. 필터링 로직 (핵심)
# ==========================================
def process_audio(audio_chunk):
    """
    3840개 데이터를 받아서 필터링 후 반환
    RNNoise는 480개씩만 처리 가능하므로 쪼개서 처리함
    """
    global CURRENT_MODE
    
    # 1. RAW 모드면 바로 리턴 (부하 최소화)
    if CURRENT_MODE == 0:
        return audio_chunk

    # 2. HPF 적용 (Mode 1 or 3)
    processed = audio_chunk.astype(np.float32)
    if CURRENT_MODE in [1, 3]:
        processed = hpf.process(audio_chunk) # Float32 반환
    
    # 3. RNNoise 적용 (Mode 2 or 3)
    if CURRENT_MODE in [2, 3]:
        # int16으로 변환해서 넣어야 함
        pcm_int16 = np.clip(processed, -32768, 32767).astype(np.int16)
        
        # 3840개를 480개씩 8번 쪼개서 처리
        denoised_parts = []
        FRAME_SIZE = 480
        
        for i in range(0, len(pcm_int16), FRAME_SIZE):
            frame = pcm_int16[i : i + FRAME_SIZE]
            if len(frame) < FRAME_SIZE: break # 자투리 방지
            
            # AI 필터링 (True/False는 음성 감지 여부)
            filtered_frame = denoiser.filter(frame, sample_rate=SAMPLE_RATE)
            denoised_parts.append(filtered_frame)
            
        # 다시 하나로 합치기
        processed_rnn = np.concatenate(denoised_parts)
        
        # 믹싱 (강도 조절)
        # processed(HPF된거)와 processed_rnn(AI된거)을 섞음
        dry = processed
        wet = processed_rnn.astype(np.float32)
        
        # Mix 적용
        final_float = (dry * (1.0 - RNN_MIX)) + (wet * RNN_MIX)
        processed = final_float

    # 4. 최종 변환 (int16)
    return np.clip(processed, -32768, 32767).astype(np.int16)

# ==========================================
# 4. 키보드 입력 스레드
# ==========================================
def input_thread():
    global CURRENT_MODE, RNN_MIX
    print("\n[Controls] Select Mode:")
    print(" 0 : RAW")
    print(" 1 : HPF")
    print(" 2 : RNN (AI)")
    print(" 3 : BOTH")
    print("Type 'r 0.5' to set AI Mix level")
    
    while True:
        try:
            cmd = input().strip()
            if cmd in ['0', '1', '2', '3']:
                CURRENT_MODE = int(cmd)
                print(f"✅ Mode: {MODE_MAP[CURRENT_MODE]}")
            
            elif cmd.startswith('r '):
                val = float(cmd.split()[1])
                RNN_MIX = max(0.0, min(1.0, val))
                print(f"✅ AI Mix Level: {RNN_MIX}")
                
        except: pass

# ==========================================
# 5. 메인 실행
# ==========================================
def main():
    t = threading.Thread(target=input_thread, daemon=True)
    t.start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"[PC] Connecting to {RECEIVER_IP}:{RECEIVER_PORT}...")
    
    try:
        sock.connect((RECEIVER_IP, RECEIVER_PORT))
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print("[PC] Connected! Streaming with DSP...")
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

                # 2. ★ 실제 필터링 수행 (PC CPU 사용) ★
                processed_audio = process_audio(audio_mono)

                # 3. RMS 계산
                rms = int(np.sqrt(np.mean(processed_audio.astype(np.float32)**2)))

                # 4. 패킷 전송 [Header + Body]
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