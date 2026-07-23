# Variables binarias y penalizaciones de restricciones (guía conceptual)

Esta sección documenta el paso de modelado que precede a una implementación de optimización. No construye una matriz QUBO, no ejecuta un solucionador ni añade código del solucionador.

### 1. Definir una decisión binaria por cada elección

Usa una variable binaria cuando una decisión tiene exactamente dos estados:

\[
x_i \in \{0, 1\}
\]

Interpreta `0` y `1` en el lenguaje del dominio antes de escribir cualquier fórmula. Por ejemplo, `x_i = 1` puede significar que la línea, instalación o nodo `i` está seleccionado, mientras que `x_i = 0` significa que no lo está. Mantén este significado consistente a lo largo del modelo.

| Decisión | Variable binaria | Significado de `1` |
| --- | --- | --- |
| Seleccionar una línea de transmisión | `x_line` | La línea pertenece al conjunto seleccionado. |
| Colocar un nodo en el lado A de una partición | `x_node` | El nodo está asignado al lado A; `0` lo asigna al lado B. |
| Activar una acción de restauración | `x_action` | La acción está incluida en el plan. |

Una variable binaria no es una cantidad. Si la decisión puede adoptar varios niveles enteros, usa una formulación entera o codifica explícitamente esos niveles; no finjas que un bit representa más información de la que realmente tiene.

### 2. Convertir una restricción rígida en una violación no negativa

Para que una restricción se haga cumplir mediante una penalización, primero escribe una expresión que sea cero exactamente cuando la restricción se satisface y positiva en caso contrario. Luego añade esa expresión a un objetivo de minimización con un peso de penalización positivo `P`:

\[
\text{objetivo penalizado} = \text{objetivo base} + P \cdot \text{violación}
\]

El peso de la penalización debe ser lo suficientemente grande como para que incumplir la restricción nunca sea preferible sólo para mejorar el objetivo base. Un peso sobredimensionado también puede hacer que la optimización numérica esté mal condicionada, por lo que elige y justifica su valor a partir de límites conocidos del objetivo en lugar de adivinar.

### Restricciones simples comunes

| Restricción | Se satisface cuando | Término de penalización | Notas |
| --- | --- | --- | --- |
| Seleccionar exactamente una opción | `Σᵢ xᵢ = 1` | `P(Σᵢ xᵢ - 1)²` | Cero sólo cuando se selecciona exactamente una opción. |
| Seleccionar a lo sumo una opción | `Σᵢ xᵢ ≤ 1` | `P Σᵢ<ⱼ xᵢxⱼ` | Cada par seleccionado simultáneamente incurre en un coste. |
| Seleccionar al menos una opción | `Σᵢ xᵢ ≥ 1` | `P(1 - Σᵢ xᵢ)²` **solo cuando** `Σᵢ xᵢ ∈ {0,1}` | Para más de dos candidatos, usa una construcción con variables auxiliares u otra codificación adecuada; este cuadrado también penalizaría seleccionar más de una. |
| Requerir `x_a` sólo si `x_b` | `x_a ≤ x_b` | `P x_a(1 - x_b)` | La única violación es `x_a = 1`, `x_b = 0`. |
| Evitar dos elecciones juntas | `x_a + x_b ≤ 1` | `P x_ax_b` | Apropiado para elecciones mutuamente excluyentes. |
| Forzar que dos elecciones concuerden | `x_a = x_b` | `P(x_a - x_b)²` | Penaliza las dos asignaciones discrepantes. |

Aquí `Σ` denota una suma sobre las variables binarias indicadas. Debido a que las variables binarias satisfacen `x_i² = x_i`, las expresiones al cuadrado pueden luego simplificarse algebraicamente. Esa simplificación no se realiza deliberadamente en este README y aquí no se produce ningún QUBO.

### 3. Validar la penalización antes de implementarla

Para una restricción pequeña, enumera cada asignación binaria en papel o en una tabla. Confirma que las asignaciones válidas tienen penalización cero y las inválidas tienen una penalización estrictamente positiva.

Por ejemplo, para `x_a ≤ x_b`, el término `x_a(1 - x_b)` da:

| `x_a` | `x_b` | ¿Válido? | Penalización |
| ---: | ---: | --- | ---: |
| 0 | 0 | Sí | 0 |
| 0 | 1 | Sí | 0 |
| 1 | 0 | No | 1 |
| 1 | 1 | Sí | 0 |

Esta comprobación por tabla de verdad detecta errores de signo e implicaciones invertidas antes de que intervenga cualquier optimizador o flujo de trabajo cuántico.

### Límite del alcance

Esta guía termina al definir variables y documentar expresiones de penalización. Construir un QUBO, seleccionar magnitudes de penalización para una instancia concreta y ejecutar solucionadores clásicos o cuánticos quedan como trabajo futuro y validado por separado.
