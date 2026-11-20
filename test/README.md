# Pruebas de NOTVENCE

Instala los requisitos de pruebas dentro del entorno virtual:

```powershell
python -m pip install -r requirements-test.txt
```

Ejecuta la suite desde la raíz del repositorio:

```powershell
python -m unittest discover -s test -v
```

Las pruebas de API reemplazan las dependencias de base de datos y envío de correo; no escriben en MySQL ni envían notificaciones reales.
