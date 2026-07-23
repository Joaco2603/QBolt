# Modelo de Ising: contrato de conversión de QUBO

Este módulo proporcionará el límite determinista entre la representación QUBO
de minimización del proyecto y el Hamiltoniano de Ising consumido por QAOA.
Solo convertirá coeficientes; la construcción de circuitos, la optimización,
la ejecución del backend y el muestreo de resultados pertenecen a capas
posteriores.

> **Estado:** solo diseño y contrato TDD. Aún no se incluye una implementación
> de producción.

## Objetivo

La futura clase `IsingModel`:

1. construirá un modelo de Ising a partir del `QuboModel` existente;
2. preservará cada variable de decisión y auxiliar en orden determinista;
3. expondrá el desplazamiento constante, los campos locales y los acoplamientos entre pares;
4. evaluará una asignación completa de espines; y
5. preservará exactamente la energía QUBO bajo el mapeo de binario a espín.

La conversión no debe reinterpretar el peso de las aristas de la red de
transmisión. En este proyecto, el peso del grafo sigue siendo la suma de la
tensión nominal de los circuitos en kV: es un proxy de modelado, no capacidad,
flujo de potencia, impedancia ni riesgo operativo.

## Convención matemática

El QUBO existente es un objetivo de minimización:

```text
E_Q(x) = c + Σ_i a_i x_i + Σ_(i<j) b_ij x_i x_j
```

donde cada variable binaria es `x_i ∈ {0, 1}`. La convención de espines de
Ising es:

```text
z_i = 1 - 2x_i
x_i = (1 - z_i) / 2
z_i ∈ {-1, +1}
```

Por lo tanto, `x = 0` se mapea a `z = +1`, y `x = 1` se mapea a `z = -1`.
La energía de Ising de minimización resultante es:

```text
E_I(z) = C + Σ_i h_i z_i + Σ_(i<j) J_ij z_i z_j
```

con los coeficientes:

```text
J_ij = b_ij / 4
h_i  = -a_i / 2 - Σ_(j ≠ i) b_ij / 4
C    = c + Σ_i a_i / 2 + Σ_(i<j) b_ij / 4
```

El invariante principal es la equivalencia energética exacta:

```text
E_Q(x) = E_I(1 - 2x)
```

La constante `C` DEBE conservarse. Omitirla preservaría el `argmin` del
optimizador, pero corrompería las comparaciones de energía, la evidencia de
benchmarks y los cálculos posteriores de razón de aproximación.

## Contrato público para implementar mediante TDD

### `IsingModel.from_qubo`

```text
IsingModel.from_qubo(qubo: QuboModel) -> IsingModel
```

La factoría leerá la instantánea del QUBO sin mutarla. El modelo creado
expondrá:

| Campo | Significado |
| --- | --- |
| `variables` | Variables de decisión seguidas de variables auxiliares, preservando su orden de origen |
| `offset` | Constante `C` de la energía de Ising |
| `linear` | Mapeo `variable -> h_i`, que incluye cada variable del modelo |
| `quadratic` | Mapeo canónico `(left, right) -> J_ij` para acoplamientos distintos de cero |

Las claves de pares deben ser canónicas y deterministas. Los autoacoplamientos
están prohibidos: los términos diagonales de QUBO pertenecen a su mapeo lineal
porque `x_i² = x_i`.

### `energy`

```text
energy(spins: Mapping[str, int]) -> float
```

El método evaluará el objetivo completo de Ising, incluido el desplazamiento.
Solo aceptará asignaciones que:

- contengan cada variable del modelo exactamente una vez;
- no contengan ninguna variable desconocida; y
- utilicen valores enteros de espín `-1` o `+1` (los booleanos no son espines válidos).

Las asignaciones inválidas generarán `ValueError`, identificando en el mensaje
la variable faltante, la variable desconocida o el espín inválido.

### Ayudantes de conversión de asignaciones

```text
binary_to_spins(assignment: Mapping[str, int]) -> dict[str, int]
spins_to_binary(assignment: Mapping[str, int]) -> dict[str, int]
```

Estos ayudantes implementarán el mapeo documentado sin cambiar los nombres de
las variables ni el orden de inserción. Aplicarán la misma validación de
cobertura exacta que `energy`; los valores binarios deben ser enteros `0` o
`1`.

## Política de validación y numérica

- La entrada debe ser un `QuboModel`; no se aceptan mapeos arbitrarios.
- Cada coeficiente QUBO y cada coeficiente de Ising resultante debe ser finito.
- Un par puede proporcionarse en cualquiera de las orientaciones solo después de la construcción del QUBO; la representación de Ising almacena un único par canónico.
- Los acoplamientos con valor cero pueden omitirse de `quadratic`; todas las variables permanecen presentes en `linear`, incluso cuando su campo local es cero.
- La conversión es determinista y no realiza redondeos ni eliminación de coeficientes basada en tolerancias.
- El `QuboModel` de origen y las asignaciones proporcionadas por quien llama nunca se mutan.

## Límites

Esta clase no:

- crea un QUBO de Max-Cut ni elige penalizaciones de restricciones;
- construye operadores de Pauli ni un circuito PyTKET;
- ejecuta QAOA ni un emulador de Quantinuum;
- elimina variables auxiliares;
- optimiza, normaliza ni reescala coeficientes; ni
- afirma que una energía de Ising sea una medición física de la red eléctrica.

Estas responsabilidades requieren contratos separados para que la conversión
algebraica pueda verificarse exhaustivamente antes de introducir la ejecución
cuántica.

## Entrega para TDD

Implementa una por una las pruebas documentadas en
[`../../../../tests/optimizer/qubo_ising_qaoa/ising/test_ising.md`](../../../../tests/optimizer/qubo_ising_qaoa/ising/test_ising.md).
La primera prueba ejecutable debe fallar porque `IsingModel` no existe. Solo
después debe añadirse código de producción, siguiendo
ROJO → VERDE → REFACTORIZAR.
