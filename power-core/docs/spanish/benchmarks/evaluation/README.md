# Evaluaciones versionadas

Cada ejecución o conjunto comparable de ejecuciones se documenta en un
directorio numerado:

```text
evaluation/
├── TEMPLATE.md
├── v001/
│   └── README.md
├── v002/
│   └── README.md
└── ...
```

## Convención

- Usar `vNNN` con tres dígitos y numeración consecutiva (`v001`, `v002`, ...).
- Copiar `TEMPLATE.md` a `vNNN/README.md`; no modificar el template para
  registrar un resultado concreto.
- Una versión contiene solo corridas comparables: misma instancia, convención
  de objetivo y presupuesto experimental declarado.
- Si cambia la instancia, la formulación QUBO/Ising, el backend, los shots, el
  rango de profundidades o la política de semillas, crear una versión nueva.
- Guardar tablas y figuras generadas dentro de la carpeta de su versión. Nunca
  sobrescribir una evaluación publicada.

La numeración identifica evidencia reproducible, no una mejora garantizada:
una versión posterior puede revelar una regresión, un fallo o una limitación.

## Crear una versión

```bash
mkdir -p power-core/docs/spanish/benchmarks/evaluation/v001
cp power-core/docs/spanish/benchmarks/evaluation/TEMPLATE.md \
  power-core/docs/spanish/benchmarks/evaluation/v001/README.md
```

Completar cada campo antes de usar la versión como evidencia en el informe o
la presentación.
