import yt_dlp
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import threading
import os
import sys


#ola pero no ola de mar ola de saludo
#yo si leo mis codigos chupen el pico la wea no esta 100% hecha por ia lo revise y tambien programe algunas lineas
#chupen la coyoma


carpeta_destino = ""

def seleccionar_carpeta():
    global carpeta_destino
    carpeta = filedialog.askdirectory()
    if carpeta:
        carpeta_destino = carpeta
        nombre_corto = os.path.basename(carpeta) if os.path.basename(carpeta) else carpeta
        lbl_carpeta_seleccionada.config(text=f"Carpeta: .../{nombre_corto}", fg="#10E56C")

def iniciar_descarga():
    url = entrada_url.get().strip()
    opcion_seleccionada = combo_calidad.get()
    
    if not url:
        messagebox.showwarning("Atención", "Por favor, pega el enlace de un video.")
        return
        
    ruta_guardado = carpeta_destino if carpeta_destino else os.getcwd()
    
    boton_descargar.config(state=tk.DISABLED, bg="#472C63", fg="#C1A7D9")
    etiqueta_estado.config(text="Inspeccionando video... Espera un momento.", fg="#f1c40f")
    barra_progreso['value'] = 0  # Reiniciamos la barra a 0

    # Esta función se ejecuta muchas veces por segundo durante la descarga
    def hook_progreso(d):
        if d['status'] == 'downloading':
            try:
                # Calculamos el porcentaje
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                descargado = d.get('downloaded_bytes', 0)
                if total > 0:
                    porcentaje = (descargado / total) * 100
                    barra_progreso['value'] = porcentaje
                    # Actualizamos el texto para mostrar el porcentaje
                    etiqueta_estado.config(text=f"Descargando... {porcentaje:.1f}%", fg="#f1c40f")
            except Exception:
                pass
        elif d['status'] == 'finished':
            barra_progreso['value'] = 100
            etiqueta_estado.config(text="Uniendo y procesando archivo... (esto puede tardar)", fg="#f1c40f")

    def tarea_descarga():
        # Magia para saber dónde está el .exe y la carpeta bin
        if getattr(sys, 'frozen', False):
            directorio_base = os.path.dirname(sys.executable)
        else:
            directorio_base = os.path.dirname(os.path.abspath(__file__))
            
        ruta_ffmpeg = os.path.join(directorio_base, "bin")

        opciones = {
            'outtmpl': os.path.join(ruta_guardado, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'ffmpeg_location': ruta_ffmpeg,
            'progress_hooks': [hook_progreso], # <--- Enganchamos la barra de progreso aquí
        }
        
        ext_esperada = 'mp4'
        
        if opcion_seleccionada == "Solo Audio (MP3 - Máxima Calidad)":
            ext_esperada = 'mp3'
            opciones.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            })
        elif opcion_seleccionada == "Máxima Calidad Disponible":
            opciones['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif opcion_seleccionada == "Calidad Media (720p)":
            opciones['format'] = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]'
        elif opcion_seleccionada == "Calidad Baja (480p)":
            opciones['format'] = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]'

        try:
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
                        etiqueta_estado.config(text="Descarga cancelada por el usuario.", fg="#ff4757")
                        boton_descargar.config(state=tk.NORMAL, bg="#10E56C", fg="#241432")
                        return
                        
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
            
            # Descarga real
            with yt_dlp.YoutubeDL(opciones) as ydl_descarga:
                ydl_descarga.download([url])
                
            etiqueta_estado.config(text="¡Boom! Descarga completada con éxito.", fg="#10E56C")
            messagebox.showinfo("Éxito", "¡Tu archivo ha sido descargado correctamente!")
            
        except Exception as e:
            etiqueta_estado.config(text="Ocurrió un error en la descarga.", fg="#ff4757")
            messagebox.showerror("Error", f"No se pudo descargar:\n{e}")
        finally:
            boton_descargar.config(state=tk.NORMAL, bg="#10E56C", fg="#241432")
            entrada_url.delete(0, tk.END)

    hilo = threading.Thread(target=tarea_descarga)
    hilo.start()

# --- INTERFAZ GRÁFICA ---

ventana = tk.Tk()
ventana.title("ReSave")

try:
    ventana.iconbitmap("icono.ico")
except Exception:
    pass

ventana.geometry("480x580") # Aumentamos un poquito la altura para que quepa la barra
ventana.configure(bg="#241432")
ventana.resizable(False, False)

estilo = ttk.Style()
estilo.theme_use('clam')
estilo.configure("TCombobox", fieldbackground="#472C63", background="#472C63", foreground="white", arrowcolor="#10E56C")
# Creamos un estilo personalizado para que la barra de progreso sea verde y violeta
estilo.configure("Verde.Horizontal.TProgressbar", background="#10E56C", troughcolor="#472C63", bordercolor="#241432")

# --- BANNER ---
try:
    imagen_pila = Image.open("banner.jpg")
    imagen_pila = imagen_pila.resize((480, 150), Image.LANCZOS)
    imagen_banner = ImageTk.PhotoImage(imagen_pila)
    
    lbl_banner = tk.Label(ventana, image=imagen_banner, bd=0)
    lbl_banner.pack()
    

except Exception:
    titulo = tk.Label(ventana, text="YOUTUBE DOWNLOADER", font=("Segoe UI", 16, "bold"), fg="#10E56C", bg="#241432")
    titulo.pack(pady=(25, 10))

tarjeta = tk.Frame(ventana, bg="#331E47", highlightbackground="#472C63", highlightthickness=1)
tarjeta.pack(padx=25, pady=10, fill=tk.BOTH, expand=True)

lbl_url = tk.Label(tarjeta, text="Enlace del video de YouTube:", font=("Segoe UI", 10), fg="#C1A7D9", bg="#331E47")
lbl_url.pack(anchor="w", padx=20, pady=(15, 2))

entrada_url = tk.Entry(tarjeta, font=("Segoe UI", 11), bg="#472C63", fg="white", insertbackground="#10E56C", bd=0, relief=tk.FLAT)
entrada_url.pack(fill=tk.X, padx=20, pady=(0, 12), ipady=5)

lbl_opciones = tk.Label(tarjeta, text="Selecciona el formato / calidad:", font=("Segoe UI", 10), fg="#C1A7D9", bg="#331E47")
lbl_opciones.pack(anchor="w", padx=20, pady=(0, 2))

# Cambié el texto para que el usuario sepa que ahora es la calidad máxima
opciones_calidad = [
    "Máxima Calidad Disponible",
    "Calidad Media (720p)",
    "Calidad Baja (480p)",
    "Solo Audio (MP3 - Máxima Calidad)"
]
combo_calidad = ttk.Combobox(tarjeta, values=opciones_calidad, state="readonly", font=("Segoe UI", 10))
combo_calidad.current(0)
combo_calidad.pack(fill=tk.X, padx=20, pady=(0, 15))

frame_carpeta = tk.Frame(tarjeta, bg="#331E47")
frame_carpeta.pack(fill=tk.X, padx=20, pady=(0, 20))

boton_carpeta = tk.Button(
    frame_carpeta, text="📁 Seleccionar", font=("Segoe UI", 9, "bold"), 
    bg="#472C63", fg="white", activebackground="#5A387C", activeforeground="white",
    bd=0, cursor="hand2", command=seleccionar_carpeta
)
boton_carpeta.pack(side=tk.LEFT, ipady=4, ipadx=5)

lbl_carpeta_seleccionada = tk.Label(
    frame_carpeta, text="Carpeta: (Misma del programa)", 
    font=("Segoe UI", 9, "italic"), fg="#C1A7D9", bg="#331E47"
)
lbl_carpeta_seleccionada.pack(side=tk.LEFT, padx=10)

boton_descargar = tk.Button(
    tarjeta, text="INICIAR DESCARGA", font=("Segoe UI", 11, "bold"), 
    bg="#10E56C", fg="#241432", activebackground="#0EC95F", activeforeground="#241432",
    bd=0, cursor="hand2", command=iniciar_descarga
)
boton_descargar.pack(fill=tk.X, padx=20, pady=(0, 10), ipady=6)

# --- NUEVO: BARRA DE PROGRESO ---
barra_progreso = ttk.Progressbar(tarjeta, orient="horizontal", mode="determinate", style="Verde.Horizontal.TProgressbar")
barra_progreso.pack(fill=tk.X, padx=20, pady=(0, 15))

etiqueta_estado = tk.Label(ventana, text="", font=("Segoe UI", 10, "italic"), fg="#C1A7D9", bg="#241432")
etiqueta_estado.pack(pady=(0, 10))

ventana.mainloop()