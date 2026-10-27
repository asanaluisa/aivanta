# Aivanta — Inteligencia sobre el valor y el retorno de la IA

[English](README.md) · **Español**

> **¿Obtenemos de la IA más valor del que gastamos en ella?**

Aivanta es una plataforma analítica B2B completa que relaciona el consumo de IA (tokens, modelos, proveedores, solicitudes) con resultados de negocio medidos (tiempo ahorrado, calidad, ahorros, costes evitados) y evalúa la IA con el mismo rigor que cualquier otra inversión. No se queda en la factura de la API: determina, con evidencia, dónde conviene ampliar, optimizar, restringir, probar o abandonar el uso de IA.

![Resumen ejecutivo](docs/screenshots/dashboard_en.png)

| | |
|---|---|
| ![IA frente a procesos sin IA](docs/screenshots/comparison_es.png) | ![Recomendaciones](docs/screenshots/recommendations_es.png) |

> Todas las cifras de este repositorio proceden de un **conjunto de datos sintético y reproducible**. Los nombres de los modelos (`gpt-demo-large`, `claude-demo-compact`…) y sus precios son marcadores ficticios, no tarifas oficiales de los proveedores.

---

## Qué hace

| Pregunta | Cómo la responde Aivanta |
|---|---|
| **¿Cuánto gastamos?** | Normaliza el uso exportado de OpenAI, Anthropic y Google Gemini, valora cada registro con tarifas versionadas (incluido el precio de los tokens en caché) y lo asigna a departamentos y casos de uso. El consumo que no se puede atribuir queda visible como **sin asignar**. |
| **¿Qué obtenemos?** | Recoge referencias, mediciones de tareas con y sin IA, calidad, revisión y retrabajo, y reclamaciones de beneficio con su estado de verificación. Solo computan en el ROI los ahorros **verificados** y la contribución o los costes evitados **respaldados** por una medición controlada. |
| **¿Compensa?** | Un motor de ROI determinista (ROI, beneficio neto, ratio beneficio/coste, periodo de recuperación, volumen de equilibrio, escenarios), una comparación entre IA y procesos sin IA con intervalos del 95 % y recomendaciones explicables basadas en reglas. Si la evidencia no basta, muestra **«Evidencia insuficiente»** en lugar de una cifra. |

### Aspectos destacados
- **ROI basado en evidencia**: cada indicador se etiqueta como *Medido*, *Con evidencia* o *Estimación*; las estimaciones se muestran pero nunca entran en el ROI. Se evita la doble contabilización agrupando las reclamaciones que describen un mismo resultado.
- **Nunca se presupone que la IA sea mejor**: el motor de comparación puede recomendar *mantener*, *optimizar*, *usar solo en determinados tipos de tarea*, *realizar un experimento controlado* o *dejar de usarla*, y distingue los diseños causales (aleatorizado, grupo de control) de los correlacionales.
- **Coste total de propiedad**: uso de modelos, suscripciones, infraestructura, implantación, mantenimiento y revisión humana y retrabajo *incrementales*.
- **Totalmente bilingüe (EN/ES)**: ficheros de localización estructurados, terminología empresarial de España, formato de números, moneda y fechas según el idioma, y exportaciones CSV localizadas (`;` y coma decimal para hojas de cálculo en español). Un test comprueba la paridad de claves, los marcadores y que todo código que emite el backend tenga traducción.
- **Multiempresa y gobernado**: aislamiento de datos por organización, control de acceso por roles (administración, finanzas, analista, lectura), supuestos editables, instantáneas de ROI congeladas y registro de auditoría.

## Puesta en marcha

Requisitos: Docker con Compose.

```bash
cp .env.example .env          # y define AIVANTA_JWT_SECRET con una cadena aleatoria larga
docker compose up --build
```

- Aplicación web: <http://localhost:3000>
- Documentación de la API (OpenAPI): <http://localhost:8000/docs>

En el primer arranque el backend aplica las migraciones y carga los datos sintéticos de demostración (dos organizaciones, para demostrar el aislamiento). Accede con cualquier cuenta de demostración; la contraseña es `AIVANTA_DEMO_PASSWORD` (por defecto `aivanta-demo`):

| Cuenta | Rol | Puede |
|---|---|---|
| `admin@aivanta.demo` | Administración | todo, incluido el registro de auditoría |
| `finance@aivanta.demo` | Finanzas | modificar supuestos del ROI y congelar instantáneas |
| `analyst@aivanta.demo` | Analista | cargar archivos de uso |
| `viewer@aivanta.demo` | Lectura | solo consultar |
| `admin@northwind.demo` | Administración de otra organización | solo ve sus propios datos |

Para recargar los datos de demostración: `make seed` (`docker compose exec backend python -m app.seed --reset`).

### Sin Docker

```bash
# backend (Python 3.10+, PostgreSQL 14+)
cd backend
pip install -r requirements-dev.txt
export AIVANTA_DATABASE_URL=postgresql+psycopg://aivanta:aivanta@localhost:5432/aivanta
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload

# frontend (Node 20+)
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## Arquitectura

```
frontend/  Next.js 15 · React 19 · TypeScript · Tailwind CSS v4 · gráficos con d3-scale/d3-shape
  src/i18n/        messages/en.json, messages/es.json, núcleo de traducción, proveedor
  src/features/    una vista por página (resumen, costes, departamentos, resultados, comparación…)
  src/components/  estructura de la app, filtros, tarjetas de indicadores, gráficos, primitivas de UI
backend/
  aivanta_core/    lógica de dominio sin dependencias de framework (solo biblioteca estándar)
    pricing.py  roi.py  stats.py  comparison.py  analytics.py  recommendations.py
    ingestion/  synthetic.py  reporting.py  serialize.py  locales/
  app/             FastAPI · SQLAlchemy 2 · Pydantic v2 · autenticación JWT · control por roles
  migrations/      Alembic (DDL en migrations/sql/0001_initial.sql)
samples/           archivos de ejemplo documentados para cada formato de ingesta
docs/              arquitectura, definiciones financieras, caso de estudio (EN/ES)
```

La decisión de diseño central: **toda la lógica de negocio vive en `aivanta_core`, un paquete de Python puro sin dependencias de framework.** La API carga los registros de una organización en clases de datos simples y se los entrega a los motores; esos mismos motores alimentan las exportaciones, el script de carga y los tests. Detalle en [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (en inglés).

## Metodología del ROI (resumen)

```
Coste total asociado a la IA = uso de modelos y API + suscripciones + infraestructura + implantación
                             + mantenimiento + revisión humana incremental + retrabajo incremental
Beneficio bruto              = ahorros financieros verificados + contribución incremental respaldada
                             + costes evitados respaldados          (una reclamación por resultado)
Beneficio neto               = beneficio bruto − coste total asociado a la IA
ROI %                        = (beneficio bruto − coste total) / coste total × 100
```

Las horas ahorradas se presentan por separado y nunca se convierten en efectivo dentro del ROI. El ROI no se muestra (estado *evidencia insuficiente*) si no hay ningún beneficio verificado o respaldado, si se han medido menos de 30 tareas con IA o si la medición dura menos de 14 días; todos son supuestos editables. Definiciones completas en [docs/FINANCIAL_DEFINITIONS.md](docs/FINANCIAL_DEFINITIONS.md) (en inglés).

## Ingesta

| Formato | Endpoint | Estado |
|---|---|---|
| CSV canónico de Aivanta (cualquier proveedor) | `POST /api/ingestion/aivanta_csv` | implementado y probado |
| Exportación de uso de la organización en OpenAI (JSON) | `POST /api/ingestion/openai` | implementado, probado con muestra |
| Exportación del informe de uso de Anthropic (JSON) | `POST /api/ingestion/anthropic` | implementado, probado con muestra |
| Registro de `usageMetadata` de Gemini (JSONL) | `POST /api/ingestion/google` | implementado, probado con muestra |
| Sincronización directa con las API de los proveedores | — | **no implementada** (indicado en la interfaz) |

Los adaptadores siguen los nombres de campo publicados por cada proveedor tal como se entendían a mediados de 2026; conviene contrastarlos con tus propias exportaciones. Las cargas son idempotentes, las filas no válidas se rechazan indicando el motivo y la atribución se resuelve con reglas de asignación (clave de API, proyecto, espacio de trabajo o etiqueta → departamento / caso de uso). Ver [samples/README.md](samples/README.md).

## Tests y estado de verificación

| Área | Qué hay | ¿Se ejecutó al construir este repositorio? |
|---|---|---|
| Motor (precios, ROI, estadística, comparación, recomendaciones, ingesta, datos sintéticos, informes, respuestas de la API) | 106 tests de pytest, incluida la conciliación de cada métrica del panel con los registros de origen | **Sí**, todos pasan |
| Esquema de base de datos | `migrations/sql/0001_initial.sql` | **Sí**, aplicado sobre PostgreSQL 16 |
| API web (FastAPI + SQLAlchemy + Alembic) | `tests/api/`: autenticación, roles, aislamiento entre organizaciones, idempotencia de la ingesta, informes, instantáneas, auditoría y comparación del ORM con la migración | **No**: el entorno de construcción no tenía acceso al índice de paquetes de Python. Ejecuta `pytest` con `AIVANTA_TEST_DATABASE_URL` (la integración continua lo hace). |
| Lógica del frontend | 14 tests con `node:test`: paridad EN/ES, marcadores, terminología, traducción de todos los códigos del backend, formato de números, fechas y moneda, codificación de filtros | **Sí**, todos pasan |
| Interfaz | todas las páginas renderizadas en Chromium sin interfaz con respuestas reales de la API, en EN y ES, escritorio y móvil | **Sí**, mediante un entorno con transporte simulado |
| `next build`, `tsc` con los paquetes de tipos reales, `docker compose up` | flujo de CI en `.github/workflows/ci.yml` | **No**, por el mismo motivo; ejecútalos en local o en CI |

## Decisiones de diseño y limitaciones
- **Gráficos** con `d3-scale` y `d3-shape` renderizados por React en lugar de Recharts: misma función (librería consolidada), control total de la accesibilidad (vista de tabla en cada gráfico, nada codificado solo por color) y una paleta validada para daltonismo.
- **Analítica en memoria**: los datos de una organización se cargan una vez por versión y se cachean; es suficiente para decenas de miles de registros. Con millones, las agregaciones pasarían a SQL (agregados diarios materializados).
- **El token de sesión** se guarda en `localStorage` por simplicidad; en producción debería usarse una cookie httpOnly.
- **Las escrituras en caché de Anthropic** se valoran al precio normal de entrada; los tokens de razonamiento de Gemini se facturan como salida.
- **Solo tema claro.**

## Documentación
- [Arquitectura](docs/ARCHITECTURE.md) (inglés)
- [Definiciones financieras](docs/FINANCIAL_DEFINITIONS.md) (inglés)
- [Caso de estudio](docs/CASE_STUDY.es.md) · [Case study](docs/CASE_STUDY.md)

---

Desarrollado por **Andrés Sebastián Analuisa** como proyecto de portfolio en ingeniería de IA, ingeniería de datos y sistemas de IA para negocio. Licencia MIT.
