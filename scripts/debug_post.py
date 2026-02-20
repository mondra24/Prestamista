import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','prestamos_config.settings')
import django
django.setup()
from django.test import Client
from django.contrib.auth.models import User
from django.urls import reverse

c=Client()
# crear usuario y login
User.objects.filter(username='tempuser').delete()
u=User.objects.create_user('tempuser','temp@example.com','pass1234')
# preparar datos mínimos para crear préstamo
from core.models import Cliente
Cliente.objects.filter(nombre='Temp').delete()
cliente=Cliente.objects.create(nombre='Temp',apellido='User',telefono='123',direccion='x')
# Build post data matching PrestamoForm fields
post={
 'cliente': str(cliente.pk),
 'monto_solicitado': '10000',
 'tasa_interes_porcentaje': '10',
 'cuotas_pactadas': '5',
 'frecuencia': 'SE',
 'fecha_inicio': '2026-02-19',
}
resp=c.post(reverse('core:prestamo_create'), post)
print('status',resp.status_code)
print(resp.content.decode('utf-8')[:4000])
