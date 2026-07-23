# Contrato de prueba Goemans‑Williamson

## Objetivo de la prueba

El módulo ejecutable de pytest es
`power-core/tests/optimizer/goemans-williamson/tests_goemans_williamson.py`.
Este archivo Markdown define su contrato de comportamiento; `index.py` no es un
nombre de prueba pytest ejecutable y no debe usarse como objetivo de prueba.

La API de producción es:

```python
solve_goemans_williamson(
    graph: nx.Graph,
    *,
    seed: int,
    rounds: int = 128,
    solver: str = "SCS",
    optimal_weight: float | None = None,
) -> GoemansWilliamsonResult
```

El resultado inmutable registra las particiones positiva y negativa, el peso del
cut, el valor SDP, la ratio empírica, la seed, las rondas solicitadas, la ronda
ganadora, el solver y el estado del solver.

## Contrato del adaptador Strategy

`GoemansWilliamsonStrategy` adapta esta API al runner independiente del
optimizador:

- Su identificador estable es `goemans-williamson`.
- Solo acepta `rounds` y `solver` en `SolverRunRequest.options`.
- Convierte la partición positiva a `1` y la negativa a `0`.
- Recalcula el corte normalizado contra el grafo del request.
- Devuelve errores de validación y SDP como
  `SolverRunResult(status="failed")`.
- Registra evidencia SDP y de redondeo serializable como JSON, sin exponer la
  matriz numérica en la metadata compartida.

## Secuencia RED-a-VERDE (RED-to-GREEN)

1. Validar el tipo de grafo, IDs de nodos como strings, topología simple y
   no dirigida, pesos explícitos, finitos y no negativos, rondas positivas y
   seed entera.
2. Verificar que un corte conocido se sume una vez por arista y que coincida
   con los objetivos Ising y Laplaciano ponderado.
3. Verificar el SDP para una arista ponderada y para un triángulo; afirmar
   simetría, diagonal unitaria, viabilidad PSD dentro de tolerancia, y
   `cut <= optimum <= sdp`.
4. Verificar que salidas inválidas o fallidas del solver sean rechazadas,
   mientras que solo errores PSD del tamaño de la tolerancia sean reparados
   antes de la factorización.
5. Verificar reproducibilidad con seed fija, particiones disjuntas exhaustivas,
   manejo determinista de producto punto cero, y desempate por la ronda más
   temprana.
6. Verificar que seleccionar la mejor entre múltiples hiperplanos nunca sea
   peor que el primer hiperplano generado con la misma secuencia de seed.
7. Enumerar cada asignación para grafos pequeños para validar óptimos exactos
   y ratios empíricas. No afirmar la expectativa 0.87856 para una ejecución con
   seed individual.
8. Cubrir grafos vacíos, nodos aislados, grafos desconectados y pesos cero;
   requerir `empirical_ratio is None` cuando el óptimo exacto sea cero.
9. Cargar `power-core/artifacts/regional_instance.json` de forma determinista,
   verificar que fuerza bruta produzca el óptimo de referencia `1058.0 kV`, y
   comparar particiones solo hasta el complemento.
10. Verificar defaults, validación de opciones, partición normalizada, corte
    recalculado, preservación del request y errores estructurados del Strategy.
11. Inyectar el Strategy en `SolverRunner` y verificar la instancia regional
    sin agregar ramas específicas del optimizador al runner.

## Comandos de aceptación

```bash
python -m pytest power-core/tests/optimizer/goemans-williamson/tests_goemans_williamson.py
python -m pytest power-core/tests/optimizer/test_goemans_williamson_strategy.py
python -m pytest power-core/tests/test_run_solver.py
python -m pytest power-core/tests
```
