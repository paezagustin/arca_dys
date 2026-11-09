# ARCA DYS como aplicación web en la LAN

La dirección prevista es `https://arcadys.dulceysalado.ar`. La instalación abre
Facturación en modo standalone en los navegadores compatibles. Gestión, Resumen,
Sueldos y Fiados conservan el acceso familiar. El manifiesto y los iconos son
estáticos. La app usa la red para todos los datos y formularios, sin service
worker ni caché offline. Las páginas, la sesión y los PDF conservan `no-store`.

## Auditoría previa al despliegue

El 07/11/2026, Google Public DNS devolvió los servidores autoritativos de
Cloudflare y `NXDOMAIN` para `arcadys.dulceysalado.ar` (A, AAAA, CNAME y CAA),
`_acme-challenge.arcadys.dulceysalado.ar` (TXT y CNAME) y un nombre aleatorio
de control (A y AAAA). La consulta CAA al dominio base no devolvió registros.
Esto describe las respuestas públicas observadas. Todavía hay que verificar
la zona y los túneles en el panel de Cloudflare, y la red efectiva de la Pi.

Ejecutar este inventario de lectura en la Raspberry. Guardar la salida en un
lugar privado. Evitar `docker inspect` sin filtro, `docker compose config` sin
`--quiet` y archivos de configuración que incluyan credenciales.

```bash
docker compose ls
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker network ls
docker volume ls
for id in $(docker ps -q); do
  docker inspect --format '{{.Name}} proyecto={{index .Config.Labels "com.docker.compose.project"}} servicio={{index .Config.Labels "com.docker.compose.service"}} compose={{index .Config.Labels "com.docker.compose.project.config_files"}} red={{.HostConfig.NetworkMode}}{{range $name, $_ := .NetworkSettings.Networks}} {{$name}}{{end}}{{range .Mounts}}{{println}}{{.Source}} -> {{.Destination}}{{end}}' "$id"
done
ip -br address
ip -4 route
ip -6 route
sudo ss -ltnup
systemctl list-sockets --all
sudo nft list ruleset
sudo iptables -S
sudo iptables -t nat -S
sudo ip6tables -S
sudo ip6tables -t nat -S
```

- Identificar en Portainer quién administra cada stack, su revisión, montajes,
  redes, puertos y archivos efectivos. Registrar estado y pruebas de salud de
  FastAPI, PostgreSQL, ngrok, Pi-hole, dnscrypt, Cloudflared, BookStack, Uptime
  Kuma y los demás servicios. Contrastar con el Compose versionado. Para el
  acceso previo de ARCA DYS, consultar [acceso privado y webhook](ACCESO_PRIVADO.md).
- Confirmar la reserva de `192.168.0.80`, la interfaz y el prefijo autorizado,
  y que el socket IPv4 `192.168.0.80:443` esté libre. Un bind wildcard en 443
  también puede ocuparlo. Identificar 80 y 8001, IPv6, Tailscale, redes de
  invitados y reglas del router de NAT, UPnP y firewall WAN IPv6. Validar que
  los clientes consulten Pi-hole y que este resuelva sus otros nombres locales.
- En Cloudflare revisar registros explícitos y wildcard, posibles delegaciones
  de `_acme-challenge`, CAA y todos los hostnames publicados de los túneles,
  incluidos comodines y reglas finales que reenvíen al backend. El webhook de
  ngrok debe conservar la política exacta de método y ruta de la instalación.
  Revisar el upstream real del webhook antes de tocar un listener alternativo.
- Si hay un proxy existente que pueda usar DNS-01, el bind indicado y el mismo
  control por origen sin afectar a otros stacks, evaluar su reutilización.
  Si hay un conflicto o se requiere un cambio compartido de impacto incierto,
  detenerse y resolverlo antes de seguir.

## Configuración candidata

El [Compose separado](../deploy/pwa/compose.yml) usa Traefik oficial fijado por
digest. Traefik incluye el proveedor Cloudflare de DNS-01 y automatiza la emisión
y renovación en el mismo proceso. Caddy requeriría una imagen con el módulo
Cloudflare incorporado. El proveedor de archivos evita el socket de Docker y
la detección de otros stacks. El modo host permite llegar al FastAPI de loopback
sin publicar otro puerto. El único listener del proxy es `192.168.0.80:443` IPv4.
La [ruta](../deploy/pwa/routes.yml) comprueba el hostname y el origen de la
conexión TCP, excluye a la propia Pi y no confía en `X-Forwarded-For` del cliente.
Aplicar estos archivos solo si el inventario confirma las direcciones y el
prefijo `/24`. Si hay segmentos no autorizados dentro del prefijo, delimitar las
redes o dispositivos autorizados antes de continuar.

El firewall del host debe limitar el acceso a la interfaz y orígenes autorizados.
Si la Pi administra filtros con nftables directo, este ejemplo es una tabla
dedicada que solo agrega rechazos para el destino nuevo. Sustituir `eth0` y el
prefijo por los datos verificados. Revisar la persistencia con el mecanismo que
administra el firewall y validar después de recargarlo. Si el firewall usa otro
gestor, agregar el equivalente con ese gestor. El router debe carecer de rutas
WAN hacia ese listener y hacia el backend.

```nft
table inet arca_dys_pwa {
  chain input {
    type filter hook input priority -10; policy accept;
    ip daddr 192.168.0.80 tcp dport 443 iifname != "eth0" drop
    ip daddr 192.168.0.80 tcp dport 443 ip saddr != 192.168.0.0/24 drop
  }
}
```

Guardar esas reglas revisadas en un archivo privado `firewall.nft`. Comprobarlo
con `sudo nft -c -f firewall.nft` antes de cargarlo con `sudo nft -f firewall.nft`.
El backend debe quedar enlazado a `127.0.0.1:8001` y aislado de otras redes
Docker ajenas. Solo el agente ngrok ya autorizado conserva su acceso interno
según la política del webhook. Eliminar los accesos alternativos LAN/Tailscale
al backend al final del corte, después de verificar HTTPS y confirmar que el
webhook no depende de ellos. Si el acceso anterior se implementa con un socket
dedicado, registrar si estaba habilitado, detener el socket y su servicio, y
volver a comprobar `ss` y el puerto publicado. Si el puerto 8001 aparece en una
dirección wildcard, un socket IPv6 o una publicación directa de Docker, resolver
esa exposición antes de dar el corte por terminado.

## Preparación y corte manual

1. Respaldar privadamente la configuración efectiva, el estado del firewall y
   el registro previo de Pi-hole, si existiera. Guardar la referencia y una
   copia de la imagen web instalada. Conservar intacta la política de ngrok.
   Ensayar con la imagen derivada y datos ficticios antes de aplicarla.
2. Desplegar solo los archivos PWA sobre la imagen efectiva. Evitar una
   actualización general de `main` si esa imagen corresponde a otro esquema.
   Usar el gestor del proyecto original y añadir un override exclusivo de
   imagen. El ejemplo siguiente supone que el inventario confirmó el servicio
   `fastapi`, el contenedor `fastapi_app` y la ruta `/app/app`. El checkout
   revisado debe contener los cambios PWA.

   ```bash
   umask 077
   stamp=$(date -u +%Y%m%dT%H%M%SZ)
   state="$HOME/.config/arca-dys-pwa"
   install -d -m 0700 "$state"
   candidate=$(mktemp -d "$state/image.XXXXXX")
   previous="arca-dys-local:before-pwa-$stamp"
   next="arca-dys-local:pwa-$stamp"
   docker image tag "$(docker inspect -f '{{.Image}}' fastapi_app)" "$previous"
   docker save -o "$state/before-pwa-$stamp.tar" "$previous"
   git archive HEAD app/assets/manifest.json app/assets/pwa app/templates/pwa_head.html | tar -x -C "$candidate"
   cat > "$candidate/Dockerfile" <<'EOF'
   ARG BASE_IMAGE
   FROM ${BASE_IMAGE}
   COPY app/assets/manifest.json /app/app/assets/manifest.json
   COPY app/assets/pwa/ /app/app/assets/pwa/
   COPY app/templates/pwa_head.html /app/app/templates/pwa_head.html
   RUN python -c 'from pathlib import Path; p=Path("/app/app/templates/base.html"); html=p.read_text(encoding="utf-8"); assert html.count("</head>")==1 and "pwa_head.html" not in html and "rel=\"manifest\"" not in html; p.write_text(html.replace("</head>", "{% include \"pwa_head.html\" %}\n</head>"), encoding="utf-8")'
   EOF
   docker build --network none --build-arg "BASE_IMAGE=$previous" -t "$next" "$candidate"
   printf 'services:\n  fastapi:\n    image: %s\n' "$next" > "$state/image.yml"
   printf 'services:\n  fastapi:\n    image: %s\n' "$previous" > "$state/rollback.yml"
   ```

   En Bash, reemplazar las rutas, el proyecto y los `-f` por los que realmente
   usa la instalación. Antes de actualizar, comprobar que el comando conserva
   los archivos originales y el overlay privado de acceso. Si Portainer es el
   dueño exclusivo del stack, gestionar allí el mismo cambio acotado de imagen.

   ```bash
   app_compose=(docker compose -p PROYECTO --env-file /ruta/real/.env.prod -f /ruta/real/compose.yml -f /ruta/real/overlay.yml)
   "${app_compose[@]}" -f "$state/image.yml" config --quiet
   "${app_compose[@]}" -f "$state/image.yml" up -d --no-deps --no-build --pull never fastapi
   ```

3. Crear un token API dedicado en Cloudflare con `Zone:Read` y `DNS:Edit`,
   limitado a la zona `dulceysalado.ar`. Estos comandos presuponen el Docker
   rootful de la Pi sin remapeo de UID. El proceso Traefik necesita que su UID
   efectivo pueda leer el token y escribir el estado. Crear archivos privados
   sin sobrescribir el estado si ya existe.

   ```bash
   proxy_state=/var/lib/arca-dys-pwa
   token_file=/etc/arca-dys-pwa/cloudflare-token
   sudo install -d -o root -g root -m 0700 "$proxy_state" "$proxy_state/staging" "$proxy_state/production" /etc/arca-dys-pwa
   for file in "$proxy_state/staging/acme.json" "$proxy_state/production/acme.json" "$token_file"; do
     sudo test -e "$file" || sudo install -o root -g root -m 0600 /dev/null "$file"
   done
   sudoedit "$token_file"
   ```

   Preparar `$state/proxy.env` con modo `0600`, valores absolutos para
   `PWA_CLOUDFLARE_TOKEN_FILE=/etc/arca-dys-pwa/cloudflare-token` y
   `PWA_ACME_STATE=/var/lib/arca-dys-pwa/staging`, y el correo en `PWA_ACME_EMAIL`.
   El proxy requiere salida DNS hacia los resolvers y autoritativos, y HTTPS
   hacia Cloudflare y Let's Encrypt.

   ```bash
   pwa_compose=(docker compose --env-file "$state/proxy.env" -f deploy/pwa/compose.yml)
   "${pwa_compose[@]}" config --quiet
   "${pwa_compose[@]}" up -d https
   "${pwa_compose[@]}" ps
   ```

   Confirmar en privado la emisión staging. Luego cambiar `PWA_ACME_STATE` a
   `/var/lib/arca-dys-pwa/production`, fijar `PWA_ACME_DIRECTORY=https://acme-v02.api.letsencrypt.org/directory`
   y ejecutar `up -d https` otra vez. Guardar y respaldar los directorios ACME
   fuera de Git porque contienen claves privadas. Conservar el estado y el token
   vigente para que Traefik renueve automáticamente.

   Para el arranque de producción en la Pi, instalar `prepare-https.sh` en
   `/etc/arca-dys-pwa/` y `arca-dys-pwa-https.service` en
   `/etc/systemd/system/`. El servicio espera la IP de `eth0`, carga la tabla
   privada desde `/etc/arca-dys-pwa/firewall.nft` y arranca Traefik con
   `production.env`. Activarlo con `sudo systemctl daemon-reload` y
   `sudo systemctl enable --now arca-dys-pwa-https.service`. Compose mantiene
   `restart: "no"` para que el proxy siempre pase por esa preparación.
   Registrar el vencimiento inicial y verificar que se extienda tras el primer
   ciclo. Una emisión staging comprueba DNS-01, pero no la confianza del cliente.
4. En Pi-hole agregar solo un registro DNS local A
   `arcadys.dulceysalado.ar → 192.168.0.80`. El certificado usa el TXT temporal
   de DNS-01. Mantener el hostname de la interfaz sin A, AAAA o CNAME públicos.
   Desde otra PC de la LAN, probar primero con `--resolve` y después por Pi-hole,
   ambos con validación de certificado.

   ```bash
   dig @192.168.0.80 arcadys.dulceysalado.ar A +short
   dig @192.168.0.80 arcadys.dulceysalado.ar AAAA +short
   for type in A AAAA CNAME; do dig @1.1.1.1 arcadys.dulceysalado.ar "$type"; done
   curl --resolve arcadys.dulceysalado.ar:443:192.168.0.80 -fsSI https://arcadys.dulceysalado.ar/assets/manifest.json
   curl -fsS -D - -o /dev/null https://arcadys.dulceysalado.ar/page/invoice | grep -Ei '^(HTTP/|cache-control:)'
   openssl s_client -connect 192.168.0.80:443 -servername arcadys.dulceysalado.ar -verify_hostname arcadys.dulceysalado.ar -verify_return_error </dev/null
   ```

## Validación del corte

- Desde dos equipos LAN, confirmar resolución A, ausencia de AAAA para la app,
  cadena TLS, sesión `Secure`/`HttpOnly`, navegación sin redirecciones a HTTP y
  acceso familiar. Probar formulario y PDF de prueba en un entorno simulado.
  En producción usar vistas de lectura y, si corresponde, un PDF ya emitido.
  Si un redirect de FastAPI usa `http`, revisar el origen que realmente ve
  Uvicorn y sus proxies de confianza. Cualquier ajuste debe limitarse al
  intermediario verificado. `FORWARDED_ALLOW_IPS=*` ampliaría esa confianza a
  otros procesos y contenedores.
- Probar Android con el DNS privado y Chrome/Brave con el DNS seguro que use el
  dispositivo. Un proveedor externo que omita Pi-hole puede devolver NXDOMAIN.
  En la Wi-Fi autorizada, usar el DNS entregado por la red o un resolver que
  conozca la zona local. Safari e iOS también deben usar esa resolución.
- Tras retirar el acceso alternativo, verificar desde LAN que el puerto 8001
  no responda y que no haya listeners del proxy en IPv6 o Tailscale. Desde
  invitados/Tailscale y desde datos móviles con Wi-Fi y VPN apagados, probar la
  URL. Desde una red externa, intentar además con `curl --resolve` hacia las IP
  WAN IPv4 e IPv6 del equipo o router si existen, para separar DNS de alcance
  de red. Comprobar que las rutas de interfaz estén bloqueadas en ngrok y en
  los hostnames de Cloudflared, sin enviar POST al webhook productivo.
- Comparar estado de los servicios y sus monitores con el inventario. Verificar
  el webhook a través de su política efectiva y la recepción natural de eventos
  autorizados. Si algo falla, recuperar el acceso anterior antes de cerrar.

## Instalar en el teléfono

Hacer la prueba de aceptación desde `https://arcadys.dulceysalado.ar` en la
Wi-Fi autorizada. HTTPS protege las sesiones y los datos fiscales en tránsito.
Algunos navegadores también permiten añadir sitios HTTP a la pantalla de
inicio. La opción del menú y la forma de apertura dependen del navegador.
[Instalación web en Android](https://chromium.googlesource.com/experimental/chromium/src/+/HEAD/docs/webapps/README.md)

Para diagnosticar la versión servida, abrir `/assets/manifest.json` en el mismo
host y puerto de ARCA DYS. Debe devolver JSON con `name` igual a `ARCA DYS`,
`display` igual a `standalone` y `start_url` igual a `/page/invoice`. Si devuelve
404 o una página HTML, comprobar qué imagen está sirviendo el sitio y si la
ruta del manifiesto llega a FastAPI.

- **Android Chrome.** En la Wi-Fi autorizada, abrir Facturación en la URL HTTPS.
  En **⋮**, elegir **Instalar aplicación** o **Instalar y crear acceso directo**
  y luego **Instalar**. Abrir el icono y comprobar que inicia en Facturación.
  [Ayuda de Chrome](https://support.google.com/chrome/answer/9658361?co=GENIE.Platform%3DAndroid&hl=es)
- **Android Brave.** Probar **⋮ → Añadir a pantalla de inicio** y elegir
  **Instalar** si aparece. Si el icono conserva la barra de direcciones en el
  Moto G52, usar Chrome para el modo standalone. [Incidencia de Brave](https://github.com/brave/brave-browser/issues/56133)
- **iPhone Safari.** Abrir la misma URL en Facturación, tocar **Compartir →
  Añadir a pantalla de inicio**, activar **Abrir como app web** si aparece y
  tocar **Añadir**. Abrir el icono, navegar a Gestión y volver a Facturación.
  [Guía de Apple](https://support.apple.com/es-es/guide/iphone/iphea86e5236/ios)
- **Windows Chrome.** Usar el sitio desde una pestaña o instalarlo desde el
  menú de Chrome. Comprobar navegación, apertura desde el icono y descarga.

## Recuperación

Detener el servicio con `sudo systemctl disable --now arca-dys-pwa-https.service`
antes de retirar el acceso. Si el proxy se inició directamente desde Compose,
detenerlo con `"${pwa_compose[@]}" stop https`. Revertir la entrada
local de Pi-hole y retirar la tabla dedicada, si se usó, con
`sudo nft delete table inet arca_dys_pwa`. Retirar también su configuración
persistente. Recuperar el acceso HTTP anterior solo con los listeners privados
registrados. Si también se revierte la imagen, recuperar la etiqueta desde
`before-pwa-$stamp.tar` con `docker load -i` si fuera necesario y ejecutar:

```bash
"${app_compose[@]}" -f "$state/rollback.yml" up -d --no-deps --no-build --pull never fastapi
```

Mantener el archivo ACME privado para un nuevo intento y volver a verificar
la política del webhook, el acceso privado y el estado de los demás servicios.
Esta recuperación es de red e imagen. La PWA no añade migraciones ni requiere
restaurar la base de datos.

Referencias de operación. [Traefik y ACME](https://doc.traefik.io/traefik/v3.7/reference/install-configuration/tls/certificate-resolvers/acme/), [proveedor Cloudflare](https://go-acme.github.io/lego/dns/cloudflare/), [DNS-01](https://letsencrypt.org/docs/challenge-types/).
