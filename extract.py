import cv2
import matplotlib.pyplot as plt

# 打开视频文件
video = cv2.VideoCapture("video/cs2.mkv")
num = 0 # 计算器
save_step = 30 #  间隔帧
while True:
    # 读取一帧
    ret, frame = video.read()
    if not ret:
        break
    num +=1
    if num % save_step == 0:
        cv2.imwrite("./cs2/" + str(num) + ".jpg", frame)
