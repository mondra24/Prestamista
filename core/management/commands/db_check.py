"""
Comando de diagnóstico de base de datos.
Verifica que la app esté conectada a PostgreSQL y NO a SQLite efímero.
Imprime info útil en los logs de deploy de Railway.
"""
import os
import sys
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Verifica la conexión a la base de datos antes de migrar'

    def handle(self, *args, **options):
        db_config = settings.DATABASES['default']
        engine = db_config.get('ENGINE', '')
        name = db_config.get('NAME', '')
        host = db_config.get('HOST', 'N/A')
        port = db_config.get('PORT', 'N/A')

        self.stdout.write("=" * 60)
        self.stdout.write("  DIAGNÓSTICO DE BASE DE DATOS")
        self.stdout.write("=" * 60)
        self.stdout.write(f"  ENGINE : {engine}")
        self.stdout.write(f"  HOST   : {host}")
        self.stdout.write(f"  PORT   : {port}")
        self.stdout.write(f"  NAME   : {name}")

        database_url = os.environ.get('DATABASE_URL', '')
        database_public_url = os.environ.get('DATABASE_PUBLIC_URL', '')

        if database_url:
            # Mostrar solo el host, no la password
            masked = database_url.split('@')[-1] if '@' in database_url else '(set)'
            self.stdout.write(f"  DATABASE_URL     : ...@{masked}")
        else:
            self.stdout.write(self.style.ERROR("  DATABASE_URL     : *** NO CONFIGURADA ***"))

        if database_public_url:
            masked = database_public_url.split('@')[-1] if '@' in database_public_url else '(set)'
            self.stdout.write(f"  DATABASE_PUBLIC_URL : ...@{masked}")
        else:
            self.stdout.write(f"  DATABASE_PUBLIC_URL : no configurada")

        self.stdout.write("=" * 60)

        # FRENO DE SEGURIDAD: Si estamos en Railway y usando SQLite, ABORTAR
        # Detectar Railway con TODAS las variables posibles
        railway_vars = [
            'RAILWAY_ENVIRONMENT', 'RAILWAY_PUBLIC_DOMAIN',
            'RAILWAY_SERVICE_ID', 'RAILWAY_PROJECT_ID',
            'RAILWAY_REPLICA_ID', 'RAILWAY_DEPLOYMENT_ID',
            'RAILWAY_ENVIRONMENT_NAME', 'RAILWAY_GIT_BRANCH',
            'RAILWAY_STATIC_URL', 'RAILWAY_ENVIRONMENT_ID',
        ]
        is_railway = any(os.environ.get(var) for var in railway_vars)

        if 'sqlite' in engine.lower():
            if is_railway:
                self.stderr.write(self.style.ERROR(
                    "\n"
                    "╔══════════════════════════════════════════════════════╗\n"
                    "║  ¡¡¡ ERROR CRÍTICO !!!                              ║\n"
                    "║                                                      ║\n"
                    "║  La app está usando SQLite en Railway.               ║\n"
                    "║  SQLite se BORRA en cada deploy.                     ║\n"
                    "║                                                      ║\n"
                    "║  SOLUCIÓN:                                           ║\n"
                    "║  1. Ir a Railway → tu servicio web → Variables       ║\n"
                    "║  2. Agregar: DATABASE_URL = ${{Postgres.DATABASE_URL}} ║\n"
                    "║  3. Re-deploy                                        ║\n"
                    "╚══════════════════════════════════════════════════════╝\n"
                ))
                sys.exit(1)
            elif not settings.DEBUG:
                # No es Railway detectado, pero tampoco es DEBUG → producción
                self.stderr.write(self.style.ERROR(
                    "\n"
                    "╔══════════════════════════════════════════════════════╗\n"
                    "║  ¡¡¡ ERROR CRÍTICO !!!                              ║\n"
                    "║                                                      ║\n"
                    "║  La app está usando SQLite en modo producción.       ║\n"
                    "║  Los datos se PERDERÁN en cada deploy.               ║\n"
                    "║                                                      ║\n"
                    "║  SOLUCIÓN:                                           ║\n"
                    "║  Configurar la variable de entorno DATABASE_URL      ║\n"
                    "║  apuntando a una base PostgreSQL persistente.        ║\n"
                    "╚══════════════════════════════════════════════════════╝\n"
                ))
                sys.exit(1)

        if 'postgresql' in engine.lower() or 'postgres' in engine.lower():
            # Intentar conectar y contar registros
            try:
                from django.db import connection
                with connection.cursor() as cursor:
                    # Verificar si las tablas existen
                    cursor.execute(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name LIKE 'core_%'"
                    )
                    table_count = cursor.fetchone()[0]
                    self.stdout.write(f"  Tablas core_*: {table_count}")

                    if table_count > 0:
                        try:
                            cursor.execute("SELECT COUNT(*) FROM core_cliente")
                            clientes = cursor.fetchone()[0]
                            cursor.execute("SELECT COUNT(*) FROM core_prestamo")
                            prestamos = cursor.fetchone()[0]
                            cursor.execute("SELECT COUNT(*) FROM core_cuota")
                            cuotas = cursor.fetchone()[0]
                            cursor.execute("SELECT COUNT(*) FROM django_migrations")
                            migrations = cursor.fetchone()[0]
                            self.stdout.write(f"  Clientes   : {clientes}")
                            self.stdout.write(f"  Préstamos  : {prestamos}")
                            self.stdout.write(f"  Cuotas     : {cuotas}")
                            self.stdout.write(f"  Migraciones: {migrations}")
                        except Exception:
                            self.stdout.write("  (tablas aún no creadas, primera migración)")
                    else:
                        self.stdout.write("  (sin tablas core_*, primera migración)")

                self.stdout.write(self.style.SUCCESS("\n  ✓ Conexión a PostgreSQL OK"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"\n  ✗ Error conectando a PostgreSQL: {e}"))
                sys.exit(1)
        
        self.stdout.write("=" * 60)
