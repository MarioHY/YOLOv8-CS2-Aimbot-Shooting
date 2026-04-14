<div align="center">
  
# 🚀 YOLOv8 CS2 Auto-Aim & Visual Detection System

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![YOLOv8](https://img.shields.io/badge/Model-YOLOv8-red.svg)](https://github.com/ultralytics/ultralytics)
[![PyQt5](https://img.shields.io/badge/UI-PyQt5-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)

基于 YOLOv8 深度学习模型的 CS2（Counter-Strike 2）实时目标检测与辅助系统。本项目通过高速屏幕采集与 GPU 加速推理，实现对游戏内敌方目标的识别、自动锁头及射击功能。

</div>

---

## 📺 性能与效果说明 (General Performance)

> **声明**：本程序展示的是**通用计算机视觉辅助**效果，其表现受多种因素影响。


<div align="center">
  <img src="demo.gif" width="80%" title="竖屏效果演示">
  <p><em>竖屏实时检测效果演示</em></p>
</div>

* **识别表现**：效果处于“一般辅助”水平。在光线充足、目标清晰的场景下识别较准；但在烟雾弹、强闪光、杂乱背景或目标极远时，可能会出现识别跳变或漏检。
* **硬件依赖**：效果依赖 GPU 算力。在 RTX 3060 及以上显卡上，推理延迟通常可保持在极低水平，能够满足实时性需求。
* **平滑度**：代码内置了分步平滑算法，模拟真人手感，避免准星瞬间“传送”，但这也意味着在极高速移动的目标面前可能存在一定的跟随延迟。

---

## 🛠️ 环境部署

### 1. 创建虚拟环境
建议使用 Conda 管理环境以确保依赖稳定：
```bash
conda create -n lock python=3.12.0
conda activate lock
```

### 2. 安装所需库
建议使用 Conda 管理环境以确保依赖稳定：
```bash
# 安装基础依赖
pip install ultralytics mss pyautogui PyQt5 pywin32
```

### 3. 安装 CUDA & cuDNN
为了获得流畅的运行效果，必须配置与你显卡驱动相匹配的 NVIDIA 加速环境：

A. 检查支持的 CUDA 版本
1. 按下 Win + R，输入 cmd。

2. 输入 nvidia-smi 并回车。

3. 查看右上角的 CUDA Version，这是你显卡驱动支持的最高版本。

B. 下载与安装
1. CUDA Toolkit: 前往 [NVIDIA 官网](https://developer.nvidia.com/cuda-toolkit-archive) 下载对应版本。

2. cuDNN: 下载[cuDNN](https://developer.nvidia.com/rdp/cudnn-archive)，解压并将文件夹内容覆盖至CUDA安装目录（默认路径：C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1）。

C. 安装 PyTorch (CUDA版)
必须安装支持 CUDA 的 PyTorch 版本，否则程序将运行在 CPU 上造成卡顿：
```bash
# 以 CUDA 12.1 为例
conda install pytorch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0 pytorch-cuda=12.1 -c pytorch -c nvidia
```

---

## 🚀 使用指南
启动程序
```bash
python main.py
```

交互操作说明
* **置信度 (Confidence)**：调节识别阈值。值越高识别越严谨，值越低越容易误判。

* **灵敏度 (Sensitivity)**：调节鼠标跟随速度。建议根据游戏内 DPI 微调。

* **检测区域**：设置屏幕右上角的扫描框大小。区域越小推理 FPS 越高，延迟越低。

* **目标选择**：支持勾选“警头部”、“匪头部”等特定标签进行针对性锁定。

---

## ⚙️ 技术特性
* **高速截屏**：利用 mss 库直接抓取屏幕显存数据，延迟远低于传统方式。

* **DPI 自适应**：内置 DPI 感知逻辑，解决高分辨率屏幕下的坐标偏移问题。

* **模拟操作**：通过 win32api 发送相对位移指令，绕过绝对坐标限制。

* **安全节流**：内置每秒开火次数限制，防止操作频率过快导致行为异常。


---

## ⚠️ 免责声明 (Disclaimer)
1. **仅限学习**：本项目仅用于 AI 技术的研究与学习，严禁在任何正式竞技环境中使用。

2. **封号风险**：使用辅助工具违反游戏服务协议，可能导致账号封禁。开发者不对任何形式的损失负责。

3. **法律合规**：请在当地法律法规允许的范围内使用，由使用者自行承担相关责任。

