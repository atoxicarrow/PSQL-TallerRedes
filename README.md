# Tarea 2 · Taller de Redes y Servicios

**Integrantes:** Álvaro Acevedo y Gustavo Fernández.  
**Semestre:** 2026-2, Universidad Diego Portales.  
**Protocolo:** PostgreSQL Frontend/Backend 3.0 (selección del curso: PSQL).

Laboratorio de comunicación entre el servidor PostgreSQL y el cliente psql en contenedores separados. Esta carpeta contiene el material para ejecutar las pruebas, inspeccionar el tráfico y entregar el informe.

## Contenido

| Archivo o carpeta | Función |
| --- | --- |
| [Informe PDF](output/pdf/Informe_Tarea_2_PostgreSQL.pdf) | Informe final con los capítulos 1 y 2, resultados y figuras en anexos. |
| [capturas/](capturas/) | Cinco archivos PCAP originales para comprobar el análisis en Wireshark. |
| [scripts/lab.py](scripts/lab.py) | Creación del entorno, ejecución de pruebas y captura de tráfico. |
| [sql/](sql/) | Preparación de datos y pruebas SQL. |
| [Containerfile.cliente](Containerfile.cliente) | Construcción del cliente con psql y tcpdump. |
| [.env.example](.env.example) | Configuración de ejemplo con credenciales ficticias. |
| [.gitignore](.gitignore) | Excluye configuración local y archivos generados. |

El informe contiene las capturas de pantalla de Kitty; no es necesario subir esas imágenes por separado. Los PCAP sí se incluyen porque permiten analizar los paquetes originales.

## Requisitos

- Linux con Podman; probado en Fedora, Podman 6.1.3, x86_64.
- Python 3, sin paquetes adicionales.
- Acceso a Docker Hub y repositorios Alpine para la primera construcción.
- TShark para el registro del entorno durante las pruebas y Wireshark para la inspección gráfica.

Se utilizó PostgreSQL/psql 16.15 y tcpdump 4.99.6. La imagen base se fija por digest en el script y en el Containerfile; la versión de tcpdump puede variar al reconstruir desde los repositorios Alpine.

## Crear e iniciar el laboratorio

Desde la raíz del repositorio:

```bash
cp .env.example .env
python3 scripts/lab.py setup
```

El script crea la red `taller_redes`, el volumen `taller_datos`, el servidor `pg_server` y el cliente `pg_client`. Construye el cliente con tcpdump y el permiso `NET_RAW`, espera que el servidor acepte conexiones y prepara dos registros en la tabla `equipos`.

Si esos nombres ya existen, reutiliza los contenedores y el volumen; no reemplaza su configuración. Las variables de inicialización no cambian las contraseñas de una base ya existente.

Las credenciales de laboratorio son usuario `estudiante`, contraseña `clave_lab` y base `taller`. Son datos ficticios. `.env` queda excluido de Git. El puerto 5432 se utiliza dentro de la red de contenedores y no se publica al anfitrión.

## Conectarse y consultar

```bash
podman exec -it pg_client psql -h pg_server -U estudiante -d taller
```

Ingresar `clave_lab` cuando solicite contraseña. Dentro de psql:

```sql
SELECT current_database(), current_user, inet_server_addr(), inet_server_port();
SELECT * FROM equipos ORDER BY id;
\q
```

Las IP que aparecen en las filas de `equipos` son datos de ejemplo. Las direcciones de los contenedores pueden cambiar al reproducir; se utiliza `pg_server` como destino gracias al DNS de la red.

## Ejecutar las pruebas

```bash
python3 scripts/lab.py test
```

| Caso | Resultado esperado |
| --- | --- |
| Sesión completa | Identificación, dos filas de equipos y cierre voluntario. |
| Operaciones CRUD | INSERT 0 2, UPDATE 1, DELETE 1 y una fila final. |
| Error SQL | División por cero (SQLSTATE 22012), seguida de una consulta válida en la misma conexión. |
| Contraseña incorrecta | FATAL 28P01, salida de psql con código 2 y ninguna consulta ejecutada. |

La prueba CRUD vacía y reinicia únicamente la tabla auxiliar `pruebas_redes`. La tabla `equipos` se conserva. El error SQL se prueba fuera de una transacción explícita y se permite continuar intencionalmente.

**Repetir las pruebas sobrescribe las cuatro capturas automatizadas**, pero conserva `00_consulta_inicial.pcap`. También genera registros en `evidencias/`, excluidos de Git. Los números de paquete y tiempos pueden variar; el PDF describe la ejecución guardada, por lo que no se actualiza automáticamente al repetir las pruebas.

## Analizar las capturas

Abrir `capturas/01_sesion_completa.pcap` en Wireshark y aplicar:

```text
tcp.port == 5432
```

En la captura incluida:

- Paquetes 1-3: establecimiento TCP.
- 4, 6 y 8: SSLRequest, respuesta N y StartupMessage.
- 9-13: autenticación SCRAM-SHA-256 y aceptación.
- 16-17: consulta de equipos y respuesta con dos filas.
- 18-21: Terminate y cierre TCP.

En `03_error_sql.pcap`, el paquete 15 contiene el error 22012; el 16, ReadyForQuery; y los paquetes 18-19, una consulta posterior y su respuesta. En `04_auth_fallida.pcap`, el paquete 13 contiene FATAL 28P01 y no se ejecuta SQL.

La captura manual `00_consulta_inicial.pcap` tiene dos flujos y utiliza otra numeración: la consulta está en el paquete 27. La sesión del laboratorio no usa TLS; SCRAM autentica, pero no cifra las consultas ni los resultados.


## Detener y volver a iniciar

```bash
python3 scripts/lab.py stop
python3 scripts/lab.py setup
```

La detención conserva los datos y los contenedores.

## Problemas frecuentes

- **Falta NET_RAW o tcpdump en un cliente anterior:** copiar primero los archivos que se quieran conservar, detener y eliminar únicamente `pg_client`, y ejecutar `python3 scripts/lab.py setup`. La base de datos está en el servidor y su volumen.
- **Contraseña incorrecta:** comprobar que `.env` coincida con las credenciales del volumen existente. Cambiar variables de inicialización no cambia una contraseña ya creada.
- **PCAP vacío:** esperar el inicio de tcpdump, usar `--immediate-mode` y detener con Ctrl+C para cerrar el archivo.
- **Docker Compose:** no se necesita; los scripts utilizan Podman directamente.

## Referencias técnicas

- [Flujo de mensajes PostgreSQL 16](https://www.postgresql.org/docs/16/protocol-flow.html).
- [Formatos de mensajes](https://www.postgresql.org/docs/16/protocol-message-formats.html).
- [SASL/SCRAM](https://www.postgresql.org/docs/16/sasl-authentication.html).
- [Imagen oficial PostgreSQL](https://hub.docker.com/_/postgres).
- [Podman run](https://docs.podman.io/en/v6.1.3/markdown/podman-run.1.html).
