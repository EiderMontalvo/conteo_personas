# Diseño del dashboard

Panel operativo para quien vigila el aforo en tiempo real. La pregunta de cada pantalla manda sobre la decoración.

## Pantallas y su pregunta

| Pantalla | Pregunta que responde |
|---|---|
| Monitoreo | ¿Cuánta gente hay ahora, qué tan cerca del límite, y las cámaras están vivas? |
| Analítica | ¿Cómo se movió la gente en un periodo y cuándo hay picos? |
| Aforo | ¿Qué espacio está cerca de su límite? |
| Ajustes | ¿Qué cámaras hay, cómo están conectadas y con qué umbrales se alerta? |

## Color

Tema oscuro completo (sala de monitoreo: el video luce y cansa menos la vista). Grises azulados casi negros y un solo acento cian.

| Token | Valor | Uso |
|---|---|---|
| `--bg` / `--surface` / `--surface-2` | `#0D1015` / `#151A21` / `#1B2129` | Página, tarjetas, controles |
| `--border` / `--border-strong` | `#252C36` / `#343C48` | Bordes y divisores |
| `--text` / `--text-2` / `--text-3` | `#E6E9EE` / `#A2AAB6` / `#8A93A0` | Texto principal, secundario, ejes (≥ 4.5:1 sobre las superficies) |
| `--ink` | `#090B0F` | Barra lateral |
| `--accent` / `--accent-strong` | `#2FC6D6` / `#22B5C6` | Serie "Entradas", anillos, botón principal (texto oscuro `--on-accent` encima) |
| `--series-out` | `#8590A2` | Serie "Salidas" |
| `--ok` / `--warn` / `--danger` | `#3CC287` / `#E8A93C` / `#F26B5E` | Estado de aforo y de conexión, siempre con ícono y texto |

El cian no se usa para estados, y los estados no se usan para series: cada color significa una sola cosa.
Los colores que necesitan los gráficos desde JS viven en `src/components/theme.js` y deben coincidir con `index.css`.

## Forma

- Radios: 6 px en controles, 10 px en elementos internos, 14 px en tarjetas. Nada totalmente redondeado (sin píldoras).
- Tarjetas planas con borde de 1 px; la sombra queda solo para modales y menús flotantes.
- El video en vivo va sobre negro puro con datos superpuestos (cámara, EN VIVO solo si llegan imágenes, hora, conteos).
- Estados como texto con ícono, no como cápsulas de color.

## Tipografía

Archivo variable (autoalojada, funciona sin internet). El eje de ancho hace el trabajo de dos familias:
títulos y cifras en 118 % de ancho, texto corrido en 100 %. Cifras con `tabular-nums` para que no salten al actualizarse.

## Movimiento

Solo transiciones de estado (hover, foco, apertura de modal) de 150–200 ms. Nada en bucle. Se respeta `prefers-reduced-motion`.
