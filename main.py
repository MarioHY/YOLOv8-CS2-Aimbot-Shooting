import sys  # 用来sys.exit,sys.argv
import cv2  # OpenCV
import numpy as np  # 数组
import pyautogui  # 用于模拟鼠标键盘操作，以及获取鼠标位置
from ultralytics import YOLO  # yolov8的加载检测模型
import mss  # 高效截屏库，用于抓取屏幕区域
import win32gui, win32con, win32api  # Windows的API封装
import torch  # pytorch，用于张量处理和模型推理的
import time  # 时间相关操作
import threading  # 线程支持，用于后台检测线程，主要是转图形化，避免停止检测导致停止整个程序
from ctypes import windll  # 访问Windows的ddl，用于获取该win信息

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QCheckBox, QGroupBox, QSpinBox
)
# 将numpy图像转换为Qt可显示的 QPixmap，不用cv2.imshow
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, pyqtSignal, QObject  # Qt 常量、信号与 QObject 基类

# 设置教程为DPI感知，避免在高DPI屏幕上界面缩放模糊
try:
    windll.user32.SetProcessDPIAware()
except Exception:
    # 如果不是 Windows或调用失败，忽略错误
    pass

# 预定义一下标签名，将模型输出的类别id映射为对应的
CLASS_LABELS = {
    1: "警头部",
    2: "警身体",
    3: "匪头部",
    4: "匪身体"
}

# 默认标准目标
TARGET_CLASSES = ["警头部", "匪头部"]

# 关闭PyAutoGUI的故障安全功能，就是鼠标移动到屏幕左上角的异常的安全功能
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.0001 # 设置每次调用后的暂停时间

# 获取屏幕的宽度和高度
screen_width = windll.user32.GetSystemMetrics(0)
screen_height = windll.user32.GetSystemMetrics(1)

# 初始监测区域，默认1280x768，右上角方便一些，为屏幕右上角区域
REGION_WIDTH = 1280
REGION_HEIGHT = 768
# 计算默认检测区域矩形开始点
REGION_LEFT = max(0, screen_width - REGION_WIDTH)
REGION_TOP = 0

# 变量别名，主要是没图形化前的，就不改了
WINDOW_WIGHT = REGION_WIDTH
WINDOW_HEIGHT = REGION_HEIGHT
WINDOW_LEFT = REGION_LEFT
WINDOW_TOP = REGION_TOP

# qt图形化显示的大小
RESIZE_WIGHT, RESIZE_HEIGHT = int(WINDOW_WIGHT * 0.5), int(WINDOW_HEIGHT * 0.5)

# 定义mss截屏所需的monitor字典，指定截屏区域。
monitor = {
    'left': WINDOW_LEFT,
    'top': WINDOW_TOP,
    'width': WINDOW_WIGHT,
    'height': WINDOW_HEIGHT
}


windows_name = 'CS2 detect'  # 窗口名称
model_size = 640  # 模型输入大小，根模型训练大小一样
confidence_threshold = 0.4  # 锁头所需的最低可信度
sensitivity = 0.8  # 鼠标移动灵敏度
dead_zone = 3  # 最小移动像素阈值，小于该值不触发微小移动

# 选择运行设备，如果安装有cuda，就cuda用GPU，没有就cpu
device = 'cuda' if torch.cuda.is_available() else 'cpu'

print("加载yolo模型...")
model = YOLO('demo2.pt').to(device) # 加载模型，将模型移动到指定位置，gpu则gpu
print("加载模型成功！")

# 控制是否启用自动瞄准的全局变量
aim_enabled = False

class AutoShooter:

    def __init__(self):
        """
        初始化自动射击器参数
        """
        # 上次射击时间
        self.last_shot_time = 0
        # 自动射击是否开启
        self.shooting_enabled = False
        # 射击计数器
        self.shot_counter = 0
        # 最大每秒射击次数，防止开火过快
        self.max_shots_per_second = 3
        # 线程锁，保证多线程下对鼠标事件的互斥调用
        self.lock = threading.Lock()

    def shoot(self, x, y):
        """
        执行一次开火，使用锁保护并根据时间节流，返回是否实际执行了射击。

        :param x: 射击的x坐标.
        :param y: 射击的y坐标.
        :return: true表示成功执行了射击，false表示因冷却或者锁位执行
        """
        with self.lock:
            current_time = time.time() # 获取当前时间
            # 计算一下时间，如果时间差过快，则需等一会射击
            if current_time - self.last_shot_time < 1 / self.max_shots_per_second:
                return False
            self.last_shot_time = current_time # 如果成功，则进行这一次射击
            self.shot_counter += 1 # 统计一下射击次数
            # 模拟鼠标按下和抬起
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.02)  # 保持按下短暂时间
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            print(f"射击 #{self.shot_counter} | 坐标: ({int(x)}, {int(y)}) | 时间: {current_time:.2f}s")
            return True

    # 切换自动射击开关并返回新状态
    def toggle_shooting(self):
        """
        切换自动射击开关状态，并返回新状态。

        :return: 切换后的自动射击状态
        """
        self.shooting_enabled = not self.shooting_enabled
        return self.shooting_enabled

# 射击器实例
shooter = AutoShooter()


class ParamSignal(QObject):
    # 当有新帧可显示时发出，传递numpy ndarray，rgb格式
    # frame_ready用于传递新的帧图像
    frame_ready = pyqtSignal(np.ndarray)
    # status_update用于传递状态文本更新
    status_update = pyqtSignal(str)

# 在模块级别创建信号实例，用于Qt的GUI和线程共享
param_signal = ParamSignal()

# 选择的的类别集合
SELECTED_TARGET_CLASSES = set(TARGET_CLASSES)


def mouse_move_relative(dx, dy):
    """
    相对移动鼠标,向操作系统发送相对位移事件，因为在游戏中，绝对位移只能影响外面，不能影响影响游戏内的
    如果位移低于dead_zone则忽略移动，避免小范围抖动的情况。

    :param dx: 水平相对偏移量
    :param dy: 垂直相对偏移量
    :return: None
    """
    # 取整，移动和画图只能取整
    dx = int(round(dx))
    dy = int(round(dy))
    # 如果移动距离小于死区阈值，则不移动。
    if abs(dx) < dead_zone and abs(dy) < dead_zone:
        return
    # 调用windowAPI移动鼠标
    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, dx, dy, 0, 0)

def smooth_relative_move(target_x, target_y):
    """
    将鼠标平滑移动鼠标到目标坐标

    :param target_x: 目标屏幕X坐标
    :param target_y: 目标屏幕Y坐标
    :return: None
    """
    # 获取当前鼠标位置
    current_x, current_y = pyautogui.position()
    # 计算需要移动的绝对距离
    abs_dx = target_x - current_x
    abs_dy = target_y - current_y
    # 根据灵敏度缩放移动的绝对距离
    rel_dx = abs_dx * sensitivity
    rel_dy = abs_dy * sensitivity
    # 步数取决于位移大小，限定在 1 到 5 步之间，较大位移会分更多步
    # 动态计算鼠标平滑移动的步长，根据鼠标需要移动的距离自动调整步长大小
    # 距离越远，步长越大，避免鼠标瞬移，限制最小步长为1，最大步长为5，
    # 计算曼哈顿距离进行计算步长
    steps = max(1, min(5, int(np.sqrt(abs(rel_dx) + abs(rel_dy)) // 10)))
    # 计算每次要移动的距离，距离越远，单次步长移动越快
    step_dx = rel_dx / steps
    step_dy = rel_dy / steps

    # 分步移动，实现平滑效果
    for _ in range(steps):
        mouse_move_relative(step_dx, step_dy)
        time.sleep(0.0005)  # 很短的休眠以使移动看起来更平滑


def set_detection_size(new_width: int, new_height: int):
    """
    更新全局检测区域尺寸

    :param new_width: 新的检测区域宽度
    :param new_height: 新的检测区域高度
    :return: 是否成功设置尺寸
    """
    # 声明要修改的全局变量，
    global REGION_WIDTH, REGION_HEIGHT, REGION_LEFT, REGION_TOP
    global WINDOW_WIGHT, WINDOW_HEIGHT, WINDOW_LEFT, WINDOW_TOP
    global RESIZE_WIGHT, RESIZE_HEIGHT, monitor

    # 进行新的宽度转换，先检查是否合理
    try:
        w = int(new_width)
        h = int(new_height)
    except Exception:
        return False # 转换失败就返回错误

    # 限制区域在合理范围内，最小100，最大就是屏幕宽度，不能大于屏幕
    w = max(100, min(screen_width, w))
    h = max(100, min(screen_height, h))
    # 更新检测的框
    REGION_WIDTH = w
    REGION_HEIGHT = h
    REGION_LEFT = max(0, screen_width - REGION_WIDTH)
    REGION_TOP = 0
    # 别名
    WINDOW_WIGHT = REGION_WIDTH
    WINDOW_HEIGHT = REGION_HEIGHT
    WINDOW_LEFT = REGION_LEFT
    WINDOW_TOP = REGION_TOP
    # qt5图形化显示的宽度
    RESIZE_WIGHT = int(WINDOW_WIGHT * 0.5)
    RESIZE_HEIGHT = int(WINDOW_HEIGHT * 0.5)
    # 截屏区域新cfg的数值
    monitor['left'] = WINDOW_LEFT
    monitor['top'] = WINDOW_TOP
    monitor['width'] = WINDOW_WIGHT
    monitor['height'] = WINDOW_HEIGHT

    # 发送状态更新信号
    param_signal.status_update.emit(f"检测区域设置为 {REGION_WIDTH}x{REGION_HEIGHT} (left={monitor['left']})")
    print(f"[set_detection_size] {REGION_WIDTH}x{REGION_HEIGHT}, RESIZE={RESIZE_WIGHT}x{RESIZE_HEIGHT}")
    return True


class AimBotWorker(threading.Thread):
    def __init__(self):
        """
        初始化后台线程参数，设置为守护线程
        """
        # 设置为守护线程，程序退出时线程随主进程结束
        super().__init__(daemon=True)
        # 控制线程运行的实际，start启动或者pause暂停
        self._running = threading.Event()
        # 控制线程何时终止
        self._terminate = threading.Event()
        self._running.clear() # 初始状态暂停
        self._terminate.clear() # 初始状态不终止

    def start_worker(self):
        """
        启动后台检测线程，设置运行标志

        :return: None
        """
        # 允许运行，如果线程尚未启动则调用start()启动线程
        self._running.set() # 设置运行标志
        # 如果线程未启动，则启动它
        if not self.is_alive():
            self.start()
        param_signal.status_update.emit("检测已启动")

    def pause_worker(self):
        """
        暂停后台检测线程

        :return: None
        """
        # 暂停检测循环，不杀死进程
        self._running.clear()
        param_signal.status_update.emit("检测已暂停")

    def terminate_worker(self):
        """
        终止后台检测线程

        :return: None
        """
        # 请求线程终止
        self._terminate.set()
        self._running.set() # 确保线程能检查到终止信号


    def run(self):
        """
        线程的主循环，不断截屏并进行yolo模型推理，直到收到terminate信号

        :return: None
        """
        # 创建截屏对象
        sct = mss.mss()
        # 使用到的全局变量
        global confidence_threshold, sensitivity, RESIZE_WIGHT, RESIZE_HEIGHT
        global WINDOW_WIGHT, WINDOW_HEIGHT, monitor, aim_enabled, shooter, SELECTED_TARGET_CLASSES

        try:
            while not self._terminate.is_set(): # 如果未终止，主循环
                # 如果处于暂停状态，就等待启动
                if not self._running.is_set():
                    time.sleep(0.05)
                    continue
                try:
                    # 截取录屏区域，rgb
                    img = np.array(sct.grab(monitor))[:, :, :3]

                    # 获取HCW（0, 1, 2)格式的张量，并放到指定cpu或gpu设备上，
                    img_tensor = torch.from_numpy(img).float().to(device)
                    # 换成BCHW, batch=B （将B放在0索引处） --> BCHW格式, 255进行归一化
                    img_tensor = img_tensor.permute(2, 0, 1).unsqueeze(0) / 255.0

                    # 调整模型输入大小
                    img_tensor = torch.nn.functional.interpolate(
                        img_tensor, size=(model_size, model_size),
                        mode='bilinear', align_corners=False
                    )

                    # 进行推理，no_grad不进行梯度计算节省内存
                    with torch.no_grad():
                        results = model(img_tensor) # 获取检测到的结果

                    result = results[0]  # 获取第一个结果

                    # 分析检测结果，选择最近的目标
                    closest_target = None
                    min_distance = float('inf')

                    # 遍历模型输出的每个检测框
                    for box in result.boxes:
                        # 获取类别id
                        label_id = int(box.cls[0].item())
                        # 获取置信度
                        confidence = box.conf.item()
                        # id映射为对应中文标签
                        class_name = CLASS_LABELS.get(label_id)

                        # 如果置信度达到且是选定类别
                        if confidence >= confidence_threshold and class_name in SELECTED_TARGET_CLASSES:

                            # 获取框坐标
                            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

                            # 将坐标转换为检测坐标，检测的是模型输入大小
                            # 计算转换的比例
                            scale_x = WINDOW_WIGHT / model_size
                            scale_y = WINDOW_HEIGHT / model_size
                            # 转化为检测的真实坐标
                            real_x1 = x1 * scale_x
                            real_x2 = x2 * scale_x
                            real_y1 = y1 * scale_y
                            real_y2 = y2 * scale_y

                            # 计算头部
                            center_x = (real_x1 + real_x2) / 2
                            center_y = real_y1 + (real_y2 - real_y1) * 0.25

                            # 转为屏幕坐标，检测的真实坐标是检测范围的，现在检测屏幕的内的
                            screen_x = WINDOW_LEFT + center_x
                            screen_y = WINDOW_TOP + center_y

                            # 确保坐标在屏幕范围内
                            screen_x = max(0, min(screen_width - 1, screen_x))
                            screen_y = max(0, min(screen_height - 1, screen_y))

                            # 计算到鼠标当前位置到目标点的平方距离
                            current_x, current_y = pyautogui.position()
                            # 真实坐标减当前坐标
                            distance = (screen_x - current_x) ** 2 + (screen_y - current_y) ** 2

                            # 记录距离最近的目标
                            if distance < min_distance:
                                min_distance = distance
                                closest_target = (screen_x, screen_y)

                    # 如果存在，则处理最接近的目标
                    if closest_target:
                        screen_x, screen_y = closest_target
                        # 通过内置的getattr安全获取self的属性进行运行线程
                        running = getattr(self, "_running").is_set()

                        # 如果线程运行且用户启用了锁头
                        if running and aim_enabled:
                            param_signal.status_update.emit(
                                f"锁定目标：({int(screen_x)}, {int(screen_y)}) 距离：{int(np.sqrt(min_distance))} px"
                            )

                            # 平滑移动鼠标朝目标移动
                            smooth_relative_move(screen_x, screen_y)

                            # 如果自动射击开启，则在接近目标时触发开火
                            if shooter.shooting_enabled:
                                current_x, current_y = pyautogui.position()
                                shoot_distance = np.sqrt((screen_x - current_x) ** 2 + (screen_y - current_y) ** 2)

                                # 当鼠标已经接近目标，这里设置50px时进行设计
                                if shoot_distance < 50:
                                    shooter.shoot(screen_x, screen_y)
                        else:
                            # 线程在运行但未启用aim，或线程未运行，发送相应状态消息，显示到gui的
                            if running:
                                param_signal.status_update.emit(
                                    f"检测到目标 ({int(screen_x)}, {int(screen_y)}) - 锁头未启用"
                                )
                            else:
                                param_signal.status_update.emit(
                                    f"检测到目标 ({int(screen_x)}, {int(screen_y)}) - 线程未运行"
                                )
                    else:
                        # 没有找到任何满足条件的目标
                        param_signal.status_update.emit("未锁定目标")


                    # 将模型自动检测绘制的结果，准备在GUI中显示图像
                    annotated_frame = result.plot()  # 通常为 BGR 图像
                    w = max(1, RESIZE_WIGHT)
                    h = max(1, RESIZE_HEIGHT)
                    # 调整gui显示的大小
                    display_frame = cv2.resize(annotated_frame, (w, h))

                    # 发送图像到GUI
                    param_signal.frame_ready.emit(display_frame)
                    # 短暂延迟，避免完全占用CPU
                    time.sleep(0.001)

                except Exception as e:
                    # 捕获并上报处理异常，线程会继续循环
                    param_signal.status_update.emit(f"检测错误：{e}")
                    print(f"AimBotWorker内部异常：{e}")
                    time.sleep(0.05)
        finally:
            # 线程退出前通知gui清理
            param_signal.status_update.emit("检测线程已终止")


class MainWindow(QWidget):
    def __init__(self):
        """
        初始化主窗口布局、控件、信号连接。
        """
        super().__init__()
        # 窗口基本标题与大小
        self.setWindowTitle("CS2 Aimbot")
        self.setGeometry(100, 100, 640, 820)

        # -------------------------
        # 置信度控件
        # -------------------------
        conf_group = QGroupBox("置信度 (confidence)")
        self.conf_slider = QSlider(Qt.Horizontal)
        self.conf_slider.setRange(1, 99)  # 0.01-0.99
        self.conf_slider.setValue(int(confidence_threshold * 100))
        # 信号绑定由on_conf_changed处理
        self.conf_slider.valueChanged.connect(self.on_conf_changed)
        self.conf_label = QLabel(f"{confidence_threshold:.2f}")
        conf_layout = QHBoxLayout()
        conf_layout.addWidget(self.conf_slider)
        conf_layout.addWidget(self.conf_label)
        conf_group.setLayout(conf_layout)

        # -------------------------
        # 灵敏度控件
        # -------------------------
        sens_group = QGroupBox("灵敏度 (sensitivity)")
        self.sens_slider = QSlider(Qt.Horizontal)
        self.sens_slider.setRange(10, 300)  # 0.10-3.00
        self.sens_slider.setValue(int(sensitivity * 100))
        # 信号绑定由on_sens_changed函数处理
        self.sens_slider.valueChanged.connect(self.on_sens_changed)
        self.sens_label = QLabel(f"{sensitivity:.2f}")
        sens_layout = QHBoxLayout()
        sens_layout.addWidget(self.sens_slider)
        sens_layout.addWidget(self.sens_label)
        sens_group.setLayout(sens_layout)

        # -------------------------
        # 检测区域尺寸控件
        # -------------------------
        size_group = QGroupBox("检测区域尺寸（从屏幕右上角开始）")
        self.width_spin = QSpinBox()
        self.width_spin.setRange(100, screen_width)
        self.width_spin.setValue(REGION_WIDTH)
        self.width_spin.setSingleStep(32)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(100, screen_height)
        self.height_spin.setValue(REGION_HEIGHT)
        self.height_spin.setSingleStep(32)
        self.apply_size_btn = QPushButton("应用检测尺寸")
        # 信号绑定由on_apply_size操作函数处理
        self.apply_size_btn.clicked.connect(self.on_apply_size)
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("宽:"))
        size_layout.addWidget(self.width_spin)
        size_layout.addWidget(QLabel("高:"))
        size_layout.addWidget(self.height_spin)
        size_layout.addWidget(self.apply_size_btn)
        size_group.setLayout(size_layout)

        # -------------------------
        # 目标选择
        # -------------------------
        target_group = QGroupBox("选择射击目标")
        target_layout = QHBoxLayout()  # 水平布局，复选框在一行显示
        self.target_checkboxes = {}  # 存放label-》QCheckBox的映射
        unique_labels = sorted(set(CLASS_LABELS.values()))  # 去重并排序所有的标签字符串
        for lbl in unique_labels:
            cb = QCheckBox(lbl)
            # 根据默认的SELECTED_TARGET_CLASSES初始化勾选状态
            cb.setChecked(lbl in SELECTED_TARGET_CLASSES)
            # 每次状态变化都调用on_target_checkbox_changed函数来更新SELECTED_TARGET_CLASSES
            cb.stateChanged.connect(self.on_target_checkbox_changed)
            self.target_checkboxes[lbl] = cb
            target_layout.addWidget(cb)
        # 添加伸缩项，让复选框在一行中对齐并且不拥挤
        target_layout.addStretch()
        target_group.setLayout(target_layout)

        # -------------------------
        # 启用锁头与自动射击
        # -------------------------
        self.aim_checkbox = QCheckBox("启用锁头")
        self.aim_checkbox.setChecked(False)
        # 信号绑定由on_aim_changed函数处理
        self.aim_checkbox.stateChanged.connect(self.on_aim_changed)

        self.shooting_checkbox = QCheckBox("启用自动射击")
        self.shooting_checkbox.setChecked(False)
        # 信号绑定由on_shooting_changed函数处理
        self.shooting_checkbox.stateChanged.connect(self.on_shooting_changed)

        # -------------------------
        # 启动与暂停按钮
        # -------------------------
        self.start_btn = QPushButton("启动检测识别")
        self.stop_btn = QPushButton("暂停检测识别")
        self.stop_btn.setEnabled(False)  # 初始暂停按钮禁用
        # 信号绑定由start_worker函数处理
        self.start_btn.clicked.connect(self.start_worker)
        # 信号绑定由pause_worker函数处理
        self.stop_btn.clicked.connect(self.pause_worker)

        # -------------------------
        # 状态显示与图像显示
        # -------------------------
        self.status_label = QLabel("状态：就绪")
        self.mode_label = QLabel("模式：未运行")
        # 给mode_label加背景色，对比看起来更方便
        self.mode_label.setStyleSheet("color: white; background-color: gray; padding:4px;")
        self.image_label = QLabel()
        self.image_label.setFixedSize(RESIZE_WIGHT, RESIZE_HEIGHT)
        # 初始化为黑色空白图
        blank = np.zeros((RESIZE_HEIGHT, RESIZE_WIGHT, 3), dtype=np.uint8)
        self.set_image(blank)

        # -------------------------
        # 将所有控件放到主窗口
        # -------------------------
        vbox = QVBoxLayout()
        vbox.addWidget(conf_group)
        vbox.addWidget(sens_group)
        vbox.addWidget(size_group)
        vbox.addWidget(target_group)
        vbox.addWidget(self.aim_checkbox)
        vbox.addWidget(self.shooting_checkbox)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        vbox.addLayout(btn_layout)
        vbox.addWidget(self.status_label)
        vbox.addWidget(self.mode_label)
        vbox.addWidget(self.image_label)
        self.setLayout(vbox)

        # 后台工作线程实例
        self.worker = None
        # 图像显示帧绑定
        param_signal.frame_ready.connect(self.on_frame_ready)
        # 更新状态栏绑定
        param_signal.status_update.connect(self.on_status_update)
        # 初始化模式标签显示
        self.update_mode_label()

    # -------------------------
    # UI绑定功能函数
    # -------------------------
    def update_mode_label(self):
        """
        根据线程状态、锁头、射击开关更新模式标签的文本与背景色。

        :return: None
        """
        running = False
        if self.worker is not None:
            try:
                running = getattr(self.worker, "_running").is_set()
            except Exception:
                running = False

        aim = aim_enabled
        shoot = shooter.shooting_enabled
        if not running:
            text = f"模式：未运行 — 锁头: {'启用' if aim else '禁用'}，自动射击: {'启用' if shoot else '禁用'}"
            color = "gray"
        else:
            if aim and shoot:
                text = "模式：运行 — 锁头: 启用，自动射击: 启用 (ACTIVE)"
                color = "green"
            elif aim and not shoot:
                text = "模式：运行 — 锁头: 启用，自动射击: 未启用"
                color = "orange"
            else:
                text = "模式：运行 — 仅显示"
                color = "blue"
        self.mode_label.setText(text)
        self.mode_label.setStyleSheet(f"color: white; background-color: {color}; padding:4px;")

    def set_image(self, frame_rgb):
        """
        将RGB格式numpy数组转换为QPixmap，并显示在image_label

        :param frame_rgb: RGB格式的图像数组
        :return: None
        """
        if frame_rgb is None:
            return
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        # QImage需要底层数据指针和行字节数，Format_RGB888，假定3通道8
        img = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pix = QPixmap.fromImage(img)
        self.image_label.setPixmap(pix)

    def on_frame_ready(self, frame_rgb):
        """
        当工作线程发送新帧时调用，尝试将其显示到 GUI。
        任何显示错误都会被捕获并打印。

        :param frame_rgb: 待显示的RGB格式图像数组
        :return: None
        """
        try:
            self.set_image(frame_rgb)
        except Exception as e:
            print(f"on_frame_ready 错误: {e}")

    def on_status_update(self, text: str):
        """
        接收状态更新信号，更新状态栏文本并刷新模式标签。

        :param text: 状态描述文本
        :return: None
        """
        # 更新状态栏文本，并尝试刷新模式标签
        self.status_label.setText(f"状态：{text}")
        try:
            self.update_mode_label()
        except Exception:
            pass

    def on_conf_changed(self, val):
        """
        置信度滑块值变化时，更新全局置信度阈值。

        :param val: 滑块当前值,1-99 --》 0.01-0.99
        :return: None
        """
        # 更新全局confidence_threshold并显示新值
        global confidence_threshold
        confidence_threshold = val / 100.0
        self.conf_label.setText(f"{confidence_threshold:.2f}")
        param_signal.status_update.emit(f"置信度调整至 {confidence_threshold:.2f}")

    def on_sens_changed(self, val):
        """
        灵敏度滑块值变化时，更新全局鼠标灵敏度。

        :param val: 滑块当前值，10-300 --》 0.10-3.00
        :return: None
        """
        # 更新全局 sensitivity
        global sensitivity
        sensitivity = val / 100.0
        self.sens_label.setText(f"{sensitivity:.2f}")
        param_signal.status_update.emit(f"灵敏度调整至 {sensitivity:.2f}")

    def on_target_checkbox_changed(self, _):
        """
        当任意目标复选框状态变化时，更新全局选中目标集合

        :param _: 复选框状态，
        :return: None
        """
        global SELECTED_TARGET_CLASSES
        new_set = set()
        for lbl, cb in self.target_checkboxes.items():
            if cb.isChecked():
                new_set.add(lbl)
        SELECTED_TARGET_CLASSES = new_set
        param_signal.status_update.emit(f"已选择目标类别: {', '.join(sorted(SELECTED_TARGET_CLASSES)) or '（无）'}")
        self.update_mode_label()

    def on_aim_changed(self, state):
        """
        锁头复选框状态变化时，更新全局aim_enabled开关。

        :param state: 复选框状态
        :return: None
        """
        # 更新全局aim_enabled
        global aim_enabled
        aim_enabled = (state == Qt.Checked)
        status = "启用" if aim_enabled else "禁用"
        param_signal.status_update.emit(f"锁头已{status}")
        self.update_mode_label()

    def on_shooting_changed(self, state):
        """
        自动射击复选框状态变化时，更新射击器开关。

        :param state: 复选框状态
        :return: None
        """
        # 更新射击器的shooting_enabled状态
        global shooter
        shooter.shooting_enabled = (state == Qt.Checked)
        status = "启用" if shooter.shooting_enabled else "禁用"
        param_signal.status_update.emit(f"自动射击已{status}")
        self.update_mode_label()

    def on_apply_size(self):
        """
        点击应用检测尺寸按钮，更新检测区域参数。

        :return: None
        """
        # 应用设置的检测区域尺寸
        w = self.width_spin.value()
        h = self.height_spin.value()
        ok = set_detection_size(w, h)
        if ok:
            try:
                # 更新GUI中显示图像的QLabel的固定大小，并设置黑色空白图以刷新显示
                self.image_label.setFixedSize(RESIZE_WIGHT, RESIZE_HEIGHT)
                blank = np.zeros((RESIZE_HEIGHT, RESIZE_WIGHT, 3), dtype=np.uint8)
                self.set_image(blank)
            except Exception as e:
                print(f"on_apply_size 错误: {e}")

    def start_worker(self):
        """
        点击启动按钮时，启动/恢复后台检测线程。

        :return: None
        """
        if self.worker is None or (not self.worker.is_alive() and not self.worker._terminate.is_set()):
            self.worker = AimBotWorker()
        if self.worker._terminate.is_set():
            # 如果之前线程已被标记为终止，重新创建新的线程实例
            self.worker = AimBotWorker()
        self.worker.start_worker()
        # 更新按钮状态以避免重复启动
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        param_signal.status_update.emit("已请求启动检测")
        self.update_mode_label()

    def pause_worker(self):
        """
        点击暂停按钮时，暂停后台检测线程。

        :return: None
        """
        # 暂停检测（不杀死线程）
        if self.worker is None:
            param_signal.status_update.emit("检测尚未启动")
            return
        self.worker.pause_worker()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        param_signal.status_update.emit("已暂停检测")
        self.update_mode_label()

    def keyPressEvent(self, event):
        """
        按下ESC键关闭窗口。

        :param event: 按键事件对象
        :return: None
        """
        # 按 Esc 关闭窗口（便捷键）
        if event.key() == Qt.Key_Escape:
            self.close()

    def closeEvent(self, event):
        """
        终止后台线程，清理资源。

        :param event: 窗口关闭事件对象
        :return: None
        """
        # 窗口关闭,停止后台线程
        try:
            if self.worker is not None:
                self.worker.terminate_worker()
                self.worker.join(timeout=2.0)
        except Exception:
            pass
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()