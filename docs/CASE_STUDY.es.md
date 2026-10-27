# Caso de estudio — Medir si la IA se paga sola

[English](CASE_STUDY.md) · **Español**

*Andrés Sebastián Analuisa · Proyecto de portfolio Aivanta*

> Todas las cifras proceden del conjunto de datos sintético y reproducible de Aivanta (semilla `20260930`, del 3 de julio al 30 de septiembre de 2026). Ilustran el método; no describen a ninguna empresa real.

## 1. El problema de negocio

Casi cualquier empresa sabe cuánto paga a sus proveedores de IA. Muy pocas saben qué obtienen a cambio. Los paneles habituales se quedan en tokens y facturas, mientras que la justificación del gasto se apoya en anécdotas («el equipo dice que ahorra horas») y en métricas del propio proveedor («pipeline influido»). El resultado es previsible: el gasto en IA crece donde aporta poco y los casos de uso realmente valiosos no se escalan porque nadie puede demostrar que funcionan.

Aivanta trata la IA como cualquier otra inversión y responde a tres preguntas:

1. **¿Cuánto gastamos?**, no solo en tokens, sino en total.
2. **¿Qué resultados medibles obtenemos?**, con la evidencia que respalda cada uno.
3. **¿Es suficiente para justificar el coste?**, por organización, departamento y caso de uso, con una decisión clara.

## 2. El enfoque

**Normalizar y valorar cada llamada.** Las exportaciones de uso de OpenAI, Anthropic y Gemini tienen formas distintas y tratan de forma diferente los tokens en caché y de razonamiento. Los adaptadores por proveedor los convierten a un único modelo de evento; una tarifa versionada traduce tokens a euros con el precio vigente cada día; las reglas de atribución asignan claves de API, proyectos o etiquetas a departamentos y casos de uso. Lo que no se puede atribuir se conserva, se valora y se muestra como *sin asignar*; nunca se supone.

**Contar el coste completo.** El uso de modelos es solo una partida. Aivanta suma suscripciones, infraestructura, implantación, mantenimiento y el tiempo humano que genera la IA: revisión y retrabajo, imputados solo en la parte que supera lo que ya necesitaba el proceso sin IA.

**Solo cuenta la evidencia.** Cada reclamación de beneficio lleva un estado de verificación. Computan los ahorros verificados en contabilidad y los beneficios respaldados por una medición controlada; las estimaciones y las reclamaciones sin verificar se muestran, pero quedan fuera del ROI, y las que describen un mismo resultado se cuentan una sola vez. Si no se alcanza el umbral de evidencia, la plataforma indica *evidencia insuficiente* en lugar de dar una cifra.

**Comparar con la alternativa, no con cero.** En cada caso de uso, el trabajo asistido por IA se compara con el mismo trabajo hecho sin IA en coste total por tarea completada, tiempo, calidad, errores y retrabajo, con intervalos del 95 % y por tipo de tarea. La decisión es una de cinco: mantener, optimizar, usar solo en determinados tipos de tarea, realizar un experimento controlado o dejar de usarla.

## 3. Decisiones técnicas

| Decisión | Motivo |
|---|---|
| Un **núcleo en Python puro** (`aivanta_core`) sin dependencias de framework | Las reglas financieras deben ser deterministas y auditables. El motor se prueba en milisegundos y lo reutilizan la API, las exportaciones, la carga de datos y los tests. |
| Importes en `Decimal` y redondeo solo al presentar | Los totales cuadran al céntimo; los tests recalculan cada métrica del panel a partir de los registros de origen. |
| **La evidencia como dato**: estado de verificación y `evidence_key` en cada reclamación | Convierte «qué computa» en una regla, no en un criterio escondido en una hoja de cálculo, y permite detectar la doble contabilización. |
| Intervalos de Welch y de proporciones; diseños causales frente a correlacionales | Distingue «la IA es más rápida» de «la IA pareció más rápida en una comparación antes/después». |
| **Recomendaciones basadas en reglas** que devuelven las métricas que las activan | Primero la explicabilidad; un modelo aprendido puede llegar cuando se acumulen resultados. |
| Identificadores neutros respecto al idioma; interfaz y exportaciones localizadas | Español e inglés son experiencias completas sin acoplar los datos a un idioma. |
| FastAPI + SQLAlchemy + PostgreSQL, multiempresa con roles y auditoría | La forma de un producto empresarial real: aislamiento, roles, supuestos bajo control de cambios, instantáneas congeladas. |
| Next.js y gráficos SVG con d3 con vista de tabla | Gráficos accesibles y aptos para daltonismo, con control total de las etiquetas de procedencia y de la navegación al detalle. |

## 4. Lo que aprende la organización de demostración

**El gasto en tokens no es donde se va el dinero.** La organización gastó **8658 €** en modelos y API en 90 días (2958 millones de tokens). Eso es solo el **6,5 %** de los **133,6 mil €** de coste total asociado a la IA. Dominan la implantación (38 %), las suscripciones (21 %) y la revisión humana y el retrabajo (28 %). Un panel de tokens habría pasado por alto el 93 % del coste.

**En conjunto, la IA no se pagó sola en este periodo, y la plataforma explica por qué.** El beneficio bruto con evidencia es de **98,3 mil €** (ahorros verificados 45,5 mil €, costes evitados respaldados 48,4 mil €, contribución respaldada 4,4 mil €), lo que da un **ROI del −26,4 %** (ratio beneficio/coste de 0,74). Como la mayor parte del coste es implantación inicial, el resultado mensual recurrente es positivo y el **periodo de recuperación es de unos 9,6 meses**. Los escenarios van del −43,9 % (conservador) al +50,9 % (optimista, que incluye estimaciones y así se indica).

**Una contabilidad ingenua habría anunciado un éxito.** Contar las reclamaciones estimadas, sin verificar y duplicadas habría convertido el −26 % en un **+6,6 %**; sumar además el valor de las 3066 horas «ahorradas» como si fueran efectivo habría dado un **+128 %**. La diferencia entre esas cifras es la razón de ser del producto.

**Dos casos de uso sostienen la cartera:**

| Caso de uso | Diseño | Resultado | Decisión |
|---|---|---|---|
| Clasificación de incidencias de soporte | aleatorizado | ROI **+238 %**, 2,68 € más barato por incidencia, misma calidad | mantener; candidato a ampliarse |
| Asistente de revisión de código | grupo de control | ROI **+71 %**, 18 min más rápido por revisión, 20,91 € más barato | mantener; candidato a ampliarse |
| Redacción de prospección comercial | grupo de control | ROI **−92 %**; con IA cuesta 12,51 € *más* por correo; la revisión consume el tiempo ahorrado | optimizar (un modelo más barato ahorraría unos 900 € al mes; el problema real es la licencia de 6000 € al mes) |
| Redacción de contenidos de marketing | grupo de control | 32 min más rápido por pieza, pero 10 puntos menos de calidad; los artículos extensos fallan y las publicaciones en redes funcionan | usar IA solo en redes sociales |
| Conciliación de facturas | observacional | 16 tareas, solo estimaciones | realizar un experimento controlado antes de invertir más |

**Alertas que importan.** El motor de reglas señala el exceso del presupuesto de Ventas (117 % del presupuesto de septiembre), un pico de gasto de un día causado por un bucle de reintentos descontrolado (7,5 desviaciones típicas por encima de lo normal), un aumento del 141 % del gasto de Ventas frente a los 30 días anteriores (en parte por ese bucle) sin mejores resultados, y un 29 % del gasto que no se puede atribuir a ningún caso de uso.

## 5. Validación

* 106 tests del backend cubren las tarifas, la imputación de costes, la selección de beneficios, cada fórmula del ROI, el umbral de evidencia, los escenarios, el volumen de equilibrio y el periodo de recuperación, la estadística (incluida la cobertura de los intervalos), cada decisión de la comparación, cada regla de recomendación, la ingesta de cada muestra de proveedor, la reproducibilidad de los datos sintéticos y la conciliación de cada total del panel con los registros de origen.
* El esquema se aplicó sobre PostgreSQL 16; se incluye para la integración continua una batería de tests de la API (autenticación, roles, aislamiento entre organizaciones, ingesta idempotente, exportaciones, instantáneas, auditoría y comparación entre el ORM y la migración).
* Los tests del frontend comprueban que inglés y español tienen las mismas claves y marcadores, que se usa la terminología acordada en español y que todo código que emite el backend tiene traducción. Todas las páginas se renderizaron en un navegador sin interfaz con respuestas reales de la API en ambos idiomas, en escritorio y en móvil.

## 6. Siguientes pasos

1. Conectores directos con las API de uso de los proveedores y una pasarela o SDK que etiquete cada solicitud con su caso de uso y su tarea en origen.
2. Tablas de agregados diarios para volúmenes de producción.
3. Gestión de experimentos: asignación, cálculo de potencia y seguimiento secuencial para la recomendación de «realizar un experimento controlado».
4. Integración contable para que Finanzas marque beneficios como verificados desde el sistema contable.
5. Evaluación de calidad (LLM como evaluador calibrado con revisión humana) para alimentar las puntuaciones de calidad.

## Competencias demostradas

Sistemas de IA (economía de tokens, caché, gamas de modelos, normalización multiproveedor) · ingeniería de datos (ingesta, idempotencia, atribución, modelado relacional, migraciones) · razonamiento financiero (coste total de propiedad, ROI, periodo de recuperación, equilibrio, escenarios, doble contabilización) · estadística y diseño experimental · desarrollo full-stack (FastAPI, PostgreSQL, Next.js, TypeScript) · diseño de producto para dirección · internacionalización · pruebas y verificación.
