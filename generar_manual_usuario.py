"""
Generador de Manual de Usuario con Screenshots - PrestaFacil
Sistema de Gestion de Prestamos y Cobranzas
Genera un PDF completo con capturas reales del sistema.
"""
from fpdf import FPDF
from PIL import Image as PILImage
from datetime import datetime
import os

SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")

# Dimensiones utiles de la pagina A4 (en mm)
PAGE_W = 210
MARGIN_L = 10
MARGIN_R = 10
MARGIN_TOP = 20   # espacio del header
MARGIN_BOT = 25   # espacio del footer + auto break
USABLE_W = PAGE_W - MARGIN_L - MARGIN_R          # 190mm
USABLE_H = 297 - MARGIN_TOP - MARGIN_BOT         # ~252mm

# Limites para imagenes
MOB_W = 55          # ancho para screenshots movil
MOB_MAX_H = 195     # alto maximo movil (dejar espacio para caption + margen)
DESK_W = 170        # ancho para screenshots escritorio
DESK_MAX_H = 170    # alto maximo escritorio


def _get_img_dims(filepath, target_w):
    """Calcula (w, h) en mm respetando el max height segun tipo."""
    im = PILImage.open(filepath)
    pw, ph = im.size
    ratio = ph / pw
    h = target_w * ratio
    return target_w, h


def _fit_image(filepath, target_w, max_h):
    """Ajusta el ancho para que la altura no supere max_h."""
    w, h = _get_img_dims(filepath, target_w)
    if h > max_h:
        # Reducir ancho proporcionalmente para que quepa
        w = max_h / h * w
        h = max_h
    return w, h


class ManualPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=MARGIN_BOT)
        self.chapter_num = 0
        self.section_num = 0

    def header(self):
        if self.page_no() <= 2:  # portada + indice sin header
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, "PrestaFacil  -  Manual de Usuario", align="L")
        self.cell(0, 8, f"Pagina {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.3)
        self.line(MARGIN_L, 14, PAGE_W - MARGIN_R, 14)
        self.ln(4)

    def footer(self):
        self.set_y(-18)
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.3)
        self.line(MARGIN_L, self.get_y(), PAGE_W - MARGIN_R, self.get_y())
        self.ln(2)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(150, 150, 150)
        self.cell(
            0, 6,
            f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  Documento confidencial",
            align="C",
        )

    # ----------------------------------------------------------------
    #  Helpers de espacio
    # ----------------------------------------------------------------
    def remaining_space(self):
        """mm disponibles hasta el margen inferior."""
        return 297 - MARGIN_BOT - self.get_y()

    def ensure_space(self, needed_mm):
        """Si no cabe, saltar de pagina."""
        if self.remaining_space() < needed_mm:
            self.add_page()

    # ----------------------------------------------------------------
    #  Helpers de texto
    # ----------------------------------------------------------------
    def chapter_title(self, title):
        self.chapter_num += 1
        self.section_num = 0
        self.add_page()
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(25, 135, 84)
        self.cell(0, 14, f"{self.chapter_num}. {title}", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(25, 135, 84)
        self.set_line_width(0.8)
        self.line(MARGIN_L, self.get_y(), PAGE_W - MARGIN_R, self.get_y())
        self.ln(8)
        self.set_text_color(0, 0, 0)

    def section_title(self, title):
        self.section_num += 1
        self.ensure_space(20)
        self.ln(5)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(13, 110, 253)
        self.cell(0, 10, f"{self.chapter_num}.{self.section_num}  {title}", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def bullet(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_x(MARGIN_L)
        self.multi_cell(0, 5.5, f"    - {text}")
        self.set_x(MARGIN_L)

    def bold_bullet(self, bold_part, rest):
        self.set_font("Helvetica", "", 10)
        self.set_x(MARGIN_L)
        self.write(5.5, "    - ")
        self.set_font("Helvetica", "B", 10)
        self.write(5.5, bold_part)
        self.set_font("Helvetica", "", 10)
        self.write(5.5, rest)
        self.ln(6.5)
        self.set_x(MARGIN_L)

    def info_box(self, title, text, r=217, g=237, b=247):
        self.ensure_space(18)
        self.ln(3)
        self.set_fill_color(r, g, b)
        self.set_draw_color(r - 40, g - 40, b - 40)
        y0 = self.get_y()
        self.set_font("Helvetica", "B", 9)
        self.cell(0, 7, f"   {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.multi_cell(0, 5, f"   {text}", fill=True)
        y1 = self.get_y()
        self.rect(MARGIN_L, y0, USABLE_W, y1 - y0)
        self.ln(4)

    def warning_box(self, text):
        self.info_box("IMPORTANTE", text, r=255, g=243, b=205)

    def tip_box(self, text):
        self.info_box("CONSEJO", text, r=209, g=236, b=241)

    def table_header(self, cols, widths):
        self.ensure_space(12)
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(52, 58, 64)
        self.set_text_color(255, 255, 255)
        for i, col in enumerate(cols):
            self.cell(widths[i], 8, f" {col}", border=1, fill=True, align="C")
        self.ln()
        self.set_text_color(0, 0, 0)

    def table_row(self, cells, widths, fill=False):
        self.set_font("Helvetica", "", 9)
        if fill:
            self.set_fill_color(245, 245, 245)
        for i, cell_text in enumerate(cells):
            self.cell(widths[i], 7, f" {cell_text}", border=1, fill=fill, align="L")
        self.ln()

    # ----------------------------------------------------------------
    #  Helpers de imagen
    # ----------------------------------------------------------------
    def _img_path(self, filename):
        return os.path.join(SCREENSHOT_DIR, filename)

    def _img_exists(self, filename):
        return os.path.exists(self._img_path(filename))

    def add_screenshot(self, filename, caption="", target_w=None, max_h=None, is_mobile=True):
        """Inserta un screenshot centrado con caption. Respeta limites de alto."""
        path = self._img_path(filename)
        if not os.path.exists(path):
            return  # silencioso

        if target_w is None:
            target_w = MOB_W if is_mobile else DESK_W
        if max_h is None:
            max_h = MOB_MAX_H if is_mobile else DESK_MAX_H

        w, h = _fit_image(path, target_w, max_h)
        total_needed = h + 12  # imagen + caption + padding

        # Si no cabe, pagina nueva
        if self.remaining_space() < total_needed:
            self.add_page()

        # Centrar horizontalmente
        x = (PAGE_W - w) / 2

        # Borde suave alrededor de la imagen
        self.set_draw_color(220, 220, 220)
        self.set_line_width(0.3)
        y0 = self.get_y()
        self.rect(x - 1, y0 - 1, w + 2, h + 2)

        self.image(path, x=x, y=y0, w=w, h=h)
        self.set_y(y0 + h + 3)

        if caption:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(110, 110, 110)
            self.cell(0, 5, caption, align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_text_color(0, 0, 0)
        self.ln(4)

    def add_mobile_screenshot(self, filename, caption=""):
        self.add_screenshot(filename, caption, target_w=MOB_W, max_h=MOB_MAX_H, is_mobile=True)

    def add_desktop_screenshot(self, filename, caption=""):
        self.add_screenshot(filename, caption, target_w=DESK_W, max_h=DESK_MAX_H, is_mobile=False)

    def add_mobile_desktop_pair(self, base_name, section_name):
        """Inserta par movil + escritorio, cada uno bien dimensionado."""
        mob = f"{base_name}_mobile.png"
        desk = f"{base_name}_desktop.png"

        if self._img_exists(mob):
            self.add_mobile_screenshot(mob, f"{section_name} - Vista movil")

        if self._img_exists(desk):
            self.add_desktop_screenshot(desk, f"{section_name} - Vista escritorio")


# ====================================================================
#  CONTENIDO DEL MANUAL
# ====================================================================
def build_manual():
    pdf = ManualPDF()
    pdf.set_title("PrestaFacil - Manual de Usuario")
    pdf.set_author("PrestaFacil")

    # ================================================================
    #  PORTADA
    # ================================================================
    pdf.add_page()
    pdf.ln(35)

    pdf.set_font("Helvetica", "B", 38)
    pdf.set_text_color(25, 135, 84)
    pdf.cell(0, 18, "PrestaFacil", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 18)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 12, "Manual de Usuario", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_draw_color(25, 135, 84)
    pdf.set_line_width(1.2)
    pdf.line(65, pdf.get_y(), 145, pdf.get_y())
    pdf.ln(8)

    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 7, "Sistema Integral de Gestion de Prestamos y Cobranzas", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, "Disenado para cobrar en la calle desde el celular", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(12)

    # 3 previews en la portada (a escala segura)
    preview_imgs = [
        ("01_login_mobile.png", "Login"),
        ("02_dashboard_mobile.png", "Dashboard"),
        ("09_cobros_mobile.png", "Cobros"),
    ]
    preview_w = 38
    preview_max_h = 80
    gap = 8
    total_w = preview_w * 3 + gap * 2
    start_x = (PAGE_W - total_w) / 2
    y0 = pdf.get_y()
    max_actual_h = 0

    for idx, (img, _cap) in enumerate(preview_imgs):
        path = pdf._img_path(img)
        if os.path.exists(path):
            w, h = _fit_image(path, preview_w, preview_max_h)
            x = start_x + idx * (preview_w + gap) + (preview_w - w) / 2
            pdf.image(path, x=x, y=y0, w=w, h=h)
            if h > max_actual_h:
                max_actual_h = h

    pdf.set_y(y0 + max_actual_h + 3)

    # Captions bajo los previews
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(130, 130, 130)
    for idx, (_img, cap) in enumerate(preview_imgs):
        x = start_x + idx * (preview_w + gap)
        pdf.set_x(x)
        pdf.cell(preview_w, 5, cap, align="C")
    pdf.ln(14)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"Version 1.0   |   {datetime.now().strftime('%d/%m/%Y')}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Django 4.2  |  Bootstrap 5.3  |  PWA  |  PostgreSQL", align="C", new_x="LMARGIN", new_y="NEXT")

    # ================================================================
    #  INDICE
    # ================================================================
    pdf.add_page()
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(25, 135, 84)
    pdf.cell(0, 14, "Indice de Contenidos", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(25, 135, 84)
    pdf.set_line_width(0.6)
    pdf.line(MARGIN_L, pdf.get_y(), 80, pdf.get_y())
    pdf.ln(8)

    toc = [
        "Introduccion al Sistema",
        "Roles y Permisos",
        "Inicio de Sesion y Navegacion",
        "Dashboard (Pantalla Principal)",
        "Gestion de Clientes",
        "Gestion de Prestamos",
        "Cobros del Dia",
        "Cierre de Caja",
        "Planilla de Impresion",
        "Reportes Generales",
        "Exportacion a Excel",
        "Notificaciones",
        "Gestion de Usuarios (Admin)",
        "Auditoria del Sistema (Admin)",
        "Respaldos de Base de Datos (Admin)",
        "Configuraciones Administrables",
        "Preguntas Frecuentes",
        "Glosario de Terminos",
    ]
    pdf.set_text_color(0, 0, 0)
    for i, t in enumerate(toc, 1):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(14, 9, f"  {i}.")
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 9, t, new_x="LMARGIN", new_y="NEXT")

    # ================================================================
    #  CAP 1 - INTRODUCCION
    # ================================================================
    pdf.chapter_title("Introduccion al Sistema")
    pdf.body_text(
        "PrestaFacil es un sistema web Mobile-First disenado para la gestion "
        "completa del ciclo de vida de prestamos personales. Permite a un equipo "
        "de cobradores administrar clientes, crear prestamos, registrar pagos en "
        "la calle desde el celular, y al administrador supervisar toda la "
        "operacion en tiempo real."
    )

    pdf.section_title("Que puede hacer el sistema?")
    features = [
        ("Crear prestamos ", "con calculo automatico de intereses y cuotas."),
        ("Cobrar cuotas en tiempo real ", "desde el celular sin recargar la pagina."),
        ("Pagos parciales ", "con opciones flexibles para el monto restante."),
        ("Renovar prestamos ", "sumando saldo pendiente al nuevo monto."),
        ("Frecuencias: ", "Diario, Semanal, Quincenal, Mensual."),
        ("Metodos de pago: ", "Efectivo, Transferencia, Mixto."),
        ("Interes por mora ", "configurable (porcentaje diario + dias de gracia)."),
        ("Reportes y planillas ", "de impresion con filtros avanzados."),
        ("Exportacion a Excel ", "de planilla, cierre, clientes y prestamos."),
        ("Notificaciones ", "automaticas de cuotas vencidas y cobros."),
        ("Auditoria completa ", "de todas las acciones del sistema."),
        ("PWA: ", "instalable en el celular como app nativa."),
    ]
    for b, r in features:
        pdf.bold_bullet(b, r)

    pdf.section_title("Para quien es el sistema?")
    w = [40, 150]
    pdf.table_header(["Rol", "Uso principal"], w)
    pdf.table_row(["Administrador", "Supervisar cobradores, reportes, gestionar usuarios"], w)
    pdf.table_row(["Supervisor", "Revisar reportes y planillas sin gestionar usuarios"], w, True)
    pdf.table_row(["Cobrador", "Cobrar cuotas, gestionar sus clientes y prestamos"], w)

    # ================================================================
    #  CAP 2 - ROLES
    # ================================================================
    pdf.chapter_title("Roles y Permisos")
    pdf.body_text(
        "El sistema maneja tres roles. Los cobradores solo ven SUS clientes y "
        "prestamos. El administrador ve la informacion de todos."
    )

    pdf.section_title("Administrador")
    for t in [
        "Ve TODOS los clientes, prestamos y cuotas del sistema.",
        "Puede crear, editar y desactivar usuarios.",
        "Accede a Auditoria, Respaldos, Configuraciones.",
        "Puede exportar datos a Excel de todo el sistema.",
        "Accede al panel de administracion de Django (/admin/).",
    ]:
        pdf.bullet(t)

    pdf.section_title("Supervisor")
    for t in [
        "Ve reportes generales y planillas.",
        "Puede cobrar cuotas y gestionar prestamos.",
        "NO puede crear ni editar usuarios.",
    ]:
        pdf.bullet(t)

    pdf.section_title("Cobrador")
    for t in [
        "Solo ve SUS clientes y prestamos asignados.",
        "Puede crear clientes y prestamos (se asignan a el automaticamente).",
        "Cobra cuotas en la calle desde su celular.",
        "Ve su propio cierre de caja y dashboard personal.",
    ]:
        pdf.bullet(t)

    pdf.warning_box(
        "Los permisos se aplican automaticamente. Un cobrador nunca vera datos "
        "de otros cobradores, aunque intente acceder por URL directa."
    )

    # ================================================================
    #  CAP 3 - LOGIN Y NAVEGACION
    # ================================================================
    pdf.chapter_title("Inicio de Sesion y Navegacion")

    pdf.section_title("Pantalla de inicio de sesion")
    pdf.body_text(
        "Al ingresar a la URL del sistema se muestra la pantalla de login. "
        "Ingrese su nombre de usuario y contrasena, luego presione 'Iniciar Sesion'."
    )
    pdf.add_mobile_screenshot("01_login_mobile.png", "Login - Vista movil")
    pdf.add_desktop_screenshot("01_login_desktop.png", "Login - Vista escritorio")

    pdf.section_title("Navegacion en el celular")
    pdf.body_text(
        "La barra de navegacion inferior tiene 5 botones principales:"
    )
    pdf.bullet("Inicio: Dashboard con resumen del dia.")
    pdf.bullet("Clientes: Lista y gestion de clientes.")
    pdf.bullet("Cobros: Pantalla principal de cobros (boton central destacado).")
    pdf.bullet("Cierre: Cierre de caja del dia.")
    pdf.bullet("Reportes: Reportes generales y estadisticas.")
    pdf.ln(2)
    pdf.body_text(
        "En la parte superior encontrara: la fecha actual, icono de "
        "notificaciones, selector de tema claro/oscuro y boton de cerrar sesion."
    )

    pdf.section_title("Navegacion en escritorio")
    pdf.body_text(
        "En pantallas grandes aparece un menu lateral (sidebar) con todas las "
        "opciones: Dashboard, Cobros del Dia, Clientes, Prestamos, Cierre de "
        "Caja, Reportes, Notificaciones. Para administradores se agregan: "
        "Usuarios, Auditoria, Respaldos y Admin Django."
    )

    pdf.section_title("Instalar como aplicacion (PWA)")
    pdf.body_text(
        "El sistema es una Progressive Web App. Para instalarlo en su celular:"
    )
    pdf.bullet("Abra la URL en Chrome o Safari.")
    pdf.bullet("Toque el menu del navegador (3 puntos en Chrome).")
    pdf.bullet("Seleccione 'Agregar a pantalla de inicio'.")
    pdf.bullet("Tendra el sistema como app con icono propio en su celular.")

    # ================================================================
    #  CAP 4 - DASHBOARD
    # ================================================================
    pdf.chapter_title("Dashboard (Pantalla Principal)")
    pdf.body_text(
        "El Dashboard es la primera pantalla al iniciar sesion. "
        "Muestra un resumen en tiempo real de la actividad del dia."
    )
    pdf.add_mobile_screenshot("02_dashboard_mobile.png", "Dashboard - Vista movil")
    pdf.add_desktop_screenshot("02_dashboard_desktop.png", "Dashboard - Vista escritorio")

    pdf.section_title("Tarjetas de estadisticas")
    pdf.body_text("En la parte superior del Dashboard se muestran 4 indicadores:")
    w = [50, 140]
    pdf.table_header(["Indicador", "Descripcion"], w)
    pdf.table_row(["Cobrado Hoy", "Total en pesos cobrados en el dia actual"], w)
    pdf.table_row(["Cobros Hoy", "Cantidad de cuotas cobradas hoy"], w, True)
    pdf.table_row(["Pendientes Hoy", "Cuotas que vencen hoy y aun no fueron cobradas"], w)
    pdf.table_row(["Vencidas", "Cuotas vencidas de dias anteriores sin cobrar"], w, True)

    pdf.section_title("Acciones rapidas")
    pdf.body_text("Debajo de las estadisticas hay 4 botones de acceso directo:")
    pdf.bullet("Cobros del Dia: ir directamente a cobrar cuotas.")
    pdf.bullet("Nuevo Prestamo: crear un prestamo rapidamente.")
    pdf.bullet("Nuevo Cliente: registrar un cliente nuevo.")
    pdf.bullet("Imprimir Planilla: generar la planilla de cobros del dia.")

    pdf.section_title("Resumen de cartera")
    pdf.body_text(
        "Al final del Dashboard se muestra: cantidad de clientes activos, "
        "prestamos activos y el total pendiente por cobrar."
    )
    pdf.tip_box(
        "Los administradores ven datos de TODOS los cobradores. "
        "Cada cobrador solo ve los datos de SU propia cartera."
    )

    # ================================================================
    #  CAP 5 - CLIENTES
    # ================================================================
    pdf.chapter_title("Gestion de Clientes")

    pdf.section_title("Lista de clientes")
    pdf.body_text(
        "Acceda desde la barra inferior > Clientes. Muestra todos sus clientes "
        "con buscador por nombre y filtros por categoria."
    )
    pdf.add_mobile_screenshot("03_clientes_lista_mobile.png", "Lista de clientes - Movil")
    pdf.add_desktop_screenshot("03_clientes_lista_desktop.png", "Lista de clientes - Escritorio")

    pdf.section_title("Crear un nuevo cliente")
    pdf.body_text("Para registrar un cliente nuevo:")
    pdf.bullet("Toque el boton '+ Nuevo Cliente'.")
    pdf.bullet("Complete los campos: Nombre, Apellido, Telefono, Direccion, "
               "Tipo de Negocio, Limite de Credito, Ruta de Cobro, Dia de Pago "
               "Preferido, Categoria, Estado y Notas.")
    pdf.bullet("Presione 'Guardar'. El cliente se asigna a usted automaticamente.")
    pdf.add_mobile_screenshot("04_cliente_nuevo_mobile.png", "Formulario de nuevo cliente")

    pdf.section_title("Detalle de un cliente")
    pdf.body_text("Al tocar un cliente de la lista podra ver:")
    pdf.bullet("Datos personales y de contacto.")
    pdf.bullet("Tipo de negocio y ruta de cobro asignada.")
    pdf.bullet("Limite de credito vigente y categoria actual.")
    pdf.bullet("Lista de prestamos asociados con su estado.")
    pdf.bullet("Botones para editar datos o crear nuevo prestamo.")
    pdf.add_mobile_screenshot("05_cliente_detalle_mobile.png", "Detalle de cliente")

    pdf.section_title("Categorias de clientes")
    pdf.body_text("El sistema clasifica automaticamente a los clientes:")
    w = [35, 155]
    pdf.table_header(["Categoria", "Descripcion"], w)
    pdf.table_row(["Excelente", "Mas del 95% de cuotas pagadas a tiempo"], w)
    pdf.table_row(["Regular", "Entre 70% y 95% pagadas a tiempo"], w, True)
    pdf.table_row(["Moroso", "Menos del 70% pagadas a tiempo"], w)
    pdf.table_row(["Nuevo", "Categoria inicial para clientes nuevos"], w, True)

    pdf.info_box("ACTUALIZACION AUTOMATICA",
                 "Cuando un prestamo finaliza, la categoria se recalcula "
                 "automaticamente segun el historial de pagos del cliente.")

    pdf.section_title("Limites de credito")
    pdf.body_text(
        "El sistema aplica multiples niveles de limite (el mas restrictivo gana):"
    )
    pdf.bullet("Limite individual del cliente.")
    pdf.bullet("Limite por categoria (Excelente, Regular, etc.).")
    pdf.bullet("Limite por tipo de negocio.")
    pdf.bullet("Limite basado en porcentaje sobre deuda actual.")
    pdf.ln(2)
    pdf.tip_box("Un limite de $0 significa 'sin limite definido' en ese nivel.")

    # ================================================================
    #  CAP 6 - PRESTAMOS
    # ================================================================
    pdf.chapter_title("Gestion de Prestamos")

    pdf.section_title("Lista de prestamos")
    pdf.body_text(
        "Acceda desde Menu > Prestamos. Puede filtrar por estado: "
        "Activo, Finalizado, Renovado o Cancelado."
    )
    pdf.add_mobile_screenshot("06_prestamos_lista_mobile.png", "Lista de prestamos - Movil")
    pdf.add_desktop_screenshot("06_prestamos_lista_desktop.png", "Lista de prestamos - Escritorio")

    pdf.section_title("Crear un nuevo prestamo")
    pdf.body_text("Para crear un prestamo:")
    pdf.bullet("Toque '+ Nuevo Prestamo'.")
    pdf.bullet("Seleccione el Cliente.")
    pdf.bullet("Ingrese: Monto Solicitado, Tasa de Interes (%), Numero de Cuotas, "
               "Frecuencia de pago y Fecha de Inicio.")
    pdf.bullet("Presione 'Guardar'.")
    pdf.ln(2)
    pdf.body_text("El sistema calcula automaticamente:")
    pdf.bullet("Monto total = Capital + (Capital x Tasa de interes)")
    pdf.bullet("Monto de cada cuota = Total / Numero de cuotas")
    pdf.bullet("Fechas de vencimiento segun la frecuencia elegida")
    pdf.bullet("Fecha estimada de finalizacion")
    pdf.add_mobile_screenshot("07_prestamo_nuevo_mobile.png", "Formulario de nuevo prestamo")

    pdf.warning_box(
        "Para prestamos DIARIOS, el sistema salta los domingos automaticamente "
        "al generar las fechas de cuotas. La primera cuota vence el mismo dia de inicio."
    )

    pdf.section_title("Detalle de un prestamo")
    pdf.body_text("Al tocar un prestamo de la lista podra ver:")
    pdf.bullet("Resumen completo: monto solicitado, total, tasa, frecuencia.")
    pdf.bullet("Barra de progreso visual del avance de pagos.")
    pdf.bullet("Montos: pagado, pendiente y porcentaje completado.")
    pdf.bullet("Lista de TODAS las cuotas con su estado (Pendiente, Pagada, Parcial).")
    pdf.bullet("Boton 'Renovar Prestamo' (si esta activo).")
    pdf.add_mobile_screenshot("08_prestamo_detalle_mobile.png", "Detalle de prestamo - Movil")
    pdf.add_desktop_screenshot("08_prestamo_detalle_desktop.png", "Detalle de prestamo - Escritorio")

    pdf.section_title("Renovar un prestamo")
    pdf.body_text("La renovacion permite crear un nuevo prestamo absorbiendo la deuda actual:")
    pdf.bullet("Desde el detalle del prestamo activo, toque 'Renovar'.")
    pdf.bullet("El sistema muestra el saldo pendiente del prestamo actual.")
    pdf.bullet("Ingrese: nuevo monto, tasa, cantidad de cuotas y frecuencia.")
    pdf.bullet("Presione 'Renovar Prestamo'.")
    pdf.ln(2)
    pdf.body_text("El sistema realiza automaticamente:")
    pdf.bullet("Marca las cuotas pendientes del prestamo anterior como pagadas.")
    pdf.bullet("Cambia el prestamo anterior a estado 'Renovado'.")
    pdf.bullet("Crea nuevo prestamo con capital = nuevo monto + saldo pendiente.")
    pdf.bullet("Genera las nuevas cuotas con sus fechas.")

    pdf.info_box("RESTRICCIONES DE RENOVACION",
                 "Segun la categoria del cliente puede haber restricciones: "
                 "no permitir renovar con deuda pendiente o exigir dias "
                 "minimos pagados antes de poder renovar.")

    # ================================================================
    #  CAP 7 - COBROS
    # ================================================================
    pdf.chapter_title("Cobros del Dia")
    pdf.body_text(
        "Esta es la pantalla mas importante para el cobrador. Acceda desde el "
        "boton central de la barra inferior o desde Menu > Cobros del Dia."
    )
    pdf.add_mobile_screenshot("09_cobros_mobile.png", "Cobros del dia - Movil")
    pdf.add_desktop_screenshot("09_cobros_desktop.png", "Cobros del dia - Escritorio")

    pdf.section_title("Organizacion de cuotas")
    pdf.body_text("Las cuotas se organizan en 4 pestanas:")
    w = [40, 150]
    pdf.table_header(["Pestana", "Contenido"], w)
    pdf.table_row(["Vencidas", "Cuotas de dias anteriores sin cobrar (en rojo)"], w)
    pdf.table_row(["Hoy", "Cuotas que vencen hoy (en amarillo)"], w, True)
    pdf.table_row(["Semana", "Cuotas de los proximos 7 dias"], w)
    pdf.table_row(["Mes", "Cuotas del dia 8 al 30 hacia adelante"], w, True)

    pdf.ln(2)
    pdf.body_text(
        "Dentro de cada pestana, las cuotas se agrupan por Ruta de Cobro "
        "y se ordenan alfabeticamente por apellido del cliente."
    )

    pdf.section_title("Como cobrar una cuota")
    pdf.body_text("El proceso de cobro es simple y rapido:")
    pdf.bullet("Encuentre la cuota en la lista (use las pestanas para filtrar).")
    pdf.bullet("Toque el boton verde 'Cobrar' junto a la cuota.")
    pdf.bullet("Se abre un modal con: nombre del cliente, monto y numero de cuota.")
    pdf.bullet("Confirme tocando 'Cobrar'.")
    pdf.bullet("La cuota se marca como pagada instantaneamente (sin recargar la pagina).")
    pdf.bullet("Las estadisticas del dashboard se actualizan en tiempo real.")

    pdf.section_title("Pagos parciales")
    pdf.body_text(
        "Si el cliente no puede pagar el monto completo de la cuota, "
        "ingrese un monto menor y elija que hacer con el restante:"
    )
    pdf.ln(1)
    pdf.bold_bullet("a) IGNORAR: ", "el restante queda pendiente en la misma cuota. "
                    "El estado cambia a 'Pago Parcial'.")
    pdf.bold_bullet("b) SUMAR A PROXIMA: ", "el restante se agrega al monto de la "
                    "proxima cuota. La cuota actual se marca como pagada.")
    pdf.bold_bullet("c) CUOTA ESPECIAL: ", "se crea una cuota adicional con fecha "
                    "personalizada por el monto restante. La cuota actual se marca pagada.")

    pdf.warning_box(
        "Todas las modificaciones quedan registradas en el Historial de pagos. "
        "Las cuotas que recibieron monto de otra se marcan como 'Modificada'."
    )

    pdf.section_title("Metodos de pago")
    w = [40, 150]
    pdf.table_header(["Metodo", "Descripcion"], w)
    pdf.table_row(["Efectivo", "Pago en billetes o monedas (opcion por defecto)"], w)
    pdf.table_row(["Transferencia", "Pago por transferencia bancaria o digital"], w, True)
    pdf.table_row(["Mixto", "Parte en efectivo + parte en transferencia"], w)

    pdf.section_title("Interes por mora")
    pdf.body_text(
        "Para cuotas vencidas, el sistema calcula interes de mora automaticamente:"
    )
    pdf.bullet("Se aplica un porcentaje diario sobre el monto pendiente.")
    pdf.bullet("Los dias de gracia son configurables (no cobra mora durante esos dias).")
    pdf.bullet("Al cobrar, el sistema sugiere el monto con mora incluida.")

    # ================================================================
    #  CAP 8 - CIERRE DE CAJA
    # ================================================================
    pdf.chapter_title("Cierre de Caja")
    pdf.body_text(
        "Acceda desde la barra inferior > Cierre o desde el menu lateral. "
        "Muestra un resumen detallado de todos los pagos del dia."
    )
    pdf.add_mobile_screenshot("10_cierre_caja_mobile.png", "Cierre de caja - Movil")
    pdf.add_desktop_screenshot("10_cierre_caja_desktop.png", "Cierre de caja - Escritorio")

    pdf.section_title("Informacion mostrada")
    pdf.bullet("Fecha del cierre (puede seleccionar otros dias).")
    pdf.bullet("Total cobrado en el dia y cantidad de pagos realizados.")
    pdf.bullet("Detalle de cada pago: cliente, numero de cuota, monto, metodo de pago.")
    pdf.bullet("Historial de modificaciones si hubo pagos parciales.")

    pdf.tip_box(
        "El administrador ve los cobros de TODOS los cobradores. "
        "Cada cobrador solo ve sus propios cobros."
    )

    # ================================================================
    #  CAP 9 - PLANILLA
    # ================================================================
    pdf.chapter_title("Planilla de Impresion")
    pdf.body_text(
        "Acceda desde 'Imprimir Planilla' en el Dashboard o desde el menu lateral. "
        "Genera una hoja para llevar impresa durante la ruta de cobros."
    )
    pdf.add_mobile_screenshot("11_planilla_mobile.png", "Planilla de impresion - Movil")
    pdf.add_desktop_screenshot("11_planilla_desktop.png", "Planilla de impresion - Escritorio")

    pdf.section_title("Filtros disponibles")
    pdf.bullet("Fecha: seleccione el dia de las cuotas a incluir.")
    pdf.bullet("Ruta: filtre por una ruta de cobro especifica.")
    pdf.bullet("Incluir vencidas: agrega cuotas atrasadas de dias anteriores.")
    pdf.bullet("Mostrar proximas: incluye cuotas de los proximos 7 dias.")
    pdf.bullet("Configuracion de planilla: seleccione entre los formatos definidos.")

    pdf.section_title("Columnas configurables")
    pdf.body_text(
        "Las columnas visibles en la planilla son personalizables desde el "
        "panel admin (/admin/). Opciones disponibles: numero, cliente, telefono, "
        "direccion, categoria, tipo de negocio, ruta, dia de pago, cuota (X/N), "
        "monto, vencimiento, monto solicitado, total, saldo pendiente, "
        "es renovacion, espacio para cobrado, firma y notas."
    )
    pdf.info_box("COLUMNA 'nvo / Renov.'",
                 "En la planilla, 'nvo' significa prestamo NUEVO (primera vez). "
                 "Si dice 'Renov.' o 'SI' es una RENOVACION de un prestamo anterior.")

    # ================================================================
    #  CAP 10 - REPORTES
    # ================================================================
    pdf.chapter_title("Reportes Generales")
    pdf.body_text(
        "Acceda desde la barra inferior > Reportes o el menu lateral."
    )
    pdf.add_mobile_screenshot("12_reportes_mobile.png", "Reportes - Movil")
    pdf.add_desktop_screenshot("12_reportes_desktop.png", "Reportes - Escritorio")

    pdf.section_title("Indicadores principales")
    w = [55, 135]
    pdf.table_header(["Indicador", "Descripcion"], w)
    pdf.table_row(["Total Clientes", "Cantidad de clientes activos en el sistema"], w)
    pdf.table_row(["Prestamos Activos", "Cantidad de prestamos vigentes"], w, True)
    pdf.table_row(["Capital en Calle", "Suma de montos pendientes de todos los prestamos"], w)
    pdf.table_row(["Cuotas Vencidas", "Cantidad total de cuotas atrasadas"], w, True)

    # ================================================================
    #  CAP 11 - EXCEL
    # ================================================================
    pdf.chapter_title("Exportacion a Excel")
    pdf.body_text("El sistema permite exportar datos a archivos Excel (.xlsx).")

    pdf.section_title("Tipos de exportacion")
    w = [50, 140]
    pdf.table_header(["Exportacion", "Contenido del archivo"], w)
    pdf.table_row(["Planilla Cobros", "Cuotas pendientes con datos del cliente y prestamo"], w)
    pdf.table_row(["Cierre de Caja", "Cobros realizados con montos y metodos de pago"], w, True)
    pdf.table_row(["Lista Clientes", "Clientes con datos de contacto y credito"], w)
    pdf.table_row(["Lista Prestamos", "Prestamos con montos, estados y progreso"], w, True)

    pdf.ln(2)
    pdf.body_text(
        "En cada pantalla encontrara un boton de Excel para descargar. "
        "Los archivos incluyen encabezados, formatos de moneda y colores."
    )
    pdf.info_box("COLORES EN EXCEL",
                 "CELESTE = cuotas que recibieron monto de otra cuota. "
                 "AMARILLO = cuotas que transfirieron monto a otra.")

    # ================================================================
    #  CAP 12 - NOTIFICACIONES
    # ================================================================
    pdf.chapter_title("Notificaciones")
    pdf.body_text(
        "Acceda desde el icono de campana en la barra superior "
        "o desde el menu lateral > Notificaciones."
    )
    pdf.add_mobile_screenshot("13_notificaciones_mobile.png", "Notificaciones")

    pdf.section_title("Tipos de notificaciones")
    w = [50, 140]
    pdf.table_header(["Tipo", "Descripcion"], w)
    rows = [
        ("Cuota Vencida", "Una cuota supero su fecha de vencimiento"),
        ("Cuota por Vencer", "Aviso de cuotas que vencen manana"),
        ("Prestamo Finalizado", "Un prestamo fue completamente pagado"),
        ("Cliente Moroso", "Un cliente acumula muchas cuotas vencidas"),
        ("Cobro Realizado", "Confirmacion de un pago registrado"),
        ("Renovacion", "Un prestamo fue renovado"),
        ("Alerta de Sistema", "Alertas de seguridad o mantenimiento"),
    ]
    for i, (tipo, desc) in enumerate(rows):
        pdf.table_row([tipo, desc], w, fill=(i % 2 == 1))

    pdf.ln(2)
    pdf.bullet("El contador rojo en la campana indica notificaciones sin leer.")
    pdf.bullet("Toque una notificacion para marcarla como leida y navegar al enlace.")
    pdf.bullet("Las notificaciones se actualizan automaticamente cada 60 segundos.")

    # ================================================================
    #  CAP 13 - USUARIOS
    # ================================================================
    pdf.chapter_title("Gestion de Usuarios (Admin)")
    pdf.body_text(
        "Solo disponible para Administradores. Acceda desde el menu lateral > Usuarios."
    )
    pdf.add_mobile_screenshot("14_usuarios_mobile.png", "Gestion de usuarios - Movil")
    pdf.add_desktop_screenshot("14_usuarios_desktop.png", "Gestion de usuarios - Escritorio")

    pdf.section_title("Crear un usuario")
    pdf.bullet("Toque '+ Nuevo Usuario'.")
    pdf.bullet("Complete: nombre de usuario, contrasena, nombre, apellido, email, rol y telefono.")
    pdf.bullet("Presione 'Guardar'.")

    pdf.section_title("Editar, activar o desactivar")
    pdf.body_text(
        "Desde la lista de usuarios puede editar datos o cambiar el estado. "
        "Un usuario desactivado no puede iniciar sesion. "
        "No es posible desactivarse a si mismo."
    )

    # ================================================================
    #  CAP 14 - AUDITORIA
    # ================================================================
    pdf.chapter_title("Auditoria del Sistema (Admin)")
    pdf.body_text(
        "Solo disponible para Administradores. Acceda desde el menu lateral > Auditoria. "
        "Registra todas las acciones importantes realizadas en el sistema."
    )

    pdf.section_title("Acciones registradas")
    w = [40, 150]
    pdf.table_header(["Accion", "Descripcion"], w)
    audit_rows = [
        ("Crear", "Creacion de clientes, prestamos o usuarios"),
        ("Editar", "Modificaciones a datos existentes"),
        ("Cobro", "Cada pago de cuota registrado"),
        ("Renovacion", "Renovaciones de prestamos"),
        ("Cambio Estado", "Cambios de categoria o estado"),
        ("Respaldo", "Creacion y descarga de respaldos"),
        ("Exportacion", "Exportaciones a Excel realizadas"),
    ]
    for i, (acc, desc) in enumerate(audit_rows):
        pdf.table_row([acc, desc], w, fill=(i % 2 == 1))

    pdf.section_title("Filtros de busqueda")
    pdf.body_text(
        "Puede filtrar los registros por: usuario, tipo de accion, "
        "tipo de modelo afectado y rango de fechas."
    )

    # ================================================================
    #  CAP 15 - RESPALDOS
    # ================================================================
    pdf.chapter_title("Respaldos de Base de Datos (Admin)")
    pdf.body_text(
        "Solo disponible para Administradores. Acceda desde el menu lateral > Respaldos."
    )
    pdf.section_title("Como crear un respaldo")
    pdf.bullet("Toque 'Crear Respaldo' para generar una copia de la base de datos.")
    pdf.bullet("Puede descargar respaldos anteriores desde la lista.")
    pdf.bullet("El sistema realiza limpieza automatica, manteniendo solo los ultimos N respaldos.")

    # ================================================================
    #  CAP 16 - CONFIGURACIONES
    # ================================================================
    pdf.chapter_title("Configuraciones Administrables")
    pdf.body_text(
        "Todas las configuraciones se gestionan desde el panel de "
        "administracion de Django, accesible en la URL /admin/."
    )

    pdf.section_title("Rutas de Cobro")
    pdf.body_text(
        "Zonas geograficas para organizar clientes y planillas. "
        "Cada ruta tiene: nombre, color identificativo y orden de aparicion."
    )

    pdf.section_title("Tipos de Negocio")
    pdf.body_text(
        "Categorias de negocio del cliente (Almacen, Kiosco, Verduleria, etc.). "
        "Cada tipo puede tener un limite de credito sugerido."
    )

    pdf.section_title("Configuracion de Credito")
    pdf.body_text("Define limites por categoria de cliente:")
    pdf.bullet("Limite maximo de prestamo por categoria.")
    pdf.bullet("Porcentaje adicional permitido sobre deuda actual.")
    pdf.bullet("Permitir o no renovacion con deuda pendiente.")
    pdf.bullet("Dias minimos pagados antes de poder renovar.")

    pdf.section_title("Configuracion de Mora")
    pdf.bullet("Porcentaje diario de interes por mora.")
    pdf.bullet("Dias de gracia antes de aplicar mora.")
    pdf.bullet("Monto minimo de mora a cobrar.")
    pdf.bullet("Activar o desactivar la aplicacion automatica.")

    pdf.section_title("Configuracion de Planilla")
    pdf.body_text(
        "Personalice la planilla de impresion: titulo, subtitulo, agrupacion "
        "(por ruta o por categoria) y columnas visibles. Puede activar, "
        "desactivar, reordenar y renombrar cada columna."
    )

    # ================================================================
    #  CAP 17 - FAQ
    # ================================================================
    pdf.chapter_title("Preguntas Frecuentes")

    pdf.section_title("Que pasa si cobro una cuota por error?")
    pdf.body_text(
        "Contacte al administrador. El puede revertir el cobro desde "
        "el panel de administracion (/admin/) en la seccion Cuotas."
    )

    pdf.section_title("Que significa 'nvo' en la planilla?")
    pdf.body_text(
        "'nvo' es la abreviatura de NUEVO. Indica que el prestamo es nuevo "
        "(no es renovacion). Si dice 'Renov.' o 'SI', es una renovacion."
    )

    pdf.section_title("Como veo prestamos de otro cobrador?")
    pdf.body_text(
        "Solo el Administrador tiene acceso a los datos de todos los cobradores. "
        "Si necesita ver datos de otro cobrador, consulte con su administrador."
    )

    pdf.section_title("El sistema funciona sin internet?")
    pdf.body_text(
        "No. Requiere conexion a internet para funcionar. La PWA puede "
        "mostrar la interfaz momentaneamente sin conexion, pero no puede "
        "procesar cobros ni acceder a datos sin conectividad."
    )

    pdf.section_title("Como se calcula la mora?")
    pdf.body_text(
        "Formula: Mora = Monto pendiente x (Porcentaje diario / 100) "
        "x (Dias vencidos - Dias de gracia)"
    )
    pdf.ln(1)
    pdf.body_text(
        "Ejemplo: cuota de $10.000, mora 0.5% diario, 3 dias de gracia, "
        "10 dias vencida:\n"
        "Mora = $10.000 x 0.005 x (10 - 3) = $350"
    )

    pdf.section_title("Como funciona la renovacion internamente?")
    pdf.bullet("Las cuotas pendientes del prestamo actual se marcan como 'Pagadas'.")
    pdf.bullet("El saldo pendiente se suma al nuevo monto solicitado.")
    pdf.bullet("El prestamo anterior cambia a estado 'Renovado'.")
    pdf.bullet("Se crea un nuevo prestamo con capital = nuevo monto + saldo.")
    pdf.bullet("Se generan las nuevas cuotas con sus fechas de vencimiento.")

    # ================================================================
    #  CAP 18 - GLOSARIO
    # ================================================================
    pdf.chapter_title("Glosario de Terminos")
    pdf.body_text(
        "Referencia rapida de los terminos utilizados en el sistema:"
    )
    terms = [
        ("Capital", "Monto que el cliente recibe (sin intereses)."),
        ("Cuota", "Cada pago individual que debe realizar el cliente."),
        ("Cuota especial", "Cuota adicional creada por un pago parcial."),
        ("Frecuencia", "Periodicidad: Diario, Semanal, Quincenal o Mensual."),
        ("Interes", "Porcentaje sobre el capital cobrado como ganancia."),
        ("Mora", "Interes extra aplicado por cuota vencida."),
        ("Monto solicitado", "Igual al Capital. Lo que pide el cliente."),
        ("Monto total", "Capital + Intereses. Lo que paga el cliente."),
        ("nvo", "Abreviatura de 'Nuevo' (no es renovacion)."),
        ("Pago parcial", "Cuando se paga menos del monto total de la cuota."),
        ("Planilla", "Hoja impresa con las cuotas a cobrar del dia."),
        ("PWA", "Progressive Web App. App instalable en el celular."),
        ("Renovacion", "Nuevo prestamo que absorbe la deuda anterior."),
        ("Ruta de cobro", "Zona geografica para organizar la cobranza."),
        ("Saldo pendiente", "Monto que falta cobrar de un prestamo."),
    ]
    w = [45, 145]
    pdf.table_header(["Termino", "Definicion"], w)
    for i, (term, defn) in enumerate(terms):
        pdf.table_row([term, defn], w, fill=(i % 2 == 1))

    # ================================================================
    #  GUARDAR
    # ================================================================
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Manual_Usuario_PrestaFacil.pdf")
    pdf.output(out)
    size_kb = os.path.getsize(out) / 1024
    print(f"\n{'='*60}")
    print(f"  Manual generado exitosamente!")
    print(f"  Archivo : {out}")
    print(f"  Paginas : {pdf.page_no()}")
    print(f"  Tamano  : {size_kb:.0f} KB")
    print(f"{'='*60}\n")
    return out


if __name__ == "__main__":
    build_manual()
