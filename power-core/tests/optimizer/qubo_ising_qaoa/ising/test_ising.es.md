# Contrato de pruebas TDD para `IsingModel`

Estas pruebas definirán el comportamiento de la futura conversión de QUBO a Ising.
Son solo documentación: no crear `ising.py` mientras este contrato está
en revisión.

## Punto de prueba (test seam)

Las pruebas cargarán el `QuboModel` existente y el futuro `IsingModel` directamente
desde sus módulos fuente. Usarán QUBOs pequeños construidos a mano para que los
coeficientes esperados puedan calcularse por inspección, sin importar QAOA,
PyTKET, SciPy, un backend o conjuntos de datos de redes de transmisión.

Use enumeración binaria exacta para modelos con como máximo tres variables. Para
cada asignación binaria `x`, derive `z = 1 - 2x` y afirme:

```text
qubo.minimum_energy(x) == ising.energy(z)
```

Para QUBOs con variables auxiliares, minimice la energía Ising sobre cada
asignación de espines auxiliares y compare ese mínimo con
`qubo.minimum_energy(primary_assignment)`. No compare una asignación QUBO que
solo contenga variables primarias directamente con una asignación Ising completa
elegida arbitrariamente.

## Orden RED → GREEN de las pruebas

Implemente una prueba a la vez. Cada nueva prueba debe fallar por el comportamiento
ausente previsto antes de añadir el cambio mínimo en producción que haga que pase.

| Orden | Prueba | Comportamiento esperado |
| ---: | --- | --- |
| 1 | `test_from_qubo_converts_one_linear_term` | Para `E_Q = c + ax`, el modelo produce `C = c + a/2` y `h = -a/2`. |
| 2 | `test_from_qubo_converts_one_quadratic_term` | Para `bxy`, produce `J_xy = b/4`, sustrae `b/4` de ambos campos locales y añade `b/4` al offset. |
| 3 | `test_from_qubo_accumulates_multiple_terms_per_variable` | El campo local de una variable incluye su coeficiente lineal y cada coeficiente cuadrático incidente. |
| 4 | `test_from_qubo_preserves_decision_then_auxiliary_variable_order` | `variables` es determinista y conserva todas las variables del QUBO. |
| 5 | `test_from_qubo_canonicalizes_pair_keys` | Cada par aparece una sola vez con orientación estable y no se emite auto-acoplamiento. |
| 6 | `test_energy_matches_qubo_for_every_two_variable_assignment` | Las asignaciones exhaustivas tienen energías QUBO e Ising exactamente iguales. |
| 7 | `test_energy_matches_qubo_for_a_three_variable_constraint_model` | La equivalencia exacta también se mantiene para una salida representativa de `ConstraintBuilder`. |
| 8 | `test_energy_includes_the_constant_offset` | Una contribución constante permanece observable en cada asignación. |
| 9 | `test_binary_to_spins_uses_zero_to_positive_one_and_one_to_negative_one` | Se aplica la asignación documentada sin cambiar nombres u orden. |
| 10 | `test_spins_to_binary_is_the_inverse_mapping` | Un viaje de ida y vuelta reproduce la asignación binaria válida original. |
| 11 | `test_energy_rejects_missing_and_unknown_variables` | La cobertura de la asignación debe coincidir exactamente con el modelo. |
| 12 | `test_energy_rejects_non_spin_values_including_booleans` | Solo se aceptan los enteros `-1` y `+1`. |
| 13 | `test_binary_to_spins_rejects_non_binary_values_including_booleans` | Solo se aceptan los enteros `0` y `1`. |
| 14 | `test_from_qubo_rejects_non_finite_coefficients` | `NaN` e infinitos no pueden entrar ni salir del límite de conversión. |
| 15 | `test_conversion_does_not_mutate_the_qubo` | Las variables fuente y los mapeos de coeficientes permanecen sin cambios. |
| 16 | `test_energy_does_not_mutate_the_spin_assignment` | La evaluación es una operación de solo lectura. |

## Fixtures iniciales

| Fixture | Propósito |
| --- | --- |
| `linear_qubo` | Una variable con un offset no nulo y coeficiente lineal |
| `pair_qubo` | Dos variables con términos lineales y una interacción cuadrática |
| `three_variable_qubo` | Modelo representativo pequeño para enumeración exhaustiva |
| `qubo_with_auxiliary` | Confirma el orden decisión/auxiliar y la preservación completa de variables |
| `all_binary_assignments` | Enumeración determinista de asignaciones `0/1` |

Use coeficientes que hagan obvios signos incorrectos y la ausencia de la constante.
Incluya al menos un coeficiente lineal negativo y un coeficiente cuadrático positivo.
Evite depender únicamente de ejemplos simétricos donde un error de signo podría
pasar accidentalmente.

## Afirmaciones importantes

- Asegure `offset`, cada campo local y cada acoplamiento por par por separado antes
  de confiar en la equivalencia de energía.
- Asegure explícitamente la convención `x = 0 -> z = +1` y `x = 1 -> z = -1`.
- Asegure la cobertura exacta de variables tanto para variables de decisión como auxiliares.
- Asegure todas las asignaciones para el modelo pequeño, no sólo un óptimo conveniente.
- Haga snapshot de las entradas antes y después de la conversión/evaluación para demostrar que no hay mutación.
- Use `pytest.approx` únicamente para efectos de aritmética de punto flotante; no debe ocultar una convención algebraica incorrecta.

## Pruebas deliberadamente excluidas

Las pruebas siguientes pertenecen a otros módulos y no deben añadirse aquí:

- construcción de un objetivo Max-Cut a partir de un grafo;
- selección o calibración de valores de penalización QUBO;
- construcción de operadores de Pauli o circuitos cuánticos;
- profundidad de QAOA, tiros (shots), convergencia del optimizador o ejecución en backend;
- decodificar bitstrings muestreados en una partición de grafo;
- cálculo de la razón de aproximación y comparación con solucionadores clásicos.

## Criterios de finalización

La fase de documentación se considera completa cuando la convención matemática,
la API pública, la política de validación y el orden RED de pruebas son aceptados.

La fase de implementación futura comienza creando solo la primera prueba ejecutable.
Estará completa únicamente después de que todas las pruebas documentadas pasen,
se demuestre la equivalencia exhaustiva de energía y el módulo de producción no
contenga dependencias de backends cuánticos.
