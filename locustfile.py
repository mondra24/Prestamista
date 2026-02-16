"""
Test de carga COMPLETO para Sistema de Préstamos.
Simula cobradores y admins realizando TODAS las operaciones (lectura + escritura).

⚠️  ESTE TEST MODIFICA LA BASE DE DATOS:
    - Crea clientes de test (nombre: "Locust_*")
    - Crea préstamos de test
    - Registra cobros de cuotas
    - Cambia categorías de clientes
    - Renueva préstamos
    - Marca notificaciones como leídas

Instalación:
    pip install locust

Ejecutar contra Railway:
    locust -f locustfile.py --host=https://prestamista-production.up.railway.app

Ejecutar headless (4 usuarios, 2 min):
    locust -f locustfile.py --host=https://prestamista-production.up.railway.app -u 4 -r 2 --run-time 2m --headless

Ejecutar local:
    locust -f locustfile.py --host=http://127.0.0.1:8000
"""
import random
import json
import re
from datetime import date
from locust import HttpUser, task, between


# ==================== CONFIGURACIÓN ====================
USUARIOS = [
    ("nacho", "123"),
    ("martin", "123"),
    ("gonza", "123"),
    ("chacho", "123"),
]

TERMINOS_BUSQUEDA = ["mar", "juan", "car", "ana", "pe", "lo", "go", "lu", "test", "loc"]

NOMBRES_TEST = ["Locust_Ana", "Locust_Juan", "Locust_Pedro", "Locust_María", "Locust_Carlos",
                "Locust_Laura", "Locust_Diego", "Locust_Sofía", "Locust_Mateo", "Locust_Lucía"]
APELLIDOS_TEST = ["García", "López", "Martínez", "Rodríguez", "Pérez", "Sánchez", "Gómez",
                  "Díaz", "Torres", "Flores"]


def _extraer_csrf(response):
    """Extraer CSRF token de cookies o del HTML"""
    csrf = response.cookies.get("csrftoken", "")
    if not csrf:
        match = re.search(r'csrfmiddlewaretoken.*?value=["\']([^"\']+)', response.text or "")
        if match:
            csrf = match.group(1)
    return csrf


def _extraer_csrf_cookie(client):
    """Obtener CSRF de las cookies del cliente"""
    return client.cookies.get("csrftoken", "")


class CobradorUser(HttpUser):
    """
    Simula un cobrador realizando TODAS las operaciones:
    - Navegación (dashboard, cobros, clientes, préstamos)
    - Búsqueda predictiva
    - CREAR clientes
    - EDITAR clientes
    - CREAR préstamos
    - COBRAR cuotas (AJAX POST)
    - RENOVAR préstamos
    - Cambiar categoría de clientes
    - Exportar Excel
    - Notificaciones
    """
    weight = 3
    wait_time = between(1, 4)

    def on_start(self):
        """Login al iniciar"""
        self.username, self.password = random.choice(USUARIOS)
        self.cliente_ids = []
        self.prestamo_ids = []
        self.cuota_ids = []

        response = self.client.get("/login/", name="GET /login/")
        if response.status_code != 200:
            print(f"[{self.username}] Error al cargar login: {response.status_code}")
            return

        csrftoken = _extraer_csrf(response)

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
            self._recopilar_datos()
        else:
            print(f"[{self.username}] Login FALLIDO")

    def _recopilar_datos(self):
        """Obtener IDs de clientes, préstamos y cuotas del usuario"""
        resp = self.client.get("/clientes/", name="GET /clientes/ (recopilar)")
        if resp.status_code == 200:
            ids = re.findall(r'/clientes/(\d+)/', resp.text or "")
            self.cliente_ids = list(set(int(x) for x in ids))[:30]

        resp = self.client.get("/prestamos/?estado=AC", name="GET /prestamos/ (recopilar)")
        if resp.status_code == 200:
            ids = re.findall(r'/prestamos/(\d+)/', resp.text or "")
            self.prestamo_ids = list(set(int(x) for x in ids))[:30]

        resp = self.client.get("/api/cuotas-hoy/", name="GET /api/cuotas-hoy/ (recopilar)")
        if resp.status_code == 200:
            try:
                data = resp.json()
                self.cuota_ids = [c['id'] for c in data.get('cuotas', [])]
            except Exception:
                pass

    # ==================== NAVEGACIÓN (LECTURA) ====================

    @task(5)
    def ver_dashboard(self):
        self.client.get("/", name="GET / (dashboard)")

    @task(5)
    def ver_cobros(self):
        self.client.get("/cobros/", name="GET /cobros/")

    @task(4)
    def api_cuotas_hoy(self):
        resp = self.client.get("/api/cuotas-hoy/", name="GET /api/cuotas-hoy/")
        if resp.status_code == 200:
            try:
                data = resp.json()
                nuevas = [c['id'] for c in data.get('cuotas', [])]
                if nuevas:
                    self.cuota_ids = nuevas
            except Exception:
                pass

    @task(3)
    def ver_clientes(self):
        self.client.get("/clientes/", name="GET /clientes/")

    @task(3)
    def buscar_cliente(self):
        termino = random.choice(TERMINOS_BUSQUEDA)
        self.client.get(f"/api/buscar-clientes/?q={termino}", name="GET /api/buscar-clientes/?q=...")

    @task(2)
    def ver_prestamos(self):
        self.client.get("/prestamos/", name="GET /prestamos/")

    @task(2)
    def ver_prestamos_activos(self):
        self.client.get("/prestamos/?estado=AC", name="GET /prestamos/?estado=AC")

    @task(2)
    def ver_detalle_cliente(self):
        if self.cliente_ids:
            pk = random.choice(self.cliente_ids)
        else:
            pk = random.randint(1, 50)
        with self.client.get(f"/clientes/{pk}/", name="GET /clientes/<pk>/", catch_response=True) as r:
            if r.status_code == 404:
                r.success()

    @task(2)
    def ver_detalle_prestamo(self):
        if self.prestamo_ids:
            pk = random.choice(self.prestamo_ids)
        else:
            pk = random.randint(1, 50)
        with self.client.get(f"/prestamos/{pk}/", name="GET /prestamos/<pk>/", catch_response=True) as r:
            if r.status_code == 404:
                r.success()

    @task(2)
    def ver_cierre_caja(self):
        self.client.get("/cierre-caja/", name="GET /cierre-caja/")

    @task(1)
    def ver_reportes(self):
        self.client.get("/reportes/", name="GET /reportes/")

    @task(1)
    def ver_planilla(self):
        self.client.get("/planilla/", name="GET /planilla/")

    @task(1)
    def exportar_cierre_excel(self):
        self.client.get("/exportar/cierre/", name="GET /exportar/cierre/ (Excel)")

    @task(1)
    def exportar_planilla_excel(self):
        self.client.get("/exportar/planilla/", name="GET /exportar/planilla/ (Excel)")

    @task(2)
    def api_notificaciones(self):
        self.client.get("/api/notificaciones/", name="GET /api/notificaciones/")

    @task(1)
    def ver_notificaciones(self):
        self.client.get("/notificaciones/", name="GET /notificaciones/")

    # ==================== CREAR CLIENTE (POST) ====================

    @task(1)
    def crear_cliente(self):
        """Crear un cliente nuevo via formulario POST"""
        resp = self.client.get("/clientes/nuevo/", name="GET /clientes/nuevo/")
        if resp.status_code != 200:
            return

        csrf = _extraer_csrf(resp)
        if not csrf:
            csrf = _extraer_csrf_cookie(self.client)

        nombre = random.choice(NOMBRES_TEST)
        apellido = f"{random.choice(APELLIDOS_TEST)}_{random.randint(1000, 9999)}"

        with self.client.post(
            "/clientes/nuevo/",
            data={
                "csrfmiddlewaretoken": csrf,
                "nombre": nombre,
                "apellido": apellido,
                "telefono": f"351{random.randint(1000000, 9999999)}",
                "direccion": f"Calle Test {random.randint(100, 9999)}",
                "tipo_negocio": "",
                "tipo_comercio": "",
                "limite_credito": str(random.choice([0, 50000, 100000])),
                "ruta": "",
                "dia_pago_preferido": "",
                "categoria": random.choice(["NU", "RE", "EX"]),
                "estado": "AC",
                "notas": f"Creado por test Locust - {self.username}",
            },
            headers={"Referer": self.host + "/clientes/nuevo/"},
            name="POST /clientes/nuevo/ (crear)",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 302):
                r.success()
                if r.url and '/clientes/' in r.url:
                    match = re.search(r'/clientes/(\d+)/', r.url)
                    if match:
                        self.cliente_ids.append(int(match.group(1)))
            else:
                r.failure(f"Status {r.status_code}")

    # ==================== EDITAR CLIENTE (POST) ====================

    @task(1)
    def editar_cliente(self):
        """Editar un cliente existente"""
        if not self.cliente_ids:
            return

        pk = random.choice(self.cliente_ids)
        resp = self.client.get(f"/clientes/{pk}/editar/", name="GET /clientes/<pk>/editar/")
        if resp.status_code != 200:
            return

        csrf = _extraer_csrf(resp)
        if not csrf:
            csrf = _extraer_csrf_cookie(self.client)

        with self.client.post(
            f"/clientes/{pk}/editar/",
            data={
                "csrfmiddlewaretoken": csrf,
                "nombre": random.choice(NOMBRES_TEST),
                "apellido": f"{random.choice(APELLIDOS_TEST)}_{random.randint(1000, 9999)}",
                "telefono": f"351{random.randint(1000000, 9999999)}",
                "direccion": f"Calle Editada {random.randint(100, 9999)}",
                "tipo_negocio": "",
                "tipo_comercio": "",
                "limite_credito": str(random.choice([0, 50000, 100000, 200000])),
                "ruta": "",
                "dia_pago_preferido": "",
                "categoria": random.choice(["NU", "RE", "EX", "MO"]),
                "estado": "AC",
                "notas": f"Editado por Locust - {self.username}",
            },
            headers={"Referer": self.host + f"/clientes/{pk}/editar/"},
            name="POST /clientes/<pk>/editar/ (editar)",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 302):
                r.success()
            elif r.status_code == 404:
                r.success()
            else:
                r.failure(f"Status {r.status_code}")

    # ==================== CREAR PRÉSTAMO (POST) ====================

    @task(1)
    def crear_prestamo(self):
        """Crear un préstamo nuevo via formulario POST"""
        if not self.cliente_ids:
            return

        resp = self.client.get("/prestamos/nuevo/", name="GET /prestamos/nuevo/")
        if resp.status_code != 200:
            return

        csrf = _extraer_csrf(resp)
        if not csrf:
            csrf = _extraer_csrf_cookie(self.client)

        cliente_id = random.choice(self.cliente_ids)
        monto = random.choice([5000, 10000, 20000, 50000])
        tasa = random.choice([5, 10, 15, 20])
        cuotas = random.choice([10, 15, 20, 30])
        frecuencia = random.choice(["DI", "SE", "QU", "ME"])
        fecha_hoy = date.today().strftime("%Y-%m-%d")

        with self.client.post(
            "/prestamos/nuevo/",
            data={
                "csrfmiddlewaretoken": csrf,
                "cliente": str(cliente_id),
                "monto_solicitado": str(monto),
                "tasa_interes_porcentaje": str(tasa),
                "cuotas_pactadas": str(cuotas),
                "frecuencia": frecuencia,
                "fecha_inicio": fecha_hoy,
                "notas": f"Test Locust - {self.username}",
            },
            headers={"Referer": self.host + "/prestamos/nuevo/"},
            name="POST /prestamos/nuevo/ (crear)",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 302):
                r.success()
                if r.url and '/prestamos/' in r.url:
                    match = re.search(r'/prestamos/(\d+)/', r.url)
                    if match:
                        self.prestamo_ids.append(int(match.group(1)))
            else:
                r.failure(f"Status {r.status_code}")

    # ==================== COBRAR CUOTA (AJAX POST) ====================

    @task(3)
    def cobrar_cuota(self):
        """Registrar pago de cuota pendiente via AJAX"""
        if not self.cuota_ids:
            resp = self.client.get("/api/cuotas-hoy/", name="GET /api/cuotas-hoy/ (pre-cobro)")
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    self.cuota_ids = [c['id'] for c in data.get('cuotas', [])]
                except Exception:
                    pass
            if not self.cuota_ids:
                return

        cuota_id = self.cuota_ids.pop(0)
        csrf = _extraer_csrf_cookie(self.client)
        metodo = random.choice(["EF", "EF", "EF", "TR", "MX"])

        payload = {
            "metodo_pago": metodo,
            "accion_restante": "ignorar",
        }

        if random.random() < 0.2:
            payload["monto"] = random.choice([500, 1000, 2000, 3000])

        if metodo == "TR":
            payload["referencia_transferencia"] = f"TR-LOCUST-{random.randint(1000, 9999)}"
        elif metodo == "MX":
            payload["referencia_transferencia"] = f"MX-LOCUST-{random.randint(1000, 9999)}"

        with self.client.post(
            f"/api/cobrar/{cuota_id}/",
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "X-CSRFToken": csrf,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": self.host + "/cobros/",
            },
            name="POST /api/cobrar/<pk>/ (cobro)",
            catch_response=True,
        ) as r:
            if r.status_code == 200:
                try:
                    data = r.json()
                    if data.get('success'):
                        r.success()
                    else:
                        r.failure(data.get('message', 'Error desconocido'))
                except Exception:
                    r.success()
            elif r.status_code == 404:
                r.success()
            else:
                r.failure(f"Status {r.status_code}")

    # ==================== CAMBIAR CATEGORÍA CLIENTE (AJAX POST) ====================

    @task(1)
    def cambiar_categoria(self):
        """Cambiar categoría de un cliente via AJAX"""
        if not self.cliente_ids:
            return

        pk = random.choice(self.cliente_ids)
        csrf = _extraer_csrf_cookie(self.client)
        nueva_cat = random.choice(["EX", "RE", "MO", "NU"])

        with self.client.post(
            f"/api/cliente/{pk}/categoria/",
            data=json.dumps({"categoria": nueva_cat}),
            headers={
                "Content-Type": "application/json",
                "X-CSRFToken": csrf,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": self.host + f"/clientes/{pk}/",
            },
            name="POST /api/cliente/<pk>/categoria/",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 404):
                r.success()
            else:
                r.failure(f"Status {r.status_code}")

    # ==================== MARCAR NOTIFICACIÓN LEÍDA ====================

    @task(1)
    def marcar_notificacion_leida(self):
        """Marcar una notificación como leída"""
        resp = self.client.get("/api/notificaciones/", name="GET /api/notificaciones/ (pre-marcar)")
        if resp.status_code != 200:
            return
        try:
            data = resp.json()
            notifs = data.get('notificaciones', [])
            if not notifs:
                return
            nid = notifs[0]['id']
        except Exception:
            return

        with self.client.get(
            f"/notificaciones/{nid}/leida/",
            name="GET /notificaciones/<pk>/leida/",
            catch_response=True,
            headers={"X-Requested-With": "XMLHttpRequest"},
        ) as r:
            if r.status_code in (200, 302, 404):
                r.success()

    # ==================== RENOVAR PRÉSTAMO (POST) ====================

    @task(1)
    def renovar_prestamo(self):
        """Renovar un préstamo existente"""
        if not self.prestamo_ids:
            return

        pk = random.choice(self.prestamo_ids)

        resp = self.client.get(f"/prestamos/{pk}/renovar/", name="GET /prestamos/<pk>/renovar/")
        if resp.status_code != 200:
            return

        csrf = _extraer_csrf(resp)
        if not csrf:
            csrf = _extraer_csrf_cookie(self.client)

        with self.client.post(
            f"/prestamos/{pk}/renovar/",
            data={
                "csrfmiddlewaretoken": csrf,
                "nuevo_monto": str(random.choice([5000, 10000, 20000])),
                "nueva_tasa": str(random.choice([5, 10, 15])),
                "nuevas_cuotas": str(random.choice([10, 15, 20])),
                "nueva_frecuencia": random.choice(["DI", "SE"]),
            },
            headers={"Referer": self.host + f"/prestamos/{pk}/renovar/"},
            name="POST /prestamos/<pk>/renovar/ (renovar)",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 302):
                r.success()
                if pk in self.prestamo_ids:
                    self.prestamo_ids.remove(pk)
                if r.url and '/prestamos/' in r.url:
                    match = re.search(r'/prestamos/(\d+)/', r.url)
                    if match:
                        self.prestamo_ids.append(int(match.group(1)))
            else:
                r.failure(f"Status {r.status_code}")


class AdminUser(HttpUser):
    """
    Simula un admin: todas las operaciones del cobrador + gestión de usuarios,
    auditoría, respaldos, generación de notificaciones.
    """
    weight = 1
    wait_time = between(2, 5)

    def on_start(self):
        """Login como admin (nacho)"""
        self.username = "nacho"
        self.password = "123"
        self.cliente_ids = []
        self.prestamo_ids = []
        self.cuota_ids = []

        response = self.client.get("/login/", name="GET /login/ (admin)")
        csrftoken = _extraer_csrf(response)

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

        # Recopilar datos
        resp = self.client.get("/clientes/", name="GET /clientes/ (admin recopilar)")
        if resp and resp.status_code == 200:
            ids = re.findall(r'/clientes/(\d+)/', resp.text or "")
            self.cliente_ids = list(set(int(x) for x in ids))[:30]

        resp = self.client.get("/prestamos/?estado=AC", name="GET /prestamos/ (admin recopilar)")
        if resp and resp.status_code == 200:
            ids = re.findall(r'/prestamos/(\d+)/', resp.text or "")
            self.prestamo_ids = list(set(int(x) for x in ids))[:30]

        resp = self.client.get("/api/cuotas-hoy/", name="GET /api/cuotas-hoy/ (admin recopilar)")
        if resp and resp.status_code == 200:
            try:
                data = resp.json()
                self.cuota_ids = [c['id'] for c in data.get('cuotas', [])]
            except Exception:
                pass

    # ==================== NAVEGACIÓN ADMIN ====================

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
        self.client.get("/exportar/clientes/", name="GET /exportar/clientes/ (Excel admin)")

    @task(1)
    def exportar_prestamos(self):
        self.client.get("/exportar/prestamos/", name="GET /exportar/prestamos/ (Excel admin)")

    # ==================== COBRAR CUOTA (ADMIN) ====================

    @task(2)
    def cobrar_cuota(self):
        """Admin también cobra cuotas"""
        if not self.cuota_ids:
            resp = self.client.get("/api/cuotas-hoy/", name="GET /api/cuotas-hoy/ (admin pre-cobro)")
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    self.cuota_ids = [c['id'] for c in data.get('cuotas', [])]
                except Exception:
                    pass
            if not self.cuota_ids:
                return

        cuota_id = self.cuota_ids.pop(0)
        csrf = _extraer_csrf_cookie(self.client)

        with self.client.post(
            f"/api/cobrar/{cuota_id}/",
            data=json.dumps({"metodo_pago": "EF", "accion_restante": "ignorar"}),
            headers={
                "Content-Type": "application/json",
                "X-CSRFToken": csrf,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": self.host + "/cobros/",
            },
            name="POST /api/cobrar/<pk>/ (admin cobro)",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 404):
                r.success()
            else:
                r.failure(f"Status {r.status_code}")

    # ==================== CREAR CLIENTE (ADMIN) ====================

    @task(1)
    def crear_cliente(self):
        """Admin crea clientes también"""
        resp = self.client.get("/clientes/nuevo/", name="GET /clientes/nuevo/ (admin)")
        if resp.status_code != 200:
            return

        csrf = _extraer_csrf(resp)
        if not csrf:
            csrf = _extraer_csrf_cookie(self.client)

        with self.client.post(
            "/clientes/nuevo/",
            data={
                "csrfmiddlewaretoken": csrf,
                "nombre": f"Locust_Admin_{random.randint(1, 999)}",
                "apellido": f"{random.choice(APELLIDOS_TEST)}_{random.randint(1000, 9999)}",
                "telefono": f"351{random.randint(1000000, 9999999)}",
                "direccion": f"Av. Admin {random.randint(100, 9999)}",
                "tipo_negocio": "",
                "tipo_comercio": "",
                "limite_credito": str(random.choice([0, 100000, 200000])),
                "ruta": "",
                "dia_pago_preferido": "",
                "categoria": "NU",
                "estado": "AC",
                "notas": "Creado por admin test Locust",
            },
            headers={"Referer": self.host + "/clientes/nuevo/"},
            name="POST /clientes/nuevo/ (admin crear)",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 302):
                r.success()
                if r.url and '/clientes/' in r.url:
                    match = re.search(r'/clientes/(\d+)/', r.url)
                    if match:
                        self.cliente_ids.append(int(match.group(1)))
            else:
                r.failure(f"Status {r.status_code}")

    # ==================== GENERAR NOTIFICACIONES (ADMIN) ====================

    @task(1)
    def generar_notificaciones(self):
        """Generar notificaciones de cuotas vencidas"""
        with self.client.get(
            "/api/generar-notificaciones/",
            name="GET /api/generar-notificaciones/",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 403):
                r.success()

    # ==================== MARCAR TODAS LEÍDAS (ADMIN) ====================

    @task(1)
    def marcar_todas_leidas(self):
        """Marcar todas las notificaciones como leídas"""
        with self.client.get(
            "/notificaciones/todas-leidas/",
            name="GET /notificaciones/todas-leidas/",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 302):
                r.success()
