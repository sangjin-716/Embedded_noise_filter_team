# **2025-2 Embedded System Design Project** 
> **Team:** Noise_Filter_Team(Silentium Factorem)

> **Period:** 2025.11.26 ~ 2025.12.22

---
## 🔊 Distributed Real-Time Voice Noise Filtering System (실시간 음성 노이즈 제거 임베디드 시스템)


---

## 👥 팀원 및 역할 분담 (Roles & Responsibilities)
> **팀원:** 정상진, 신정수 

프로젝트 수행을 위해 필요한 세부 직무 리스트입니다.

| 구분 | 상세 직무 (Tasks) | 담당자 |
| :--- | :--- | :---: |
| **System Arch.** | 전체 시스템 구조 설계 및 네트워크 토폴로지 정의 | `[  ]` |
| **Network** | TCP/IP 소켓 통신 구현 (Latency 최적화, 패킷 구조 설계) | `[  ]` |
| **DSP / AI** | 오디오 신호 처리 (RMS 계산, HPF 알고리즘, RNNoise 적용) | `[  ]` |
| **Embedded SW** | 송신부(Pi A) 센서 제어 로직 (초음파, 키패드 연동) | `[  ]` |
| **Embedded SW** | 수신부(Pi B) 출력 제어 로직 (OLED, NeoPixel, I2S 앰프) | `[  ]` |
| **Hardware** | 회로 설계, 브레드보드 배선, 납땜 및 케이블링 | `[  ]` |
| **Mechanical** | 기구 하우징(Case) 3D 모델링 및 제작 | `[  ]` |
| **Documentation** | 제안서, 최종 보고서 작성, 발표 자료(PPT) 및 데모 영상 제작 | `[  ]` |

---

## 📖 프로젝트 개요 (Overview)

**Edge Live Stream Filter System**은 두 대의 Raspberry Pi 4를 활용한 **분산형 실시간 오디오 처리 시스템**입니다.

기존 PC 기반 노이즈 캔슬링 소프트웨어의 리소스 점유 문제와 보안 취약점을 해결하기 위해 고안되었습니다. 모든 오디오 수집, 전송, 필터링 연산을 **엣지 디바이스(Edge Device)**에서 독립적으로 수행함으로써 사용자 PC의 부하를 **'Zero'**로 유지하며, 물리적 센서(초음파)와 연동하여 사용자가 없을 때는 **네트워크 패킷 전송을 원천 차단(Packet Cut-off)**하여 물리적 보안성을 확보합니다.

### 🎯 주요 기능 (Key Features)

* **📡 초저지연 네트워크 스트리밍 (Low-latency Streaming)**
    * TCP/IP 소켓 통신 최적화(Nagle 알고리즘 해제)를 통해 실시간 음성 전송 보장.
    * 직접 연결(Direct LAN) 및 Wi-Fi 환경 모두 지원.
* **🎛️ DSP 기반 노이즈 필터링 (Multi-Mode DSP)**
    * **Mode 0 (RAW):** 원본 오디오 바이패스.
    * **Mode 1 (HPF):** 저주파 및 진동 소음 제거 (High Pass Filter).
    * **Mode 2 (RNNoise):** 딥러닝 기반 사람 목소리 분리 및 잡음 제거.
    * **Mode 3 (Hybrid):** HPF + RNNoise 직렬 적용.
* **📊 실시간 시각화 (Real-time VU Meter)**
    * 오디오 신호의 RMS(에너지)를 계산하여 NeoPixel LED Bar로 실시간 시각화.
    * OLED 디스플레이를 통해 IP 주소, 필터 모드, 네트워크 상태 모니터링.
* **🛡️ 물리적 보안 및 능동 제어 (Physical Security & Control)**
    * **Smart Wake-up:** 초음파 센서로 사용자 재실 감지 시에만 시스템 작동.
    * **Packet Cut-off:** 사용자 부재 또는 Mute 시 네트워크 전송 로직 차단.
    * **Emergency Mute:** 정전식 터치 센서를 통한 즉각적인 음소거 및 상태 표시.

---

## 🏗️ 시스템 아키텍처 (Architecture)

### 1. 시스템 개념도 (Concept)
사용자의 음성을 수집(Pi A)하여 필터링 후 전송하고, 수신측(Pi B)에서 재생 및 시각화하는 전체 흐름입니다.

```mermaid
graph LR
    classDef pi fill:#d45500,stroke:#333,stroke-width:2px,color:white;
    classDef sensor fill:#f9f,stroke:#333,stroke-width:1px;
    classDef output fill:#6affcd,stroke:#333,stroke-width:1px;
    classDef network fill:#4d9de0,stroke:#333,stroke-width:2px,color:white,stroke-dasharray: 5 5;

    subgraph User_Side [사용자 환경]
        User((사용자))
        Sound_Source[음성 신호]
    end

    subgraph Edge_Device_A [Sender: Intelligent Mic]
        Pi_A["<b>Raspberry Pi 4 (A)</b><br>오디오 수집 및 패킷 전송"]:::pi
        Mic[USB 마이크]:::sensor
        Ultra_A["초음파 센서<br>Smart Wake-up"]:::sensor
    end

    subgraph Network_Layer [Local Network Connection]
        Ethernet{"<b>IEEE 802.3 / 802.11ac</b><br>TCP/IP Stream"}:::network
    end

    subgraph Edge_Device_B [Receiver: Media Station]
        Pi_B["<b>Raspberry Pi 4 (B)</b><br>출력 제어 및 시각화"]:::pi
        
        subgraph Inputs [입력 제어]
            Keypad["3-Key 키패드<br>Mode Select"]:::sensor
            Touch["정전식 터치 센서<br>Mute / Resume"]:::sensor
        end

        subgraph Outputs [피드백 출력]
            OLED["OLED 디스플레이<br>상태 정보 표시"]:::output
            NeoPixel["NeoPixel Stick<br>VU Meter 시각화"]:::output
            Amp["I2S 앰프 + 스피커<br>오디오 출력"]:::output
        end
    end

    User -->|접근| Ultra_A
    User -->|목소리| Sound_Source
    Sound_Source --> Mic
    Ultra_A -.->|Presence Signal| Pi_A
    Mic -->|Raw PCM Audio| Pi_A
    Pi_A ==>|Packet Stream| Ethernet
    Ethernet ==>|Receive Packet| Pi_B
    Inputs -->|GPIO Signal| Pi_B
    Pi_B -->|I2S Audio| Amp
    Pi_B -->|I2C Data| OLED
    Pi_B -->|PWM/Data| NeoPixel
    
```

### 2. 하드웨어 블록도 (Hardware Block Diagram)
각 라즈베리파이에 연결된 센서 및 액추에이터의 인터페이스 상세입니다.

```mermaid
graph TD
    %% 스타일 정의
    classDef cpu fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef bus fill:#fff9c4,stroke:#fbc02d,stroke-width:1px;

    subgraph Sender_Unit ["<b>Edge Device A</b> <br>(송신부: 연산/필터링)"]
        CPU_A["<b>Raspberry Pi 4 CPU</b><br>DSP (HPF/RNNoise)"]:::cpu
        
        USB_Port[USB Interface]:::bus
        GPIO_A[GPIO Interface]:::bus
        
        Mic_HW["USB Mike <br>(●Voice IN)"]
        SR04_A["<b>[INPUT]</b> <br>Sonar sensor<br>(Auto Wake-up)"]
        Keypad_HW["<b>[INPUT]</b> <br>1x3 Push Button<br>(Mode Control)"]

        
        CPU_A --- USB_Port
        CPU_A --- GPIO_A
        
        USB_Port --- Mic_HW
        GPIO_A --- SR04_A
        GPIO_A --- Keypad_HW
    end

    Link["<b>Ethernet / Wi-Fi</b><br>TCP/IP Socket Stream"]

    subgraph Receiver_Unit ["<b>Edge Device B</b> <br>(수신부: 출력/UI)"]
        CPU_B["<b>Raspberry Pi 4 CPU</b><br>UI / Audio Output"]:::cpu
        
        I2C_Bus["I2C Bus<br>(SDA/SCL)"]:::bus
        I2S_Bus["I2S Audio Bus<br>(BCLK/LRC/DIN)"]:::bus
        GPIO_B[General GPIO]:::bus
        
        OLED_HW["<b>[OUTPUT]</b> <br>OLED Display <br>(Status/Mode/IP)"]
        Amp_HW["<b>[OUTPUT]</b> <br> Audio Amp <br>+ 3W Speaker <br>(●Voice OUT)"]
        
        Touch_HW["<b>[INPUT]</b> <br>Capacitive Touch Sensor<br>(Mute Toggle)"]
        Neo_HW["<b>[OUTPUT]</b> <br>NeoPixel Stick 8 <br>(VU Meter)"]
        
        CPU_B --- I2C_Bus
        CPU_B --- I2S_Bus
        CPU_B --- GPIO_B
        
        I2C_Bus --- OLED_HW
        I2S_Bus --- Amp_HW
        
        GPIO_B --- Touch_HW
        GPIO_B --- Neo_HW
    end

    Sender_Unit <==> Link <==> Receiver_Unit
```

### 3. 시스템 플로우차트 (Software Flowchart)
데이터 처리 및 제어 로직의 흐름입니다.


```mermaid
flowchart TD
    %% --- 스타일 정의 ---
    classDef start fill:#333,stroke:#333,stroke-width:2px,color:white,rx:10,ry:10;
    classDef proc fill:#fff,stroke:#333,stroke-width:1px;
    classDef decision fill:#fff9c4,stroke:#fbc02d,stroke-width:2px;
    classDef sender fill:#e3f2fd,stroke:#2196f3,stroke-width:2px;
    classDef receiver fill:#e8f5e9,stroke:#4caf50,stroke-width:2px;
    classDef filter fill:#d1c4e9,stroke:#673ab7,stroke-width:2px;

    %% --- 시작점 ---
    Root((System Start)):::start --> Init["가상환경 및 라이브러리 로드"]:::proc
    Init --> Fork_A
    Init --> Fork_B

    %% --- [Pi A] 송신부 ---
    subgraph Sender_Logic [Pi_A : 감지, 필터링, 송신]
        direction TB
        Fork_A(Sender Start):::start
        
        Fork_A --> Check_User{"사용자 감지?<br>(초음파 센서)"}:::decision
        
        %% 분기: 사용자 없음
        Check_User -- No --> Packet_Cut["<b>[보안] 전송 차단</b><br>Packet Cut-off"]:::sender
        Packet_Cut --> Check_User
        
        %% 분기: 사용자 있음
        Check_User -- Yes --> Read_Mic["마이크 입력<br>(Raw PCM)"]:::sender
        Read_Mic --> Check_Mode{"필터 모드 확인<br>(Keypad 입력)"}:::decision
        
        %% 필터 모드 분기 (자연스러운 배치)
        Check_Mode -- 0 --> Filter_Raw["<b>Bypass</b><br>원본 유지"]:::proc
        Check_Mode -- 1 --> Filter_HPF["<b>HPF</b><br>저주파 억제"]:::filter
        Check_Mode -- 2 --> Filter_RNN["<b>RNNoise</b><br>Deep Learning"]:::filter
        Check_Mode -- 3 --> Filter_Both["<b>Hybrid</b><br>HPF + RNNoise"]:::filter
        
        %% 필터 합류
        Filter_Raw --> Process_Data["오디오 합성 & RMS 계산"]:::sender
        Filter_HPF --> Process_Data
        Filter_RNN --> Process_Data
        Filter_Both --> Process_Data
        
        Process_Data --> Make_Pkt["패킷 생성 <br>[Header:RMS] + [Body: Audio]"]:::sender
        Make_Pkt --> Send_Pkt["소켓 패킷 전송"]:::sender
        
        %% 루프백
        Send_Pkt --> Check_User
    end

    %% --- 네트워크 연결 ---
    Send_Pkt -.->|Stream| Recv_Pkt

    %% --- [Pi B] 수신부 ---
    subgraph Receiver_Logic [Pi_B : 재생 및 시각화]
        direction TB
        Fork_B(Receiver Start):::start
        
        Fork_B --> Recv_Pkt["패킷 수신 & 파싱"]:::receiver
        Recv_Pkt --> Check_Mute{"Mute 상태?<br>(터치 센서)"}:::decision
        
        %% Mute 분기
        Check_Mute -- Yes --> Stop_Sound["출력 중단 (Zero Write)<br>& LED 적색 점등"]:::receiver
        Stop_Sound --> Recv_Pkt
        
        %% 정상 출력 분기
        Check_Mute -- No --> Output_Spk["I2S 앰프 스피커 출력"]:::receiver
        Output_Spk --> Update_Visual["<b>- NeoPixel VU Meter</b> <br>(소리 크기 시각화)<br><b>- OLED 디스플레이</b> <br>(상태/모드 정보 갱신)"]:::receiver
        
        Update_Visual --> Recv_Pkt
    end

```

## 🛠 기술 스택 (Tech Stack)

| 분류 | 상세 기술 | 비고 |
| :--- | :--- | :--- |
| **Hardware** | **Raspberry Pi 4 Model B (4GB)** | Main Controller (x2) |
| | **MAX98357A (I2S Amp)** | High Quality Audio Output |
| | **HC-SR04** / **TTP223** | Ultrasonic / Touch Sensor |
| | **SSD1306 (OLED)** / **WS2812B** | Display / NeoPixel LED |
| **Language** | **Python 3.9+** | Main Development Language |
| **Network** | **TCP/IP Socket** | `socket`, `struct` (Low-latency) |
| **Audio/DSP** | **NumPy**, **PyAudio**, **RNNoise** | Signal Processing & AI Filter |
| **Library** | `adafruit-circuitpython-ssd1306` | OLED Control |
| | `rpi_ws281x` | NeoPixel Control |
| | `RPi.GPIO` | General Sensor Control |