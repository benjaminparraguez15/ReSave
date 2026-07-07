import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import threading
import os
import sys
import json
import io
import re
import time
import subprocess
import urllib.request
from datetime import datetime


#ola pero no ola de mar ola de saludo
#yo si leo mis codigos chupen el pico la wea no esta 100% hecha por ia lo revise y tambien programe algunas lineas
#chupen la coyoma


APP_VERSION = "2.1"

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

NOMBRE_YTDLP = "yt-dlp.exe" if os.name == "nt" else "yt-dlp"
RUTA_YTDLP = os.path.join(RUTA_FFMPEG, NOMBRE_YTDLP)

# En Windows evita que se abra una consola negra cada vez que llamamos a yt-dlp/ffmpeg
CREATIONFLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


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
    if not os.path.isfile(RUTA_YTDLP):
        messagebox.showwarning("yt-dlp no disponible", "No se encontró yt-dlp. Usa el botón '🔄 Actualizar yt-dlp' para descargarlo primero.")
        return

    boton_previa.config(state=tk.DISABLED)
    etiqueta_estado.config(text="Buscando información del video...", fg="#f1c40f")

    def _tarea():
        try:
            resultado = subprocess.run(
                [RUTA_YTDLP, "--skip-download", "--no-warnings", "--flat-playlist", "--dump-single-json", url],
                capture_output=True, text=True, encoding="utf-8", errors="ignore",
                creationflags=CREATIONFLAGS, timeout=30
            )
            if resultado.returncode != 0 or not resultado.stdout.strip():
                mensaje_error = resultado.stderr.strip().splitlines()[-1] if resultado.stderr.strip() else "No se pudo leer el video."
                raise Exception(mensaje_error)

            info = json.loads(resultado.stdout)
            es_playlist_detectada = info.get('_type') == 'playlist' or 'entries' in info
            if es_playlist_detectada:
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


# --- Motor de descarga: yt-dlp.exe externo (permite auto-actualizarse) ---
def _construir_argumentos_base(item):
    opcion = item["calidad"]
    es_playlist = item.get("es_playlist", False)

    args = [
        RUTA_YTDLP, "--newline", "--no-warnings", "--no-color",
        "--ffmpeg-location", RUTA_FFMPEG,
        "--progress-template", "download:PROGRESO|%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s",
    ]

    ext_esperada, formato_label = "mp4", "Video"

    if opcion == "Solo Audio (MP3 - Máxima Calidad)":
        ext_esperada, formato_label = "mp3", "MP3"
        args += ["-x", "--audio-format", "mp3", "--audio-quality", "320K"]
    elif opcion == "Solo Audio (WAV)":
        ext_esperada, formato_label = "wav", "WAV"
        args += ["-x", "--audio-format", "wav"]
    elif opcion == "Solo Audio (FLAC)":
        ext_esperada, formato_label = "flac", "FLAC"
        args += ["-x", "--audio-format", "flac"]
    elif opcion == "Solo Audio (M4A/AAC)":
        ext_esperada, formato_label = "m4a", "M4A"
        args += ["-x", "--audio-format", "m4a"]
    elif opcion == "Máxima Calidad Disponible":
        args += ["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"]
    elif opcion == "Calidad Media (720p)":
        args += ["-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]"]
    elif opcion == "Calidad Baja (480p)":
        args += ["-f", "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]"]

    es_audio = "Solo Audio" in opcion
    if item.get("subtitulos") and not es_audio and not es_playlist:
        idioma = item.get("idioma_subs") or "es"
        args += ["--write-subs", "--write-auto-subs", "--sub-langs", idioma, "--convert-subs", "srt"]

    if es_playlist:
        args += ["--download-archive", RUTA_ARCHIVO_DESCARGAS]
    else:
        args += ["--no-playlist"]

    return args, ext_esperada, formato_label


def _obtener_nombre_base(url):
    try:
        resultado = subprocess.run(
            [RUTA_YTDLP, "--skip-download", "--no-warnings", "--no-playlist",
             "--print", "filename", "-o", "%(title)s.%(ext)s", url],
            capture_output=True, text=True, encoding="utf-8", errors="ignore",
            creationflags=CREATIONFLAGS, timeout=30
        )
        lineas = [l for l in resultado.stdout.strip().splitlines() if l.strip()]
        if lineas:
            return os.path.splitext(os.path.basename(lineas[-1]))[0]
    except Exception:
        pass
    return None


def _terminar_arbol(proc):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            creationflags=CREATIONFLAGS, capture_output=True)
        else:
            proc.terminate()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _vigilar_cancelacion(proc):
    while proc.poll() is None:
        if evento_cancelar.is_set():
            _terminar_arbol(proc)
            break
        time.sleep(0.3)


def _descargar_item(item, ruta_guardado):
    url = item["url"]
    es_playlist = item.get("es_playlist", False)
    args, ext_esperada, formato_label = _construir_argumentos_base(item)

    nombre_base = None
    outtmpl = os.path.join(ruta_guardado, '%(title)s.%(ext)s')

    if es_playlist:
        outtmpl = os.path.join(ruta_guardado, '%(playlist_title)s', '%(playlist_index)s - %(title)s.%(ext)s')
    else:
        nombre_base = _obtener_nombre_base(url) or "video"
        ruta_final_esperada = os.path.join(ruta_guardado, f"{nombre_base}.{ext_esperada}")

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
                    if not os.path.exists(os.path.join(ruta_guardado, nuevo_nombre)):
                        outtmpl = os.path.join(ruta_guardado, f"{nombre_base} ({contador}).%(ext)s")
                        break
                    contador += 1
            elif respuesta is True:
                args = args + ["--force-overwrites"]

    args = args + ["-o", outtmpl, url]

    proc = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="ignore", bufsize=1,
        creationflags=CREATIONFLAGS
    )

    threading.Thread(target=_vigilar_cancelacion, args=(proc,), daemon=True).start()

    titulo_detectado = None
    ultima_linea = ""

    for linea in proc.stdout:
        linea = linea.rstrip("\n")
        if not linea.strip():
            continue
        ultima_linea = linea

        if linea.startswith("PROGRESO|"):
            partes = (linea.split("|") + ["", "", ""])[1:4]
            porcentaje_str, velocidad_str, eta_str = partes
            try:
                porcentaje = float(porcentaje_str.strip().replace("%", ""))
                ventana.after(0, lambda p=porcentaje: barra_progreso.config(value=p))
                ventana.after(0, lambda p=porcentaje: etiqueta_estado.config(text=f"Descargando... {p:.1f}%", fg="#f1c40f"))
            except ValueError:
                pass
            ventana.after(0, lambda v=velocidad_str.strip(), e=eta_str.strip(): etiqueta_velocidad.config(text=f"↓ {v}   ETA: {e}"))
        elif "[Merger]" in linea or "[ExtractAudio]" in linea or "Extracting audio" in linea:
            ventana.after(0, lambda: barra_progreso.config(value=100))
            ventana.after(0, lambda: etiqueta_estado.config(text="Uniendo y procesando archivo... (esto puede tardar)", fg="#f1c40f"))
        else:
            coincidencia = re.match(r'\[download\] Downloading playlist:\s*(.+)', linea)
            if coincidencia:
                titulo_detectado = coincidencia.group(1).strip()

    proc.wait()

    if evento_cancelar.is_set():
        raise Exception("CANCELADO_POR_USUARIO")

    if proc.returncode != 0:
        raise Exception(ultima_linea or f"yt-dlp terminó con código {proc.returncode}")

    return True, (titulo_detectado or nombre_base or "Video"), formato_label


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

    if not os.path.isfile(RUTA_YTDLP):
        messagebox.showwarning("yt-dlp no disponible", "No se encontró yt-dlp. Usa el botón '🔄 Actualizar yt-dlp' para descargarlo primero.")
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


# --- yt-dlp: instalación / actualización del binario externo ---
def descargar_ytdlp_binario():
    boton_actualizar.config(state=tk.DISABLED)
    etiqueta_estado.config(text="Descargando yt-dlp...", fg="#f1c40f")

    def _tarea():
        try:
            os.makedirs(RUTA_FFMPEG, exist_ok=True)
            url_descarga = f"https://github.com/yt-dlp/yt-dlp/releases/latest/download/{NOMBRE_YTDLP}"

            def _reporte(bloques, tam_bloque, total):
                if total > 0:
                    porcentaje = min(100, bloques * tam_bloque * 100 / total)
                    ventana.after(0, lambda p=porcentaje: etiqueta_estado.config(text=f"Descargando yt-dlp... {p:.0f}%", fg="#f1c40f"))

            urllib.request.urlretrieve(url_descarga, RUTA_YTDLP, reporthook=_reporte)
            if os.name != "nt":
                os.chmod(RUTA_YTDLP, 0o755)
            ventana.after(0, lambda: etiqueta_estado.config(text="yt-dlp instalado correctamente.", fg="#10E56C"))
        except Exception as e:
            ventana.after(0, lambda e=e: messagebox.showerror("Error", f"No se pudo descargar yt-dlp:\n{e}"))
        finally:
            ventana.after(0, lambda: boton_actualizar.config(state=tk.NORMAL))

    threading.Thread(target=_tarea, daemon=True).start()


def actualizar_ytdlp():
    if not os.path.isfile(RUTA_YTDLP):
        descargar_ytdlp_binario()
        return

    boton_actualizar.config(state=tk.DISABLED)
    etiqueta_estado.config(text="Buscando actualizaciones de yt-dlp...", fg="#f1c40f")

    def _tarea():
        try:
            resultado = subprocess.run(
                [RUTA_YTDLP, "-U"], capture_output=True, text=True,
                encoding="utf-8", errors="ignore", creationflags=CREATIONFLAGS, timeout=60
            )
            salida_completa = ((resultado.stdout or "") + "\n" + (resultado.stderr or "")).strip()
            lineas_utiles = [l for l in salida_completa.splitlines() if l.strip()]
            salida = lineas_utiles[-1] if lineas_utiles else "Sin respuesta de yt-dlp."
            color = "#10E56C" if resultado.returncode == 0 else "#ff4757"
            ventana.after(0, lambda s=salida, c=color: etiqueta_estado.config(text=s, fg=c))
        except Exception as e:
            ventana.after(0, lambda e=e: messagebox.showerror("Error", f"No se pudo actualizar yt-dlp:\n{e}"))
        finally:
            ventana.after(0, lambda: boton_actualizar.config(state=tk.NORMAL))

    threading.Thread(target=_tarea, daemon=True).start()


def verificar_ytdlp():
    if os.path.isfile(RUTA_YTDLP):
        return
    respuesta = messagebox.askyesno(
        "yt-dlp no encontrado",
        f"No se encontró el motor de descarga (yt-dlp) en:\n{RUTA_YTDLP}\n\n"
        "¿Quieres descargarlo ahora automáticamente? (requiere internet)"
    )
    if respuesta:
        descargar_ytdlp_binario()
    else:
        etiqueta_estado.config(text="yt-dlp no está instalado: las descargas no funcionarán.", fg="#ff4757")


def mostrar_version_ytdlp():
    if not os.path.isfile(RUTA_YTDLP):
        return

    def _tarea():
        try:
            resultado = subprocess.run(
                [RUTA_YTDLP, "--version"], capture_output=True, text=True,
                encoding="utf-8", errors="ignore", creationflags=CREATIONFLAGS, timeout=10
            )
            version = resultado.stdout.strip()
            if version:
                ventana.after(0, lambda v=version: etiqueta_estado.config(text=f"yt-dlp v{v} listo.", fg="#C1A7D9"))
        except Exception:
            pass

    threading.Thread(target=_tarea, daemon=True).start()


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

boton_actualizar = tk.Button(
    frame_url_botones, text="🔄 Actualizar yt-dlp", font=("Segoe UI", 9, "bold"),
    bg="#472C63", fg="white", activebackground="#5A387C", activeforeground="white",
    bd=0, cursor="hand2", command=actualizar_ytdlp
)
boton_actualizar.pack(side=tk.LEFT, padx=(10, 0), ipady=3, ipadx=8)

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
    frame_botones_cola, text=" Agregar a la cola", font=("Segoe UI", 9),
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
ventana.after(500, verificar_ytdlp)
ventana.after(700, intentar_pegar_portapapeles)
ventana.after(1200, mostrar_version_ytdlp)

ventana.mainloop()