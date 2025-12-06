from ultralytics import YOLO

if __name__ == '__main__':
    # 载入yolov8n轻量化模型
    model = YOLO('yolov8n.pt')

    # 训练参数
    model.train(
        data="cs2.yaml",        # 配置文件
        device=0,
        workers=0,              #单进程加载，避免报错
        epochs=50,             # 50轮测试先
        batch=8,                # 8G显存，用8batch可以
        lr0=0.001,              # 适配batch=8，比默认略低，避免震荡
        imgsz=640,              # 训练输入的一般都是640，到时候检测也是转640
    )
