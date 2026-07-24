# Plan de benchmarks para Challenge 1

Este documento define cómo se comparan los solucionadores de Max-Cut sobre
**la misma instancia regional ponderada**. El peso de cada arista es la suma de
los voltajes nominales de sus circuitos (kV): es un proxy reproducible de
importancia, no capacidad, flujo eléctrico, impedancia ni riesgo.

No se comparan tiempos, objetivos ni particiones entre instancias distintas.
Cada corrida debe registrar el identificador y digest de la instancia, la
semilla, las versiones de dependencias y la configuración completa.

## Benchmarks que usamos

| Solucionador | Rol | Estado | Por qué se usa |
| --- | --- | --- | --- |
| QAOA | Método cuántico evaluado | Implementado | Es el objeto principal del experimento; se evalúa por su valor de corte y su ratio de aproximación, no por una afirmación de ventaja cuántica. |
| Goemans-Williamson (GW) | Baseline clásico de alta calidad | Implementado | Es la referencia de aproximación más importante para Max-Cut ponderado no negativo: combina relajación SDP y redondeo aleatorio, con garantía teórica esperada bajo sus supuestos. |
| Búsqueda exhaustiva | Oráculo exacto | Por integrar al runner de benchmarks | Para los grafos de 6–12 nodos del reto es viable: como máximo hay \(2^{11}=2048\) cortes no complementarios. Produce `OPT`, necesario para calcular ratios de aproximación honestos. |
| Greedy | Baseline clásico liviano | Implementado | Mide cuánto valor obtiene una heurística simple y rápida; evita que QAOA o GW parezcan útiles si no superan un método elemental. |

## Qué exige la rúbrica / skill

La skill `quantathon-challenge-1` requiere:

1. Comparar la **misma instancia** contra **Goemans-Williamson** y **greedy**.
2. Incluir **búsqueda exhaustiva o simulated annealing cuando sea factible**.
3. Para QAOA, ejecutar al menos **cinco inicializaciones distintas por
   configuración** y reportar media, desviación estándar, estado del
   optimizador y profundidad `p`.
4. Reportar el ratio de aproximación
   \[
   r = E_{QAOA} / E_{optimal},
   \]
   manteniendo consistente la convención de maximización de Max-Cut o la de
   minimización de Ising. En las tablas de Max-Cut se usa equivalentemente
   `cut_qaoa / OPT`.
5. Mostrar `r` frente a `p`. Si se hacen afirmaciones de escalabilidad,
   comparar al menos dos tamaños de instancia.
6. Registrar corridas fallidas o no convergentes; no ocultarlas ni sustituirlas
   silenciosamente.
7. No afirmar ventaja cuántica ni superioridad sobre GW.

Para el alcance actual, la búsqueda exhaustiva no es opcional en la práctica:
es factible y elimina la ambigüedad de usar una heurística como referencia del
óptimo.

## Extras útiles

| Extra | Prioridad | Por qué agrega valor |
| --- | --- | --- |
| Simulated annealing | Alta | Aporta un baseline heurístico estocástico distinto de GW y permite evaluar sensibilidad a semilla y presupuesto de iteraciones. No reemplaza `OPT` cuando la búsqueda exhaustiva es viable. |
| Random cut con múltiples semillas | Alta | Es el control de cordura mínimo: demuestra cuánto valor puede aparecer por azar y detecta errores de signos, pesos o evaluación del corte. |
| Búsqueda local desde greedy o random starts | Media | Separa el beneficio de una mejora local barata del beneficio atribuible a QAOA. Debe reportar número de reinicios y criterio de parada. |
| Métricas de tiempo y recursos | Media | Sirven para caracterizar costo experimental —tiempo de SDP, evaluaciones del optimizador, shots y backend—, pero no son evidencia de ventaja cuántica. |
| Experimento con ruido / emulación H2 | Media, si está disponible | Evalúa degradación de QAOA bajo condiciones más realistas. Debe compararse contra el baseline ideal con igual instancia, profundidad y presupuesto, sin presentarlo como resultado de hardware físico. |

## Protocolo mínimo reproducible

1. Cargar una instancia regional ponderada y preservar su procedencia.
2. Validar la formulación QUBO/Ising contra el valor de corte de búsqueda
   exhaustiva en una instancia pequeña.
3. Calcular `OPT` por búsqueda exhaustiva.
4. Ejecutar las estrategias implementadas de greedy y GW, junto con QAOA, sobre el mismo grafo y con pesos sin transformar.
5. Ejecutar QAOA con al menos cinco semillas/inicializaciones por cada valor de
   `p`; conservar tanto éxitos como fallos.
6. Reportar una tabla por configuración con valor de corte, `OPT`, ratio,
   semilla, estado, `p`, shots, backend y tiempos. Para los métodos
   estocásticos, incluir media y desviación estándar.
7. Generar la gráfica de ratio frente a profundidad y una comparación de al
   menos dos tamaños solo si se discute escalabilidad.

## Interpretación correcta

- GW, greedy y las heurísticas adicionales son comparadores, no adversarios que
  deban ser descartados para favorecer una narrativa cuántica.
- El mejor bitstring medido por QAOA no prueba optimalidad global.
- El ratio se interpreta con cuidado si `OPT = 0`: en ese caso no se informa
  una división artificial como `0/0`.
- Los resultados de emulación de Quantinuum H2 representan emulación; no deben
  describirse como ejecuciones en hardware cuántico.

## Referencias internas

- [`Template de evaluaciones versionadas`](evaluation/README.md)
- [`skills/quantathon-challenge-1/SKILL.md`](../../../../skills/quantathon-challenge-1/SKILL.md)
- [`QAOA`](../../../src/optimizer/quantum/qaoa/qaoa.md)
- [`Goemans-Williamson`](../../../src/optimizer/random_approximation/goemans-williamson.md)
- [`Instancia regional`](../regional-instance-graph.md)
