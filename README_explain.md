# Embedded_System_Design

 두 대의 라즈베리파이4 를 이용하여 마이크 음성을 실시간으로 전송하고 수신측에서 필터(HPF, RNNoise)를 이용하여 출력한다.

### Pi_A : 마이크 입력 -> Raw -> 소켓 전송
### pi_B : 소켓 수신 -> filter -> 출력
 차후에 Pi_A에 filter를 넣어줄 예정

## 1. 기본 준비

sudo apt update
sudo apt upgrade -y
sudo apt install -y git python3 python3-venv python3-pip

### 가상환경 
python3 -m venv audioenv

### pip
pip install --upgrade pip

# 패키지 설치
pip install -r requirements.txt

## 2. 수신단 
sudo apt install -y libportaudio2 libportaudio-dev alsa-utils

## 3. 필터 있는 Pi
sudo apt install -y autoconf automake libtool pkg -config build-essential

cd ~
git clone https://github.com/xiph/rnnoise
cd rnnoise
./autogen.sh
./configure
make
sudo make install

sudo ldconfig

## 4. IP 주소 확인 (차후에 다른 네트워크에서 가능한지 확인 필요, 공인 Ip 확인 필요)
hostname -I

## 5. 실행

### Pi_B
source audioenv/bin/activate
python3 pi_XXXXXXX.py

#### 필터 설정
0=RAW, 1=HPF, 2=RNN, 3=BOTH

### Pi_A
source audioenv/bin/activate
python3 pi_xxxxxxxx.py

# 필터

## RNNoise

## HPF(하이패스 필터) : 생각보다 효과가 미미함
저주파를 억제하고 높은 주파수는 통과시키는 역할
사람 말소리는 100~4kHz 사이
코드에서 fc는 하이패스 컷오프 주파수 이거 밑에 값은 필터링함

sample=(현재 입력)
prev_x=(그전 입력)
prev_y=(그전 출력)

sample - prev_x
천천히 변하는 저주파는 거의 0이 되고
빠르게 변하는 고주파는 크게 남게한다.

prev_y + sample - prev_x
단순히 sample - prev_x 만 계산하면 고주파만 남고 저주파는 싹다 날려서 부자연스러울수 있음
따라서 과거 출력을 섞어 주며 자연스럽게 만들어줌

HPF는 저주파(DC. 진동, 바람소리 등)를 잡아주는 역할
