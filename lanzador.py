import os
import sys

# Definir la ruta base y CAMBIAR el directorio activo de trabajo
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

# Forzar a la aplicación a ejecutarse desde su carpeta raíz para leer .streamlit
os.chdir(base_dir)

import time
import socket
import threading
import webbrowser
import subprocess
import streamlit.web.cli as stcli

def abrir_navegador(url):
    time.sleep(2.5)
    edge_64 = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    edge_32 = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    
    if os.path.exists(edge_64):
        subprocess.Popen([edge_64, f"--app={url}", "--no-first-run"])
    elif os.path.exists(edge_32):
        subprocess.Popen([edge_32, f"--app={url}", "--no-first-run"])
    else:
        webbrowser.open(url)

def obtener_puerto_libre():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    puerto = sock.getsockname()[1]
    sock.close()
    return puerto

def main():
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    app_path = os.path.join(base_dir, "app.py")
    puerto = obtener_puerto_libre()
    url = f"http://127.0.0.1:{puerto}"

    threading.Thread(target=abrir_navegador, args=(url,), daemon=True).start()

    sys.argv = [
        "streamlit",
        "run",
        app_path,
        f"--server.port={puerto}",
        "--server.headless=true",
        "--global.developmentMode=false",
        "--client.showErrorDetails=true"
    ]

    stcli.main()

if __name__ == "__main__":
    main()