# Desplegar NOTVENCE en Render

## Requisitos

- Un MySQL externo accesible desde Render. Render Blueprints administra PostgreSQL, no MySQL.
- Un usuario MySQL dedicado para la aplicación, con acceso solo a la base de NOTVENCE.
- Acceso a Render y al repositorio GitHub.

No uses el MySQL de `localhost`: Render no puede conectarse a tu computadora. El proveedor externo debe permitir conexiones desde Render y, si ofrece TLS, debes configurarlo con su certificado CA.

## Antes de publicar

Hay credenciales OAuth versionadas en Git. Revoca el cliente OAuth y el consentimiento/token anterior desde Google Cloud Console y la configuración de seguridad de la cuenta Google. Quitar los archivos del commit actual no los borra del historial de Git ni invalida las credenciales filtradas.

Los archivos locales se conservan; Git deja de incluirlos en los siguientes commits. No subas `.env`, archivos OAuth ni tokens al repositorio.

## Crear el servicio

1. Confirma los cambios y súbelos a GitHub.
2. En Render, elige **New → Blueprint** y conecta el repositorio `lunafulminante/notvene-copia`.
3. Render leerá `render.yaml`. En la configuración del servicio, introduce las variables de MySQL:
   - `NOTVENCE_DB_HOST`
   - `NOTVENCE_DB_PORT`
   - `NOTVENCE_DB_NAME`
   - `NOTVENCE_DB_USER`
   - `NOTVENCE_DB_PASSWORD`
4. Si el proveedor requiere una CA para TLS, súbela como secret file y establece `NOTVENCE_DB_SSL_CA` con la ruta del archivo.
5. Render genera `NOTVENCE_JWT_SECRET`. El correo queda desactivado inicialmente.
6. Despliega y comprueba `https://<servicio>.onrender.com/health`; debe responder `{"status":"ok"}`.

La app también necesita conectarse al MySQL externo desde el entorno de Render. Si el proveedor usa una lista de IP permitidas, añade las direcciones de salida que Render muestra para el servicio.

## Notificaciones Gmail

Después de revocar las credenciales antiguas, crea y autoriza credenciales OAuth nuevas. Guarda el contenido JSON del token como variable secreta `NOTVENCE_GMAIL_TOKEN_JSON` en Render y cambia `NOTVENCE_EMAIL_ENABLED` a `true`. No pegues ese JSON en GitHub ni en el chat.

## App móvil

Al compilar/publicar la app móvil, configura `EXPO_PUBLIC_API_URL` como:

```text
https://<servicio>.onrender.com/api
```

La compilación móvil se publica aparte; Render aloja el backend y la interfaz web.
