# Cartera en Mora — App Flask

Gestión de clientes morosos con historial de gestiones, resumen por estado y exportación PDF.

## Variables de entorno (Railway)

| Variable | Descripción | Ejemplo |
|---|---|---|
| `SECRET_KEY` | Clave secreta Flask | `una-clave-larga-aleatoria` |
| `APP_PASSWORD` | Contraseña de acceso a la app | `tuclave2024` |
| `EMAIL_DESTINO` | Tu email para notificaciones | `tu@email.com` |
| `RESEND_API_KEY` | API key de Resend | `re_xxxx...` |
| `EMAIL_FROM` | Email remitente (verificado en Resend) | `noreply@tudominio.com` |
| `RAILWAY_VOLUME_MOUNT_PATH` | Railway lo setea solo si usás volumen | `/data` |

## Deploy en Railway

1. Subir todos los archivos a un repositorio GitHub
2. Crear nuevo proyecto en Railway → "Deploy from GitHub repo"
3. Agregar las variables de entorno
4. (Opcional) Agregar un volumen persistente en `/data` para que los datos sobrevivan los redeploys
5. Listo ✓

## Datos iniciales

La primera vez que inicia, carga automáticamente los 14 clientes del informe original.

## Funcionalidades

- ✅ Login con contraseña
- ✅ Tabla de clientes con edición inline (click en cualquier campo)
- ✅ Filtros por estado y perspectiva de cobro
- ✅ Historial de gestiones expandible por cliente (📝)
- ✅ Dashboard con resumen por estado y perspectiva
- ✅ Exportar PDF completo con resumen
- ✅ Notificaciones por email al cambiar el estado de un cliente (vía Resend)
- ✅ Persistencia en JSON (Railway volume o disco local)
