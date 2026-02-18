import sys
import threading
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from opcua import Client, ua

# --- CONNECTION CONFIG ---
URL = "opc.tcp://192.168.0.20:49320"
TAGS = {
    "PV":    "ns=2;s=DR.Device1.Symbol Set.PV",
    "CV":    "ns=2;s=DR.Device1.Symbol Set.CV",
    "START": "ns=2;s=DR.Device1.Symbol Set.start",
    "STOP":  "ns=2;s=DR.Device1.Symbol Set.STOP",
    "RESET": "ns=2;s=DR.Device1.Symbol Set.RESET",
    "MOTOR": "ns=2;s=DR.Device1.Symbol Set.MOTOR",
    "Q":     "ns=2;s=DR.Device1.Symbol Set.Q"
}

# --- THEME COLORS ---
BG_COLOR = "#F2F4F7"
PRIMARY = "#0D47A1"
SUCCESS = "#4CAF50"
DANGER = "#D32F2F"
WARNING = "#F39C12"

class IndustrialSCADA(QMainWindow):
    update_signal = Signal(str, object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MOTOR HMI")
        self.resize(1280, 800)
        
        self.client = Client(URL)
        self.nodes = {}
        self.connected = False
        self.chart_points = 0

        self.init_ui()
        self.update_signal.connect(self.handle_updates)
        
        threading.Thread(target=self.opc_worker, daemon=True).start()

    def init_ui(self):
        central = QWidget()
        central.setStyleSheet(f"background-color: {BG_COLOR};")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. HEADER
        header = QFrame()
        header.setFixedHeight(60)
        header.setStyleSheet(f"background: {PRIMARY}; border: none;")
        h_layout = QHBoxLayout(header)
        title = QLabel("MOTOR CONTROL & MONITORING SYSTEM")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: bold; margin-left: 20px;")
        self.status_lbl = QLabel("PLC: OFFLINE")
        self.status_lbl.setStyleSheet("color: #FFCDD2; font-weight: bold; margin-right: 20px;")
        h_layout.addWidget(title)
        h_layout.addStretch()
        h_layout.addWidget(self.status_lbl)
        main_layout.addWidget(header)

        # 2. BODY
        body = QHBoxLayout()
        body.setContentsMargins(10, 10, 10, 10)
        body.setSpacing(15)
        main_layout.addLayout(body)

        # --- LEFT PANEL: DATA & CHARTS ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        body.addWidget(left_panel, 4)

        # Top: KPI Cards
        cards = QHBoxLayout()
        self.cv_card = self.create_card("ACTUAL COUNT (CV)", "0", "#3498db")
        self.pv_card = self.create_card("SET LIMIT (PV)", "0", "#9b59b6")
        cards.addWidget(self.cv_card["frame"])
        cards.addWidget(self.pv_card["frame"])
        left_layout.addLayout(cards)

        # Middle: Real-Time Trend Chart
        self.init_chart()
        left_layout.addWidget(self.chart_view, 1)

        # Bottom: Alarm Banner (Slim & Contextual)
        self.msg_bar = QLabel("SYSTEM READY")
        self.msg_bar.setFixedHeight(45)
        self.msg_bar.setAlignment(Qt.AlignCenter)
        self.msg_bar.setStyleSheet("background: #34495e; color: white; font-weight: bold; border-radius: 4px;")
        left_layout.addWidget(self.msg_bar)

        # --- RIGHT PANEL: CONTROLS & IO ---
        right_panel = QFrame()
        right_panel.setFixedWidth(320)
        right_panel.setStyleSheet("background: white; border-radius: 8px; border: 1px solid #CFD8DC;")
        right_layout = QVBoxLayout(right_panel)
        body.addWidget(right_panel)

        right_layout.addWidget(QLabel("STATUS INDICATORS", styleSheet="font-weight: bold; color: #546E7A; margin-bottom: 5px;"))
        self.mtr_led = self.create_indicator(right_layout, "MOTOR STATUS")
        self.q_led = self.create_indicator(right_layout, "LIMIT REACHED (Q)")
        
        right_layout.addSpacing(20)
        right_layout.addWidget(QLabel("SET POINT CONFIGURATION", styleSheet="font-weight: bold; color: #546E7A;"))
        self.pv_input = QLineEdit()
        self.pv_input.setPlaceholderText("Enter new PV...")
        self.pv_input.setStyleSheet("font-size: 16px; padding: 10px; border: 1px solid #bdc3c7; border-radius: 4px; color: black;")
        btn_set = QPushButton("UPDATE LIMIT")
        btn_set.setStyleSheet(f"background: {PRIMARY}; color: white; font-weight: bold; padding: 10px; border-radius: 4px;")
        btn_set.clicked.connect(self.write_pv)
        right_layout.addWidget(self.pv_input)
        right_layout.addWidget(btn_set)

        right_layout.addStretch()
        
        # Operation Buttons
        right_layout.addWidget(QLabel("MACHINE CONTROL", styleSheet="font-weight: bold; color: #546E7A;"))
        self.btn_start = self.create_op_btn(right_layout, "START MOTOR", SUCCESS)
        self.btn_stop = self.create_op_btn(right_layout, "STOP MOTOR", DANGER)
        self.btn_reset = self.create_op_btn(right_layout, "RESET COUNTER", WARNING)

        self.btn_start.clicked.connect(lambda: self.pulse_tag("START"))
        self.btn_stop.clicked.connect(lambda: self.pulse_tag("STOP"))
        self.btn_reset.clicked.connect(lambda: self.pulse_tag("RESET"))

    def init_chart(self):
        self.chart = QChart()
        self.chart.setAnimationOptions(QChart.SeriesAnimations)
        self.series = QLineSeries()
        self.series.setName("Live CV Trend")
        pen = QPen(QColor("#3498db"))
        pen.setWidth(3)
        self.series.setPen(pen)
        
        self.chart.addSeries(self.series)
        
        self.axis_x = QValueAxis()
        self.axis_x.setRange(0, 100)
        self.axis_x.setLabelFormat("%d")
        self.axis_x.setTitleText("Time (Samples)")

        self.axis_y = QValueAxis()
        self.axis_y.setRange(0, 50)
        self.axis_y.setTitleText("Count Value")

        self.chart.addAxis(self.axis_x, Qt.AlignBottom)
        self.chart.addAxis(self.axis_y, Qt.AlignLeft)
        self.series.attachAxis(self.axis_x)
        self.series.attachAxis(self.axis_y)

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setStyleSheet("background: white; border-radius: 8px; border: 1px solid #CFD8DC;")

    def create_card(self, title, val, color):
        f = QFrame()
        f.setStyleSheet(f"background: white; border-radius: 8px; border-top: 4px solid {color};")
        l = QVBoxLayout(f)
        l.addWidget(QLabel(title, styleSheet="color: #78909C; font-size: 11px; font-weight: bold;"))
        v = QLabel(val)
        v.setFont(QFont("Consolas", 36, QFont.Bold))
        v.setStyleSheet(f"color: {color}; border: none;")
        v.setAlignment(Qt.AlignCenter)
        l.addWidget(v)
        return {"frame": f, "label": v}

    def create_indicator(self, layout, text):
        h = QHBoxLayout()
        led = QLabel()
        led.setFixedSize(20, 20)
        led.setStyleSheet("background: #B0BEC5; border-radius: 10px; border: 1px solid #78909C;")
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 12px; color: #37474F;")
        h.addWidget(led); h.addWidget(lbl); h.addStretch()
        layout.addLayout(h)
        return led

    def create_op_btn(self, layout, text, color):
        b = QPushButton(text)
        b.setFixedHeight(50)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(f"QPushButton {{ background: {color}; color: white; font-weight: bold; border-radius: 4px; }} "
                        f"QPushButton:hover {{ background-color: silver; color: black; }}")
        layout.addWidget(b)
        return b

    # --- OPC UA & LOGIC ---
    def opc_worker(self):
        try:
            self.client.connect()
            self.connected = True
            self.update_signal.emit("STATUS", "PLC: ONLINE")
            sub_nodes = []
            for name, addr in TAGS.items():
                node = self.client.get_node(addr)
                self.nodes[name] = node
                if name in ["PV", "CV", "MOTOR", "Q"]: sub_nodes.append(node)
            handler = SubHandler(self)
            sub = self.client.create_subscription(200, handler)
            sub.subscribe_data_change(sub_nodes)
        except Exception as e:
            self.update_signal.emit("STATUS", f"PLC: ERROR")

    @Slot(str, object)
    def handle_updates(self, tag, val):
        if tag == "STATUS":
            self.status_lbl.setText(val)
            self.status_lbl.setStyleSheet("color: #C8E6C9;" if "ONLINE" in val else "color: #FFCDD2;")
        elif tag == "CV":
            self.cv_card["label"].setText(str(val))
            # Update Chart
            self.chart_points += 1
            self.series.append(self.chart_points, float(val))
            if self.chart_points > 100:
                self.axis_x.setRange(self.chart_points - 100, self.chart_points)
        elif tag == "PV":
            self.pv_card["label"].setText(str(val))
            self.axis_y.setRange(0, float(val) + 10)
            if not self.pv_input.hasFocus(): self.pv_input.setText(str(val))
        elif tag == "MOTOR":
            self.mtr_led.setStyleSheet(f"background: {SUCCESS}; border-radius: 10px;" if val else "background: #B0BEC5; border-radius: 10px;")
        elif tag == "Q":
            self.q_led.setStyleSheet(f"background: {WARNING}; border-radius: 10px;" if val else "background: #B0BEC5; border-radius: 10px;")
            if val:
                self.msg_bar.setText("⚠️ LIMIT REACHED: RESET OR INCREASE PV")
                self.msg_bar.setStyleSheet("background: #E67E22; color: white; font-weight: bold; border-radius: 4px;")
            else:
                self.msg_bar.setText("SYSTEM READY")
                self.msg_bar.setStyleSheet("background: #34495e; color: white; font-weight: bold; border-radius: 4px;")

    def write_pv(self):
        if not self.connected: return
        try:
            val = int(self.pv_input.text())
            self.nodes["PV"].set_attribute(ua.AttributeIds.Value, ua.DataValue(ua.Variant(val, ua.VariantType.UInt16)))
            self.pv_input.clearFocus()
        except: pass

    def pulse_tag(self, name):
        if not self.connected: return
        def toggle(v):
            try: self.nodes[name].set_attribute(ua.AttributeIds.Value, ua.DataValue(ua.Variant(v, ua.VariantType.Boolean)))
            except: pass
        toggle(True)
        QTimer.singleShot(600, lambda: toggle(False))

class SubHandler:
    def __init__(self, hmi): self.hmi = hmi
    def datachange_notification(self, node, val, data):
        nid = str(node.nodeid)
        if "CV" in nid: self.hmi.update_signal.emit("CV", val)
        elif "PV" in nid: self.hmi.update_signal.emit("PV", val)
        elif "MOTOR" in nid: self.hmi.update_signal.emit("MOTOR", val)
        elif "Q" in nid or nid.endswith(".Q"): self.hmi.update_signal.emit("Q", val)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = IndustrialSCADA()
    window.show()
    sys.exit(app.exec())
