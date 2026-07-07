import yt_dlp
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import threading
import os
import sys
import json
import io
import subprocess
import urllib.request
from datetime import datetime


#ola pero no ola de mar ola de saludo
#yo si leo mis codigos chupen el pico la wea no esta 100% hecha por ia lo revise y tambien programe algunas lineas
#chupen la coyoma


APP_VERSION = "2.0"

# --- Notificaciones de escritorio (opcional, si no está instalado plyer simplemente no se notifica) ---
try:
    from plyer import notification as _plyer_notification
    NOTIFICACIONES_OK = True
except Exception:
    NOTIFICACIONES_OK = False


def notificar(titulo, mensaje):
    if NOTIFICACIONES_OK:
        try:
            _plyer_notification.notify(title=titulo, message=mensaje, app_name="ReSave", timeout=5)
        except Exception:
            pass


# --- Rutas base (funciona igual en .py suelto o en .exe empaquetado) ---
if getattr(sys, 'frozen', False):
    DIRECTORIO_BASE = os.path.dirname(sys.executable)
else:
    DIRECTORIO_BASE = os.path.dirname(os.path.abspath(__file__))

RUTA_FFMPEG = os.path.join(DIRECTORIO_BASE, "bin")
RUTA_CONFIG = os.path.join(DIRECTORIO_BASE, "config.json")
RUTA_HISTORIAL = os.path.join(DIRECTORIO_BASE, "historial.json")
RUTA_ARCHIVO_DESCARGAS = os.path.join(DIRECTORIO_BASE, "archivo_descargas.txt")


# --- Configuración persistente (última carpeta usada, etc.) ---
def cargar_config():
    try:
        with open(RUTA_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def guardar_config(config):
    try:
        with open(RUTA_CONFIG, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# --- Historial de descargas ---
def cargar_historial():
    try:
        with open(RUTA_HISTORIAL, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def guardar_historial(historial):
    try:
        with open(RUTA_HISTORIAL, "w", encoding="utf-8") as f:
            json.dump(historial[-300:], f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def agregar_al_historial(titulo, formato, carpeta, url):
    historial = cargar_historial()
    historial.append({
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "titulo": titulo,
        "formato": formato,
        "carpeta": carpeta,
        "url": url,
    })
    guardar_historial(historial)


# --- Helpers de formato ---
def formatear_duracion(segundos):
    if not segundos:
        return "--"
    segundos = int(segundos)
    m, s = divmod(segundos, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def formatear_velocidad(valor):
    if not valor:
        return "--"
    for unidad in ("B/s", "KB/s", "MB/s", "GB/s"):
        if valor < 1024:
            return f"{valor:.1f} {unidad}"
        valor /= 1024
    return f"{valor:.1f} TB/s"


def formatear_eta(segundos):
    if segundos is None:
        return "--"
    segundos = int(segundos)
    m, s = divmod(segundos, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


# --- Estado global ---
config_actual = cargar_config()
carpeta_destino = config_actual.get("ultima_carpeta", "")
if carpeta_destino and not os.path.isdir(carpeta_destino):
    carpeta_destino = ""

cola_descargas = []          # lista de dicts: url, calidad, subtitulos, idioma_subs, es_playlist
evento_cancelar = threading.Event()
procesando_cola = False
imagen_miniatura_actual = None


def seleccionar_carpeta():
    global carpeta_destino
    carpeta = filedialog.askdirectory()
    if carpeta:
        carpeta_destino = carpeta
        nombre_corto = os.path.basename(carpeta) if os.path.basename(carpeta) else carpeta
        lbl_carpeta_seleccionada.config(text=f"Carpeta: .../{nombre_corto}", fg="#10E56C")
        config_actual["ultima_carpeta"] = carpeta
        guardar_config(config_actual)


# --- Vista previa (título, duración, miniatura, detección de playlist) ---
def iniciar_vista_previa():
    url = entrada_url.get().strip()
    if not url:
        messagebox.showwarning("Atención", "Pega primero un enlace de YouTube.")
        return

    boton_previa.config(state=tk.DISABLED)
    etiqueta_estado.config(text="Buscando información del video...", fg="#f1c40f")

    def _tarea():
        try:
            opciones_previa = {'quiet': True, 'skip_download': True, 'extract_flat': 'in_playlist'}
            with yt_dlp.YoutubeDL(opciones_previa) as ydl:
                info = ydl.extract_info(url, download=False)

            es_playlist = info.get('_type') == 'playlist' or 'entries' in info
            if es_playlist:
                entradas = list(info.get('entries') or [])
                titulo = info.get('title') or "Playlist"
                ventana.after(0, _mostrar_previa_playlist, titulo, len(entradas))
            else:
                titulo = info.get('title', 'Sin título')
                duracion = formatear_duracion(info.get('duration'))
                miniatura_url = info.get('thumbnail')
                ventana.after(0, _mostrar_previa_video, titulo, duracion, miniatura_url)
        except Exception as e:
            ventana.after(0, lambda e=e: etiqueta_estado.config(text=f"No se pudo obtener información: {e}", fg="#ff4757"))
        finally:
            ventana.after(0, lambda: boton_previa.config(state=tk.NORMAL))

    threading.Thread(target=_tarea, daemon=True).start()


def _mostrar_previa_video(titulo, duracion, miniatura_url):
    chk_playlist.pack_forget()
    var_es_playlist.set(False)
    lbl_titulo_previo.config(text=f"🎬 {titulo}")
    lbl_duracion_previo.config(text=f"⏱ Duración: {duracion}")
    lbl_miniatura.config(image="", text="🎬")
    etiqueta_estado.config(text="Información cargada.", fg="#10E56C")

    if miniatura_url:
        def _descargar_miniatura():
            try:
                with urllib.request.urlopen(miniatura_url, timeout=8) as resp:
                    datos = resp.read()
                imagen = Image.open(io.BytesIO(datos))
                imagen = imagen.resize((160, 90), Image.LANCZOS)
                ventana.after(0, _aplicar_miniatura, imagen)
            except Exception:
                pass
        threading.Thread(target=_descargar_miniatura, daemon=True).start()


def _aplicar_miniatura(imagen_pil):
    global imagen_miniatura_actual
    imagen_miniatura_actual = ImageTk.PhotoImage(imagen_pil)
    lbl_miniatura.config(image=imagen_miniatura_actual, text="")


def _mostrar_previa_playlist(titulo, cantidad):
    lbl_titulo_previo.config(text=f"📃 Playlist: {titulo}")
    lbl_duracion_previo.config(text=f"{cantidad} videos encontrados")
    lbl_miniatura.config(image="", text="📃")
    chk_playlist.pack(anchor="w", pady=(4, 0))
    var_es_playlist.set(True)
    etiqueta_estado.config(text="Playlist detectada.", fg="#10E56C")


# --- Cola de descargas ---
def agregar_a_cola():
    url = entrada_url.get().strip()
    if not url:
        messagebox.showwarning("Atención", "Pega un enlace antes de agregar a la cola.")
        return

    item = {
        "url": url,
        "calidad": combo_calidad.get(),
        "subtitulos": var_subtitulos.get(),
        "idioma_subs": combo_idioma_subs.get(),
        "es_playlist": var_es_playlist.get(),
    }
    cola_descargas.append(item)
    icono = "📃" if item["es_playlist"] else "🎬"
    lista_cola.insert(tk.END, f"{icono} {url}  [{item['calidad']}]")

    entrada_url.delete(0, tk.END)
    lbl_titulo_previo.config(text="")
    lbl_duracion_previo.config(text="")
    lbl_miniatura.config(image="", text="🎬")
    chk_playlist.pack_forget()
    var_es_playlist.set(False)


def quitar_seleccionado_cola():
    seleccion = lista_cola.curselection()
    if not seleccion:
        return
    indice = seleccion[0]
    lista_cola.delete(indice)
    del cola_descargas[indice]


def cancelar_descarga_actual():
    evento_cancelar.set()
    etiqueta_estado.config(text="Cancelando...", fg="#ff4757")
    boton_cancelar.config(state=tk.DISABLED)


def _on_calidad_change(event=None):
    if "Solo Audio" in combo_calidad.get():
        chk_subtitulos.config(state=tk.DISABLED)
        var_subtitulos.set(False)
        combo_idioma_subs.config(state=tk.DISABLED)
    else:
        chk_subtitulos.config(state=tk.NORMAL)
        combo_idioma_subs.config(state="readonly")


# --- Descarga de un ítem individual (video, audio o playlist) ---
def _descargar_item(item, ruta_guardado):
    url = item["url"]
    opcion_seleccionada = item["calidad"]
    es_playlist = item.get("es_playlist", False)

    def hook_progreso(d):
        if evento_cancelar.is_set():
            raise Exception("CANCELADO_POR_USUARIO")
        if d['status'] == 'downloading':
            try:
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                descargado = d.get('downloaded_bytes', 0)
                velocidad = formatear_velocidad(d.get('speed'))
                eta = formatear_eta(d.get('eta'))
                if total_bytes > 0:
                    porcentaje = (descargado / total_bytes) * 100
                    ventana.after(0, lambda p=porcentaje: barra_progreso.config(value=p))
                    ventana.after(0, lambda p=porcentaje: etiqueta_estado.config(text=f"Descargando... {p:.1f}%", fg="#f1c40f"))
                ventana.after(0, lambda v=velocidad, e=eta: etiqueta_velocidad.config(text=f"↓ {v}   ETA: {e}"))
            except Exception:
                pass
        elif d['status'] == 'finished':
            ventana.after(0, lambda: barra_progreso.config(value=100))
            ventana.after(0, lambda: etiqueta_estado.config(text="Uniendo y procesando archivo... (esto puede tardar)", fg="#f1c40f"))

    opciones = {
        'noplaylist': not es_playlist,
        'ffmpeg_location': RUTA_FFMPEG,
        'progress_hooks': [hook_progreso],
        'ignoreerrors': es_playlist,
    }

    ext_esperada = 'mp4'
    formato_label = "Video"

    if opcion_seleccionada == "Solo Audio (MP3 - Máxima Calidad)":
        ext_esperada = 'mp3'
        formato_label = "MP3"
        opciones.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320'}],
        })
    elif opcion_seleccionada == "Solo Audio (WAV)":
        ext_esperada = 'wav'
        formato_label = "WAV"
        opciones.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}],
        })
    elif opcion_seleccionada == "Solo Audio (FLAC)":
        ext_esperada = 'flac'
        formato_label = "FLAC"
        opciones.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'flac'}],
        })
    elif opcion_seleccionada == "Solo Audio (M4A/AAC)":
        ext_esperada = 'm4a'
        formato_label = "M4A"
        opciones.update({
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a'}],
        })
    elif opcion_seleccionada == "Máxima Calidad Disponible":
        opciones['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    elif opcion_seleccionada == "Calidad Media (720p)":
        opciones['format'] = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]'
    elif opcion_seleccionada == "Calidad Baja (480p)":
        opciones['format'] = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]'

    es_audio = "Solo Audio" in opcion_seleccionada
    if item.get("subtitulos") and not es_audio and not es_playlist:
        idioma = item.get("idioma_subs") or "es"
        opciones.update({
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': [idioma],
        })
        opciones['postprocessors'] = opciones.get('postprocessors', []) + [
            {'key': 'FFmpegSubtitlesConvertor', 'format': 'srt'}
        ]

    if es_playlist:
        # Nota: con ignoreerrors activo, cancelar detiene la cola tras el video en curso
        # (yt-dlp puede saltar al siguiente antes de detenerse por completo).
        opciones['outtmpl'] = os.path.join(ruta_guardado, '%(playlist_title)s', '%(playlist_index)s - %(title)s.%(ext)s')
        opciones['download_archive'] = RUTA_ARCHIVO_DESCARGAS
        with yt_dlp.YoutubeDL(opciones) as ydl:
            info = ydl.extract_info(url, download=True)
            titulo_final = info.get('title', 'Playlist') if info else 'Playlist'
        return True, titulo_final, f"Playlist ({formato_label})"

    # --- Video o audio individual ---
    opciones['outtmpl'] = os.path.join(ruta_guardado, '%(title)s.%(ext)s')

    with yt_dlp.YoutubeDL(opciones) as ydl:
        info = ydl.extract_info(url, download=False)
        ruta_base = ydl.prepare_filename(info)
        nombre_base = os.path.splitext(os.path.basename(ruta_base))[0]
        ruta_final_esperada = os.path.join(ruta_guardado, f"{nombre_base}.{ext_esperada}")
        outtmpl_final = os.path.join(ruta_guardado, '%(title)s.%(ext)s')

        if os.path.exists(ruta_final_esperada):
            respuesta = messagebox.askyesnocancel(
                "Archivo Existente",
                f"El archivo '{nombre_base}.{ext_esperada}' ya existe.\n\n"
                "¿Deseas REEMPLAZARLO?\n\n"
                "• SÍ = Sobrescribir el viejo\n"
                "• NO = Guardar como copia nueva\n"
                "• CANCELAR = Abortar"
            )
            if respuesta is None:
                return False, nombre_base, formato_label
            elif respuesta is False:
                contador = 1
                while True:
                    nuevo_nombre = f"{nombre_base} ({contador}).{ext_esperada}"
                    nueva_ruta = os.path.join(ruta_guardado, nuevo_nombre)
                    if not os.path.exists(nueva_ruta):
                        outtmpl_final = os.path.join(ruta_guardado, f"{nombre_base} ({contador}).%(ext)s")
                        break
                    contador += 1
            elif respuesta is True:
                opciones['overwrites'] = True

    opciones['outtmpl'] = outtmpl_final
    with yt_dlp.YoutubeDL(opciones) as ydl_descarga:
        ydl_descarga.download([url])

    return True, nombre_base, formato_label


def _procesar_cola():
    global procesando_cola
    ruta_guardado = carpeta_destino if carpeta_destino else os.getcwd()
    total = len(cola_descargas)
    exitosos = 0

    while cola_descargas:
        item = cola_descargas[0]
        posicion = total - len(cola_descargas) + 1
        ventana.after(0, lambda p=posicion, t=total, u=item['url']: etiqueta_estado.config(
            text=f"Procesando {p}/{t}: {u[:50]}", fg="#f1c40f"))
        ventana.after(0, lambda: barra_progreso.config(value=0))

        if evento_cancelar.is_set():
            break

        try:
            ok, titulo_final, formato_final = _descargar_item(item, ruta_guardado)
            if ok:
                exitosos += 1
                agregar_al_historial(titulo_final, formato_final, ruta_guardado, item['url'])
        except Exception as e:
            if "CANCELADO_POR_USUARIO" not in str(e):
                ventana.after(0, lambda e=e: messagebox.showerror("Error", f"No se pudo descargar:\n{e}"))

        cola_descargas.pop(0)
        ventana.after(0, lambda: lista_cola.delete(0))

        if evento_cancelar.is_set():
            break

    procesando_cola = False
    ventana.after(0, _finalizar_procesamiento, exitosos, total)


def _finalizar_procesamiento(exitosos, total):
    boton_descargar.config(state=tk.NORMAL, bg="#10E56C", fg="#241432")
    boton_cancelar.config(state=tk.DISABLED)
    barra_progreso['value'] = 0
    etiqueta_velocidad.config(text="")
    refrescar_historial()

    if evento_cancelar.is_set():
        etiqueta_estado.config(text="Descarga(s) cancelada(s) por el usuario.", fg="#ff4757")
    else:
        etiqueta_estado.config(text=f"Listo: {exitosos}/{total} descargas completadas.", fg="#10E56C")
        notificar("ReSave", f"{exitosos}/{total} descargas completadas.")


def iniciar_descarga():
    global procesando_cola
    if procesando_cola:
        return

    if entrada_url.get().strip():
        agregar_a_cola()

    if not cola_descargas:
        messagebox.showwarning("Atención", "Agrega al menos un video a la cola (o pega un enlace).")
        return

    evento_cancelar.clear()
    procesando_cola = True
    boton_descargar.config(state=tk.DISABLED, bg="#472C63", fg="#C1A7D9")
    boton_cancelar.config(state=tk.NORMAL)

    hilo = threading.Thread(target=_procesar_cola, daemon=True)
    hilo.start()


# --- Historial (pestaña) ---
def refrescar_historial():
    for fila in tabla_historial.get_children():
        tabla_historial.delete(fila)
    for entrada in reversed(cargar_historial()):
        tabla_historial.insert("", tk.END, values=(
            entrada.get("fecha", ""),
            entrada.get("titulo", ""),
            entrada.get("formato", ""),
            entrada.get("carpeta", ""),
        ))


def abrir_carpeta_historial():
    seleccion = tabla_historial.selection()
    if not seleccion:
        messagebox.showinfo("Historial", "Selecciona una descarga primero.")
        return
    carpeta = tabla_historial.item(seleccion[0], "values")[3]
    if os.path.isdir(carpeta):
        try:
            if os.name == "nt":
                os.startfile(carpeta)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", carpeta])
            else:
                subprocess.Popen(["xdg-open", carpeta])
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la carpeta:\n{e}")
    else:
        messagebox.showwarning("Historial", "Esa carpeta ya no existe.")


def limpiar_historial():
    if messagebox.askyesno("Confirmar", "¿Borrar todo el historial de descargas?"):
        guardar_historial([])
        refrescar_historial()


# --- Chequeos al iniciar ---
def verificar_ffmpeg():
    ejecutable = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    ruta = os.path.join(RUTA_FFMPEG, ejecutable)
    if not os.path.isfile(ruta):
        messagebox.showwarning(
            "FFmpeg no encontrado",
            f"No se encontró FFmpeg en:\n{ruta}\n\n"
            "Las conversiones a MP3/WAV/FLAC y la unión de video+audio podrían fallar.\n"
            "Coloca ffmpeg.exe dentro de una carpeta 'bin' junto al programa."
        )


def verificar_actualizacion_ytdlp():
    def _check():
        try:
            with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=6) as resp:
                datos = json.loads(resp.read().decode())
            ultima = datos["info"]["version"]
            actual = getattr(yt_dlp.version, "__version__", "0")
            if ultima != actual:
                ventana.after(0, lambda: etiqueta_estado.config(
                    text=f"Hay una nueva versión de yt-dlp disponible ({ultima}). La tuya: {actual}.",
                    fg="#f1c40f"
                ))
        except Exception:
            pass
    threading.Thread(target=_check, daemon=True).start()


def intentar_pegar_portapapeles():
    try:
        contenido = ventana.clipboard_get().strip()
        if contenido.startswith("http") and ("youtube.com" in contenido or "youtu.be" in contenido):
            entrada_url.delete(0, tk.END)
            entrada_url.insert(0, contenido)
            etiqueta_estado.config(text="Enlace detectado en el portapapeles.", fg="#10E56C")
    except Exception:
        pass


# --- INTERFAZ GRÁFICA ---

ventana = tk.Tk()
ventana.title(f"ReSave v{APP_VERSION}")

try:
    ventana.iconbitmap("icono.ico")
except Exception:
    pass

ventana.geometry("540x860")
ventana.configure(bg="#241432")
ventana.resizable(False, False)

estilo = ttk.Style()
estilo.theme_use('clam')
estilo.configure("TCombobox", fieldbackground="#472C63", background="#472C63", foreground="white", arrowcolor="#10E56C")
estilo.configure("Verde.Horizontal.TProgressbar", background="#10E56C", troughcolor="#472C63", bordercolor="#241432")
estilo.configure("TNotebook", background="#241432", borderwidth=0)
estilo.configure("TNotebook.Tab", background="#472C63", foreground="white", padding=(14, 6))
estilo.map("TNotebook.Tab", background=[("selected", "#10E56C")], foreground=[("selected", "#241432")])
estilo.configure("Treeview", background="#472C63", fieldbackground="#472C63", foreground="white", rowheight=24)
estilo.configure("Treeview.Heading", background="#331E47", foreground="#10E56C")

# --- BANNER ---
try:
    imagen_pila = Image.open("banner.jpg")
    imagen_pila = imagen_pila.resize((540, 140), Image.LANCZOS)
    imagen_banner = ImageTk.PhotoImage(imagen_pila)

    lbl_banner = tk.Label(ventana, image=imagen_banner, bd=0)
    lbl_banner.pack()

except Exception:
    titulo = tk.Label(ventana, text="YOUTUBE DOWNLOADER", font=("Segoe UI", 16, "bold"), fg="#10E56C", bg="#241432")
    titulo.pack(pady=(25, 10))

# --- PESTAÑAS ---
notebook = ttk.Notebook(ventana)
pestana_descarga = tk.Frame(notebook, bg="#241432")
pestana_historial = tk.Frame(notebook, bg="#241432")
notebook.add(pestana_descarga, text="  Descargar  ")
notebook.add(pestana_historial, text="  Historial  ")
notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 5))

# ================= PESTAÑA DESCARGAR =================
tarjeta = tk.Frame(pestana_descarga, bg="#331E47", highlightbackground="#472C63", highlightthickness=1)
tarjeta.pack(padx=15, pady=10, fill=tk.BOTH, expand=True)

lbl_url = tk.Label(tarjeta, text="Enlace del video de YouTube:", font=("Segoe UI", 10), fg="#C1A7D9", bg="#331E47")
lbl_url.pack(anchor="w", padx=20, pady=(15, 2))

entrada_url = tk.Entry(tarjeta, font=("Segoe UI", 11), bg="#472C63", fg="white", insertbackground="#10E56C", bd=0, relief=tk.FLAT)
entrada_url.pack(fill=tk.X, padx=20, pady=(0, 8), ipady=5)

frame_url_botones = tk.Frame(tarjeta, bg="#331E47")
frame_url_botones.pack(fill=tk.X, padx=20, pady=(0, 10))
boton_previa = tk.Button(
    frame_url_botones, text="🔍 Vista previa", font=("Segoe UI", 9, "bold"),
    bg="#472C63", fg="white", activebackground="#5A387C", activeforeground="white",
    bd=0, cursor="hand2", command=iniciar_vista_previa
)
boton_previa.pack(side=tk.LEFT, ipady=3, ipadx=8)

# --- Vista previa: miniatura, título, duración, playlist ---
frame_previa = tk.Frame(tarjeta, bg="#331E47")
frame_previa.pack(fill=tk.X, padx=20, pady=(0, 10))

frame_miniatura = tk.Frame(frame_previa, bg="#472C63", width=140, height=90)
frame_miniatura.pack(side=tk.LEFT, padx=(0, 10))
frame_miniatura.pack_propagate(False)
lbl_miniatura = tk.Label(frame_miniatura, text="🎬", font=("Segoe UI", 20), bg="#472C63", fg="#C1A7D9")
lbl_miniatura.pack(fill=tk.BOTH, expand=True)

frame_info_previa = tk.Frame(frame_previa, bg="#331E47")
frame_info_previa.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

lbl_titulo_previo = tk.Label(frame_info_previa, text="", font=("Segoe UI", 9, "bold"), fg="white", bg="#331E47", wraplength=280, justify="left")
lbl_titulo_previo.pack(anchor="w")

lbl_duracion_previo = tk.Label(frame_info_previa, text="", font=("Segoe UI", 9), fg="#C1A7D9", bg="#331E47")
lbl_duracion_previo.pack(anchor="w")

var_es_playlist = tk.BooleanVar(value=False)
chk_playlist = tk.Checkbutton(
    frame_info_previa, text="Descargar playlist completa", variable=var_es_playlist,
    bg="#331E47", fg="#C1A7D9", selectcolor="#472C63", activebackground="#331E47"
)
# chk_playlist se muestra (pack) solo cuando se detecta una playlist real

lbl_opciones = tk.Label(tarjeta, text="Selecciona el formato / calidad:", font=("Segoe UI", 10), fg="#C1A7D9", bg="#331E47")
lbl_opciones.pack(anchor="w", padx=20, pady=(0, 2))

opciones_calidad = [
    "Máxima Calidad Disponible",
    "Calidad Media (720p)",
    "Calidad Baja (480p)",
    "Solo Audio (MP3 - Máxima Calidad)",
    "Solo Audio (WAV)",
    "Solo Audio (FLAC)",
    "Solo Audio (M4A/AAC)",
]
combo_calidad = ttk.Combobox(tarjeta, values=opciones_calidad, state="readonly", font=("Segoe UI", 10))
combo_calidad.current(0)
combo_calidad.pack(fill=tk.X, padx=20, pady=(0, 10))
combo_calidad.bind("<<ComboboxSelected>>", _on_calidad_change)

frame_subs = tk.Frame(tarjeta, bg="#331E47")
frame_subs.pack(fill=tk.X, padx=20, pady=(0, 12))
var_subtitulos = tk.BooleanVar(value=False)
chk_subtitulos = tk.Checkbutton(
    frame_subs, text="Descargar subtítulos", variable=var_subtitulos,
    bg="#331E47", fg="#C1A7D9", selectcolor="#472C63", activebackground="#331E47"
)
chk_subtitulos.pack(side=tk.LEFT)
combo_idioma_subs = ttk.Combobox(frame_subs, values=["es", "en", "auto"], state="readonly", width=6, font=("Segoe UI", 9))
combo_idioma_subs.current(0)
combo_idioma_subs.pack(side=tk.LEFT, padx=10)

frame_carpeta = tk.Frame(tarjeta, bg="#331E47")
frame_carpeta.pack(fill=tk.X, padx=20, pady=(0, 15))

boton_carpeta = tk.Button(
    frame_carpeta, text="📁 Seleccionar", font=("Segoe UI", 9, "bold"),
    bg="#472C63", fg="white", activebackground="#5A387C", activeforeground="white",
    bd=0, cursor="hand2", command=seleccionar_carpeta
)
boton_carpeta.pack(side=tk.LEFT, ipady=4, ipadx=5)

texto_carpeta_inicial = f"Carpeta: .../{os.path.basename(carpeta_destino)}" if carpeta_destino else "Carpeta: (Misma del programa)"
color_carpeta_inicial = "#10E56C" if carpeta_destino else "#C1A7D9"
lbl_carpeta_seleccionada = tk.Label(
    frame_carpeta, text=texto_carpeta_inicial,
    font=("Segoe UI", 9, "italic"), fg=color_carpeta_inicial, bg="#331E47"
)
lbl_carpeta_seleccionada.pack(side=tk.LEFT, padx=10)

# --- Cola de descargas ---
frame_cola = tk.Frame(tarjeta, bg="#331E47")
frame_cola.pack(fill=tk.X, padx=20, pady=(0, 10))

lbl_cola = tk.Label(frame_cola, text="Cola de descargas:", font=("Segoe UI", 10), fg="#C1A7D9", bg="#331E47")
lbl_cola.pack(anchor="w")

frame_lista_cola = tk.Frame(frame_cola, bg="#331E47")
frame_lista_cola.pack(fill=tk.X, pady=(2, 5))
lista_cola = tk.Listbox(frame_lista_cola, height=4, bg="#472C63", fg="white", bd=0, selectbackground="#10E56C", selectforeground="#241432")
scroll_cola = ttk.Scrollbar(frame_lista_cola, orient="vertical", command=lista_cola.yview)
lista_cola.configure(yscrollcommand=scroll_cola.set)
lista_cola.pack(side=tk.LEFT, fill=tk.X, expand=True)
scroll_cola.pack(side=tk.RIGHT, fill=tk.Y)

frame_botones_cola = tk.Frame(frame_cola, bg="#331E47")
frame_botones_cola.pack(fill=tk.X, pady=(0, 5))
boton_agregar_cola = tk.Button(
    frame_botones_cola, text="➕ Agregar a la cola", font=("Segoe UI", 9),
    bg="#472C63", fg="white", bd=0, cursor="hand2", command=agregar_a_cola
)
boton_agregar_cola.pack(side=tk.LEFT, ipady=3, ipadx=5)
boton_quitar_cola = tk.Button(
    frame_botones_cola, text="🗑 Quitar seleccionado", font=("Segoe UI", 9),
    bg="#472C63", fg="white", bd=0, cursor="hand2", command=quitar_seleccionado_cola
)
boton_quitar_cola.pack(side=tk.LEFT, padx=10, ipady=3, ipadx=5)

# --- Botones de acción y progreso ---
frame_botones_descarga = tk.Frame(tarjeta, bg="#331E47")
frame_botones_descarga.pack(fill=tk.X, padx=20, pady=(0, 10))

boton_descargar = tk.Button(
    frame_botones_descarga, text="▶ INICIAR DESCARGA", font=("Segoe UI", 11, "bold"),
    bg="#10E56C", fg="#241432", activebackground="#0EC95F", activeforeground="#241432",
    bd=0, cursor="hand2", command=iniciar_descarga
)
boton_descargar.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)

boton_cancelar = tk.Button(
    frame_botones_descarga, text="✕ Cancelar", font=("Segoe UI", 10, "bold"),
    bg="#472C63", fg="#ff4757", activebackground="#5A387C", activeforeground="#ff4757",
    bd=0, cursor="hand2", command=cancelar_descarga_actual, state=tk.DISABLED
)
boton_cancelar.pack(side=tk.LEFT, padx=(10, 0), ipady=6, ipadx=8)

barra_progreso = ttk.Progressbar(tarjeta, orient="horizontal", mode="determinate", style="Verde.Horizontal.TProgressbar")
barra_progreso.pack(fill=tk.X, padx=20, pady=(0, 5))

etiqueta_velocidad = tk.Label(tarjeta, text="", font=("Segoe UI", 9), fg="#C1A7D9", bg="#331E47")
etiqueta_velocidad.pack(anchor="e", padx=20, pady=(0, 10))

# ================= PESTAÑA HISTORIAL =================
frame_historial = tk.Frame(pestana_historial, bg="#241432")
frame_historial.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

columnas = ("fecha", "titulo", "formato", "carpeta")
tabla_historial = ttk.Treeview(frame_historial, columns=columnas, show="headings", height=18)
tabla_historial.heading("fecha", text="Fecha")
tabla_historial.heading("titulo", text="Título")
tabla_historial.heading("formato", text="Formato")
tabla_historial.heading("carpeta", text="Carpeta")
tabla_historial.column("fecha", width=110)
tabla_historial.column("titulo", width=210)
tabla_historial.column("formato", width=90)
tabla_historial.column("carpeta", width=90)

scroll_historial = ttk.Scrollbar(frame_historial, orient="vertical", command=tabla_historial.yview)
tabla_historial.configure(yscrollcommand=scroll_historial.set)
tabla_historial.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scroll_historial.pack(side=tk.RIGHT, fill=tk.Y)

frame_botones_historial = tk.Frame(pestana_historial, bg="#241432")
frame_botones_historial.pack(fill=tk.X, padx=15, pady=(0, 15))
boton_abrir_carpeta = tk.Button(
    frame_botones_historial, text="📂 Abrir carpeta", font=("Segoe UI", 9, "bold"),
    bg="#472C63", fg="white", bd=0, cursor="hand2", command=abrir_carpeta_historial
)
boton_abrir_carpeta.pack(side=tk.LEFT, ipady=4, ipadx=8)
boton_limpiar_historial = tk.Button(
    frame_botones_historial, text="🗑 Limpiar historial", font=("Segoe UI", 9, "bold"),
    bg="#472C63", fg="white", bd=0, cursor="hand2", command=limpiar_historial
)
boton_limpiar_historial.pack(side=tk.LEFT, padx=10, ipady=4, ipadx=8)

# --- Estado global (visible siempre, debajo de las pestañas) ---
etiqueta_estado = tk.Label(ventana, text="", font=("Segoe UI", 10, "italic"), fg="#C1A7D9", bg="#241432")
etiqueta_estado.pack(pady=(0, 10))

# --- Inicialización ---
_on_calidad_change()
refrescar_historial()
ventana.after(300, verificar_ffmpeg)
ventana.after(500, intentar_pegar_portapapeles)
ventana.after(1000, verificar_actualizacion_ytdlp)

ventana.mainloop()