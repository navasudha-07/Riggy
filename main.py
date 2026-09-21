import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import socket
import threading
import time
import pygame
import json
from datetime import datetime
import os
from collections import deque
import math
import statistics
import subprocess
import cv2
import numpy as np
from ebooklib import epub
from jinja2 import Template
import base64
import fitz  # PyMuPDF
import sys

def resource_path(relative_path):
    try:
        # When running as a compiled executable
        base_path = sys._MEIPASS
    except Exception:
        # When running as a normal script
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def fechar_janela():
    app.destroy()
    sys.exit(0)

# === CONFIGURATION ===
PORTA_UDP = 5000
TIMEOUT = 0.01
LP_ALPHA = 0.9
WINDOW_SIZE = 20
TARGET_FPS = 15
FRAME_INTERVAL = 1.0 / TARGET_FPS
BUFFER_SIZE = 2048
recording_start = None
recording_end = None

# === TECHNICAL STANDARDS ===
estruturas_normas = {
    'Reinforced Concrete (NBR 6118)': {
        'tilt': 1.0,
        'vib': 0.7,
        'norma': 'NBR 6118',
        'descricao': 'Reinforced concrete structures - Procedure'
    },
    'Steel Structures (NBR 8800)': {
        'tilt': 1.5,
        'vib': 0.5,
        'norma': 'NBR 8800',
        'descricao': 'Design of steel structures and composite steel and concrete structures'
    },
    'Lightweight Structures (NBR 15370)': {
        'tilt': 2.0,
        'vib': 0.3,
        'norma': 'NBR 15370',
        'descricao': 'Wooden structures - Test methods'
    },
    'Bridges and Viaducts (NBR 7188)': {
        'tilt': 0.8,
        'vib': 0.4,
        'norma': 'NBR 7188',
        'descricao': 'Road and pedestrian live load on bridges'
    },
    'Precast Structures (NBR 9062)': {
        'tilt': 1.2,
        'vib': 0.6,
        'norma': 'NBR 9062',
        'descricao': 'Design and execution of precast concrete structures'
    },
    'Custom': {
        'tilt': 80.0,
        'vib': 1.5,
        'norma': 'Custom Limits',
        'descricao': 'User defined limits'
    }
}

# Global variables for current limits
TILT_THRESHOLD = 80.0
VIB_THRESHOLD = 1.5
ESTRUTURA_ATUAL = 'Custom'
UNIDADE_VIB_ATUAL = 'g'

# === AUDIO ===
pygame.mixer.init()
def tocar_alerta(nome_arquivo):
    caminho = resource_path(nome_arquivo)
    if os.path.isfile(caminho):
        pygame.mixer.music.load(caminho)
        pygame.mixer.music.play()

# === GLOBAL VARIABLES ===
running = False
thread = None
recording = False
video_writer = None
video_filename = None
frames_buffer = []
last_frame_time = 0

data_thread = None
graph_thread = None
video_thread = None

import queue
data_queue = queue.Queue()
graph_queue = queue.Queue()

graph_cache = {}
last_update_time = 0
UPDATE_INTERVAL = 0.1

performance_stats = {
    'frames_captured': 0,
    'last_update_time': 0,
    'real_fps': 0
}

loading_dots = 0
loading_timer_epub = None
loading_timer_pdf = None

INTERPOLACAO_HABILITADA = False
encerrado = False

tempo = []
tilts = deque(maxlen=WINDOW_SIZE)
vibracoes = deque(maxlen=WINDOW_SIZE)
alerts = []

tilts_all = []
vibracoes_all = []

tilt_alerted = False
vib_alerted = False
t = 0
gravity = [0.0, 0.0, 9.81]

# === UNIT CONVERSION FUNCTIONS ===
def g_para_ms2(valor_g):
    """Converts acceleration from g to m/s²"""
    return valor_g * 9.81

def ms2_para_g(valor_ms2):
    """Converts acceleration from m/s² to g"""
    return valor_ms2 / 9.81

def obter_limite_vib_convertido():
    """Gets the vibration limit in the correct unit"""
    global VIB_THRESHOLD, UNIDADE_VIB_ATUAL
    if UNIDADE_VIB_ATUAL == 'm/s²':
        return VIB_THRESHOLD
    else:
        return VIB_THRESHOLD

def converter_vibracao_para_unidade_norma(vib_g):
    """Converts vibration from g to the standard unit (m/s²)"""
    global UNIDADE_VIB_ATUAL
    if UNIDADE_VIB_ATUAL == 'm/s²':
        return g_para_ms2(vib_g)
    else:
        return vib_g

# === VIDEO RECORDING ===
def iniciar_gravacao():
    global recording, video_writer, video_filename, frames_buffer, recording_start
    if recording:
        return
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_filename = f"gravacao_graficos_{now}.mp4"
    recording = True
    frames_buffer = []
    recording_start = datetime.now()
    print(f"Starting recording: {video_filename}")

def finalizar_gravacao():
    global recording, video_writer, frames_buffer, recording_end
    if not recording:
        return
    recording = False
    recording_end = datetime.now()

    if len(frames_buffer) == 0:
        print("No frames captured for recording")
        return
    try:
        height, width, channels = frames_buffer[0].shape
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        duracao_segundos = (recording_end - recording_start).total_seconds()
        fps_real = len(frames_buffer) / duracao_segundos if duracao_segundos > 0 else TARGET_FPS
        
        fps_video = fps_real
        video_writer = cv2.VideoWriter(video_filename, fourcc, fps_video, (width, height))
        
        if len(frames_buffer) > 1:
            print(f"Using real frames: {len(frames_buffer)} frames")
            print(f"Calculated real FPS: {fps_video:.2f}")
            print(f"Video speed will match real test speed")
        
        for frame in frames_buffer:
            video_writer.write(frame)
        video_writer.release()
        video_writer = None
        
        duracao_real = (recording_end - recording_start).total_seconds()
        fps_real = len(frames_buffer) / duracao_real if duracao_real > 0 else 0
        performance_stats['real_fps'] = fps_real
        
        print(f"Recording finished: {video_filename}")
        print(f"Captured frames: {len(frames_buffer)}")
        print(f"Real FPS: {fps_video:.2f}")
        print(f"Test duration: {duracao_segundos:.2f} seconds")
        print(f"Video duration: {len(frames_buffer) / fps_video:.2f} seconds")
        print(f"✅ Video with correct speed!")
        if video_filename and os.path.isfile(video_filename):
            print(f"Video saved: {video_filename}")
    except Exception as e:
        print(f"Error finishing recording: {e}")
        if video_writer:
            video_writer.release()

def capturar_frame_grafico():
    global frames_buffer, last_frame_time, performance_stats
    if not recording:
        return
    
    current_time = time.time()
    if current_time - last_frame_time < FRAME_INTERVAL:
        return
    
    last_frame_time = current_time
    
    performance_stats['frames_captured'] += 1
    performance_stats['last_update_time'] = current_time
    
    try:
        canvas.draw()
        canvas.flush_events()
        
        buf = canvas.buffer_rgba()
        buf = np.asarray(buf)
        buf = buf.reshape(canvas.get_width_height()[::-1] + (4,))
        
        frame_rgb = buf[:, :, :3]
        frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        frame = cv2.resize(frame, (640, 480))
        frame = cv2.resize(frame, (640, 480), interpolation=cv2.INTER_LINEAR)
        
        frames_buffer.append(frame.copy())
        
        if len(frames_buffer) > 1000:
            frames_buffer.pop(0)
            
    except Exception as e:
        print(f"Erro ao capturar frame: {e}")
        try:
            buf = np.frombuffer(canvas.tostring_rgb(), dtype=np.uint8)
            buf = buf.reshape(canvas.get_width_height()[::-1] + (3,))
            frame = cv2.cvtColor(buf, cv2.COLOR_RGB2BGR)
            frame = cv2.resize(frame, (640, 480))
            frames_buffer.append(frame.copy())
            if len(frames_buffer) > 500:
                frames_buffer.pop(0)
        except Exception as e2:
            print(f"Error in frame capture fallback: {e2}")


EPUB_TEMPLATE = """
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{{ titulo }}</title>
    <meta charset="utf-8"/>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 20px;
            color: #333;
        }
        .header {
            text-align: center;
            border-bottom: 3px solid #FF8800;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .logo {
            color: #FF8800;
            font-size: 24px;
            font-weight: bold;
        }
        .subtitle {
            color: #666;
            font-size: 14px;
        }
        .section {
            margin: 20px 0;
            padding: 15px;
            border-left: 4px solid #FF8800;
            background-color: #f9f9f9;
        }
        .section-title {
            color: #FF8800;
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .norma-section {
            background-color: #f0f0ff;
            border: 2px solid #0066cc;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 15px 0;
        }
        .stat-item {
            margin: 5px 0;
        }
        .status-conforme {
            color: #008000;
            font-weight: bold;
        }
        .status-nao-conforme {
            color: #cc0000;
            font-weight: bold;
        }
        .video-section {
            background-color: #1a1a1a;
            color: white;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
            text-align: center;
        }
        .video-container {
            margin: 20px 0;
            background-color: #000;
            border-radius: 5px;
            padding: 10px;
        }
        video {
            max-width: 100%;
            height: auto;
            border-radius: 5px;
            background-color: #000;
        }
        .video-fallback {
            background-color: #333;
            padding: 20px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .video-fallback a {
            color: #FF8800;
            text-decoration: none;
            font-weight: bold;
        }
        .video-fallback a:hover {
            text-decoration: underline;
        }
        .footer {
            border-top: 1px solid #FF8800;
            padding-top: 15px;
            margin-top: 30px;
            font-size: 12px;
            color: #666;
        }
        .chart-container {
            text-align: center;
            margin: 20px 0;
        }
        .chart-container img {
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        .video-info {
            font-size: 12px;
            color: #ccc;
            margin: 10px 0;
        }
        .compatibility-note {
            background-color: #2a2a2a;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
            font-size: 12px;
            color: #aaa;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">RIGGY REPORT</div>
        <div class="subtitle">UDP SensaGram - Sensor Monitoring</div>
    </div>

    <div class="norma-section">
        <div class="section-title">📋 APPLIED TECHNICAL STANDARD</div>
        <p><strong>Evaluated Structure:</strong> {{ estrutura_atual }}</p>
        <p><strong>Applied Standard:</strong> {{ norma_info.norma }}</p>
        <p><strong>Description:</strong> {{ norma_info.descricao }}</p>
        <p><strong>Limits:</strong> Tilt ≤ {{ limite_tilt }}° | Vibration ≤ {{ limite_vib }} {{ unidade_display }}</p>
    </div>

    <div class="section">
        <div class="section-title">GENERAL INFORMATION</div>
        <div class="stats-grid">
            <div>
                <div class="stat-item"><strong>Date and Time:</strong> {{ data_hora }}</div>
                <div class="stat-item"><strong>Collected Points:</strong> {{ pontos_coletados }}</div>
                <div class="stat-item"><strong>Test Duration:</strong> {{ duracao_teste }} seconds</div>
            </div>
            <div>
                <div class="stat-item"><strong>Tilt Alerts:</strong> {{ alertas_tilt }}</div>
                <div class="stat-item"><strong>Vibration Alerts:</strong> {{ alertas_vib }}</div>
            </div>
        </div>
    </div>

    {% if mostrar_tilt %}
    <div class="section">
        <div class="section-title">📐 TILT STATISTICS (°)</div>
        <div class="stats-grid">
            <div>
                <div class="stat-item"><strong>Average:</strong> {{ tilt_media }}°</div>
                <div class="stat-item"><strong>Maximum:</strong> {{ tilt_max }}°</div>
                <div class="stat-item"><strong>Minimum:</strong> {{ tilt_min }}°</div>
            </div>
            <div>
                <div class="stat-item"><strong>Standard Deviation:</strong> {{ tilt_std }}°</div>
                <div class="stat-item"><strong>Standard Limit:</strong> {{ limite_tilt }}°</div>
                <div class="stat-item"><strong>Status:</strong> 
                    <span class="{{ 'status-conforme' if tilt_status == 'COMPLIANT' else 'status-nao-conforme' }}">
                        {{ tilt_status }}
                    </span>
                </div>
                <div class="stat-item"><strong>Evaluation:</strong> {{ tilt_avaliacao }}</div>
            </div>
        </div>
    </div>
    {% endif %}

    {% if mostrar_vib %}
    <div class="section">
        <div class="section-title">📳 VIBRATION STATISTICS ({{ unidade_display }})</div>
        <div class="stats-grid">
            <div>
                <div class="stat-item"><strong>Average:</strong> {{ vib_media }}{{ unidade_display }}</div>
                <div class="stat-item"><strong>Maximum:</strong> {{ vib_max }}{{ unidade_display }}</div>
                <div class="stat-item"><strong>Minimum:</strong> {{ vib_min }}{{ unidade_display }}</div>
            </div>
            <div>
                <div class="stat-item"><strong>Standard Deviation:</strong> {{ vib_std }}{{ unidade_display }}</div>
                <div class="stat-item"><strong>Standard Limit:</strong> {{ limite_vib }}{{ unidade_display }}</div>
                <div class="stat-item"><strong>Status:</strong> 
                    <span class="{{ 'status-conforme' if vib_status == 'COMPLIANT' else 'status-nao-conforme' }}">
                        {{ vib_status }}
                    </span>
                </div>
                <div class="stat-item"><strong>Evaluation:</strong> {{ vib_avaliacao }}</div>
            </div>
        </div>
        {% if unidade_display == 'm/s²' %}
        <p style="font-size: 12px; color: #666; margin-top: 10px;">
            * Values converted from g to m/s² according to NBR ISO 2631-1
        </p>
        {% endif %}
    </div>
    {% endif %}

    {% if graficos %}
    <div class="section">
        <div class="section-title">📊 COMPLETE GRAPHS OVER TIME</div>
        {% for grafico in graficos %}
        <div class="chart-container">
            <img src="{{ grafico.src }}" alt="{{ grafico.alt }}" />
            <p>{{ grafico.titulo }}</p>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    {% if video_data %}
    <div class="video-section">
        <div class="section-title" style="color: #FF8800;">🎥 RECORDING OF GRAPHS</div>
        <p><strong>File:</strong> {{ video_filename }}</p>
        <p><strong>Captured Frames:</strong> {{ frames_capturados }}</p>
        <p><strong>Duration:</strong> {{ duracao_video }} seconds</p>
        <p><strong>Size:</strong> {{ video_size_mb }} MB</p>
        
        <div class="video-container">
            {% if video_base64 %}
            <!-- Video embedded directly as base64 -->
            <video controls preload="metadata" style="width: 100%; max-width: 640px;">
                <source src="data:video/mp4;base64,{{ video_base64 }}" type="video/mp4">
                <p style="color: #ff6666;">Your EPUB reader does not support HTML5 videos.</p>
            </video>
            <div class="video-info">
                ✅ Video embedded directly in EPUB (base64)
            </div>
            {% else %}
            <!-- Video as attached file -->
            <video controls preload="metadata" style="width: 100%; max-width: 640px;">
                <source src="{{ video_src }}" type="video/mp4">
                <div class="video-fallback">
                    <p style="color: #ff6666;">❌ Could not load video</p>
                    <p>The video is attached to the EPUB as a separate file.</p>
                    <p>Try to extract the file "{{ video_filename }}" from the EPUB.</p>
                </div>
            </video>
            <div class="video-info">
                📎 Video attached as separate file
            </div>
            {% endif %}
        </div>
        
        <div class="compatibility-note">
            <strong>💡 Compatibility Tip:</strong><br>
            • <strong>Calibre:</strong> Supports HTML5 videos ✅<br>
            • <strong>Adobe Digital Editions:</strong> Limited support ⚠️<br>
            • <strong>Apple Books:</strong> Supports videos ✅<br>
            • <strong>Google Play Books:</strong> Limited support ⚠️<br>
            <br>
            If the video does not play, the original file is saved at: <strong>{{ video_filename }}</strong>
        </div>
    </div>
    {% endif %}

    <div class="footer">
        <p><strong>Generated by Riggy - UDP SensaGram</strong></p>
        <p>Report generated on {{ data_hora }}</p>
    </div>
</body>
</html>
"""

# === EPUB REPORT GENERATION ===
def gerar_relatorio_epub():
    global video_filename, recording_start, recording_end, ESTRUTURA_ATUAL, UNIDADE_VIB_ATUAL
    
    # Disable button and show loading
    btn_report_epub.configure(state='disabled', text='Generating EPUB...')
    app.update()

    finalizar_gravacao()

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    epub_filename = f"epub_report_{now}.epub"

    # Calculate statistics
    tilt_list = [v for v in tilts_all if not math.isnan(v)] if grafico_tilt_var.get() else []
    vib_list = [v for v in vibracoes_all if not math.isnan(v)] if grafico_vib_var.get() else []
    
    tilt_media = sum(tilt_list) / len(tilt_list) if tilt_list else 0
    vib_media = sum(vib_list) / len(vib_list) if vib_list else 0
    tilt_max = max(tilt_list) if tilt_list else 0
    tilt_min = min(tilt_list) if tilt_list else 0
    vib_max = max(vib_list) if vib_list else 0
    vib_min = min(vib_list) if vib_list else 0
    tilt_std = statistics.stdev(tilt_list) if len(tilt_list) > 1 else 0
    vib_std = statistics.stdev(vib_list) if len(vib_list) > 1 else 0

    # Convert vibration stats to standard unit if necessary
    if UNIDADE_VIB_ATUAL == 'm/s²':
        vib_media_norma = g_para_ms2(vib_media)
        vib_max_norma = g_para_ms2(vib_max)
        vib_min_norma = g_para_ms2(vib_min)
        vib_std_norma = g_para_ms2(vib_std)
        unidade_display = 'm/s²'
    else:
        vib_media_norma = vib_media
        vib_max_norma = vib_max
        vib_min_norma = vib_min
        vib_std_norma = vib_std
        unidade_display = 'g'

    duracao_real = (recording_end - recording_start).total_seconds() if recording_start and recording_end else len(frames_buffer)/10

    # Prepare template data
    norma_info = estruturas_normas.get(ESTRUTURA_ATUAL, estruturas_normas['Custom'])
    
    # Compliance status
    tilt_status = "COMPLIANT" if tilt_max < TILT_THRESHOLD else "NON-COMPLIANT"
    vib_max_comparacao = vib_max if UNIDADE_VIB_ATUAL == 'g' else g_para_ms2(vib_max)
    vib_status = "COMPLIANT" if vib_max_comparacao < VIB_THRESHOLD else "NON-COMPLIANT"
    
    # Technical evaluations
    if tilt_max < TILT_THRESHOLD * 0.5:
        tilt_avaliacao = "EXCELLENT"
    elif tilt_max < TILT_THRESHOLD * 0.8:
        tilt_avaliacao = "GOOD"
    elif tilt_max < TILT_THRESHOLD:
        tilt_avaliacao = "ACCEPTABLE"
    else:
        tilt_avaliacao = "CRITICAL"
    
    if vib_max_comparacao < VIB_THRESHOLD * 0.5:
        vib_avaliacao = "EXCELLENT"
    elif vib_max_comparacao < VIB_THRESHOLD * 0.8:
        vib_avaliacao = "GOOD"
    elif vib_max_comparacao < VIB_THRESHOLD:
        vib_avaliacao = "ACCEPTABLE"
    else:
        vib_avaliacao = "CRITICAL"

    # Generate graphs for EPUB
    graficos_info = []
    graficos_paths = salvar_graficos_completos_para_epub(tilts_all, vibracoes_all, grafico_tilt_var.get(), grafico_vib_var.get())
    
    for i, path in enumerate(graficos_paths):
        if 'tilt' in path:
            graficos_info.append({
                'src': f'images/grafico_tilt_{i}.png',
                'alt': 'Tilt Graph over Time',
                'titulo': 'Tilt (°) over Time',
                'path': path
            })
        else:
            graficos_info.append({
                'src': f'images/grafico_vib_{i}.png',
                'alt': 'Vibration Graph over Time',
                'titulo': f'Vibration ({unidade_display}) over Time',
                'path': path
            })

    # === VIDEO LOGIC ===
    video_base64 = None
    video_size_mb = 0
    if video_filename and os.path.isfile(video_filename):
        try:
            # Convert video to H.264
            video_h264_filename = f"video_h264_{now}.mp4"
            converter_video_para_h264(video_filename, video_h264_filename)
            
            # Read converted video
            with open(video_h264_filename, 'rb') as video_file:
                video_data = video_file.read()
                video_size_mb = len(video_data) / (1024 * 1024)
                
                # If under 10MB, convert to base64
                if video_size_mb < 10:
                    video_base64 = base64.b64encode(video_data).decode('utf-8')
                    print(f"✅ Video converted to base64: {video_size_mb:.2f} MB")
                else:
                    print(f"⚠️ Video too large ({video_size_mb:.2f} MB), will be attached as file")
            
            # Remove temp H.264 video
            if os.path.exists(video_h264_filename):
                os.remove(video_h264_filename)
                
        except Exception as e:
            print(f"Error processing video: {e}")
            try:
                with open(video_filename, 'rb') as video_file:
                    video_data = video_file.read()
                    video_size_mb = len(video_data) / (1024 * 1024)
            except:
                video_data = None

    # Template data
    template_data = {
        'titulo': 'Riggy Report - UDP SensaGram',
        'estrutura_atual': ESTRUTURA_ATUAL,
        'norma_info': norma_info,
        'limite_tilt': f"{TILT_THRESHOLD:.1f}",
        'limite_vib': f"{VIB_THRESHOLD:.2f}",
        'unidade_display': unidade_display,
        'data_hora': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        'pontos_coletados': len(tempo),
        'duracao_teste': f"{duracao_real:.1f}",
        'alertas_tilt': sum(1 for a in alerts if a[0]=='tilt') if grafico_tilt_var.get() else 0,
        'alertas_vib': sum(1 for a in alerts if a[0]=='vibration') if grafico_vib_var.get() else 0,
        'mostrar_tilt': grafico_tilt_var.get(),
        'mostrar_vib': grafico_vib_var.get(),
        'tilt_media': f"{tilt_media:.2f}",
        'tilt_max': f"{tilt_max:.2f}",
        'tilt_min': f"{tilt_min:.2f}",
        'tilt_std': f"{tilt_std:.2f}",
        'tilt_status': tilt_status,
        'tilt_avaliacao': tilt_avaliacao,
        'vib_media': f"{vib_media_norma:.3f}",
        'vib_max': f"{vib_max_norma:.3f}",
        'vib_min': f"{vib_min_norma:.3f}",
        'vib_std': f"{vib_std_norma:.3f}",
        'vib_status': vib_status,
        'vib_avaliacao': vib_avaliacao,
        'graficos': graficos_info,
        'video_data': video_filename and os.path.isfile(video_filename),
        'video_filename': os.path.basename(video_filename) if video_filename else '',
        'frames_capturados': len(frames_buffer),
        'duracao_video': f"{duracao_real:.1f}",
        'video_src': 'video/gravacao.mp4' if video_filename else '',
        'video_base64': video_base64,
        'video_size_mb': f"{video_size_mb:.2f}"
    }

    # Create EPUB
    try:
        book = epub.EpubBook()
        
        # Metadata
        book.set_identifier('riggy-report-' + now)
        book.set_title('Riggy Report - UDP SensaGram')
        book.set_language('en-US')
        book.add_author('Riggy - UDP SensaGram')
        book.add_metadata('DC', 'description', 'Structural sensor monitoring report')

        # Render HTML template
        template = Template(EPUB_TEMPLATE)
        html_content = template.render(**template_data)
        
        # Create main chapter
        chapter = epub.EpubHtml(title='Monitoring Report', 
                               file_name='report.xhtml', 
                               lang='en-US')
        chapter.content = html_content
        book.add_item(chapter)

        # Add graph images
        for grafico in graficos_info:
            if os.path.exists(grafico['path']):
                with open(grafico['path'], 'rb') as img_file:
                    img_data = img_file.read()
                
                img_item = epub.EpubItem(
                    uid=f"img_{grafico['src'].split('/')[-1]}",
                    file_name=grafico['src'],
                    media_type="image/png",
                    content=img_data
                )
                book.add_item(img_item)

        # Add video if not base64
        if video_filename and os.path.isfile(video_filename) and not video_base64:
            try:
                with open(video_filename, 'rb') as video_file:
                    video_data = video_file.read()
                
                video_item = epub.EpubItem(
                    uid="video_gravacao",
                    file_name="video/gravacao.mp4",
                    media_type="video/mp4",
                    content=video_data
                )
                book.add_item(video_item)
                print(f"✅ Video attached to EPUB: {len(video_data)} bytes")
            except Exception as e:
                print(f"Error attaching video to EPUB: {e}")

        # Define reading order
        book.toc = [chapter]
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Define spine
        book.spine = ['nav', chapter]

        # Write EPUB
        epub.write_epub(epub_filename, book, {})
        
        # Remove temp graph files
        for path in graficos_paths:
            try:
                os.remove(path)
            except Exception as e:
                print(f"Error removing temp file {path}: {e}")

        print(f"✅ EPUB Report generated: {epub_filename}")
        if video_base64:
            print(f"✅ Video embedded as base64 in HTML")
        elif video_filename and os.path.isfile(video_filename):
            print(f"✅ Video attached as a separate file")
        
        # Try to open file
        try:
            os.startfile(epub_filename)
        except:
            print(f"File saved at: {os.path.abspath(epub_filename)}")

    except Exception as e:
        print(f"Error generating EPUB: {e}")
        import traceback
        traceback.print_exc()
    
    # Stop animation and restore button
    global loading_timer_epub
    if loading_timer_epub:
        app.after_cancel(loading_timer_epub)
    btn_report_epub.configure(state='normal', text='Generate EPUB')
    app.update()

def converter_video_para_h264(input_file, output_file):
    """Converts video to H.264 using OpenCV for better compatibility"""
    try:
        cap = cv2.VideoCapture(input_file)
        
        # Original video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # H.264 codec (more compatible)
        fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264
        out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
        
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            out.write(frame)
            frame_count += 1
        
        cap.release()
        out.release()
        
        print(f"✅ Video converted to H.264: {frame_count} frames")
        return True
        
    except Exception as e:
        print(f"Error converting to H.264: {e}")
        return False

# === PDF REPORT GENERATION ===
def gerar_relatorio_pdf():
    global video_filename, recording_start, recording_end, ESTRUTURA_ATUAL, UNIDADE_VIB_ATUAL
    
    # Disable button and show loading
    btn_report_pdf.configure(state='disabled', text='Generating PDF...')
    app.update()

    finalizar_gravacao()

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"pdf_report_{now}.pdf"

    # Statistics
    tilt_list = [v for v in tilts_all if not math.isnan(v)] if grafico_tilt_var.get() else []
    vib_list = [v for v in vibracoes_all if not math.isnan(v)] if grafico_vib_var.get() else []
    tilt_media = sum(tilt_list) / len(tilt_list) if tilt_list else 0
    vib_media = sum(vib_list) / len(vib_list) if vib_list else 0
    tilt_max = max(tilt_list) if tilt_list else 0
    tilt_min = min(tilt_list) if tilt_list else 0
    vib_max = max(vib_list) if vib_list else 0
    vib_min = min(vib_list) if vib_list else 0
    tilt_std = statistics.stdev(tilt_list) if len(tilt_list) > 1 else 0
    vib_std = statistics.stdev(vib_list) if len(vib_list) > 1 else 0

    # Convert vibration stats if necessary
    if UNIDADE_VIB_ATUAL == 'm/s²':
        vib_media_norma = g_para_ms2(vib_media)
        vib_max_norma = g_para_ms2(vib_max)
        vib_min_norma = g_para_ms2(vib_min)
        vib_std_norma = g_para_ms2(vib_std)
        unidade_display = 'm/s²'
    else:
        vib_media_norma = vib_media
        vib_max_norma = vib_max
        vib_min_norma = vib_min
        vib_std_norma = vib_std
        unidade_display = 'g'

    duracao_real = (recording_end - recording_start).total_seconds() if recording_start and recording_end else len(frames_buffer)/10

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    color_orange = (1, 0.5, 0)
    color_black = (0, 0, 0)
    color_gray = (0.3, 0.3, 0.3)
    color_light_gray = (0.9, 0.9, 0.9)
    color_blue = (0, 0.4, 0.8)

    y_pos = 800
    desenhou_estatisticas = False

    # Header
    logo_path = os.path.join(os.path.dirname(__file__), 'riggy-logo.jpeg')
    if os.path.isfile(logo_path):
        try:
            logo_rect = fitz.Rect(50, y_pos-60, 110, y_pos)
            page.insert_image(logo_rect, filename=logo_path)
        except:
            pass

    page.insert_text((130, y_pos-20), "RIGGY REPORT", fontsize=20, color=color_orange)
    page.insert_text((130, y_pos-40), "UDP SensaGram - Sensor Monitoring", fontsize=12, color=color_gray)
    page.draw_line(fitz.Point(50, y_pos-70), fitz.Point(545, y_pos-70), color=color_orange, width=2)
    y_pos -= 90

    # === TECHNICAL STANDARD SECTION ===
    norma_info = estruturas_normas.get(ESTRUTURA_ATUAL, estruturas_normas['Custom'])
    norma_rect = fitz.Rect(50, y_pos-100, 545, y_pos)
    page.draw_rect(norma_rect, color=(0.95, 0.95, 1.0), fill=(0.95, 0.95, 1.0))
    page.draw_rect(norma_rect, color=color_blue, width=2)
    page.insert_text((60, y_pos-15), "📋 APPLIED TECHNICAL STANDARD", fontsize=12, color=color_blue)
    page.insert_text((60, y_pos-35), f"Evaluated Structure: {ESTRUTURA_ATUAL}", fontsize=11, color=color_black)
    page.insert_text((60, y_pos-50), f"Applied Standard: {norma_info['norma']}", fontsize=11, color=color_black)
    page.insert_text((60, y_pos-65), f"Description: {norma_info['descricao']}", fontsize=9, color=color_gray)
    
    # Standard limits
    limite_tilt_display = TILT_THRESHOLD
    limite_vib_display = VIB_THRESHOLD
    page.insert_text((60, y_pos-80), f"Limits: Tilt ≤ {limite_tilt_display:.1f}° | Vibration ≤ {limite_vib_display:.2f} {unidade_display}", fontsize=10, color=color_black)
    y_pos -= 120

    # General info
    info_rect = fitz.Rect(50, y_pos-80, 545, y_pos)
    page.draw_rect(info_rect, color=color_light_gray, fill=color_light_gray)
    page.draw_rect(info_rect, color=color_gray, width=1)
    page.insert_text((60, y_pos-15), "GENERAL INFORMATION", fontsize=12, color=color_orange)
    page.insert_text((60, y_pos-35), f"Date and Time: {datetime.now():%d/%m/%Y %H:%M:%S}", fontsize=11, color=color_black)
    page.insert_text((60, y_pos-50), f"Collected Points: {len(tempo)}", fontsize=11, color=color_black)
    page.insert_text((300, y_pos-35), f"Tilt Alerts: {sum(1 for a in alerts if a[0]=='tilt') if grafico_tilt_var.get() else 0}", fontsize=11, color=color_black)
    page.insert_text((300, y_pos-50), f"Vibration Alerts: {sum(1 for a in alerts if a[0]=='vibration') if grafico_vib_var.get() else 0}", fontsize=11, color=color_black)
    page.insert_text((60, y_pos-65), f"Test Duration: {duracao_real:.1f} seconds", fontsize=11, color=color_black)
    y_pos -= 100

    # Tilt statistics
    if grafico_tilt_var.get():
        desenhou_estatisticas = True
        tilt_rect = fitz.Rect(50, y_pos-140, 545, y_pos)
        page.draw_rect(tilt_rect, color=color_light_gray, fill=color_light_gray)
        page.draw_rect(tilt_rect, color=color_gray, width=1)
        page.insert_text((60, y_pos-15), "📐 TILT STATISTICS (°)", fontsize=12, color=color_orange)
        page.insert_text((60, y_pos-35), f"Average: {tilt_media:.2f}°", fontsize=11, color=color_black)
        page.insert_text((60, y_pos-50), f"Maximum: {tilt_max:.2f}°", fontsize=11, color=color_black)
        page.insert_text((60, y_pos-65), f"Minimum: {tilt_min:.2f}°", fontsize=11, color=color_black)
        page.insert_text((300, y_pos-35), f"Standard Deviation: {tilt_std:.2f}°", fontsize=11, color=color_black)
        page.insert_text((300, y_pos-50), f"Standard Limit: {TILT_THRESHOLD:.1f}°", fontsize=11, color=color_black)
        
        # Compliance status
        status_tilt = "COMPLIANT" if tilt_max < TILT_THRESHOLD else "NON-COMPLIANT"
        color_status = (0, 0.7, 0) if tilt_max < TILT_THRESHOLD else (0.8, 0, 0)
        page.insert_text((300, y_pos-65), f"Status: {status_tilt}", fontsize=11, color=color_status)
        
        # Technical evaluation
        if tilt_max < TILT_THRESHOLD * 0.5:
            avaliacao = "EXCELLENT"
        elif tilt_max < TILT_THRESHOLD * 0.8:
            avaliacao = "GOOD"
        elif tilt_max < TILT_THRESHOLD:
            avaliacao = "ACCEPTABLE"
        else:
            avaliacao = "CRITICAL"
        page.insert_text((300, y_pos-80), f"Evaluation: {avaliacao}", fontsize=10, color=color_gray)
        y_pos -= 160

    # Vibration statistics
    if grafico_vib_var.get():
        desenhou_estatisticas = True
        vib_rect = fitz.Rect(50, y_pos-140, 545, y_pos)
        page.draw_rect(vib_rect, color=color_light_gray, fill=color_light_gray)
        page.draw_rect(vib_rect, color=color_gray, width=1)
        page.insert_text((60, y_pos-15), f"📳 VIBRATION STATISTICS ({unidade_display})", fontsize=12, color=color_orange)
        page.insert_text((60, y_pos-35), f"Average: {vib_media_norma:.3f}{unidade_display}", fontsize=11, color=color_black)
        page.insert_text((60, y_pos-50), f"Maximum: {vib_max_norma:.3f}{unidade_display}", fontsize=11, color=color_black)
        page.insert_text((60, y_pos-65), f"Minimum: {vib_min_norma:.3f}{unidade_display}", fontsize=11, color=color_black)
        page.insert_text((300, y_pos-35), f"Standard Deviation: {vib_std_norma:.3f}{unidade_display}", fontsize=11, color=color_black)
        
        limite_vib_display_norma = VIB_THRESHOLD
        page.insert_text((300, y_pos-50), f"Standard Limit: {limite_vib_display_norma:.2f}{unidade_display}", fontsize=11, color=color_black)
        
        # Compliance status
        vib_max_comparacao = vib_max if UNIDADE_VIB_ATUAL == 'g' else g_para_ms2(vib_max)
        limite_comparacao = VIB_THRESHOLD
        status_vib = "COMPLIANT" if vib_max_comparacao < limite_comparacao else "NON-COMPLIANT"
        color_status = (0, 0.7, 0) if vib_max_comparacao < limite_comparacao else (0.8, 0, 0)
        page.insert_text((300, y_pos-65), f"Status: {status_vib}", fontsize=11, color=color_status)
        
        # Technical evaluation
        if vib_max_comparacao < limite_comparacao * 0.5:
            avaliacao = "EXCELLENT"
        elif vib_max_comparacao < limite_comparacao * 0.8:
            avaliacao = "GOOD"
        elif vib_max_comparacao < limite_comparacao:
            avaliacao = "ACCEPTABLE"
        else:
            avaliacao = "CRITICAL"
        page.insert_text((300, y_pos-80), f"Evaluation: {avaliacao}", fontsize=10, color=color_gray)
        
        # Unit conversion note
        if UNIDADE_VIB_ATUAL == 'm/s²':
            page.insert_text((60, y_pos-95), "* Values converted from g to m/s² according to NBR ISO 2631-1", fontsize=8, color=color_gray)
        y_pos -= 160

    # If no statistics were drawn, correct y_pos
    if not desenhou_estatisticas:
        y_pos -= 40

    # Video section
    if video_filename and os.path.isfile(video_filename):
        video_rect = fitz.Rect(50, y_pos-100, 545, y_pos)
        page.draw_rect(video_rect, color=(0.1, 0.1, 0.1), fill=(0.1, 0.1, 0.1))
        page.draw_rect(video_rect, color=color_orange, width=2)
        page.insert_text((60, y_pos-15), "🎥 RECORDING OF GRAPHS", fontsize=12, color=color_orange)
        page.insert_text((60, y_pos-35), f"File: {video_filename}", fontsize=11, color=(1, 1, 1))
        page.insert_text((60, y_pos-50), f"Captured Frames: {len(frames_buffer)}", fontsize=11, color=(1, 1, 1))
        page.insert_text((60, y_pos-65), f"Approximate Duration: {duracao_real:.1f} seconds", fontsize=11, color=(1, 1, 1))
        try:
            with open(video_filename, 'rb') as video_file:
                video_bytes = video_file.read()
            doc.embfile_add(video_filename, video_bytes, filename=os.path.basename(video_filename))
            page.insert_text((400, y_pos-35), "📎 VIDEO ATTACHED", fontsize=12, color=color_orange)
            page.insert_text((400, y_pos-50), "Click on attachment icon", fontsize=10, color=(0.8, 0.8, 0.8))
            page.insert_text((400, y_pos-65), "in your PDF reader", fontsize=10, color=(0.8, 0.8, 0.8))
        except Exception as e:
            print(f"Error attaching video: {e}")
            page.insert_text((400, y_pos-35), "❌ ATTACHMENT ERROR", fontsize=12, color=(0.8, 0, 0))
            page.insert_text((400, y_pos-50), "Video saved separately", fontsize=10, color=(0.8, 0.8, 0.8))
        y_pos -= 30

    # Footer
    page.draw_line(fitz.Point(50, 80), fitz.Point(545, 80), color=color_orange, width=1)
    page.insert_text((50, 60), "Generated by Riggy - UDP SensaGram", fontsize=10, color=color_gray)
    page.insert_text((50, 45), f"Report generated on {datetime.now():%d/%m/%Y at %H:%M:%S}", fontsize=9, color=color_gray)
    page.insert_text((400, 60), f"Page 1 of 1", fontsize=10, color=color_gray)

    # Insert complete graphs on new page
    graficos_paths = salvar_graficos_completos_para_pdf(tilts_all, vibracoes_all, grafico_tilt_var.get(), grafico_vib_var.get())
    if graficos_paths:
        page_graficos = doc.new_page(width=595, height=842)
        y_graf = 800
        page_graficos.insert_text((60, y_graf-20), "COMPLETE GRAPHS OVER TIME", fontsize=16, color=color_orange)
        y_graf -= 40
        for path in graficos_paths:
            try:
                img = fitz.Pixmap(path)
                img_width = 400
                img_height = int(img.height * (img_width / img.width))
                img_rect = fitz.Rect((595-img_width)//2, y_graf-img_height, (595+img_width)//2, y_graf)
                page_graficos.insert_image(img_rect, filename=path)
                y_graf -= (img_height + 20)
            except Exception as e:
                print(f"Error inserting graph in PDF: {e}")

    doc.save(pdf_filename)
    doc.close()

    # Remove temporary graph files
    for path in graficos_paths:
        try:
            os.remove(path)
        except Exception as e:
            print(f"Error removing temporary file {path}: {e}")

    try:
        os.startfile(pdf_filename)
    except:
        pass

    print(f"PDF Report generated: {pdf_filename}")
    if video_filename and os.path.isfile(video_filename):
        print(f"Video attached to PDF: {video_filename}")
    
    # Stop animation and restore button
    global loading_timer_pdf
    if loading_timer_pdf:
        app.after_cancel(loading_timer_pdf)
    btn_report_pdf.configure(state='normal', text='Generate PDF')
    app.update()

def salvar_graficos_completos_para_epub(tilts_all, vibracoes_all, show_tilt, show_vib):
    """Saves graphs as PNG images for the EPUB"""
    global UNIDADE_VIB_ATUAL
    paths = []
    
    if show_tilt and tilts_all:
        fig_tilt, ax_tilt = plt.subplots(figsize=(8, 4))
        ax_tilt.plot(list(range(len(tilts_all))), tilts_all, color='#FF8800', linewidth=2)
        ax_tilt.set_ylim(0, 100)
        ax_tilt.set_title('Tilt (°) over time', fontsize=14, fontweight='bold')
        ax_tilt.set_ylabel('Degrees')
        ax_tilt.set_xlabel('Time (samples)')
        ax_tilt.grid(True, alpha=0.3)
        fig_tilt.tight_layout()
        tilt_path = f"tilt_grafico_epub_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        fig_tilt.savefig(tilt_path, dpi=150, bbox_inches='tight')
        plt.close(fig_tilt)
        paths.append(tilt_path)
    
    if show_vib and vibracoes_all:
        fig_vib, ax_vib = plt.subplots(figsize=(8, 4))
        
        # Convert data to correct unit if necessary
        vib_data = vibracoes_all
        unidade_display = 'g'
        if UNIDADE_VIB_ATUAL == 'm/s²':
            vib_data = [g_para_ms2(v) for v in vibracoes_all]
            unidade_display = 'm/s²'
            
        ax_vib.plot(list(range(len(vib_data))), vib_data, color='#FFB266', linewidth=2)
        
        # Adjust scale based on unit
        if UNIDADE_VIB_ATUAL == 'm/s²':
            ax_vib.set_ylim(0, 50)
        else:
            ax_vib.set_ylim(0, 5)
            
        ax_vib.set_title(f'Vibration ({unidade_display}) over time', fontsize=14, fontweight='bold')
        ax_vib.set_ylabel(unidade_display)
        ax_vib.set_xlabel('Time (samples)')
        ax_vib.grid(True, alpha=0.3)
        fig_vib.tight_layout()
        vib_path = f"vib_grafico_epub_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        fig_vib.savefig(vib_path, dpi=150, bbox_inches='tight')
        plt.close(fig_vib)
        paths.append(vib_path)
    
    return paths

def salvar_graficos_completos_para_pdf(tilts_all, vibracoes_all, show_tilt, show_vib):
    """Saves graphs as PNG images for the PDF"""
    global UNIDADE_VIB_ATUAL
    paths = []
    
    if show_tilt and tilts_all:
        fig_tilt, ax_tilt = plt.subplots(figsize=(6, 3))
        ax_tilt.plot(list(range(len(tilts_all))), tilts_all, color='#FF8800', linewidth=2)
        ax_tilt.set_ylim(0, 100)
        ax_tilt.set_title('Tilt (°) over time', fontsize=12, fontweight='bold')
        ax_tilt.set_ylabel('Degrees')
        ax_tilt.set_xlabel('Time (samples)')
        fig_tilt.tight_layout()
        tilt_path = f"tilt_grafico_pdf_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        fig_tilt.savefig(tilt_path)
        plt.close(fig_tilt)
        paths.append(tilt_path)
    
    if show_vib and vibracoes_all:
        fig_vib, ax_vib = plt.subplots(figsize=(6, 3))
        
        # Convert data to correct unit if necessary
        vib_data = vibracoes_all
        unidade_display = 'g'
        if UNIDADE_VIB_ATUAL == 'm/s²':
            vib_data = [g_para_ms2(v) for v in vibracoes_all]
            unidade_display = 'm/s²'
            
        ax_vib.plot(list(range(len(vib_data))), vib_data, color='#FFB266', linewidth=2)
        
        # Adjust scale based on unit
        if UNIDADE_VIB_ATUAL == 'm/s²':
            ax_vib.set_ylim(0, 50)
        else:
            ax_vib.set_ylim(0, 5)
            
        ax_vib.set_title(f'Vibration ({unidade_display}) over time', fontsize=12, fontweight='bold')
        ax_vib.set_ylabel(unidade_display)
        ax_vib.set_xlabel('Time (samples)')
        fig_vib.tight_layout()
        vib_path = f"vib_grafico_pdf_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        fig_vib.savefig(vib_path)
        plt.close(fig_vib)
        paths.append(vib_path)
    
    return paths

def animar_loading_epub():
    """Animates the loading text with dots for EPUB"""
    global loading_dots, loading_timer_epub
    loading_dots = (loading_dots + 1) % 4
    dots = "." * loading_dots
    btn_report_epub.configure(text=f'Generating EPUB{dots}')
    
    if btn_report_epub.cget('state') == 'disabled':
        loading_timer_epub = app.after(500, animar_loading_epub)

def animar_loading_pdf():
    """Animates the loading text with dots for PDF"""
    global loading_dots, loading_timer_pdf
    loading_dots = (loading_dots + 1) % 4
    dots = "." * loading_dots
    btn_report_pdf.configure(text=f'Generating PDF{dots}')
    
    if btn_report_pdf.cget('state') == 'disabled':
        loading_timer_pdf = app.after(500, animar_loading_pdf)

def gerar_relatorio_epub_com_loading():
    """Wrapper to generate EPUB report with error handling"""
    global loading_timer_epub
    
    # Start loading animation
    loading_dots = 0
    animar_loading_epub()
    
    try:
        gerar_relatorio_epub()
    except Exception as e:
        print(f"Error generating EPUB report: {e}")
        if loading_timer_epub:
            app.after_cancel(loading_timer_epub)
        btn_report_epub.configure(state='normal', text='Generate EPUB')
        app.update()

def gerar_relatorio_pdf_com_loading():
    """Wrapper to generate PDF report with error handling"""
    global loading_timer_pdf
    
    # Start loading animation
    loading_dots = 0
    animar_loading_pdf()
    
    try:
        gerar_relatorio_pdf()
    except Exception as e:
        print(f"Error generating PDF report: {e}")
        if loading_timer_pdf:
            app.after_cancel(loading_timer_pdf)
        btn_report_pdf.configure(state='normal', text='Generate PDF')
        app.update()

# === UDP THREAD ===
def processar_dados_thread():
    """Separate thread for processing UDP data"""
    global t, running, gravity, tilt_alerted, vib_alerted
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORTA_UDP))
    sock.settimeout(TIMEOUT)
    
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Gravity calibration
    for _ in range(WINDOW_SIZE):
        if not running: return
        try:
            data, _ = sock.recvfrom(BUFFER_SIZE)
            obj = json.loads(data.decode())
            if 'accelerometer' in obj.get('type',''):
                ax, ay, az = obj.get('values')[:3]
                gravity[0] = LP_ALPHA*gravity[0] + (1-LP_ALPHA)*ax
                gravity[1] = LP_ALPHA*gravity[1] + (1-LP_ALPHA)*ay
                gravity[2] = LP_ALPHA*gravity[2] + (1-LP_ALPHA)*az
        except:
            pass

    while running:
        try:
            data, _ = sock.recvfrom(BUFFER_SIZE)
            obj = json.loads(data.decode())
        except:
            continue

        if 'accelerometer' not in obj.get('type',''):
            continue

        ax, ay, az = obj.get('values')[:3]

        # Gravity filter
        gravity[0] = LP_ALPHA*gravity[0] + (1-LP_ALPHA)*ax
        gravity[1] = LP_ALPHA*gravity[1] + (1-LP_ALPHA)*ay
        gravity[2] = LP_ALPHA*gravity[2] + (1-LP_ALPHA)*az
        gx, gy, gz = gravity

        # Tilt
        mag = math.sqrt(gx*gx + gy*gy + gz*gz)
        cos_t = gz/mag if mag else 1
        cos_t = max(-1.0, min(1.0, cos_t))
        tilt_angle = math.degrees(math.acos(cos_t))
        tilts.append(tilt_angle)
        tilts_all.append(tilt_angle)

        # Vibration - kept in g for internal processing
        total_acc = math.sqrt(ax*ax + ay*ay + az*az)
        vib = abs(total_acc - 9.81)
        vibracoes.append(vib)
        vibracoes_all.append(vib)
        avg_vib = sum(vibracoes) / len(vibracoes) if vibracoes else 0

        tempo.append(t)
        t += 1

        # Tilt Alert
        if grafico_tilt_var.get():
            avg_tilt = sum(tilts) / len(tilts) if tilts else 0
            if avg_tilt >= TILT_THRESHOLD and not tilt_alerted:
                alerts.append(('tilt', datetime.now(), avg_tilt))
                tocar_alerta('alerta_inclinacao.mp3')
                tilt_alerted = True
            if avg_tilt < TILT_THRESHOLD - 20:
                tilt_alerted = False

        # Vibration Alert - compare in correct unit
        if grafico_vib_var.get():
            if UNIDADE_VIB_ATUAL == 'm/s²':
                avg_vib_comparacao = g_para_ms2(avg_vib)
            else:
                avg_vib_comparacao = avg_vib
                
            if avg_vib_comparacao >= VIB_THRESHOLD and not vib_alerted:
                alerts.append(('vibration', datetime.now(), avg_vib_comparacao))
                tocar_alerta('alerta_vibracao.mp3')
                vib_alerted = True
            if avg_vib_comparacao < VIB_THRESHOLD - (0.3 if UNIDADE_VIB_ATUAL == 'g' else 3.0):
                vib_alerted = False

# === USER INTERFACE ===
ctk.set_appearance_mode('dark')
ctk.set_default_color_theme('dark-blue')

# Custom colors
COR_LARANJA = '#FF8800'  # Orange
COR_PRETO = '#181818'   # Black
COR_CINZA = '#232323'   # Gray
COR_TEXTO = '#FFFFFF'   # White

app = ctk.CTk()
app.title('Riggy - UDP SensaGram (EPUB + PDF)')
app.geometry('900x750')
app.configure(bg=COR_PRETO)

ico_path = resource_path('riggy-logo.ico')
if os.path.isfile(ico_path):
    try:
        app.iconbitmap(ico_path)
    except Exception as e:
        print(f"Error loading icon: {e}")

# Set window icon
ico_path = os.path.join(os.path.dirname(__file__), 'riggy-logo.ico')
if os.path.isfile(ico_path):
    try:
        app.iconbitmap(ico_path)
    except Exception:
        pass

app.protocol("WM_DELETE_WINDOW", fechar_janela)

# Function to get local IP
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip
    except Exception:
        return '127.0.0.1'

def get_wifi_ssid():
    if os.name == 'nt':  # Windows
        try:
            output = subprocess.check_output(['netsh', 'wlan', 'show', 'interfaces'], encoding='utf-8', errors='ignore')
            for line in output.split('\n'):
                if 'SSID' in line and 'BSSID' not in line:
                    ssid = line.split(':', 1)[1].strip()
                    if ssid and ssid.lower() != 'ssid':
                        return ssid
        except Exception:
            pass
    return 'N/A'

# === MAIN LAYOUT ===
frame_titulo = ctk.CTkFrame(app, fg_color='transparent')
frame_titulo.pack(fill='x', pady=(10, 0))
label_titulo = ctk.CTkLabel(frame_titulo, text='Riggy', font=('Segoe UI', 24, 'bold'), text_color=COR_LARANJA)
label_titulo.pack(anchor='center')

local_ip = get_local_ip()
wifi_ssid = get_wifi_ssid()
label_ip = ctk.CTkLabel(frame_titulo, text=f'ip: {local_ip}  port: {PORTA_UDP}  wifi: {wifi_ssid}', font=('Segoe UI', 14), text_color=COR_TEXTO)
label_ip.pack(anchor='center', pady=(2, 0))

frame_principal = ctk.CTkFrame(app, fg_color='transparent')
frame_principal.pack(fill='both', expand=True, padx=20, pady=10)

frame_esquerdo = ctk.CTkFrame(frame_principal, fg_color=COR_CINZA, corner_radius=16, width=320)
frame_esquerdo.pack(side='left', fill='y', padx=(0, 20), pady=0)
frame_esquerdo.pack_propagate(False)

frame_direito = ctk.CTkFrame(frame_principal, fg_color=COR_CINZA, corner_radius=16)
frame_direito.pack(side='right', fill='both', expand=True, pady=0)

# === TECHNICAL STANDARD SELECTION ===
frame_norma = ctk.CTkFrame(frame_esquerdo, fg_color='transparent')
frame_norma.pack(fill='x', pady=(10, 0), padx=10)

label_norma = ctk.CTkLabel(frame_norma, text="Technical Standard:", font=('Segoe UI', 14, 'bold'), text_color=COR_LARANJA)
label_norma.pack(pady=(0, 5))

estrutura_var = ctk.StringVar(value='Custom')
estrutura_menu = ctk.CTkOptionMenu(
    frame_norma,
    values=list(estruturas_normas.keys()),
    variable=estrutura_var,
    command=lambda _: atualizar_limites_por_norma(),
    font=('Segoe UI', 11),
    width=280
)
estrutura_menu.pack(pady=(0, 10))

label_info_norma = ctk.CTkLabel(frame_norma, text="", font=('Segoe UI', 9), text_color=COR_TEXTO, wraplength=280)
label_info_norma.pack(pady=(0, 10))

# === GRAPH CHECKBOXES ===
checkbox_frame = ctk.CTkFrame(frame_esquerdo, fg_color='transparent')
checkbox_frame.pack(fill='x', pady=(10, 0))

grafico_tilt_var = ctk.BooleanVar(value=False)
grafico_vib_var = ctk.BooleanVar(value=False)

def on_checkbox_change():
    atualizar_inputs_limites()
    atualizar_estado_iniciar()
    update_graph()

checkbox_tilt = ctk.CTkCheckBox(
    checkbox_frame, text='Tilt', variable=grafico_tilt_var,
    command=on_checkbox_change, font=('Segoe UI', 13), text_color=COR_TEXTO
)
checkbox_tilt.pack(side='left', padx=10, pady=5)

checkbox_vib = ctk.CTkCheckBox(
    checkbox_frame, text='Vibration', variable=grafico_vib_var,
    command=on_checkbox_change, font=('Segoe UI', 13), text_color=COR_TEXTO
)
checkbox_vib.pack(side='left', padx=10, pady=5)

status_label = ctk.CTkLabel(frame_esquerdo, text='Ready to start', font=('Segoe UI', 16, 'bold'), text_color=COR_LARANJA)
status_label.pack(pady=(10, 20))

# Graphs
fig, axs = plt.subplots(2, 1, figsize=(7, 5))
fig.patch.set_facecolor(COR_CINZA)
fig.tight_layout(pad=3.0)
canvas = FigureCanvasTkAgg(fig, frame_direito)

plt.rcParams['axes.facecolor'] = COR_CINZA
plt.rcParams['figure.facecolor'] = COR_CINZA
plt.rcParams['axes.labelcolor'] = COR_TEXTO
plt.rcParams['xtick.color'] = COR_TEXTO
plt.rcParams['ytick.color'] = COR_TEXTO
plt.rcParams['axes.edgecolor'] = COR_PRETO
plt.rcParams['text.color'] = COR_TEXTO

# Function to smooth signal using FFT (low-pass)
def suavizar_fft(sinal, freq_corte=10, fs=50):
    if len(sinal) < 2:
        return sinal
    N = len(sinal)
    y = np.array(sinal)
    y = y - np.mean(y)
    Y = np.fft.fft(y)
    freqs = np.fft.fftfreq(N, d=1/fs)
    Y[np.abs(freqs) > freq_corte] = 0
    y_suave = np.fft.ifft(Y).real + np.mean(sinal)
    return y_suave.tolist()

def update_graph():
    global encerrado, last_update_time, graph_cache, UNIDADE_VIB_ATUAL
    
    current_time = time.time()
    if current_time - last_update_time < UPDATE_INTERVAL:
        if running:
            app.after(50, update_graph)
        return
    
    last_update_time = current_time
    
    for ax in axs:
        ax.clear()
        ax.set_visible(False)

    show_tilt = grafico_tilt_var.get()
    show_vib = grafico_vib_var.get()

    unidade_display = 'm/s²' if UNIDADE_VIB_ATUAL == 'm/s²' else 'g'

    if encerrado:
        if show_tilt:
            axs[0].set_visible(True)
            if tilts_all:
                suave = suavizar_fft(tilts_all)
                axs[0].plot(list(range(len(suave))), suave, color=COR_LARANJA, linewidth=2)
            axs[0].set_ylim(0, 100)
            axs[0].set_title('Tilt (°) over time', color=COR_LARANJA, fontsize=12, fontweight='bold')
            axs[0].set_ylabel('Degrees', color=COR_TEXTO)
            axs[0].set_facecolor(COR_CINZA)
        if show_vib:
            idx = 1 if show_tilt else 0
            axs[idx].set_visible(True)
            if vibracoes_all:
                suave = suavizar_fft(vibracoes_all)
                if UNIDADE_VIB_ATUAL == 'm/s²':
                    suave = [g_para_ms2(v) for v in suave]
                axs[idx].plot(list(range(len(suave))), suave, color='#FFB266', linewidth=2)
            
            if UNIDADE_VIB_ATUAL == 'm/s²':
                axs[idx].set_ylim(0, 50)
            else:
                axs[idx].set_ylim(0, 5)
            
            axs[idx].set_title(f'Vibration ({unidade_display}) over time', color=COR_LARANJA, fontsize=12, fontweight='bold')
            axs[idx].set_ylabel(unidade_display, color=COR_TEXTO)
            axs[idx].set_facecolor(COR_CINZA)
        fig.tight_layout(pad=3.0)
        canvas.draw()
        return

    if not show_tilt and not show_vib:
        canvas.draw()
        if running:
            app.after(50, update_graph)
        return

    if show_tilt and show_vib:
        axs[0].set_visible(True)
        axs[1].set_visible(True)
        if tilts:
            suave = suavizar_fft(list(tilts))
            pts = list(range(len(suave)))
            axs[0].plot(pts, suave, color=COR_LARANJA, linewidth=2)
        axs[0].set_ylim(0, 100)
        axs[0].set_title('Tilt (°)', color=COR_LARANJA, fontsize=12, fontweight='bold')
        axs[0].set_ylabel('Degrees', color=COR_TEXTO)
        axs[0].set_facecolor(COR_CINZA)

        if vibracoes:
            suave = suavizar_fft(list(vibracoes))
            if UNIDADE_VIB_ATUAL == 'm/s²':
                suave = [g_para_ms2(v) for v in suave]
            pts = list(range(len(suave)))
            axs[1].plot(pts, suave, color='#FFB266', linewidth=2)
        
        if UNIDADE_VIB_ATUAL == 'm/s²':
            axs[1].set_ylim(0, 50)
        else:
            axs[1].set_ylim(0, 5)
            
        axs[1].set_title(f'Vibration ({unidade_display})', color=COR_LARANJA, fontsize=12, fontweight='bold')
        axs[1].set_ylabel(unidade_display, color=COR_TEXTO)
        axs[1].set_facecolor(COR_CINZA)

    elif show_tilt:
        axs[0].set_visible(True)
        if tilts:
            suave = suavizar_fft(list(tilts))
            pts = list(range(len(suave)))
            axs[0].plot(pts, suave, color=COR_LARANJA, linewidth=2)
        axs[0].set_ylim(0, 100)
        axs[0].set_title('Tilt (°)', color=COR_LARANJA, fontsize=12, fontweight='bold')
        axs[0].set_ylabel('Degrees', color=COR_TEXTO)
        axs[0].set_facecolor(COR_CINZA)

    elif show_vib:
        axs[0].set_visible(True)
        if vibracoes:
            suave = suavizar_fft(list(vibracoes))
            if UNIDADE_VIB_ATUAL == 'm/s²':
                suave = [g_para_ms2(v) for v in suave]
            pts = list(range(len(suave)))
            axs[0].plot(pts, suave, color='#FFB266', linewidth=2)
        
        if UNIDADE_VIB_ATUAL == 'm/s²':
            axs[0].set_ylim(0, 50)
        else:
            axs[0].set_ylim(0, 5)
            
        axs[0].set_title(f'Vibration ({unidade_display})', color=COR_LARANJA, fontsize=12, fontweight='bold')
        axs[0].set_ylabel(unidade_display, color=COR_TEXTO)
        axs[0].set_facecolor(COR_CINZA)

    fig.tight_layout(pad=3.0)
    canvas.draw()
    
    if recording:
        capturar_frame_grafico()
    
    if running:
        app.after(100, update_graph)

grafico_tilt_var.trace_add('write', lambda *a: update_graph())
grafico_vib_var.trace_add('write', lambda *a: update_graph())

btn_frame = ctk.CTkFrame(frame_esquerdo, fg_color='transparent')
btn_frame.pack(pady=(10, 0))

# Limit Inputs
frame_limites = ctk.CTkFrame(frame_esquerdo, fg_color='transparent')
frame_limites.pack(fill='x', pady=(10, 0))

entry_tilt_limit = None
entry_vib_limit = None
label_tilt = None
label_vib = None
label_nenhum = None

def atualizar_limites_por_norma():
    """Updates thresholds based on the selected technical standard"""
    global TILT_THRESHOLD, VIB_THRESHOLD, ESTRUTURA_ATUAL, UNIDADE_VIB_ATUAL
    
    estrutura = estrutura_var.get()
    ESTRUTURA_ATUAL = estrutura
    
    if estrutura in estruturas_normas:
        norma_info = estruturas_normas[estrutura]
        
        info_text = f"{norma_info['norma']}\n{norma_info['descricao']}"
        label_info_norma.configure(text=info_text)
        
        if estrutura == 'Custom':
            UNIDADE_VIB_ATUAL = 'g'
        else:
            UNIDADE_VIB_ATUAL = 'm/s²'
        
        if entry_tilt_limit:
            entry_tilt_limit.delete(0, 'end')
            entry_tilt_limit.insert(0, str(norma_info['tilt']))
        
        if entry_vib_limit:
            entry_vib_limit.delete(0, 'end')
            if estrutura == 'Custom':
                entry_vib_limit.insert(0, str(norma_info['vib']))
            else:
                entry_vib_limit.insert(0, str(norma_info['vib']))
    
    atualizar_inputs_limites()
    atualizar_estado_iniciar()

def pode_iniciar():
    if not grafico_tilt_var.get() and not grafico_vib_var.get():
        return False
    if grafico_tilt_var.get():
        if not entry_tilt_limit or not entry_tilt_limit.get().strip():
            return False
        try:
            float(entry_tilt_limit.get())
        except:
            return False
    if grafico_vib_var.get():
        if not entry_vib_limit or not entry_vib_limit.get().strip():
            return False
        try:
            float(entry_vib_limit.get())
        except:
            return False
    return True

def atualizar_estado_iniciar(*args):
    if pode_iniciar():
        btn_start.configure(state='normal')
    else:
        btn_start.configure(state='disabled')

def atualizar_inputs_limites():
    global entry_tilt_limit, entry_vib_limit, label_tilt, label_vib, label_nenhum, UNIDADE_VIB_ATUAL
    for widget in frame_limites.winfo_children():
        widget.destroy()
    entry_tilt_limit = None
    entry_vib_limit = None
    label_tilt = None
    label_vib = None
    label_nenhum = None
    
    estrutura = estrutura_var.get()
    eh_personalizada = estrutura == 'Custom'
    
    if grafico_tilt_var.get():
        label_tilt = ctk.CTkLabel(frame_limites, text="Tilt limit (°):", font=('Segoe UI', 12))
        label_tilt.pack(pady=(0, 2))
        entry_tilt_limit = ctk.CTkEntry(frame_limites, width=100)
        
        if estrutura in estruturas_normas:
            valor_inicial = str(estruturas_normas[estrutura]['tilt'])
        else:
            valor_inicial = "80.0"
        entry_tilt_limit.insert(0, valor_inicial)
        entry_tilt_limit.pack(pady=(0, 8))
        entry_tilt_limit.bind('<KeyRelease>', lambda e: atualizar_estado_iniciar())
        
        if not eh_personalizada:
            entry_tilt_limit.configure(state='disabled')
    
    if grafico_vib_var.get():
        unidade_display = 'g' if eh_personalizada else 'm/s²'
        
        label_vib = ctk.CTkLabel(frame_limites, text=f"Vibration limit ({unidade_display}):", font=('Segoe UI', 12))
        label_vib.pack(pady=(0, 2))
        entry_vib_limit = ctk.CTkEntry(frame_limites, width=100)
        
        if estrutura in estruturas_normas:
            valor_inicial = str(estruturas_normas[estrutura]['vib'])
        else:
            valor_inicial = "1.5"
        entry_vib_limit.insert(0, valor_inicial)
        entry_vib_limit.pack(pady=(0, 8))
        entry_vib_limit.bind('<KeyRelease>', lambda e: atualizar_estado_iniciar())
        
        if not eh_personalizada:
            entry_vib_limit.configure(state='disabled')
    
    if not grafico_tilt_var.get() and not grafico_vib_var.get():
        label_nenhum = ctk.CTkLabel(frame_limites, text="No graph selected", font=('Segoe UI', 12, 'italic'), text_color=COR_LARANJA)
        label_nenhum.pack(pady=10)
    atualizar_estado_iniciar()

grafico_tilt_var.trace_add('write', lambda *a: atualizar_estado_iniciar())
grafico_vib_var.trace_add('write', lambda *a: atualizar_estado_iniciar())

btn_start = ctk.CTkButton(
    frame_esquerdo, text='Start',
    fg_color=COR_LARANJA, hover_color='#FFB266',
    text_color=COR_PRETO, font=('Segoe UI', 14, 'bold'),
    width=140, height=40, corner_radius=10,
    command=lambda: start_recepcao(),
    state='disabled'
)
btn_start.pack(side='bottom', pady=20)

def setup_inputs_iniciais():
    atualizar_limites_por_norma()
    atualizar_inputs_limites()
setup_inputs_iniciais()

# Right side
frame_passos = ctk.CTkFrame(frame_direito, fg_color='transparent')
frame_passos.pack(fill='both', expand=True)
label_passos = ctk.CTkLabel(
    frame_passos,
    text=(
        'How to use Riggy:\n'
        '1. Select the technical standard or use "Custom".\n'
        '2. Select the desired graphs on the left.\n'
        '3. For a custom standard, define limits manually.\n'
        '4. Click Start to begin receiving data.\n'
        '5. Click Stop to finish data collection.\n'
        '6. Choose the format: EPUB (embedded video) or PDF (attached video).'
    ),
    font=('Segoe UI', 15),
    justify='left',
    text_color=COR_TEXTO
)
label_passos.pack(padx=30, pady=30, anchor='center')

frame_graficos = ctk.CTkFrame(frame_direito, fg_color='transparent')
canvas.get_tk_widget().pack(fill='both', expand=True, pady=(0, 10))

frame_botoes = ctk.CTkFrame(frame_graficos, fg_color='transparent')
frame_botoes.pack(fill='x', pady=(10, 10))

btn_encerrar = ctk.CTkButton(
    frame_botoes, text='Stop',
    fg_color=COR_LARANJA, hover_color='#FFB266',
    text_color=COR_PRETO, font=('Segoe UI', 14, 'bold'),
    width=120, height=40, corner_radius=10,
    command=lambda: stop_recepcao(),
    state='disabled'
)
btn_encerrar.pack(side='left', padx=5)

btn_report_epub = ctk.CTkButton(
    frame_botoes, text='Generate EPUB',
    fg_color=COR_LARANJA, hover_color='#FFB266',
    text_color=COR_PRETO, font=('Segoe UI', 14, 'bold'),
    width=120, height=40, corner_radius=10,
    command=gerar_relatorio_epub_com_loading, state='disabled'
)
btn_report_epub.pack(side='left', padx=5)

btn_report_pdf = ctk.CTkButton(
    frame_botoes, text='Generate PDF',
    fg_color=COR_LARANJA, hover_color='#FFB266',
    text_color=COR_PRETO, font=('Segoe UI', 14, 'bold'),
    width=120, height=40, corner_radius=10,
    command=gerar_relatorio_pdf_com_loading, state='disabled'
)
btn_report_pdf.pack(side='left', padx=5)

def atualizar_lado_direito(estado):
    if estado == 'passos':
        frame_graficos.pack_forget()
        frame_passos.pack(fill='both', expand=True)
    elif estado == 'graficos':
        frame_passos.pack_forget()
        frame_graficos.pack(fill='both', expand=True)
        btn_encerrar.configure(state='normal')
        btn_report_epub.configure(state='disabled')
        btn_report_pdf.configure(state='disabled')
    elif estado == 'encerrado':
        frame_passos.pack_forget()
        frame_graficos.pack(fill='both', expand=True)
        btn_encerrar.configure(state='disabled')
        btn_report_epub.configure(state='normal')
        btn_report_pdf.configure(state='normal')

atualizar_lado_direito('passos')

def start_recepcao():
    global running, data_thread, TILT_THRESHOLD, VIB_THRESHOLD, encerrado
    reset_dados()
    
    iniciar_gravacao()
    
    try:
        if grafico_tilt_var.get() and entry_tilt_limit:
            TILT_THRESHOLD = float(entry_tilt_limit.get())
    except:
        TILT_THRESHOLD = 80.0
    try:
        if grafico_vib_var.get() and entry_vib_limit:
            VIB_THRESHOLD = float(entry_vib_limit.get())
    except:
        VIB_THRESHOLD = 1.5
    
    running = True
    encerrado = False
    status_label.configure(text='Receiving...', text_color=COR_LARANJA)
    btn_start.configure(state='disabled')
    atualizar_lado_direito('graficos')
    
    data_thread = threading.Thread(target=processar_dados_thread, daemon=True)
    data_thread.start()
    update_graph()

def reset_dados():
    global tempo, tilts, vibracoes, alerts, t, gravity, tilt_alerted, vib_alerted, tilts_all, vibracoes_all
    tempo = []
    tilts = deque(maxlen=WINDOW_SIZE)
    vibracoes = deque(maxlen=WINDOW_SIZE)
    alerts = []
    t = 0
    gravity = [0.0, 0.0, 9.81]
    tilt_alerted = False
    vib_alerted = False
    tilts_all = []
    vibracoes_all = []

def stop_recepcao():
    global running, encerrado
    running = False
    encerrado = True
    status_label.configure(text='Stopped', text_color=COR_LARANJA)
    btn_start.configure(state='normal')
    atualizar_lado_direito('encerrado')
    update_graph()

if __name__ == "__main__":
    app.mainloop()