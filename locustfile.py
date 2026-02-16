"""
Test de carga para Sistema de Préstamos.
Simula 4 cobradores navegando y cobrando simultáneamente.

Instalación:
    pip install locust

Ejecutar contra Railway (4 usuarios, 2 min):
    locust -f locustfile.py --host=https://TU-APP.up.railway.app -u 4 -r 2 --run-time 2m --headless

Ejecutar con UI web (abre http://localhost:8089):
    locust -f locustfile.py --host=https://TU-APP.up.railway.app

Ejecutar local:
    locust -f locustfile.py --host=http://127.0.0.1:8000 -u 4 -r 2 --run-time 2m --headless
"""
import random
import json
from locust import HttpUser, task, between, events


# ==================== CONFIGURACIÓN ====================
# Usuarios de prueba (username, password)
USUARIOS = [
    ("nacho", "123"),
    ("martin", "123"),
    ("gonza", "123"),
    ("chacho", "123"),
]

# Términos de búsqueda para simular búsquedas predictivas
TERMINOS_BUSQUEDA = ["mar", "juan", "car", "ana", "pe", "lo", "go", "lu", "di", "so"]


class CobradorUser(HttpUser):
    """
    Simula un cobrador típico usando el sistema:
    - Ve el dashboard
    - Navega a cobros del día
    - Busca clientes
    - Ve lista de préstamos
    - Ve detalle de clientes
    - Registra cobros
    - Ve cierre de caja
    - Exporta Excel
    """
    wait_time = between(1, 4)  # Espera 1-4 seg entre acciones (simula lectura)

    def on_start(self):
        """Login al iniciar la sesión del usuario"""
        # Elegir un usuario aleatorio
        self.username, self.password = random.choice(USUARIOS)

        # Obtener CSRF token de la página de login
        response = self.client.get("/login/", name="GET /login/")
        if response.status_code != 200:
            print(f"[{self.username}] Error al cargar login: {response.status_code}")
            return

        # Extraer csrftoken de la cookie
        csrftoken = response.cookies.get("csrftoken", "")

        # Hacer POST de login
        login_response = self.client.post(
            "/login/",
            data={
                "username": self.username,
                "password": self.password,
                "csrfmiddlewaretoken": csrftoken,
            },
            headers={"Referer": self.host + "/login/"},
            name="POST /login/",
        )

        if login_response.url and "login" not in login_response.url:
            print(f"[{self.username}] Login exitoso")
        else:
            print(f"[{self.username}] Login FALLIDO - status: {login_response.status_code}")

    # ==================== NAVEGACIÓN FRECUENTE ====================

    @task(5)
    def ver_dashboard(self):
        """Dashboard principal - la página más visitada"""
        self.client.get("/", name="GET / (dashboard)")

    @task(5)
    def ver_cobros(self):
        """Página de cobros del día - uso constante durante el día"""
        self.client.get("/cobros/", name="GET /cobros/")

    @task(4)
    def api_cuotas_hoy(self):
        """API AJAX de cuotas del día - se llama al cargar cobros"""
        self.client.get("/api/cuotas-hoy/", name="GET /api/cuotas-hoy/")

    @task(3)
    def ver_clientes(self):
        """Lista de clientes"""
        self.client.get("/clientes/", name="GET /clientes/")

    @task(3)
    def buscar_cliente(self):
        """Búsqueda predictiva de clientes (AJAX autocomplete)"""
        termino = random.choice(TERMINOS_BUSQUEDA)
        self.client.get(
            f"/api/buscar-clientes/?q={termino}",
            name="GET /api/buscar-clientes/?q=...",
        )

    @task(2)
    def ver_prestamos(self):
        """Lista de préstamos"""
        self.client.get("/prestamos/", name="GET /prestamos/")

    @task(2)
    def ver_prestamos_activos(self):
        """Lista de préstamos filtrados por estado"""
        self.client.get("/prestamos/?estado=AC", name="GET /prestamos/?estado=AC")

    # ==================== CIERRE Y REPORTES ====================

    @task(2)
    def ver_cierre_caja(self):
        """Cierre de caja del día"""
        self.client.get("/cierre-caja/", name="GET /cierre-caja/")

    @task(1)
    def ver_reportes(self):
        """Reportes generales"""
        self.client.get("/reportes/", name="GET /reportes/")

    @task(1)
    def ver_planilla(self):
        """Planilla de impresión"""
        self.client.get("/planilla/", name="GET /planilla/")

    # ==================== EXPORTACIONES EXCEL ====================

    @task(1)
    def exportar_cierre_excel(self):
        """Exportar cierre de caja a Excel"""
        self.client.get("/exportar/cierre/", name="GET /exportar/cierre/ (Excel)")

    @task(1)
    def exportar_planilla_excel(self):
        """Exportar planilla de cobros a Excel"""
        self.client.get("/exportar/planilla/", name="GET /exportar/planilla/ (Excel)")

    # ==================== DETALLE DE REGISTROS ====================

    @task(2)
    def ver_detalle_cliente(self):
        """Ver detalle de un cliente aleatorio (pk 1-50)"""
        pk = random.randint(1, 50)
        with self.client.get(
            f"/clientes/{pk}/",
            name="GET /clientes/<pk>/",
            catch_response=True,
        ) as response:
            if response.status_code == 404:
                response.success()  # No contar 404 como error

    @task(2)
    def ver_detalle_prestamo(self):
        """Ver detalle de un préstamo aleatorio (pk 1-50)"""
        pk = random.randint(1, 50)
        with self.client.get(
            f"/prestamos/{pk}/",
            name="GET /prestamos/<pk>/",
            catch_response=True,
        ) as response:
            if response.status_code == 404:
                response.success()

    # ==================== NOTIFICACIONES ====================

    @task(2)
    def api_notificaciones(self):
        """Polling de notificaciones (se hace cada 60s en la app)"""
        self.client.get("/api/notificaciones/", name="GET /api/notificaciones/")

    @task(1)
    def ver_notificaciones(self):
        """Lista de notificaciones"""
        self.client.get("/notificaciones/", name="GET /notificaciones/")


class AdminUser(HttpUser):
    """
    Simula un administrador que además de cobrar,
    ve auditoría, usuarios y respaldos.
    Peso: 1 de cada 4 usuarios será admin.
    """
    weight = 1  # 1 de cada 4 será admin
    wait_time = between(2, 5)

    def on_start(self):
        """Login como admin"""
        self.username = "nacho"
        self.password = "123"

        response = self.client.get("/login/", name="GET /login/ (admin)")
        csrftoken = response.cookies.get("csrftoken", "")

        self.client.post(
            "/login/",
            data={
                "username": self.username,
                "password": self.password,
                "csrfmiddlewaretoken": csrftoken,
            },
            headers={"Referer": self.host + "/login/"},
            name="POST /login/ (admin)",
        )

    @task(3)
    def ver_dashboard(self):
        self.client.get("/", name="GET / (admin dashboard)")

    @task(2)
    def ver_cobros(self):
        self.client.get("/cobros/", name="GET /cobros/ (admin)")

    @task(2)
    def ver_usuarios(self):
        self.client.get("/usuarios/", name="GET /usuarios/")

    @task(1)
    def ver_auditoria(self):
        self.client.get("/auditoria/", name="GET /auditoria/")

    @task(1)
    def ver_respaldos(self):
        self.client.get("/respaldos/", name="GET /respaldos/")

    @task(2)
    def ver_clientes(self):
        self.client.get("/clientes/", name="GET /clientes/ (admin)")

    @task(2)
    def ver_reportes(self):
        self.client.get("/reportes/", name="GET /reportes/ (admin)")

    @task(1)
    def ver_cierre(self):
        self.client.get("/cierre-caja/", name="GET /cierre-caja/ (admin)")

    @task(1)
    def exportar_clientes(self):
        self.client.get(
            "/exportar/clientes/", name="GET /exportar/clientes/ (Excel admin)"
        )

    @task(1)
    def exportar_prestamos(self):
        self.client.get(
            "/exportar/prestamos/", name="GET /exportar/prestamos/ (Excel admin)"
        )


# Ajustar el ratio: 3 cobradores por cada 1 admin
CobradorUser.weight = 3
AdminUser.weight = 1
