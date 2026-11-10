# Despliegue

## Docker Compose (desarrollo y servidor pequeño)

1. Copiá `.env.example` a `.env` y completá `AI_API_KEY` solo si vas a usar IA
   real. Para una demo sin costo, dejá `FAKE_AI=1`.
2. Ajustá `NEXT_PUBLIC_API_URL` a la URL pública de la API. La web la usa para
   llamar al backend desde el navegador.
3. Levantá los servicios:

```bash
docker compose up --build
```

- API: <http://localhost:8000> (documentación en `/docs`).
- Web: <http://localhost:3000>.
- SQLite: volumen `tejedora-data`, archivo `/app/data/tejedora.sqlite3`.

Para producción, poné la API y la web detrás de HTTPS (por ejemplo Caddy,
nginx o un proxy del proveedor). No expongas el puerto de la base de datos.

## Variables importantes

- `CORS_ORIGINS`: orígenes permitidos, separados por coma. En producción usá
  solo el dominio de la web.
- `DATABASE_PATH`: ruta de SQLite; en Docker conviene el volumen.
- `IMAGE_TTL_HOURS`: vencimiento de las imágenes subidas.
- `MAX_UPLOAD_MB`: tamaño máximo de imagen.
- `RATE_LIMIT_PER_MINUTE`: límite por IP para `/analyze` y `/pattern`.
- `FAKE_AI`: `1` evita llamadas de red y costo; `0` usa el proveedor real.
- `AI_PROVIDER`, `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`: configuración del
  proveedor. Nunca pongas la clave en la imagen ni en el repositorio.

## Sin Docker

```bash
uv sync --all-groups
cd web && npm ci --registry=https://registry.npmjs.org && cd ..
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000
cd web && npm run build && npm run start
```

Para producción, serví la web con `next start` o con la salida standalone, y la
API con `uvicorn` detrás de un proxy. Programá un respaldo periódico del archivo
SQLite y la limpieza de imágenes vencidas (`Database.purge_expired_images`).

## Salud y diagnóstico

- `GET /health`: estado del proceso y versión del motor.
- `GET /health/ai`: configuración y sondeo de capacidades de la IA.
- Si la IA no acepta imágenes, `/analyze` devuelve un error claro; no se inventa
  un patrón.

## Limitaciones de esta entrega

- SQLite y almacenamiento local son adecuados para una instancia pequeña; para
  varias réplicas hace falta Postgres y almacenamiento de objetos.
- No hay autenticación de usuarios: los proyectos se guardan en el navegador
  (localStorage) y los patrones en SQLite por id. No subas datos sensibles.
- El contador de vueltas y el modo de pantalla encendida dependen del navegador;
  el Wake Lock API puede no estar disponible.
