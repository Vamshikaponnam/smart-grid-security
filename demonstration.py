import os
import time
import threading
import winsound
from datetime import datetime

import numpy as np
import tkinter as tk

from model.autoencoder_gan import SmartGridSecurityModel
from utils.data_loader import (
    generate_synthetic_data,
    preprocess_data
)


# ============================================================
# CONFIGURATION
# ============================================================

ATTACK_TYPES = [
    "Normal",
    "DDoS Attack",
    "Data Injection",
    "Command Injection",
    "Scanning"
]

CRITICAL_ATTACKS = {
    "DDoS Attack",
    "Data Injection",
    "Command Injection"
}

WARNING_ATTACKS = {
    "Scanning"
}

alarm_stop_event = threading.Event()


# ============================================================
# RESULTS FOLDER
# ============================================================

def create_results_folder():
    os.makedirs("results", exist_ok=True)


# ============================================================
# ALARM
# ============================================================

def trigger_attack_alarm(attack_type, count):

    alarm_stop_event.clear()

    print("\n" + "=" * 70)
    print("              !!! ATTACK DETECTED !!!")
    print("=" * 70)
    print(f"Attack Type        : {attack_type}")
    print(f"Detected Instances : {count}")
    print("Alarm Duration     : 60 seconds")
    print("Immediate Action   : REQUIRED")
    print("=" * 70)

    def alarm():

        start_time = time.time()

        while (
            time.time() - start_time < 60
            and not alarm_stop_event.is_set()
        ):

            try:
                winsound.Beep(1600, 500)
                winsound.Beep(900, 500)
                winsound.Beep(1600, 500)
                winsound.Beep(900, 500)

            except Exception:
                break

    threading.Thread(
        target=alarm,
        daemon=True
    ).start()


# ============================================================
# FALLBACK CLASSIFIER
# ============================================================

class FallbackClassifier:

    def __init__(self):
        self.centroids = {}

    def fit(self, X, y):

        X = np.asarray(X)

        if X.ndim > 2:
            X = X.reshape(X.shape[0], -1)

        y = np.asarray(y)

        for cls in np.unique(y):

            samples = X[y == cls]

            if len(samples) > 0:

                self.centroids[int(cls)] = np.mean(
                    samples,
                    axis=0
                )

        return self

    def predict_proba(self, X):

        X = np.asarray(X)

        if X.ndim > 2:
            X = X.reshape(X.shape[0], -1)

        probabilities = np.zeros(
            (len(X), len(ATTACK_TYPES)),
            dtype=np.float32
        )

        if not self.centroids:

            probabilities[:, 0] = 1.0
            return probabilities

        for i, sample in enumerate(X):

            distances = []

            for cls in range(len(ATTACK_TYPES)):

                if cls in self.centroids:

                    distance = np.linalg.norm(
                        sample - self.centroids[cls]
                    )

                else:

                    distance = 1e9

                distances.append(distance)

            distances = np.asarray(distances)

            valid = distances[distances < 1e8]

            if len(valid) == 0:

                probabilities[i, 0] = 1.0
                continue

            scale = np.mean(valid) + 1e-8

            scores = np.exp(
                -distances / scale
            )

            total = np.sum(scores)

            if total > 0:
                probabilities[i] = scores / total
            else:
                probabilities[i, 0] = 1.0

        return probabilities


def fallback_classification(
    X_train,
    y_train,
    X_test
):

    print("\nUsing fallback classifier...")

    classifier = FallbackClassifier()

    classifier.fit(
        X_train,
        y_train
    )

    return classifier.predict_proba(
        X_test
    )


# ============================================================
# THREAT SEVERITY
# ============================================================

def calculate_severity(
    attack_counts,
    total_samples
):

    total_attacks = sum(
        attack_counts.values()
    )

    if total_attacks == 0:

        return (
            "SAFE",
            "#16a34a"
        )

    dominant_attack = max(
        attack_counts,
        key=attack_counts.get
    )

    attack_rate = (
        total_attacks /
        max(total_samples, 1)
    ) * 100

    if dominant_attack in CRITICAL_ATTACKS:

        return (
            "CRITICAL",
            "#dc2626"
        )

    if dominant_attack in WARNING_ATTACKS:

        return (
            "WARNING",
            "#f59e0b"
        )

    if attack_rate >= 30:

        return (
            "CRITICAL",
            "#dc2626"
        )

    if attack_rate >= 10:

        return (
            "WARNING",
            "#f59e0b"
        )

    return (
        "SAFE",
        "#16a34a"
    )


# ============================================================
# DASHBOARD
# ============================================================

def show_security_dashboard(
    attack_counts,
    total_samples,
    anomalies,
    threshold,
    alarm_active=False
):

    root = tk.Tk()

    root.title(
        "Smart Grid Security - AI Threat Detection Center"
    )

    root.geometry(
        "1350x850"
    )

    root.minsize(
        1100,
        750
    )

    root.configure(
        bg="#0b1220"
    )

    # ========================================================
    # SAFE TKINTER CALLBACK MANAGEMENT
    # ========================================================

    closing = [False]
    after_ids = set()

    def safe_after(delay, callback):

        if closing[0]:
            return

        callback_id = [None]

        def wrapper():

            current_id = callback_id[0]

            if current_id in after_ids:
                after_ids.discard(current_id)

            if closing[0]:
                return

            try:
                callback()
            except tk.TclError:
                pass

        try:

            callback_id[0] = root.after(
                delay,
                wrapper
            )

            after_ids.add(
                callback_id[0]
            )

        except tk.TclError:
            pass

    def cancel_callbacks():

        for callback_id in list(after_ids):

            try:
                root.after_cancel(
                    callback_id
                )
            except tk.TclError:
                pass

        after_ids.clear()

    def close_dashboard():

        if closing[0]:
            return

        closing[0] = True

        alarm_stop_event.set()

        cancel_callbacks()

        try:
            root.destroy()
        except tk.TclError:
            pass

    root.protocol(
        "WM_DELETE_WINDOW",
        close_dashboard
    )

    # ========================================================
    # CALCULATIONS
    # ========================================================

    total_attacks = sum(
        attack_counts.values()
    )

    anomaly_count = int(
        np.sum(anomalies)
    )

    attack_rate = (
        total_attacks /
        max(total_samples, 1)
    ) * 100

    severity, severity_color = calculate_severity(
        attack_counts,
        total_samples
    )

    dominant_attack = max(
        attack_counts,
        key=attack_counts.get
    )

    risk_score = min(
        100,
        int(
            attack_rate * 2
            +
            (
                anomaly_count /
                max(total_samples, 1)
                * 50
            )
        )
    )

    # ========================================================
    # MAIN
    # ========================================================

    main = tk.Frame(
        root,
        bg="#0b1220"
    )

    main.pack(
        fill="both",
        expand=True
    )

    # ========================================================
    # HEADER
    # ========================================================

    header = tk.Frame(
        main,
        bg="#111827",
        height=75
    )

    header.pack(
        fill="x"
    )

    tk.Label(
        header,
        text="SMART GRID SECURITY",
        font=("Segoe UI", 22, "bold"),
        fg="white",
        bg="#111827"
    ).pack(
        side="left",
        padx=25,
        pady=18
    )

    tk.Label(
        header,
        text="AI-POWERED THREAT DETECTION & RESPONSE",
        font=("Segoe UI", 10),
        fg="#94a3b8",
        bg="#111827"
    ).pack(
        side="left",
        padx=10
    )

    clock_label = tk.Label(
        header,
        text="",
        font=("Segoe UI", 11),
        fg="#60a5fa",
        bg="#111827"
    )

    clock_label.pack(
        side="right",
        padx=25
    )

    # ========================================================
    # CLOCK
    # ========================================================

    def update_clock():

        if closing[0]:
            return

        try:

            clock_label.config(
                text=datetime.now().strftime(
                    "%d-%m-%Y   %H:%M:%S"
                )
            )

            safe_after(
                1000,
                update_clock
            )

        except tk.TclError:
            return

    update_clock()

    # ========================================================
    # STATUS
    # ========================================================

    status_frame = tk.Frame(
        main,
        bg=severity_color,
        height=60
    )

    status_frame.pack(
        fill="x",
        padx=18,
        pady=(15, 8)
    )

    if severity == "CRITICAL":

        status_text = (
            "● CRITICAL THREAT  |  "
            + dominant_attack
        )

    elif severity == "WARNING":

        status_text = (
            "● WARNING  |  "
            + dominant_attack
        )

    else:

        status_text = (
            "● SYSTEM SAFE  |  "
            "NO SERIOUS THREAT DETECTED"
        )

    status_label = tk.Label(
        status_frame,
        text=status_text,
        font=("Segoe UI", 17, "bold"),
        fg="white",
        bg=severity_color
    )

    status_label.pack(
        pady=15
    )

    # ========================================================
    # METRICS
    # ========================================================

    metrics = tk.Frame(
        main,
        bg="#0b1220"
    )

    metrics.pack(
        fill="x",
        padx=18,
        pady=8
    )

    def metric_card(
        title,
        value,
        color
    ):

        card = tk.Frame(
            metrics,
            bg="#111827"
        )

        card.pack(
            side="left",
            fill="both",
            expand=True,
            padx=5
        )

        tk.Label(
            card,
            text=title,
            font=("Segoe UI", 10, "bold"),
            fg="#94a3b8",
            bg="#111827"
        ).pack(
            pady=(12, 2)
        )

        tk.Label(
            card,
            text=value,
            font=("Segoe UI", 21, "bold"),
            fg=color,
            bg="#111827"
        ).pack(
            pady=(0, 12)
        )

    metric_card(
        "TOTAL SAMPLES",
        str(total_samples),
        "#60a5fa"
    )

    metric_card(
        "ATTACK EVENTS",
        str(total_attacks),
        "#f87171"
    )

    metric_card(
        "ANOMALIES",
        str(anomaly_count),
        "#f59e0b"
    )

    metric_card(
        "THREAT LEVEL",
        severity,
        severity_color
    )

    # ========================================================
    # BODY
    # ========================================================

    body = tk.Frame(
        main,
        bg="#0b1220"
    )

    body.pack(
        fill="both",
        expand=True,
        padx=18,
        pady=8
    )

    # ========================================================
    # LEFT
    # ========================================================

    left = tk.Frame(
        body,
        bg="#111827"
    )

    left.pack(
        side="left",
        fill="both",
        expand=True,
        padx=(0, 7)
    )

    tk.Label(
        left,
        text="ATTACK ANALYSIS",
        font=("Segoe UI", 14, "bold"),
        fg="white",
        bg="#111827"
    ).pack(
        anchor="w",
        padx=15,
        pady=12
    )

    analysis_text = (
        f"Dominant Attack : {dominant_attack}\n"
        f"Attack Rate     : {attack_rate:.2f}%\n"
        f"Risk Score      : {risk_score}/100\n"
        f"Threshold       : {threshold:.6f}\n"
        f"System Status   : {severity}"
    )

    tk.Label(
        left,
        text=analysis_text,
        justify="left",
        font=("Consolas", 10),
        fg="#cbd5e1",
        bg="#111827"
    ).pack(
        anchor="w",
        padx=15
    )

    # ========================================================
    # ATTACK DISTRIBUTION
    # ========================================================

    tk.Label(
        left,
        text="ATTACK DISTRIBUTION",
        font=("Segoe UI", 12, "bold"),
        fg="white",
        bg="#111827"
    ).pack(
        anchor="w",
        padx=15,
        pady=(18, 8)
    )

    distribution = tk.Frame(
        left,
        bg="#111827"
    )

    distribution.pack(
        fill="x",
        padx=15
    )

    bar_colors = {
        "Normal": "#16a34a",
        "DDoS Attack": "#dc2626",
        "Data Injection": "#dc2626",
        "Command Injection": "#dc2626",
        "Scanning": "#f59e0b"
    }

    for attack in ATTACK_TYPES:

        count = attack_counts.get(
            attack,
            0
        )

        percentage = (
            count /
            max(total_samples, 1)
        ) * 100

        row = tk.Frame(
            distribution,
            bg="#111827"
        )

        row.pack(
            fill="x",
            pady=4
        )

        tk.Label(
            row,
            text=attack,
            width=20,
            anchor="w",
            font=("Segoe UI", 9),
            fg="#cbd5e1",
            bg="#111827"
        ).pack(
            side="left"
        )

        bar_bg = tk.Frame(
            row,
            bg="#374151",
            height=18
        )

        bar_bg.pack(
            side="left",
            fill="x",
            expand=True,
            padx=5
        )

        width = max(
            0.02,
            min(
                1.0,
                percentage / 100
            )
        )

        tk.Frame(
            bar_bg,
            bg=bar_colors[attack],
            height=18
        ).place(
            relx=0,
            rely=0,
            relwidth=width,
            relheight=1
        )

        tk.Label(
            row,
            text=f"{count} ({percentage:.1f}%)",
            width=15,
            anchor="e",
            font=("Segoe UI", 9),
            fg="#cbd5e1",
            bg="#111827"
        ).pack(
            side="right"
        )

    # ========================================================
    # SEVERITY
    # ========================================================

    severity_box = tk.Frame(
        left,
        bg="#0f172a",
        highlightbackground=severity_color,
        highlightthickness=2
    )

    severity_box.pack(
        fill="x",
        padx=15,
        pady=18
    )

    tk.Label(
        severity_box,
        text="THREAT SEVERITY",
        font=("Segoe UI", 11, "bold"),
        fg="#94a3b8",
        bg="#0f172a"
    ).pack(
        pady=(10, 2)
    )

    tk.Label(
        severity_box,
        text=f"●  {severity}",
        font=("Segoe UI", 22, "bold"),
        fg=severity_color,
        bg="#0f172a"
    ).pack()

    description = {
        "SAFE":
            "Normal grid activity detected.",
        "WARNING":
            "Suspicious activity requires monitoring.",
        "CRITICAL":
            "Serious attack activity detected!"
    }

    tk.Label(
        severity_box,
        text=description[severity],
        font=("Segoe UI", 9),
        fg="#cbd5e1",
        bg="#0f172a"
    ).pack(
        pady=(0, 10)
    )

    # ========================================================
    # RIGHT
    # ========================================================

    right = tk.Frame(
        body,
        bg="#111827"
    )

    right.pack(
        side="right",
        fill="both",
        expand=True,
        padx=(7, 0)
    )

    # ========================================================
    # LIVE GRAPH TITLE
    # ========================================================

    tk.Label(
        right,
        text="LIVE THREAT ACTIVITY",
        font=("Segoe UI", 14, "bold"),
        fg="white",
        bg="#111827"
    ).pack(
        anchor="w",
        padx=15,
        pady=12
    )

    # ========================================================
    # GRAPH
    # ========================================================

    graph = tk.Canvas(
        right,
        height=180,
        bg="#070d19",
        highlightthickness=1,
        highlightbackground="#1e293b"
    )

    graph.pack(
        fill="x",
        padx=15
    )

    GRAPH_HEIGHT = 180
    MAX_POINTS = 100

    graph_points = []

    live_counter = [0]

    # ========================================================
    # INITIAL POINTS
    # ========================================================

    for _ in range(MAX_POINTS):

        if severity == "CRITICAL":

            value = (
                80 +
                np.random.randint(-35, 36)
            )

        elif severity == "WARNING":

            value = (
                100 +
                np.random.randint(-22, 23)
            )

        else:

            value = (
                120 +
                np.random.randint(-10, 11)
            )

        graph_points.append(
            max(
                15,
                min(
                    GRAPH_HEIGHT - 15,
                    value
                )
            )
        )

    # ========================================================
    # DRAW GRID
    # ========================================================

    def draw_grid():

        if closing[0]:
            return

        try:

            graph.delete(
                "grid"
            )

            width = graph.winfo_width()

            if width < 100:
                width = 800

            for y in range(
                20,
                GRAPH_HEIGHT,
                25
            ):

                graph.create_line(
                    0,
                    y,
                    width,
                    y,
                    fill="#172033",
                    width=1,
                    tags="grid"
                )

            for x in range(
                0,
                width,
                50
            ):

                graph.create_line(
                    x,
                    0,
                    x,
                    GRAPH_HEIGHT,
                    fill="#101827",
                    width=1,
                    tags="grid"
                )

        except tk.TclError:
            pass

    # ========================================================
    # DRAW GRAPH
    # ========================================================

    def draw_live_graph():

        if closing[0]:
            return

        try:

            graph.delete(
                "live"
            )

            width = graph.winfo_width()

            if width < 100:
                width = 800

            if len(graph_points) < 2:
                return

            step = (
                width - 20
            ) / (
                len(graph_points) - 1
            )

            coordinates = []

            for i, value in enumerate(
                graph_points
            ):

                x = (
                    10 +
                    i * step
                )

                coordinates.extend(
                    [x, value]
                )

            graph.create_line(
                *coordinates,
                fill=severity_color,
                width=3,
                smooth=True,
                tags="live"
            )

            x = coordinates[-2]
            y = coordinates[-1]

            graph.create_oval(
                x - 5,
                y - 5,
                x + 5,
                y + 5,
                fill=severity_color,
                outline="white",
                width=1,
                tags="live"
            )

        except tk.TclError:
            pass

    # ========================================================
    # LIVE VALUE
    # ========================================================

    def get_live_value():

        live_counter[0] += 1

        t = live_counter[0]

        if severity == "CRITICAL":

            value = (
                80
                +
                np.sin(t * 0.35) * 30
                +
                np.random.randint(-25, 26)
            )

            if t % 15 == 0:

                value -= np.random.randint(
                    30,
                    55
                )

        elif severity == "WARNING":

            value = (
                100
                +
                np.sin(t * 0.25) * 18
                +
                np.random.randint(-15, 16)
            )

        else:

            value = (
                120
                +
                np.sin(t * 0.20) * 8
                +
                np.random.randint(-7, 8)
            )

        return max(
            15,
            min(
                GRAPH_HEIGHT - 15,
                value
            )
        )

    # ========================================================
    # CONTINUOUS GRAPH
    # ========================================================

    def update_live_graph():

        if closing[0]:
            return

        try:

            graph_points.append(
                get_live_value()
            )

            if len(graph_points) > MAX_POINTS:

                graph_points.pop(0)

            draw_grid()
            draw_live_graph()

            if "ATTACK EVENTS" in telemetry_labels:

                current_events = (
                    total_attacks
                    +
                    live_counter[0] // 5
                )

                telemetry_labels[
                    "ATTACK EVENTS"
                ].config(
                    text=str(
                        current_events
                    )
                )

            if "EVENT RATE" in telemetry_labels:

                live_rate = (
                    attack_rate
                    +
                    np.sin(
                        live_counter[0] * 0.2
                    ) * 3
                )

                live_rate = max(
                    0,
                    live_rate
                )

                telemetry_labels[
                    "EVENT RATE"
                ].config(
                    text=f"{live_rate:.2f}%"
                )

            safe_after(
                100,
                update_live_graph
            )

        except tk.TclError:

            return

    # ========================================================
    # RESIZE
    # ========================================================

    def graph_resize(event=None):

        if closing[0]:
            return

        draw_grid()
        draw_live_graph()

    graph.bind(
        "<Configure>",
        graph_resize
    )

    draw_grid()
    draw_live_graph()

    # ========================================================
    # TELEMETRY
    # ========================================================

    telemetry = tk.Frame(
        right,
        bg="#0f172a"
    )

    telemetry.pack(
        fill="x",
        padx=15,
        pady=12
    )

    telemetry_labels = {}

    telemetry_items = [
        ("MONITORING", "ACTIVE"),
        ("ATTACK EVENTS", str(total_attacks)),
        ("ANOMALIES", str(anomaly_count)),
        ("EVENT RATE", f"{attack_rate:.2f}%")
    ]

    for name, value in telemetry_items:

        row = tk.Frame(
            telemetry,
            bg="#0f172a"
        )

        row.pack(
            fill="x",
            padx=12,
            pady=4
        )

        tk.Label(
            row,
            text=name,
            font=("Segoe UI", 9, "bold"),
            fg="#64748b",
            bg="#0f172a"
        ).pack(
            side="left"
        )

        value_label = tk.Label(
            row,
            text=value,
            font=("Segoe UI", 9, "bold"),
            fg=severity_color,
            bg="#0f172a"
        )

        value_label.pack(
            side="right"
        )

        telemetry_labels[name] = value_label

    # Start graph AFTER telemetry exists
    safe_after(
        300,
        update_live_graph
    )

    # ========================================================
    # RESPONSE CENTER
    # ========================================================

    tk.Label(
        right,
        text="AUTOMATED RESPONSE CENTER",
        font=("Segoe UI", 14, "bold"),
        fg="white",
        bg="#111827"
    ).pack(
        anchor="w",
        padx=15,
        pady=(8, 10)
    )

    response_status = tk.Label(
        right,
        text=(
            f"THREAT: {dominant_attack}"
            f"   |   "
            f"SEVERITY: {severity}"
            f"   |   "
            f"RISK: {risk_score}/100"
        ),
        font=("Segoe UI", 10, "bold"),
        fg=severity_color,
        bg="#111827"
    )

    response_status.pack(
        anchor="w",
        padx=15
    )

    # ========================================================
    # EVENT LOG
    # ========================================================

    log_frame = tk.Frame(
        right,
        bg="#0f172a"
    )

    log_frame.pack(
        fill="both",
        expand=True,
        padx=15,
        pady=10
    )

    tk.Label(
        log_frame,
        text="SECURITY EVENT LOG",
        font=("Segoe UI", 10, "bold"),
        fg="#94a3b8",
        bg="#0f172a"
    ).pack(
        anchor="w",
        padx=10,
        pady=6
    )

    log_text = tk.Text(
        log_frame,
        height=7,
        bg="#020617",
        fg="#cbd5e1",
        insertbackground="white",
        font=("Consolas", 9),
        relief="flat"
    )

    log_text.pack(
        fill="both",
        expand=True,
        padx=8,
        pady=5
    )

    now = datetime.now().strftime(
        "%H:%M:%S"
    )

    log_text.insert(
        "end",
        f"[{now}] Security monitoring started.\n"
    )

    log_text.insert(
        "end",
        f"[{now}] Dominant threat: "
        f"{dominant_attack}\n"
    )

    log_text.insert(
        "end",
        f"[{now}] Severity level: "
        f"{severity}\n"
    )

    log_text.insert(
        "end",
        f"[{now}] Risk score: "
        f"{risk_score}/100\n"
    )

    log_text.config(
        state="disabled"
    )

    # ========================================================
    # LOG FUNCTION
    # ========================================================

    def add_log(message):

        if closing[0]:
            return

        try:

            log_text.config(
                state="normal"
            )

            log_text.insert(
                "end",
                (
                    "["
                    +
                    datetime.now().strftime(
                        "%H:%M:%S"
                    )
                    +
                    "] "
                    +
                    message
                    +
                    "\n"
                )
            )

            log_text.see(
                "end"
            )

            log_text.config(
                state="disabled"
            )

        except tk.TclError:
            pass

    # ========================================================
    # RESPONSE ACTION
    # ========================================================

    def response_action(action):

        add_log(
            f"RESPONSE ACTION: {action}"
        )

        try:

            response_status.config(
                text=(
                    f"ACTION EXECUTED: {action}"
                    f"   |   "
                    f"THREAT: {dominant_attack}"
                ),
                fg="#60a5fa"
            )

        except tk.TclError:
            pass

    # ========================================================
    # BUTTONS
    # ========================================================

    button_frame = tk.Frame(
        right,
        bg="#111827"
    )

    button_frame.pack(
        fill="x",
        padx=15,
        pady=(0, 8)
    )

    for action in [
        "BLOCK ATTACK",
        "ISOLATE DEVICE",
        "INVESTIGATE"
    ]:

        tk.Button(
            button_frame,
            text=action,
            command=lambda a=action:
                response_action(a),
            bg="#1f2937",
            fg="white",
            activebackground="#374151",
            activeforeground="white",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=8
        ).pack(
            side="left",
            expand=True,
            fill="x",
            padx=3
        )

    # ========================================================
    # FOOTER
    # ========================================================

    footer = tk.Frame(
        main,
        bg="#111827"
    )

    footer.pack(
        fill="x",
        padx=18,
        pady=(0, 15)
    )

    def stop_alarm():

        alarm_stop_event.set()

        add_log(
            "Security alarm stopped manually."
        )

    tk.Button(
        footer,
        text="STOP ALARM",
        command=stop_alarm,
        bg="#991b1b",
        fg="white",
        activebackground="#b91c1c",
        activeforeground="white",
        relief="flat",
        font=("Segoe UI", 10, "bold"),
        padx=20,
        pady=8
    ).pack(
        side="left",
        padx=5
    )

    tk.Button(
        footer,
        text="CLOSE DASHBOARD",
        command=close_dashboard,
        bg="#374151",
        fg="white",
        activebackground="#4b5563",
        activeforeground="white",
        relief="flat",
        font=("Segoe UI", 10, "bold"),
        padx=20,
        pady=8
    ).pack(
        side="right",
        padx=5
    )

    # ========================================================
    # CRITICAL PULSE
    # ========================================================

    if severity == "CRITICAL":

        pulse_state = [True]

        def pulse():

            if closing[0]:
                return

            try:

                if pulse_state[0]:

                    status_frame.config(
                        bg="#991b1b"
                    )

                    status_label.config(
                        bg="#991b1b"
                    )

                else:

                    status_frame.config(
                        bg="#dc2626"
                    )

                    status_label.config(
                        bg="#dc2626"
                    )

                pulse_state[0] = (
                    not pulse_state[0]
                )

                safe_after(
                    500,
                    pulse
                )

            except tk.TclError:
                pass

        safe_after(
            500,
            pulse
        )

    # ========================================================
    # RUN
    # ========================================================

    root.mainloop()


# ============================================================
# MAIN DEMONSTRATION
# ============================================================

def run_demonstration():

    print("\n")
    print("=" * 70)
    print("          SMART GRID SECURITY AI SYSTEM")
    print("=" * 70)

    create_results_folder()

    # ========================================================
    # DATA
    # ========================================================

    print(
        "\n[1/8] Generating synthetic smart-grid data..."
    )

    df = generate_synthetic_data(
        n_samples=5000,
        time_steps=24,
        n_features=10,
        n_classes=5
    )

    print(
        "Data generation completed."
    )

    # ========================================================
    # PREPROCESSING
    # ========================================================

    print(
        "\n[2/8] Preprocessing data..."
    )

    (
        X_train,
        X_val,
        X_test,
        y_train,
        y_val,
        y_test
    ) = preprocess_data(df)

    print(
        "Training data shape :",
        X_train.shape
    )

    print(
        "Validation shape    :",
        X_val.shape
    )

    print(
        "Testing shape       :",
        X_test.shape
    )

    # ========================================================
    # MODEL
    # ========================================================

    print(
        "\n[3/8] Creating Smart Grid Security model..."
    )

    model = SmartGridSecurityModel(
        input_shape=(24, 10),
        latent_dim=32,
        num_classes=5,
        dropout_rate=0.3
    )

    print(
        "Model created successfully."
    )

    # ========================================================
    # AUTOENCODER
    # ========================================================

    print(
        "\n[4/8] Training Autoencoder..."
    )

    try:

        model.train_autoencoder(
            X_train,
            X_val,
            epochs=10,
            batch_size=32
        )

        print(
            "Autoencoder training completed."
        )

    except Exception as error:

        print(
            "[WARNING] Autoencoder error:",
            error
        )

    # ========================================================
    # GAN
    # ========================================================

    print(
        "\n[5/8] Training GAN..."
    )

    try:

        model.train_gan(
            X_train,
            epochs=10,
            batch_size=32
        )

        print(
            "GAN training completed."
        )

    except Exception as error:

        print(
            "[WARNING] GAN training failed:",
            error
        )

    # ========================================================
    # CLASSIFIER
    # ========================================================

    print(
        "\n[6/8] Training attack classifier..."
    )

    classifier_failed = False

    try:

        model.train_classifier(
            X_train,
            y_train,
            X_val,
            y_val,
            epochs=10,
            batch_size=32
        )

        print(
            "Classifier training completed."
        )

    except Exception as error:

        classifier_failed = True

        print(
            "[WARNING] Classifier training failed:"
        )

        print(
            error
        )

        print(
            "Using fallback classifier."
        )

    # ========================================================
    # FULL MODEL
    # ========================================================

    print(
        "\n[7/8] Training complete security model..."
    )

    try:

        model.train_full_model(
            X_train,
            y_train,
            X_val,
            y_val,
            epochs=5,
            batch_size=32
        )

        print(
            "Full model training completed."
        )

    except Exception as error:

        print(
            "[WARNING] Full model training failed:",
            error
        )

    # ========================================================
    # SECURITY ANALYSIS
    # ========================================================

    print(
        "\n[8/8] Running security analysis..."
    )

    # ========================================================
    # ANOMALY DETECTION
    # ========================================================

    print(
        "\nDetecting anomalies..."
    )

    try:

        (
            anomalies,
            mse,
            threshold
        ) = model.detect_anomalies(
            X_test
        )

    except Exception as error:

        print(
            "[WARNING] Anomaly detection failed:",
            error
        )

        anomalies = np.zeros(
            len(X_test),
            dtype=bool
        )

        threshold = 0.5

    # ========================================================
    # CLASSIFICATION
    # ========================================================

    print(
        "\nClassifying attacks..."
    )

    if classifier_failed:

        y_pred_proba = fallback_classification(
            X_train,
            y_train,
            X_test
        )

    else:

        try:

            y_pred_proba = (
                model.classify_attacks(
                    X_test
                )
            )

        except Exception as error:

            print(
                "[WARNING] Attack classification failed:"
            )

            print(
                error
            )

            y_pred_proba = fallback_classification(
                X_train,
                y_train,
                X_test
            )

    # ========================================================
    # PREDICTIONS
    # ========================================================

    y_pred = np.argmax(
        y_pred_proba,
        axis=1
    )

    # ========================================================
    # ATTACK COUNTS
    # ========================================================

    attack_counts = {}

    for i, attack in enumerate(
        ATTACK_TYPES
    ):

        attack_counts[attack] = int(
            np.sum(
                y_pred == i
            )
        )

    # ========================================================
    # RESULTS
    # ========================================================

    print("\n" + "=" * 70)
    print("ATTACK DETECTION RESULTS")
    print("=" * 70)

    for attack, count in attack_counts.items():

        percentage = (
            count /
            max(
                len(X_test),
                1
            )
        ) * 100

        print(
            f"{attack:<25} : "
            f"{count:<6} "
            f"({percentage:.2f}%)"
        )

    print("=" * 70)

    # ========================================================
    # THREAT ASSESSMENT
    # ========================================================

    severity, severity_color = calculate_severity(
        attack_counts,
        len(X_test)
    )

    dominant_attack = max(
        attack_counts,
        key=attack_counts.get
    )

    print("\nTHREAT ASSESSMENT")
    print("-" * 50)

    print(
        "Dominant Attack :",
        dominant_attack
    )

    print(
        "Threat Level    :",
        severity
    )

    if severity == "CRITICAL":

        print(
            "STATUS          : "
            "SERIOUS ATTACK DETECTED"
        )

    elif severity == "WARNING":

        print(
            "STATUS          : "
            "SUSPICIOUS ACTIVITY"
        )

    else:

        print(
            "STATUS          : "
            "SYSTEM SAFE"
        )

    print("-" * 50)

    # ========================================================
    # ALARM
    # ========================================================

    total_attacks = (
        len(X_test)
        -
        attack_counts.get(
            "Normal",
            0
        )
    )

    if (
        total_attacks > 0
        and severity == "CRITICAL"
    ):

        trigger_attack_alarm(
            dominant_attack,
            attack_counts[
                dominant_attack
            ]
        )

    # ========================================================
    # DASHBOARD
    # ========================================================

    print(
        "\nStarting security dashboard..."
    )

    show_security_dashboard(
        attack_counts=attack_counts,
        total_samples=len(X_test),
        anomalies=anomalies,
        threshold=threshold,
        alarm_active=(
            total_attacks > 0
        )
    )


# ============================================================
# PROGRAM ENTRY
# ============================================================

if __name__ == "__main__":

    try:

        run_demonstration()

    except KeyboardInterrupt:

        alarm_stop_event.set()

        print(
            "\nProgram stopped by user."
        )

    except Exception as error:

        alarm_stop_event.set()

        print(
            "\n" + "=" * 70
        )

        print(
            "UNEXPECTED ERROR"
        )

        print(
            "=" * 70
        )

        print(
            error
        )

        print(
            "=" * 70
        )