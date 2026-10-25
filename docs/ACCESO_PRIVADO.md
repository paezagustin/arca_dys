# Acceso privado y webhook público

La interfaz de ARCA DYS se utiliza por la LAN o por Tailscale ya instalado.
Ngrok debe exponer exclusivamente el webhook que realmente recibe Mercado Pago.
Esta política se configura en el agente existente; el código de permisos de
pantallas no es una barrera suficiente para un túnel público.

## Instalación comprobada el 25/10/2026

Se inventariaron los contenedores, redes, montajes, puertos y configuración
efectiva antes de cambiar el acceso. El Compose versionado difería de los
contenedores existentes y no se utilizó para reemplazar todo el stack.

El agente ngrok instalado aceptó una Traffic Policy que devuelve 403 cuando:

- El método no es POST.
- La ruta normalizada no coincide exactamente con el webhook utilizado.
- La ruta original no coincide exactamente con esa misma ruta.

El historial observado utilizaba solamente la ruta heredada con token.
No se habilitó automáticamente la ruta firmada adicional. Se conservaron el
dominio, el token existente y los controles de la aplicación.

La política contiene una ruta con credenciales. Su archivo real, el archivo
de autenticación del agente, los respaldos y el overlay efectivo permanecen
fuera de Git, bajo los directorios privados de configuración y estado del
usuario de la Raspberry. No deben copiarse al repositorio.

El puerto de la aplicación está enlazado a direcciones concretas de loopback,
LAN y Tailscale. El inspector de ngrok está limitado a loopback. No se
modificaron el router, Tailscale, PostgreSQL ni otros servicios.

## Cookies HTTP privadas

Por defecto, las cookies productivas siguen requiriendo HTTPS. La excepción
para HTTP se habilita únicamente configurando ambas variables:

- ARCA_HTTP_COOKIE_HOSTS: hosts de destino explícitos, separados por comas.
- ARCA_HTTP_COOKIE_CLIENT_NETWORKS: redes CIDR de clientes explícitas, separadas por comas.

El host y la dirección cliente deben coincidir con las listas. HTTPS conserva
Secure. Una dirección cliente ausente o inválida, una red mal configurada o un
host desconocido no reciben la excepción. El desarrollo mantiene su
comportamiento anterior.

El helper no utiliza X-Forwarded-For ni X-Forwarded-Host para ampliar las listas.
Debe conservarse también la configuración de proxies de confianza de Uvicorn;
no configurar FORWARDED_ALLOW_IPS=*.

Se mantienen HttpOnly, SameSite y CSRF. La excepción no habilita rutas públicas,
no cambia credenciales ni modifica facturación o Mercado Pago.

## Validación realizada

- 83 solicitudes por el dominio público: 74 rechazos 403 en ngrok y nueve
  respuestas 400 al enviar JSON deliberadamente inválido al webhook exacto.
- Rutas administrativas, métodos distintos de POST, rutas codificadas,
  sufijos, parámetros y cabeceras alternativas comprobados.
- Token heredado incorrecto y firma ausente rechazados con 401 directamente
  por la aplicación.
- Pantallas y sesiones verificadas desde otra PC por LAN y Tailscale.
- Formulario sin CSRF rechazado con 403; CSRF correcto con identificador no
  numérico rechazado con 422 antes de crear una operación fiscal.
- Siete pruebas de transporte de cookies, sin importar servicios de negocio.
- Huellas idénticas en nueve tablas comerciales y código fiscal/MP conservado.
- Usuario confirmó funcionamiento posterior al cambio.

No se emitieron facturas, se modificaron pagos ni se fabricaron notificaciones
válidas. No se reinició la Raspberry. La comprobación UPnP fue de lectura;
no verifica por sí sola todas las reglas manuales del router.

## Operación y recuperación

En la instalación inventariada, el script privado
~/.config/arca-dys-access/apply.sh utiliza el Compose original y el overlay
efectivo. Actúa únicamente sobre fastapi y ngrok, sin descargar imágenes,
reconstruir dependencias ni arrancar servicios dependientes.

El informe privado de esa instalación contiene las rutas concretas de
respaldo y dos recuperaciones: retirar solo el ajuste de cookies, o recuperar
todo el estado de acceso anterior. Esta última opción vuelve a abrir la
interfaz pública como estaba antes.

La primera aplicación utilizó una imagen derivada de la imagen instalada con
solo estos archivos: app/main.py, app/api/access.py y
app/core/access_cookies.py. Este commit incorpora esos mismos cambios al código
fuente. Publicar el commit no reconstruye ni reinicia producción.

Una actualización futura debe conservar el overlay, la política y las listas
privadas, y revisar la referencia de imagen fijada en el overlay. El Compose
original por sí solo no incorpora la política privada. No publicar archivos
privados para resolver esa diferencia.

## Dependencias del repositorio

La publicacion incluye la actualizacion autorizada a Certifi 2026.10.19 y
Pillow 13.0.0 para resolver la auditoria del CI. Se comprueban x86_64 y ARM64.
Esto no cambia las dependencias de la imagen que ya funciona en la Raspberry.
