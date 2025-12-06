# YOLOv8-CS2-Auto-Aim-Shooting
基于 YOLOv8 模型的cs2人物自动锁头射击

#### 创建虚拟环境

```
conda create -n lock python=3.12.0
conda activate lock

```
#### 安装所需库
```
pip install ultralytics
pip uninstall torch,torchvision,torchaudio
pip install mss
pip install pyautogui
pip install PyQt5
```

#### 安装CUDA 

```
# win+r，nvidia-smi显卡运算平台
# win11 12.1 4060显卡
https://developer.nvidia.com/cuda-12-1-0-download-archive?target_os=Windows&target_arch=x86_64&target_version=11&target_type=exe_local
```

#### 安装cuDNN

```
# 12.x
https://developer.nvidia.com/downloads/compute/cudnn/secure/8.9.7/local_installers/12.x/cudnn-windows-x86_64-8.9.7.29_cuda12-archive.zip/
# 安装完后解压，放在cuda目录，默认C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1
```

#### 安装torch

```
# 安装2.4.0的cuda
# CUDA 12.1
conda install pytorch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0 pytorch-cuda=12.1 -c pytorch -c nvidia
```

#### 使用
```
python main.py
```
