import socket

def hay_internet(host="8.8.8.8", port=53, timeout=1.5):
    """Devuelve True si hay conexión a internet activa."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except OSError:
        return False