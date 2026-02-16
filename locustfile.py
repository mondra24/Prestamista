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

Ejecutar contra Railway:
    locust -f locustfile.py --host=https://prestamista-production.up.railway.app

Ejecutar headless (4 usuarios, 2 min):
    locust -f locustfile.py --host=https://prestamista-production.up.railway.app -u 4 -r 2 --run-time 2m --headless
"""
import random
import json
import re
from datetime import date
from locust import HttpUser, task, between, events


# ==================== CONFIGURACIÓN ====================
USUARIOS = [
    ("nacho", "123"),
    ("martin", "123"),
    ("gonza", "123"),
    ("chacho", "123"),
]

TERMINOS_BUSQUEDA = ["mar", "juan", "car", "ana", "pe", "lo", "go", "test", "loc"]

NOMBRES_TEST = ["Locust_Ana", "Locust_Juan", "Locust_Pedro", "Locust_María", "Locust_Carlos",
                "Locust_Laura", "Locust_Diego", "Locust_Sofía", "Locust_Mateo", "Locust_Lucía"]
APELLIDOS_TEST = ["García", "López", "Martínez", "Rodríguez", "Pérez", "Sánchez", "Gómez",
                  "Díaz", "Torres", "Flores"]


def _extraer_csrf(response):
    """Extraer CSRF token de cookies o del HTML."""
    csrf = response.cookies.get("csrftoken", "")
    if not csrf:
        match = re.search(r'csrfmiddlewaretoken.*?value=["\']([^"\']+)', response.text or "")
        if match:
            csrf = match.group(1)
    if not csrf:
        match = re.search(r'name=["\']csrfmiddlewaretoken["\'].*?value=["\']([^"\']+)', response.text or "")
        if match:
            csrf = match.group(1)
    return csrf


def _extraer_csrf_cookie(client):
    """Obtener CSRF de las cookies del cliente."""
    return client.cookies.get("csrftoken", "")


def _hacer_login(client, host, username, password):
    """
    Realizar login y devolver True si fue exitoso.
    Extrae CSRF del HTML del form y envía POST con follow_redirects.
    """
    # GET login page
    resp = client.get("/login/", name="[setup] GET /login/")
    if resp.status_code != 200:
        print(f"  ✗ [{username}] No se pudo cargar /login/ → {resp.status_code}")
        return False

    csrf = _extraer_csrf(resp)
    if not csrf:
        print(f"  ✗ [{username}] No se encontró CSRF token en /login/")
        return False

    # POST login
    login_resp = client.post(
        "/login/",
        data={
            "username": username,
            "password": password,
            "csrfmiddlewaretoken": csrf,
        },
        headers={"Referer": host + "/login/"},
        name="[setup] POST /login/",
        allow_redirects=True,
    )

    # Verificar que redirigió al dashboard (no quedó en /login/)
    final_url = login_resp.url or ""
    if "login" in final_url and login_resp.status_code == 200:
        print(f"  ✗ [{username}] Login FALLIDO (redirigió de vuelta a login)")
        return False

    # Verificar acceso al dashboard
    dash = client.get("/", name="[setup] verificar login")
    if dash.status_code == 200 and "login" not in (dash.url or ""):
        print(f"  ✓ [{username}] Login OK")
        return True

    print(f"  ✗ [{username}] Login no verificado (status={dash.status_code})")
    return False


def _crear_cliente_inicial(client, host, username):
    """Crear un cliente de test y devolver su ID, o None si falla."""
    resp = client.get("/clientes/nuevo/", name="[setup] GET /clientes/nuevo/")
    if resp.status_code != 200:
        print(f"  ✗ [{username}] No se pudo acceder a /clientes/nuevo/ → {resp.status_code}")
        return None

    csrf = _extraer_csrf(resp)
    if not csrf:
        csrf = _extraer_csrf_cookie(client)
    if not csrf:
        print(f"  ✗ [{username}] No se encontró CSRF para crear cliente")
        return None

    nombre = f"Locust_Init_{random.randint(1, 9999)}"
    apellido = f"Test_{random.randint(1000, 9999)}"

    create_resp = client.post(
        "/clientes/nuevo/",
        data={
            "csrfmiddlewaretoken": csrf,
            "nombre": nombre,
            "apellido": apellido,
            "telefono": f"351{random.randint(1000000, 9999999)}",
            "direccion": f"Calle Setup {random.randint(100, 999)}",
            "tipo_negocio": "",
            "tipo_comercio": "",
            "limite_credito": "100000",
            "ruta": "",
            "dia_pago_preferido": "",
            "categoria": "NU",
            "estado": "AC",
            "notas": f"Setup inicial Locust - {username}",
        },
        headers={"Referer": host + "/clientes/nuevo/"},
        name="[setup] POST /clientes/nuevo/",
        allow_redirects=True,
    )

    if create_resp.status_code in (200, 302):
        final_url = create_resp.url or ""
        match = re.search(r'/clientes/(\d+)/', final_url)
        if match:
            cid = int(match.group(1))
            print(f"  ✓ [{username}] Cliente creado ID={cid} ({nombre})")
            return cid

    # Intentar buscar el ID en la lista de clientes
    list_resp = client.get("/clientes/", name="[setup] GET /clientes/ buscar ID")
    if list_resp.status_code == 200:
        ids = re.findall(r'/clientes/(\d+)/', list_resp.text or "")
        if ids:
            cid = int(ids[-1])
            print(f"  ✓ [{username}] Cliente encontrado ID={cid}")
            return cid

    print(f"  ✗ [{username}] No se pudo crear/encontrar cliente (status={create_resp.status_code})")
    return None


def _crear_prestamo_inicial(client, host, username, cliente_id):
    """Crear un préstamo para el cliente dado. Devolver ID o None."""
    resp = client.get("/prestamos/nuevo/", name="[setup] GET /prestamos/nuevo/")
    if resp.status_code != 200:
        return None

    csrf = _extraer_csrf(resp)
    if not csrf:
        csrf = _extraer_csrf_cookie(client)
    if not csrf:
        return None

    fecha_hoy = date.today().strftime("%Y-%m-%d")
    create_resp = client.post(
        "/prestamos/nuevo/",
        data={
            "csrfmiddlewaretoken": csrf,
            "cliente": str(cliente_id),
            "monto_solicitado": "10000",
            "tasa_interes_porcentaje": "10",
            "cuotas_pactadas": "10",
            "frecuencia": "DI",
            "fecha_inicio": fecha_hoy,
            "notas": f"Setup Locust - {username}",
        },
        headers={"Referer": host + "/prestamos/nuevo/"},
        name="[setup] POST /prestamos/nuevo/",
        allow_redirects=True,
    )

    if create_resp.status_code in (200, 302):
        final_url = create_resp.url or ""
        match = re.search(r'/prestamos/(\d+)/', final_url)
        if match:
            pid = int(match.group(1))
            print(f"  ✓ [{username}] Préstamo creado ID={pid} para cliente {cliente_id}")
            return pid

    print(f"  ✗ [{username}] No se pudo crear préstamo (status={create_resp.status_code})")
    return None


def _recopilar_ids(client, username):
    """Buscar IDs existentes de clientes, préstamos y cuotas."""
    cliente_ids = []
    prestamo_ids = []
    cuota_ids = []

    resp = client.get("/clientes/", name="[setup] GET /clientes/ recopilar")
    if resp.status_code == 200:
        ids = re.findall(r'/clientes/(\d+)/', resp.text or "")
        cliente_ids = list(set(int(x) for x in ids))[:30]

    resp = client.get("/prestamos/?estado=AC", name="[setup] GET /prestamos/ recopilar")
    if resp.status_code == 200:
        ids = re.findall(r'/prestamos/(\d+)/', resp.text or "")
        prestamo_ids = list(set(int(x) for x in ids))[:30]

    resp = client.get("/api/cuotas-hoy/", name="[setup] GET /api/cuotas-hoy/ recopilar")
    if resp.status_code == 200:
        try:
            data = resp.json()
            cuota_ids = [c['id'] for c in data.get('cuotas', [])]
        except Exception:
            pass

    print(f"  → [{username}] Datos: {len(cliente_ids)} clientes, {len(prestamo_ids)} préstamos, {len(cuota_ids)} cuotas")
    return cliente_ids, prestamo_ids, cuota_ids


# ==================== COBRADOR ====================

class CobradorUser(HttpUser):
    """
    Simula un cobrador realizando operaciones de lectura Y escritura.
    En on_start: login + creación de datos iniciales para garantizar que
    los POST siempre tengan datos con los cuales trabajar.
    """
    weight = 3
    wait_time = between(1, 3)

    def on_start(self):
        self.username, self.password = random.choice(USUARIOS)
        self.cliente_ids = []
        self.prestamo_ids = []
        self.cuota_ids = []
        self.login_ok = False

        print(f"\n{'='*50}")
        print(f"[CobradorUser] Iniciando como {self.username}...")

        # 1. Login
        if not _hacer_login(self.client, self.host, self.username, self.password):
            return

        self.login_ok = True

        # 2. Recopilar datos existentes
        self.cliente_ids, self.prestamo_ids, self.cuota_ids = _recopilar_ids(
            self.client, self.username
        )

        # 3. Si no hay clientes, crear uno
        if not self.cliente_ids:
            print(f"  [{self.username}] Sin clientes, creando datos iniciales...")
            cid = _crear_cliente_inicial(self.client, self.host, self.username)
            if cid:
                self.cliente_ids.append(cid)
                # Crear préstamo para el cliente
                pid = _crear_prestamo_inicial(self.client, self.host, self.username, cid)
                if pid:
                    self.prestamo_ids.append(pid)
                    # Refrescar cuotas
                    resp = self.client.get("/api/cuotas-hoy/", name="[setup] cuotas post-create")
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            self.cuota_ids = [c['id'] for c in data.get('cuotas', [])]
                        except Exception:
                            pass

        # 4. Si hay clientes pero no préstamos, crear uno
        if self.cliente_ids and not self.prestamo_ids:
            pid = _crear_prestamo_inicial(
                self.client, self.host, self.username, self.cliente_ids[0]
            )
            if pid:
                self.prestamo_ids.append(pid)

        print(f"  [{self.username}] Setup completo: "
              f"{len(self.cliente_ids)}C / {len(self.prestamo_ids)}P / {len(self.cuota_ids)}Q")
        print(f"{'='*50}\n")

    # ==================== NAVEGACIÓN (GET) ====================

    @task(3)
    def ver_dashboard(self):
        if not self.login_ok:
            return
        self.client.get("/", name="GET / (dashboard)")

    @task(3)
    def ver_cobros(self):
        if not self.login_ok:
            return
        self.client.get("/cobros/", name="GET /cobros/")

    @task(2)
    def api_cuotas_hoy(self):
        if not self.login_ok:
            return
        resp = self.client.get("/api/cuotas-hoy/", name="GET /api/cuotas-hoy/")
        if resp.status_code == 200:
            try:
                data = resp.json()
                nuevas = [c['id'] for c in data.get('cuotas', [])]
                if nuevas:
                    self.cuota_ids = nuevas
            except Exception:
                pass

    @task(2)
    def ver_clientes(self):
        if not self.login_ok:
            return
        resp = self.client.get("/clientes/", name="GET /clientes/")
        # Actualizar IDs de clientes
        if resp.status_code == 200:
            ids = re.findall(r'/clientes/(\d+)/', resp.text or "")
            if ids:
                self.cliente_ids = list(set(int(x) for x in ids))[:30]

    @task(2)
    def buscar_cliente(self):
        if not self.login_ok:
            return
        termino = random.choice(TERMINOS_BUSQUEDA)
        self.client.get(f"/api/buscar-clientes/?q={termino}", name="GET /api/buscar-clientes/?q=...")

    @task(1)
    def ver_prestamos(self):
        if not self.login_ok:
            return
        self.client.get("/prestamos/", name="GET /prestamos/")

    @task(1)
    def ver_prestamos_activos(self):
        if not self.login_ok:
            return
        resp = self.client.get("/prestamos/?estado=AC", name="GET /prestamos/?estado=AC")
        if resp.status_code == 200:
            ids = re.findall(r'/prestamos/(\d+)/', resp.text or "")
            if ids:
                self.prestamo_ids = list(set(int(x) for x in ids))[:30]

    @task(1)
    def ver_detalle_cliente(self):
        if not self.login_ok or not self.cliente_ids:
            return
        pk = random.choice(self.cliente_ids)
        with self.client.get(f"/clientes/{pk}/", name="GET /clientes/<pk>/", catch_response=True) as r:
            if r.status_code == 404:
                r.success()

    @task(1)
    def ver_detalle_prestamo(self):
        if not self.login_ok or not self.prestamo_ids:
            return
        pk = random.choice(self.prestamo_ids)
        with self.client.get(f"/prestamos/{pk}/", name="GET /prestamos/<pk>/", catch_response=True) as r:
            if r.status_code == 404:
                r.success()

    @task(1)
    def ver_cierre_caja(self):
        if not self.login_ok:
            return
        self.client.get("/cierre-caja/", name="GET /cierre-caja/")

    @task(1)
    def ver_reportes(self):
        if not self.login_ok:
            return
        self.client.get("/reportes/", name="GET /reportes/")

    @task(1)
    def api_notificaciones(self):
        if not self.login_ok:
            return
        self.client.get("/api/notificaciones/", name="GET /api/notificaciones/")

    # ==================== CREAR CLIENTE (POST) ====================

    @task(3)
    def crear_cliente(self):
        """Crear un cliente nuevo via formulario POST."""
        if not self.login_ok:
            return

        resp = self.client.get("/clientes/nuevo/", name="GET /clientes/nuevo/")
        if resp.status_code != 200:
            return

        csrf = _extraer_csrf(resp)
        if not csrf:
            csrf = _extraer_csrf_cookie(self.client)
        if not csrf:
            return

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
                "limite_credito": str(random.choice([50000, 100000, 200000])),
                "ruta": "",
                "dia_pago_preferido": "",
                "categoria": random.choice(["NU", "RE", "EX"]),
                "estado": "AC",
                "notas": f"Creado por Locust - {self.username}",
            },
            headers={"Referer": self.host + "/clientes/nuevo/"},
            name="POST /clientes/nuevo/ (crear)",
            catch_response=True,
            allow_redirects=True,
        ) as r:
            if r.status_code in (200, 302):
                r.success()
                final_url = r.url or ""
                match = re.search(r'/clientes/(\d+)/', final_url)
                if match:
                    self.cliente_ids.append(int(match.group(1)))
            else:
                r.failure(f"Status {r.status_code}")

    # ==================== EDITAR CLIENTE (POST) ====================

    @task(2)
    def editar_cliente(self):
        """Editar un cliente existente."""
        if not self.login_ok or not self.cliente_ids:
            return

        pk = random.choice(self.cliente_ids)
        resp = self.client.get(f"/clientes/{pk}/editar/", name="GET /clientes/<pk>/editar/")
        if resp.status_code != 200:
            return

        csrf = _extraer_csrf(resp)
        if not csrf:
            csrf = _extraer_csrf_cookie(self.client)
        if not csrf:
            return

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
                "limite_credito": str(random.choice([50000, 100000, 200000])),
                "ruta": "",
                "dia_pago_preferido": "",
                "categoria": random.choice(["NU", "RE", "EX", "MO"]),
                "estado": "AC",
                "notas": f"Editado por Locust - {self.username}",
            },
            headers={"Referer": self.host + f"/clientes/{pk}/editar/"},
            name="POST /clientes/<pk>/editar/",
            catch_response=True,
            allow_redirects=True,
        ) as r:
            if r.status_code in (200, 302):
                r.success()
            elif r.status_code == 404:
                r.success()
                if pk in self.cliente_ids:
                    self.cliente_ids.remove(pk)
            else:
                r.failure(f"Status {r.status_code}")

    # ==================== CREAR PRÉSTAMO (POST) ====================

    @task(2)
    def crear_prestamo(self):
        """Crear un préstamo nuevo via formulario POST."""
        if not self.login_ok or not self.cliente_ids:
            return

        resp = self.client.get("/prestamos/nuevo/", name="GET /prestamos/nuevo/")
        if resp.status_code != 200:
            return

        csrf = _extraer_csrf(resp)
        if not csrf:
            csrf = _extraer_csrf_cookie(self.client)
        if not csrf:
            return

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
            allow_redirects=True,
        ) as r:
            if r.status_code in (200, 302):
                r.success()
                final_url = r.url or ""
                match = re.search(r'/prestamos/(\d+)/', final_url)
                if match:
                    self.prestamo_ids.append(int(match.group(1)))
            else:
                r.failure(f"Status {r.status_code}")

    # ==================== COBRAR CUOTA (AJAX POST) ====================

    @task(4)
    def cobrar_cuota(self):
        """Registrar pago de cuota pendiente via AJAX POST."""
        if not self.login_ok:
            return

        # Si no hay cuotas, refrescar
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
        if not csrf:
            return

        metodo = random.choice(["EF", "EF", "EF", "TR", "MX"])
        payload = {
            "metodo_pago": metodo,
            "accion_restante": "ignorar",
        }
        if random.random() < 0.2:
            payload["monto"] = random.choice([500, 1000, 2000])
        if metodo in ("TR", "MX"):
            payload["referencia_transferencia"] = f"LOCUST-{random.randint(1000, 9999)}"

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
                        r.failure(data.get('message', 'Error en cobro'))
                except Exception:
                    r.success()
            elif r.status_code == 404:
                r.success()
            else:
                r.failure(f"Status {r.status_code}")

    # ==================== CAMBIAR CATEGORÍA (AJAX POST) ====================

    @task(2)
    def cambiar_categoria(self):
        """Cambiar categoría de un cliente via AJAX POST."""
        if not self.login_ok or not self.cliente_ids:
            return

        pk = random.choice(self.cliente_ids)
        csrf = _extraer_csrf_cookie(self.client)
        if not csrf:
            return

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

    # ==================== RENOVAR PRÉSTAMO (POST) ====================

    @task(2)
    def renovar_prestamo(self):
        """Renovar un préstamo existente."""
        if not self.login_ok or not self.prestamo_ids:
            return

        pk = random.choice(self.prestamo_ids)
        resp = self.client.get(f"/prestamos/{pk}/renovar/", name="GET /prestamos/<pk>/renovar/")
        if resp.status_code != 200:
            return

        csrf = _extraer_csrf(resp)
        if not csrf:
            csrf = _extraer_csrf_cookie(self.client)
        if not csrf:
            return

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
            name="POST /prestamos/<pk>/renovar/",
            catch_response=True,
            allow_redirects=True,
        ) as r:
            if r.status_code in (200, 302):
                r.success()
                if pk in self.prestamo_ids:
                    self.prestamo_ids.remove(pk)
                final_url = r.url or ""
                match = re.search(r'/prestamos/(\d+)/', final_url)
                if match:
                    self.prestamo_ids.append(int(match.group(1)))
            elif r.status_code == 404:
                r.success()
                if pk in self.prestamo_ids:
                    self.prestamo_ids.remove(pk)
            else:
                r.failure(f"Status {r.status_code}")

    # ==================== NOTIFICACIONES ====================

    @task(1)
    def marcar_notificacion_leida(self):
        """Marcar una notificación como leída."""
        if not self.login_ok:
            return

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
        ) as r:
            if r.status_code in (200, 302, 404):
                r.success()


# ==================== ADMIN ====================

class AdminUser(HttpUser):
    """
    Simula un admin: gestión de usuarios, auditoría, respaldos,
    generación de notificaciones + operaciones de cobrador.
    """
    weight = 1
    wait_time = between(2, 4)

    def on_start(self):
        self.username = "nacho"
        self.password = "123"
        self.cliente_ids = []
        self.prestamo_ids = []
        self.cuota_ids = []
        self.login_ok = False

        print(f"\n{'='*50}")
        print(f"[AdminUser] Iniciando como {self.username}...")

        if not _hacer_login(self.client, self.host, self.username, self.password):
            return

        self.login_ok = True

        self.cliente_ids, self.prestamo_ids, self.cuota_ids = _recopilar_ids(
            self.client, self.username
        )

        if not self.cliente_ids:
            cid = _crear_cliente_inicial(self.client, self.host, self.username)
            if cid:
                self.cliente_ids.append(cid)
                pid = _crear_prestamo_inicial(self.client, self.host, self.username, cid)
                if pid:
                    self.prestamo_ids.append(pid)

        print(f"  [{self.username}] Admin setup completo: "
              f"{len(self.cliente_ids)}C / {len(self.prestamo_ids)}P / {len(self.cuota_ids)}Q")
        print(f"{'='*50}\n")

    # ==================== NAVEGACIÓN ADMIN (GET) ====================

    @task(2)
    def ver_dashboard(self):
        if not self.login_ok:
            return
        self.client.get("/", name="GET / (admin)")

    @task(2)
    def ver_cobros(self):
        if not self.login_ok:
            return
        self.client.get("/cobros/", name="GET /cobros/ (admin)")

    @task(2)
    def ver_usuarios(self):
        if not self.login_ok:
            return
        self.client.get("/usuarios/", name="GET /usuarios/")

    @task(1)
    def ver_auditoria(self):
        if not self.login_ok:
            return
        self.client.get("/auditoria/", name="GET /auditoria/")

    @task(1)
    def ver_respaldos(self):
        if not self.login_ok:
            return
        self.client.get("/respaldos/", name="GET /respaldos/")

    @task(1)
    def ver_clientes(self):
        if not self.login_ok:
            return
        self.client.get("/clientes/", name="GET /clientes/ (admin)")

    @task(1)
    def ver_reportes(self):
        if not self.login_ok:
            return
        self.client.get("/reportes/", name="GET /reportes/ (admin)")

    @task(1)
    def exportar_clientes(self):
        if not self.login_ok:
            return
        self.client.get("/exportar/clientes/", name="GET /exportar/clientes/ (Excel)")

    @task(1)
    def exportar_prestamos(self):
        if not self.login_ok:
            return
        self.client.get("/exportar/prestamos/", name="GET /exportar/prestamos/ (Excel)")

    # ==================== CREAR CLIENTE (ADMIN POST) ====================

    @task(2)
    def crear_cliente(self):
        if not self.login_ok:
            return

        resp = self.client.get("/clientes/nuevo/", name="GET /clientes/nuevo/ (admin)")
        if resp.status_code != 200:
            return

        csrf = _extraer_csrf(resp)
        if not csrf:
            csrf = _extraer_csrf_cookie(self.client)
        if not csrf:
            return

        with self.client.post(
            "/clientes/nuevo/",
            data={
                "csrfmiddlewaretoken": csrf,
                "nombre": f"Locust_Adm_{random.randint(1, 999)}",
                "apellido": f"{random.choice(APELLIDOS_TEST)}_{random.randint(1000, 9999)}",
                "telefono": f"351{random.randint(1000000, 9999999)}",
                "direccion": f"Av Admin {random.randint(100, 9999)}",
                "tipo_negocio": "",
                "tipo_comercio": "",
                "limite_credito": str(random.choice([100000, 200000])),
                "ruta": "",
                "dia_pago_preferido": "",
                "categoria": "NU",
                "estado": "AC",
                "notas": "Admin test Locust",
            },
            headers={"Referer": self.host + "/clientes/nuevo/"},
            name="POST /clientes/nuevo/ (admin)",
            catch_response=True,
            allow_redirects=True,
        ) as r:
            if r.status_code in (200, 302):
                r.success()
                final_url = r.url or ""
                match = re.search(r'/clientes/(\d+)/', final_url)
                if match:
                    self.cliente_ids.append(int(match.group(1)))
            else:
                r.failure(f"Status {r.status_code}")

    # ==================== COBRAR CUOTA (ADMIN POST) ====================

    @task(2)
    def cobrar_cuota(self):
        if not self.login_ok:
            return

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
        if not csrf:
            return

        with self.client.post(
            f"/api/cobrar/{cuota_id}/",
            data=json.dumps({"metodo_pago": "EF", "accion_restante": "ignorar"}),
            headers={
                "Content-Type": "application/json",
                "X-CSRFToken": csrf,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": self.host + "/cobros/",
            },
            name="POST /api/cobrar/<pk>/ (admin)",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 404):
                r.success()
            else:
                r.failure(f"Status {r.status_code}")

    # ==================== GENERAR NOTIFICACIONES (ADMIN) ====================

    @task(1)
    def generar_notificaciones(self):
        if not self.login_ok:
            return
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
        if not self.login_ok:
            return
        with self.client.get(
            "/notificaciones/todas-leidas/",
            name="GET /notificaciones/todas-leidas/",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 302):
                r.success()
