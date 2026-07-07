import yt_dlp
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import threading
import os

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

    def tarea_descarga():
        opciones = {
            'outtmpl': os.path.join(ruta_guardado, '%(title)s.%(ext)s'),
            'noplaylist': True, # Evita descargar playlists completas por accidente
        }
        
        # Predecimos la extensión final
        ext_esperada = 'mp4'
        
        if opcion_seleccionada == "Solo Audio (MP3)":
            ext_esperada = 'mp3'
            opciones.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        elif opcion_seleccionada == "Máxima Calidad Disponible":
            opciones['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif opcion_seleccionada == "Calidad Media (720p)":
            opciones['format'] = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]'
        elif opcion_seleccionada == "Calidad Baja (480p)":
            opciones['format'] = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]'

        try:
            # PASO 1: Extraer información sin descargar para saber el nombre
            with yt_dlp.YoutubeDL(opciones) as ydl:
                info = ydl.extract_info(url, download=False)
                ruta_base = ydl.prepare_filename(info)
                
                # Limpiamos el nombre para saber exactamente cómo se guardaría
                nombre_base = os.path.splitext(os.path.basename(ruta_base))[0]
                ruta_final_esperada = os.path.join(ruta_guardado, f"{nombre_base}.{ext_esperada}")
                
                outtmpl_final = os.path.join(ruta_guardado, '%(title)s.%(ext)s')
                
                # PASO 2: Comprobar si el archivo ya existe
                if os.path.exists(ruta_final_esperada):
                    respuesta = messagebox.askyesnocancel(
                        "Archivo Existente",
                        f"El archivo '{nombre_base}.{ext_esperada}' ya existe.\n\n"
                        "¿Deseas REEMPLAZARLO?\n\n"
                        "• SÍ = Sobrescribir el viejo\n"
                        "• NO = Guardar como copia nueva\n"
                        "• CANCELAR = Abortar"
                    )
                    
                    if respuesta is None: # El usuario presionó Cancelar
                        etiqueta_estado.config(text="Descarga cancelada por el usuario.", fg="#ff4757")
                        boton_descargar.config(state=tk.NORMAL, bg="#10E56C", fg="#241432")
                        return # Salimos de la función sin descargar nada
                        
                    elif respuesta is False: # El usuario presionó NO (Quiere una copia)
                        contador = 1
                        while True:
                            nuevo_nombre = f"{nombre_base} ({contador}).{ext_esperada}"
                            nueva_ruta = os.path.join(ruta_guardado, nuevo_nombre)
                            if not os.path.exists(nueva_ruta):
                                # Ajustamos la plantilla para que use este nuevo nombre libre
                                outtmpl_final = os.path.join(ruta_guardado, f"{nombre_base} ({contador}).%(ext)s")
                                break
                            contador += 1
                            
                    elif respuesta is True: # El usuario presionó SÍ (Reemplazar)
                        opciones['overwrites'] = True

            # PASO 3: Ejecutar la descarga real con los datos confirmados
            opciones['outtmpl'] = outtmpl_final
            etiqueta_estado.config(text="Descargando... ¡Esto puede tardar un poco!", fg="#f1c40f")
            
            with yt_dlp.YoutubeDL(opciones) as ydl_descarga:
                ydl_descarga.download([url])
                
            etiqueta_estado.config(text="¡Boom! Descarga completada con éxito.", fg="#10E56C")
            messagebox.showinfo("Éxito", "¡Tu archivo ha sido descargado correctamente!")
            
        except Exception as e:
            etiqueta_estado.config(text="Ocurrió un error en la descarga.", fg="#ff4757")
            messagebox.showerror("Error", f"No se pudo descargar:\n{e}")
        finally:
            # Reactivamos el botón
            boton_descargar.config(state=tk.NORMAL, bg="#10E56C", fg="#241432")
            entrada_url.delete(0, tk.END)

    # Iniciar en hilo secundario
    hilo = threading.Thread(target=tarea_descarga)
    hilo.start()

# --- INTERFAZ GRÁFICA: COLORES DE REZE ---
# --- SI ESTAS LEYENDO ESTO ERES TERRIBLE PUTO AMIGO NO USE SOLAMENTE IA TAMBIEN PROGRAME MI CODIGO A MANO ASI CHUPAME LA PINGA ---
# --- SE QUE PARECE ESPAGUETTI PERO SE HIZO CON ESFUERZO Y EN 30 MINUTOS ASI QUE NO RECLAMEN CUALQUIER WEA AL DM

ventana = tk.Tk()
ventana.title("ReSave")
try:
    ventana.iconbitmap("icono.ico")
except Exception as e:
    print(f"No se encontró el ícono: {e}")

ventana.geometry("480x540")
ventana.configure(bg="#241432")
ventana.resizable(False, False)
ventana.geometry("480x540") # Altura ajustada para el banner y todo el contenido
ventana.configure(bg="#241432")
ventana.resizable(False, False)

estilo = ttk.Style()
estilo.theme_use('clam')
estilo.configure("TCombobox", fieldbackground="#472C63", background="#472C63", foreground="white", arrowcolor="#10E56C")

# --- Cargar e Integrar la Imagen de Banner ---
try:
    imagen_pila = Image.open("banner.jpg")
    imagen_pila = imagen_pila.resize((480, 150), Image.LANCZOS)
    imagen_banner = ImageTk.PhotoImage(imagen_pila)
    
    lbl_banner = tk.Label(ventana, image=imagen_banner, bd=0)
    lbl_banner.pack()
    
except Exception as e:
    print(f"No se pudo cargar el banner: {e}")

# Tarjeta contenedora principal
tarjeta = tk.Frame(ventana, bg="#331E47", highlightbackground="#472C63", highlightthickness=1)
tarjeta.pack(padx=25, pady=10, fill=tk.BOTH, expand=True)

lbl_url = tk.Label(tarjeta, text="Enlace del video de YouTube:", font=("Segoe UI", 10), fg="#C1A7D9", bg="#331E47")
lbl_url.pack(anchor="w", padx=20, pady=(15, 2))

entrada_url = tk.Entry(tarjeta, font=("Segoe UI", 11), bg="#472C63", fg="white", insertbackground="#10E56C", bd=0, relief=tk.FLAT)
entrada_url.pack(fill=tk.X, padx=20, pady=(0, 12), ipady=5)

lbl_opciones = tk.Label(tarjeta, text="Selecciona el formato / calidad:", font=("Segoe UI", 10), fg="#C1A7D9", bg="#331E47")
lbl_opciones.pack(anchor="w", padx=20, pady=(0, 2))

opciones_calidad = [
    "Máxima Calidad Disponible",
    "Calidad Media (720p)",
    "Calidad Baja (480p)",
    "Solo Audio (MP3)"
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
boton_descargar.pack(fill=tk.X, padx=20, pady=(0, 15), ipady=6)

etiqueta_estado = tk.Label(ventana, text="", font=("Segoe UI", 10, "italic"), fg="#C1A7D9", bg="#241432")
etiqueta_estado.pack(pady=(0, 15))

ventana.mainloop()