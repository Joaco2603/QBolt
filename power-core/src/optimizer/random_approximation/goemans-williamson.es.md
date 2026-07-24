# Goemans-Williamson para Max-Cut Ponderado

## Propósito y alcance

Este módulo resuelve el problema de Max-Cut ponderado en grafos finitos, no
dirigidos y simples, con pesos de arista no negativos. Devuelve una
bipartición, el peso del corte resultante, la cota superior de la SDP,
metadatos del redondeo aleatorio, y una razón empírica solo cuando se
proporciona un óptimo exacto positivo.

El peso actual de la red de transmisión es la suma del voltaje nominal de
circuito en kV. Es un proxy de importancia reproducible, no capacidad, flujo
de potencia, impedancia ni riesgo de falla.

## Problema discreto

Para un grafo no dirigido \(G=(V,E)\), un corte es una partición \(S,\bar
S\). Su peso es la suma de los pesos de las aristas con extremos en partes
distintas. Con una etiqueta de Ising \(s_i\in\{-1,+1\}\), sea
\(S=\{i:s_i=+1\}\). Para aristas almacenadas una sola vez,

\[
\operatorname{Cut}(s)=\frac{1}{2}\sum_{\{i,j\}\in E}w_{ij}(1-s_i s_j).
\]

La convención equivalente de energía de minimización es
\(H(s)=-\operatorname{Cut}(s)\). El signo y la convención de constantes deben
permanecer explícitos al comparar esta línea base con resultados de QUBO o
QAOA.

## Elevación matricial y relajación SDP

Sea \(X=ss^\top\). En el modelo discreto, \(X\) es simétrica, semidefinida
positiva, tiene diagonal unitaria y rango uno. Al eliminar únicamente la
restricción de rango uno se obtiene la relajación de Goemans-Williamson:

\[
\begin{aligned}
\max_X\quad &\frac{1}{2}\sum_{\{i,j\}\in E}w_{ij}(1-X_{ij})\\
\text{s.t.}\quad &X\succeq0,\\
&X_{ii}=1\quad\forall i.
\end{aligned}
\]

De forma equivalente, con el Laplaciano ponderado \(L\), el objetivo es
\(\frac14\operatorname{Tr}(LX)\). El factor \(\frac12\) de la lista de
aristas y el factor \(\frac14\) del Laplaciano evitan contar dos veces las
aristas no dirigidas. Toda asignación discreta sigue siendo factible, por lo
que el valor de la SDP es una cota superior del óptimo exacto de Max-Cut.

Las formas de Ising y matricial son algebraicamente equivalentes antes de la
relajación y conducen a esta misma SDP. Una entrada de Ising puede evitar una
conversión intermedia, pero no cambia la resolución dominante de la SDP.
Cualquier afirmación práctica de velocidad requiere un benchmark reproducible
con el mismo solver, versiones, tolerancias, hardware, grafo y repeticiones.

## Interpretación geométrica y redondeo

Factorice una solución SDP numéricamente válida como \(X=VV^\top\). Cada
fila \(v_i\) es un vector unitario; su producto punto con \(v_j\) es
\(X_{ij}\), y su ángulo determina la probabilidad de que el redondeo por
hiperplano aleatorio separe los dos nodos.

En cada ronda, extraiga \(r\sim\mathcal N(0,I)\) de un generador local creado
con la semilla registrada. Asigne el nodo \(i\) a la partición positiva
cuando \(v_i^\top r\ge0\), y a la partición negativa en caso contrario. La
regla de cero inclusivo hace deterministas los empates numéricos exactos.
Ejecute un número positivo de rondas y conserve el corte de mayor peso;
conserve la ronda más temprana en caso de empate. Canonicalice las
particiones complementarias antes de devolverlas.

## Contrato numérico y del solver

- Acepte únicamente instancias de `networkx.Graph` con IDs de nodo en forma
  de cadena, sin auto-bucles, sin aristas paralelas, y con valores `weight`
  explícitos, finitos y no negativos.
- Permita grafos vacíos, desconectados, con peso cero y con nodos aislados.
  Un grafo vacío omite la SDP y devuelve un corte de valor cero y un valor de
  SDP cero.
- Resuelva con CVXPY y SCS. Registre el nombre del solver, el estado del
  solver, las opciones del solver, la semilla, las rondas solicitadas y la
  ronda ganadora.
- Acepte `optimal`; acepte `optimal_inaccurate` solo después de la validación
  posterior a la resolución. Genere un error para cualquier otro estado o si
  falta la matriz primal.
- Simetrice la matriz devuelta. Rechace violaciones de diagonal o de PSD por
  encima de la tolerancia documentada; recorte solo los autovalores negativos
  dentro de la tolerancia antes de construir los vectores, y luego normalice
  sus filas.

## Evaluación y garantía

Calcule el peso del corte una sola vez por arista del grafo. Cuando se
dispone de un óptimo exacto positivo, reporte

\[
\text{razón empírica}=\frac{\operatorname{Cut}_{GW}}{\operatorname{OPT}}.
\]

Para \(\operatorname{OPT}=0\), la razón no está definida y se reporta como
`None`, no como \(0/0\) ni como 1. El resultado \(\alpha_{GW}\approx0.87856\)
es una garantía esperada para un solo hiperplano aleatorio aplicado a una
solución SDP exacta; no es ni una cota inferior para cada ejecución con
semilla finita ni una afirmación sobre un resultado numéricamente
aproximado del solver. Seleccionar el mejor de varias rondas no puede reducir
el corte esperado ni el observado respecto de su primera ronda.

## Limitaciones

- La resolución de la SDP es el costo dominante y no escala como el paso de
  redondeo discreto.
- El redondeo varía según la semilla; las soluciones numéricas varían según
  el solver y la tolerancia.
- La garantía clásica asume pesos no negativos y una solución SDP exacta.
- Los pesos de la red son proxies de voltaje y no deben interpretarse como
  cantidades de flujo eléctrico o de resiliencia.

## Referencias

- M. X. Goemans y D. P. Williamson, *Improved Approximation Algorithms for
  Maximum Cut and Satisfiability Problems Using Semidefinite Programming*,
  JACM 42(6), 1995.
- H. Karloff, *How Good is the Goemans--Williamson MAX CUT Algorithm?*,
  SIAM Journal on Computing 29(1), 1999.
