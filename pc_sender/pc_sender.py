import socket
import sounddevice as sd
import numpy as np

PI_IP = "172.21.107.25"  # ←라즈베리파이 IP or 공유기 공인 IP
PI_PORT = 54321

SAMPLE_RATE = 48000
CHANNELS = 1
CHUNK = 480
DTYPE = "int16"

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"Pi_B {PI_IP}:{PI_PORT} 에 연결 시도...")
    sock.connect((PI_IP, PI_PORT))
    print("연결 성공. 마이크 스트리밍 시작.")

    
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
                    print("Warning: input overflow", flush=True)

                data = frames.astype(np.int16).tobytes()
                sock.sendall(data)

        except KeyboardInterrupt:
            print("\n Ctrl+C로 종료.")
        finally:
            sock.close()
            print(" 소켓 닫힘.")


if __name__ == "__main__":
    main()
