# Guia de aprendizaje: agentes de operaciones con controles verificables

## Proposito y publico

Esta guia acompana el codigo de `ops-agent-mcp` y esta pensada para estudiantes que conocen Python basico, funciones, clases y pruebas automatizadas. No presupone experiencia previa con agentes, MCP o LangGraph. Su objetivo es explicar por que existe cada frontera del sistema, seguir una solicitud de principio a fin y distinguir las garantias reales de las que solo se esperan del modelo.

El proyecto utiliza pedidos y reembolsos ficticios como laboratorio. No es un sistema de pagos ni debe conectarse a datos reales.

## Resultados de aprendizaje

Al finalizar, el estudiante deberia poder:

1. Distinguir un modelo de lenguaje, un flujo de trabajo y un agente con herramientas.
2. Explicar por que una llamada a herramienta propuesta por el modelo no equivale a una ejecucion autorizada.
3. Seguir el ciclo planificar-validar-aprobar-ejecutar y localizar cada responsabilidad en el codigo.
4. Separar regla de negocio, politica de autorizacion, manifiesto de herramienta y prompt.
5. Describir las fronteras de confianza entre modelo, runtime, herramienta y servidor MCP.
6. Elegir pruebas apropiadas para reglas deterministas, integraciones y comportamiento probabilistico.
7. Interpretar auditoria y trazas sin confundirlas ni registrar informacion sensible.
8. Identificar limitaciones actuales: en particular, el checkpointer por defecto es en memoria y la evaluacion con modelos reales requiere credenciales.

## Mapa de lectura

| Orden | Lectura o codigo | Pregunta que responde |
|---|---|---|
| 1 | [README.md](../README.md) | Que problema resuelve el ejemplo y como ejecutarlo |
| 2 | [orders.py](../src/ops_agent/orders.py) | Que reglas pertenecen al dominio de pedidos |
| 3 | [agent_definition.py](../src/ops_agent/agent_definition.py) | Que configura y limita a un agente |
| 4 | [planner.py](../src/ops_agent/planner.py) | Como se representa la propuesta del modelo |
| 5 | [graph.py](../src/ops_agent/graph.py) | Como se coordina el ciclo y donde se aplican los controles |
| 6 | [security.py](../src/ops_agent/security.py) y [tools.py](../src/ops_agent/tools.py) | Como se valida una llamada y se conecta a herramientas |
| 7 | [mcp_server.py](../src/ops_agent/mcp_server.py) | Como se exponen operaciones mediante MCP |
| 8 | [tests/](../tests/) y [evals/](../evals/) | Que evidencia aporta cada tipo de prueba |
| 9 | [telemetry.py](../src/ops_agent/telemetry.py) | Que puede observarse sin guardar contenido completo |

Las referencias a los archivos apuntan a la implementacion actual, no a una API publica estable.

## Modulo 1 — De un modelo a un agente

### Concepto

Un modelo de lenguaje genera texto o una propuesta estructurada a partir del contexto. Por si solo, no consulta el almacen de pedidos ni ejecuta un reembolso. Un agente agrega un ciclo de control alrededor del modelo: obtiene una propuesta, decide que hacer con ella, puede llamar herramientas y vuelve a evaluar el resultado.

Un flujo de trabajo convencional tiene pasos definidos por el programa. Un agente puede elegir entre acciones permitidas segun la entrada, pero sigue estando limitado por el programa que recibe y valida esa propuesta. En este repositorio el grafo es explicito; el modelo no controla el flujo arbitrariamente.

### En este proyecto

- `Planner` abstrae la decision siguiente; `OpenAIPlanner` consulta el proveedor y `ScriptedPlanner` permite pruebas deterministas.
- `ToolCall` representa una solicitud de herramienta. Es una propuesta del modelo, no una prueba de permiso.
- `AgentDefinition` limita prompt, manifiesto de herramientas, aprobaciones requeridas y pasos maximos.
- `build_graph` coordina las transiciones y el ejecutor realiza la operacion concreta.

### Comprobacion

Explica que podria ocurrir si se eliminara la validacion del runtime y se ejecutara directamente el nombre de herramienta que devuelve el modelo. La respuesta debe incluir al menos un riesgo de permisos y uno de argumentos.

## Modulo 2 — Herramientas, esquemas y manifiestos

### Concepto

Una herramienta es una operacion que el sistema puede invocar, por ejemplo `get_order` o `request_refund`. El esquema describe la forma de sus argumentos; no demuestra que esos argumentos sean correctos para el negocio ni que el usuario tenga permiso.

El manifiesto local es la lista de capacidades que un agente puede ofrecer al modelo y que el runtime acepta. Una allowlist limita el conjunto permitido. Un esquema ayuda a rechazar campos desconocidos, campos obligatorios ausentes y tipos no admitidos antes de llegar al ejecutor.

### En este proyecto

- `ORDER_AGENT.tool_specs` es el manifiesto del agente de referencia.
- `AgentDefinition` valida nombres duplicados, tipos admitidos, parametros requeridos y referencias de aprobacion.
- `validate_args` comprueba la propuesta contra el manifiesto de esa definicion.
- `model_tool_specs()` entrega al planner una copia del manifiesto, no la estructura mutable interna.

### Limite importante

El esquema actual es intencionadamente sencillo. No es un validador completo de JSON Schema: solo se deben usar tipos que `AgentDefinition` y `validate_args` sepan validar. Las restricciones de negocio siguen perteneciendo al dominio.

### Laboratorio

Construye una definicion que solo exponga `get_order`. Confirma en una prueba que el planner no recibe `request_refund` y que una llamada inventada a esa herramienta se rechaza antes del ejecutor.

## Modulo 3 — Planificacion frente a autorizacion

### Concepto

Planificar responde “que accion parece util?”. Autorizar responde “esta identidad puede realizar esta accion, con estos argumentos y en este contexto?”. La primera pregunta puede apoyarse en un modelo; la segunda debe responderse con controles deterministas y reglas explicitas.

El prompt puede orientar el comportamiento, pero no es un control de seguridad. Un modelo puede equivocarse, ser inducido por contenido hostil o producir argumentos incorrectos. Por eso el sistema no convierte la obediencia al prompt en permiso.

### En este proyecto

1. `planner.next_action()` devuelve `Final` o `ToolCall`.
2. `graph.plan` valida la herramienta y argumentos con el manifiesto.
3. `route_after_plan` envia una propuesta invalida a `reject`.
4. La lista `approval_tools` determina si la accion necesita aprobacion humana.
5. Solo despues se invoca `ToolExecutor.call()`.

### Ejercicio de revision

En `tests/test_security.py`, identifica el caso donde una herramienta devuelve texto con instrucciones hostiles. Enumera las defensas que siguen funcionando aunque el modelo obedezca esas instrucciones. No concluyas que el ejemplo protege contra toda forma de prompt injection.

## Modulo 4 — Reglas de negocio y politica de aprobacion

### Concepto

La regla de negocio define cuando una operacion tiene sentido para el dominio. La politica define si una accion puede proceder bajo permisos y controles del sistema. La aprobacion humana es una decision adicional para acciones que requieren supervision; no reemplaza ninguna de las dos.

Separar estas decisiones evita que un cambio de proveedor o de prompt cambie accidentalmente los limites economicos del sistema.

### En este proyecto

- `OrderStore.refund` rechaza pedidos no entregados, montos no positivos y reembolsos por encima del total.
- `AgentDefinition.approval_tools` declara las herramientas que deben pasar por el nodo de aprobacion.
- `graph.approval` pausa mediante `interrupt`; el flujo registra la decision y luego enruta a ejecutar o rechazar.
- `tests/test_graph.py` comprueba los caminos de aprobacion; `tests/test_security.py` comprueba limites de negocio ante propuestas maliciosas.

### Discusion

Una aprobacion deberia referirse a una accion concreta. Pregunta que informacion tendria que quedar ligada a esa decision en un sistema de produccion: identidad, argumentos exactos, ejecucion, politica aplicada y expiracion son ejemplos relevantes.

### Limitacion actual

El grafo se compila con `InMemorySaver` cuando no se proporciona un checkpointer. Esto sirve para el ejemplo y pruebas, pero no ofrece recuperacion durable tras reiniciar el proceso. La aprobacion actual no debe presentarse como un servicio durable de aprobaciones de produccion.

## Modulo 5 — MCP y fronteras de confianza

### Concepto

MCP (Model Context Protocol) define una forma estandar de descubrir y llamar herramientas ofrecidas por un servidor. El protocolo facilita interoperabilidad; no hace que un servidor remoto sea automaticamente confiable ni que sus herramientas queden autorizadas.

Una frontera de confianza es el limite donde datos o decisiones provenientes de otro componente deben verificarse. En este ejemplo, tanto las propuestas del modelo como las descripciones y resultados remotos se tratan con cautela.

### En este proyecto

- `mcp_server.py` expone las operaciones del dominio mediante el SDK MCP.
- `McpToolExecutor` compara las herramientas anunciadas por el servidor con el manifiesto local antes de la primera llamada.
- El modelo recibe descripciones locales revisadas; no se usa el texto de descripcion remoto para ampliar sus capacidades.
- El resultado MCP se convierte a una respuesta estructurada o a un error; la logica de pedidos reside aparte.

En la implementacion actual, `check_server_tools` compara nombres y parametros requeridos; no realiza una comparacion completa de tipos, descripciones y todas las restricciones de JSON Schema. Por tanto, esta comprobacion no debe describirse como una validacion exhaustiva del contrato remoto.

### Laboratorio

Modifica en una prueba simulada el conjunto de herramientas que anuncia el servidor. Verifica los casos de herramienta adicional, herramienta ausente y parametros requeridos distintos. El control es una verificacion parcial de contrato, no autenticacion criptografica del servidor.

## Modulo 6 — Pruebas: que demuestra cada capa

| Tipo | Ejemplo | Evidencia y limite |
|---|---|---|
| Prueba de reglas de dominio por flujo | `tests/test_security.py` | Comprueba limites de reembolso ante propuestas concretas; las reglas estan implementadas en `OrderStore` |
| Prueba de politica/grafo | `tests/test_graph.py`, `tests/test_security.py` | Comprueba transiciones y bloqueos para entradas especificas |
| Prueba arquitectonica | `tests/test_architecture.py` | Detecta dependencias prohibidas y desalineacion de herramientas |
| Prueba de contrato MCP | `tests/test_security.py` | Comprueba compatibilidad de manifiestos; no prueba un servidor productivo |
| Scoring determinista de evals | `tests/test_eval_scoring.py` | Comprueba la logica del gate, no la calidad real del modelo |
| Eval de trayectoria real | `evals/trajectory_eval.py` | Observa decisiones de un modelo identificado; puede variar entre ejecuciones |

Una prueba verde significa que los casos ejecutados cumplen sus aserciones; no significa seguridad total. Las evals con LLM no sustituyen pruebas deterministas para invariantes criticos.

### Laboratorio

Elige una afirmacion de seguridad del README. Localiza el test que aporta evidencia, identifica que entrada cubre y escribe un caso negativo adicional que podria detectar una regresion.

## Modulo 7 — Auditoria y observabilidad

### Concepto

Auditoria y observabilidad responden preguntas diferentes:

- **Auditoria:** que decision o accion relevante ocurrio, quien la solicito y que resultado se registro.
- **Trazas/telemetria:** cuanto duro un paso, que componentes intervinieron y donde se produjo un error.

Ambas pueden contener datos sensibles si se diseña mal su esquema. Minimizar datos antes de almacenarlos es mas robusto que confiar en que un backend los oculte despues.

### En este proyecto

- `AuditLog` mantiene eventos en memoria o los anade a JSONL; trunca cadenas largas, pero no es un almacen durable con controles de acceso.
- `telemetry.py` emite spans tecnicos si OpenTelemetry esta instalado y usa un span no-op si no lo esta.
- Los spans incluyen nombres de operaciones y atributos tecnicos, no prompts o respuestas completas en el flujo actual.

### Pregunta de diseno

Que campos necesitarias para investigar un incidente y cuales omitirias para reducir exposicion? Justifica la diferencia entre identificadores de correlacion y payloads completos.

## Recorrido practico sugerido (90–120 minutos)

1. **Orientacion (10 min):** leer el problema, arquitectura y limites del README.
2. **Dominio (15 min):** ejecutar y modificar una prueba de `OrderStore`.
3. **Propuesta (15 min):** comparar `ScriptedPlanner` y `OpenAIPlanner`; seguir un `ToolCall`.
4. **Control (20 min):** recorrer el grafo y dibujar las ramas de herramienta invalida, lectura, aprobacion y rechazo.
5. **Herramientas (15 min):** inspeccionar el manifiesto y probar la verificacion MCP.
6. **Evidencia (15 min):** ejecutar la suite y distinguir tests locales de evals reales.
7. **Cierre (10–30 min):** completar una actividad y documentar una limitacion.

## Actividades de extension

### A. Nuevo agente de solo lectura

Crear una `AgentDefinition` limitada a `get_order`. Probar que una llamada de escritura se bloquea, que el modelo solo ve la herramienta permitida y que la misma regla se cumple usando un planner falso.

**Aceptacion:** la prueba no requiere API key; no se copia el grafo ni se modifica la autorizacion para permitir una escritura.

### B. Contrato de herramienta adicional

Definir un esquema nuevo admitido por el validador y demostrar su validacion antes de ejecutarlo. Si el tipo de argumento no esta soportado por el validador actual, documentar primero el cambio de alcance y anadir pruebas positivas y negativas.

**Aceptacion:** entradas validas e invalidas tienen resultados explicitos; el servidor MCP y el manifiesto local permanecen sincronizados.

### C. Propuesta de recuperacion durable

Diseñar, sin afirmar que ya existe, el contrato de un `StateStore` que permita restaurar una aprobacion tras reiniciar. Incluir estados terminales, expiracion, concurrencia, idempotencia y tratamiento `outcome_unknown`.

**Aceptacion:** diagrama de estados, escenarios de fallo y pruebas que distinguirian una recuperacion segura de un reintento a ciegas.

## Glosario breve

- **Agente:** aplicacion que combina un modelo con estado, herramientas y un ciclo de control.
- **Planner:** componente que transforma contexto en una accion propuesta o respuesta final.
- **Tool call:** solicitud estructurada de invocar una herramienta; no es ejecucion ni autorizacion.
- **Manifiesto:** descripcion local de herramientas y esquemas permitidos para un agente.
- **Allowlist:** conjunto explicito de elementos aceptados; lo no listado queda fuera.
- **Efecto lateral:** cambio observable fuera del calculo local, por ejemplo modificar un saldo.
- **Human-in-the-loop:** pausa donde una persona revisa y decide una accion antes de continuar.
- **Checkpointer:** componente que conserva el estado de un flujo para continuarlo; su durabilidad depende de la implementacion.
- **MCP:** protocolo para descubrir e invocar herramientas mediante un servidor.
- **Eval de trayectoria:** medicion de las acciones elegidas por el agente durante un escenario.
- **Telemetria:** datos tecnicos para medir ejecucion; no equivale al registro de auditoria.
- **Idempotencia:** propiedad por la que repetir una operacion con la misma identidad no duplica el efecto.
- **Prompt injection indirecta:** instrucciones hostiles incluidas en datos que el modelo consulta, no necesariamente en la pregunta original.

## Como mantener esta guia correcta

Cada explicacion debe seguir el codigo y las pruebas actuales. Al cambiar una garantia, actualiza en el mismo cambio la guia, el README y los tests relacionados. Marca claramente lo propuesto, lo implementado y lo que no se ha probado; nunca presentes una recomendacion de arquitectura futura como capacidad disponible.

## Fuentes primarias para ampliar

- [LangGraph: Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) — nodos, aristas, estado y compilacion del flujo.
- [MCP: especificacion](https://modelcontextprotocol.io/specification/2025-11-25) — conceptos y protocolo de herramientas; consultar la version vigente al preparar el curso.
- [OpenAI: function calling](https://platform.openai.com/docs/guides/function-calling) — formato de propuestas de llamada a herramientas del proveedor usado en el ejemplo.
- [OWASP Top 10 for LLM Applications](https://genai.owasp.org/llm-top-10/) y [OWASP Top 10 for Agentic Applications](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) — vocabulario de riesgos y controles, no certificacion del proyecto.
- [OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai) — convenciones de nombres y atributos de telemetria.

Las especificaciones y guias de proveedores evolucionan. Antes de publicar material de curso, registra la version o fecha consultada y verifica que el codigo de este repositorio sigue usando el mismo contrato.
