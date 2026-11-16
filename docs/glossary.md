# Glossary

The words below have one meaning each across the code, the documentation, the
interface and the manual. The manual's terminology section is built from this table.
The Spanish column is the term used in the Spanish interface and manual; the
Portuguese column is filled in by the translator.

Agreed with Rob in session S006 (2026-11-15).

| Term (en) | Término (es) | Termo (pt) | Meaning | Matplotlib counterpart |
|---|---|---|---|---|
| **Project** | Proyecto | | The file the user saves and opens. Holds one or more canvases. | — |
| **Canvas** | Lienzo | | One complete figure: what is exported as one image. Holds a grid of panels. | `Figure` |
| **Grid** | Cuadrícula | | How a canvas is divided: columns and rows with relative widths and heights. A cell may hold a panel or a smaller grid. | `GridSpec` |
| **Panel** | Panel | | One plot: a drawing area with its axes. | `Axes` |
| **Subplots** | Subgráficas | | A canvas with more than one panel. Not an object: a property of the canvas grid. | `subplots` |
| **Inset** | Recuadro | | A small panel placed on top of another panel. There are two kinds, below. | `inset_axes` |
| **Zoom inset** | Recuadro de ampliación | | An inset showing a region of the panel under it, with the same layers, live. Its x axis follows the panel under it. | `inset_axes` |
| **Free inset** | Recuadro libre | | An inset with its own layers and axes, independent of the panel under it. | `inset_axes` |
| **Axis** | Eje | | The x axis or a y axis of a panel: quantity, unit, limits and display options. | `Axis` |
| **Secondary x axis** | Eje x secundario | | A second x scale drawn under the main one, showing the same positions in another unit. Display only; it holds no data. | `secondary_xaxis` |
| **Break** | Corte | | An x interval hidden from a panel. Reserved for v1.1. | several `Axes` |
| **Series** | Serie | | Any x–y data set with a quantity and unit on each axis. The generic base of every plotted data set. | — |
| **Spectrum** | Espectro | | A series that is also declared UV-Vis or IR (technique) and theoretical or experimental (origin). | — |
| **Curve** | Curva | | A series sampled as a continuous line. | — |
| **Sticks** | Bastones | | The transitions or modes of a calculation: a position and an intensity each, before broadening. | — |
| **Broadening** | Ensanchamiento | | Line shape, FWHM and frequency scale factor: turns sticks into a curve. | — |
| **Layer** | Capa | | One series drawn in one panel, with its style, its transforms and the y axis it belongs to. The same series may appear in several panels, as different layers. | `Line2D`, `LineCollection` |
| **Transform** | Transformación | | An operation on y values (normalise, level, T↔A, log, inverse), stored as parameters and applied when drawing. Never changes the data. | — |
| **Crop** | Recorte | | Keeping only an x interval of a layer's data. | — |
| **View limits** | Límites de vista | | The visible range of an axis (zoom). Changes nothing in the data. | `set_xlim`, `set_ylim` |
| **Layer arrangement** | Disposición de las capas | | How the layers sharing a y axis are placed vertically: overlap, normalised overlap or stacked. | — |
| **Overlap** | Superposición | | Every layer with its own y values, drawn on top of each other. | — |
| **Normalised overlap** | Superposición normalizada | | Every layer scaled to a maximum of 1, drawn on top of each other. | — |
| **Stacked** | Apilado | | Every layer shifted upwards so that they do not touch. May be combined with normalisation. | — |
| **Compatible (y)** | Compatible (y) | | Two layers whose y values can share a y axis without normalising: same technique and same quantity (generic series: same quantity). | — |
