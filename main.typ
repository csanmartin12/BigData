#import "template.typ": udp-template, title-page, RoyalBlue

#set text(lang: "es", region: "CL")
#set page(numbering: "1 ")
#set heading(numbering: "1.1")

#title-page(
  informe-nombre: "Proyecto semestral: Gestión de datos astronómicos",
  informe-num: "Informe 1 - Big Data - Sección 2",
  integrantes: "María José Choquehuanca, Cristian San Martín",
  correos: "maria.choquehuanca@mail.udp.cl, cristian.sanmartin@mail.udp.cl",
  profesor: "Sebastián Alvarado",
  ayudantes: "No",
  fecha: "7 de octubre de 2026",
)

#show: rest => udp-template(rest)

// ================================================================
// ESTILO PARA BLOQUES DE CÓDIGO
// ================================================================

#let CodeBg = rgb("#f6f8fa")
#let CodeBorder = rgb("#d0d7de")
#let CodeText = rgb("#24292f")

#show raw.where(block: true): set block(
  fill: CodeBg,
  stroke: 0.7pt + CodeBorder,
  radius: 4pt,
  inset: 10pt,
)

#show raw.where(block: true): set text(
  fill: CodeText,
  size: 9pt,
  font: "DejaVu Sans Mono",
)

#show raw.where(block: false): set text(
  fill: RoyalBlue,
  font: "DejaVu Sans Mono",
)

// ================================================================
// ÍNDICES
// ================================================================

#outline(
  title: text(16pt, weight: "bold", fill: RoyalBlue)[Índice de contenido],
)

#v(1.5em)

#outline(
  title: text(16pt, weight: "bold", fill: RoyalBlue)[Índice de figuras],
  target: figure.where(kind: image),
)

#v(1.5em)

#pagebreak()

// ================================================================
// INTRODUCCIÓN
// ================================================================
= Resumen

Este informe presenta el diseño inicial de una arquitectura de almacenamiento y búsqueda para datos astronómicos generados por el instrumento X-shooter del Very Large Telescope. Para ello se realizó un análisis exploratorio sobre 1.861 archivos FITS distribuidos en seis conjuntos de datos, cuyos encabezados fueron extraídos directamente mediante Python y Astropy, a partir de este proceso se identificaron 681 campos FITS distintos, con un promedio de 385,34 campos por archivo, un mínimo de 320 y un máximo de 557, además de un promedio de 2,75 campos presentes sin información útil. El análisis mostró que DATE-OBS y OBJECT se encuentran disponibles en todos los archivos, mientras que RA y DEC aparecen en 269 registros, equivalentes al 14,45 % de la muestra, asimismo, se identificaron 1.841 archivos de calibración, 18 archivos científicos y dos de adquisición, lo que muestra que la estructura de los encabezados y la disponibilidad de algunos campos depende del tipo de observación. Con estos resultados se propone utilizar MongoDB para almacenar e indexar los metadatos y HDFS para conservar los archivos FITS completos, junto con un modelo de datos que permite realizar búsquedas por coordenadas, fecha, objeto y clasificación de la observación, además de mantener la información restante del encabezado y la ruta hacia el archivo correspondiente. Finalmente, se definen reglas para determinar qué archivos participan en el buscador principal y cómo deben tratarse las distintas categorías, considerando que la solución corresponde a un diseño inicial y que todavía no se han realizado pruebas de rendimiento.

= Introducción

El Observatorio Europeo Austral opera distintas instalaciones destinadas a la adquisición de datos astronómicos, entre ellas el Very Large Telescope ubicado en Cerro Paranal, Chile. Uno de sus instrumentos es X-shooter, un espectrógrafo que genera observaciones almacenadas en archivos FITS, los cuales contienen tanto los datos obtenidos durante la observación como un encabezado con información sobre el objeto observado, las coordenadas, la fecha, el instrumento utilizado y distintas configuraciones asociadas al proceso de adquisición.

El proyecto plantea la necesidad de almacenar estos archivos y localizar posteriormente su ruta a partir de los metadatos disponibles. Como punto de partida se consideran RA, DEC, DATE-OBS y OBJECT, debido a que permiten realizar búsquedas por posición, fecha y objetivo @guia. Sin embargo, los encabezados FITS no presentan exactamente la misma estructura en todos los archivos, ya que determinados atributos aparecen solamente cuando son aplicables al tipo de observación correspondiente, por lo tanto, antes de seleccionar una tecnología de almacenamiento resulta necesario conocer cómo se distribuyen los campos y cuáles pueden ser más útiles para las búsquedas.

Para abordar este problema se extrajeron los encabezados de los archivos FITS y se realizó un análisis exploratorio sobre sus atributos, considerando la cantidad de campos por archivo, los campos presentes sin información, la varianza de los atributos numéricos, la cantidad de valores distintos en los atributos no numéricos y la presencia de valores de baja frecuencia. Además, se revisaron los campos principales del buscador y se agregó un análisis de valores atípicos numéricos mediante el rango intercuartílico, con el objetivo de distinguir entre valores poco frecuentes, diferencias propias del tipo de observación y posibles problemas en los datos.

A partir de estos resultados se evaluaron las tecnologías consideradas en la asignatura y se propone una arquitectura donde MongoDB almacena los metadatos utilizados para las consultas, mientras que HDFS conserva los archivos FITS completos. Asimismo, se plantea un modelo de datos que mantiene los campos principales de búsqueda, la ubicación del archivo y el resto de los metadatos extraídos, junto con reglas para definir cómo se incorporan y consultan las distintas categorías de archivos.

En las secciones siguientes se presentan primero los conceptos necesarios para entender el análisis y la propuesta, luego se describe el procedimiento utilizado para extraer y estudiar los datos, posteriormente se muestran los resultados obtenidos y, a partir de ellos, se desarrolla la selección de tecnologías y el modelo de datos. Finalmente, se resumen los principales resultados y las limitaciones de la propuesta.


= Marco Teórico

== FITS y metadatos

Los datos utilizados en este proyecto se encuentran almacenados en formato FITS, un estándar utilizado en astronomía para representar imágenes, espectros y otros productos científicos. Un archivo puede contener una o más unidades de datos acompañadas por encabezados, en los cuales se registran distintos parámetros necesarios para describir e interpretar la observación, como el instrumento utilizado, el objeto observado, las coordenadas o el momento en que se realizó la adquisición @dicd.

Entre los campos considerados para este proyecto se encuentran RA y DEC, que representan la ascensión recta y declinación, DATE-OBS, que identifica el inicio de la observación, y OBJECT, que indica el objetivo o tipo de exposición según corresponda. Además, los encabezados pueden incluir información sobre el tiempo de exposición, el telescopio, el programa de observación y la clasificación del archivo. Estos campos no tienen que estar presentes en todos los FITS, ya que la documentación de ESO establece que determinados atributos deben incluirse cuando son aplicables al archivo correspondiente, por ejemplo, RA y DEC no son obligatorios para ciertos archivos de calibración @dicd.

Otra parte importante de los metadatos corresponde a ESO DPR CATG, ESO DPR TYPE y ESO DPR TECH, que permiten describir la categoría, el tipo y la técnica utilizada en la observación. A través de estos valores se pueden diferenciar archivos científicos, calibraciones, adquisiciones y otras categorías, lo que posteriormente permite interpretar mejor los resultados y definir qué archivos participan en cada tipo de búsqueda @dicd.


== Análisis exploratorio

El análisis exploratorio permite conocer las características principales de un conjunto de datos antes de definir cómo será almacenado o procesado @guia. En este proyecto se utiliza para estudiar la estructura de los encabezados FITS, revisar qué información aparece con mayor frecuencia y detectar diferencias entre los distintos tipos de archivos.

Para los atributos numéricos se utiliza la varianza como medida de dispersión. Debido a que se trabaja con el conjunto completo disponible para esta entrega, se utiliza la varianza poblacional

$
sigma^2 = 1 / N sum_(i=1)^N (x_i - mu)^2
$

donde $N$ corresponde a la cantidad de valores disponibles, $x_i$ representa cada observación y $mu$ corresponde a la media. Una varianza mayor indica una mayor dispersión de los valores, aunque su magnitud depende de la escala y de las unidades del atributo, por lo tanto, no puede utilizarse por sí sola para decidir qué campo es más importante @montgomery.

En los atributos no numéricos se utiliza la cantidad de valores distintos, también denominada cardinalidad, para observar si un campo presenta pocas categorías o si cambia en gran parte de los archivos. Este resultado también ayuda a interpretar los valores de baja frecuencia, ya que un identificador como ARCFILE puede ser diferente en todos los registros sin que esto represente una anomalía.

Para estudiar los valores poco frecuentes se calcula la frecuencia relativa de cada valor utilizando solamente los registros donde el campo contiene información

$
f_r(v) = f(v) / N_c
$

donde $f(v)$ corresponde a la cantidad de veces que aparece un valor y $N_c$ a la cantidad de registros disponibles para ese campo. En este trabajo se considera de baja frecuencia un valor presente en menos del 1 % de estos registros, utilizando este porcentaje solamente como un criterio para identificar casos poco representados y no como una regla para determinar que un dato sea incorrecto.

Además, para algunos atributos numéricos se utiliza el rango intercuartílico o IQR, el cual se calcula a partir del primer y tercer cuartil

$
"IQR" = Q_3 - Q_1
$

y permite definir los límites

$
L_i = Q_1 - 1.5 dot "IQR"
$

$
L_s = Q_3 + 1.5 dot "IQR"
$

Un valor ubicado fuera de estos límites se considera estadísticamente atípico @montgomery. Sin embargo, esto no significa necesariamente que exista un error, ya que un valor puede ser poco común en el conjunto completo y al mismo tiempo ser normal dentro de un determinado tipo de observación. Por esta razón, los valores detectados deben revisarse considerando su contexto antes de tomar una decisión sobre ellos.


== Almacenamiento y búsqueda

Los encabezados FITS pueden contener una cantidad elevada de atributos y no todos aparecen en cada archivo, por lo que una base de datos documental resulta adecuada para representar este tipo de información. MongoDB almacena los registros mediante documentos que pueden contener atributos simples, estructuras anidadas y campos opcionales, además permite crear índices sobre aquellos valores que participan con mayor frecuencia en las consultas @mongodb.

En este proyecto MongoDB se considera para almacenar los metadatos y resolver las búsquedas, mientras que los archivos FITS completos se mantienen en HDFS. Este último corresponde a un sistema de archivos distribuido que permite almacenar información entre distintos nodos y utilizar replicación para mejorar la tolerancia frente a fallos @hdfs. De esta manera, el buscador puede trabajar con los metadatos sin tener que leer directamente los archivos binarios cada vez que se realiza una consulta.

Los índices permiten reducir la cantidad de documentos que deben revisarse durante una búsqueda, aunque también requieren almacenamiento y mantenimiento, por lo que no resulta conveniente crear uno para cada campo disponible. En consecuencia, la propuesta prioriza los atributos utilizados directamente para localizar y clasificar archivos, como fecha, objeto, coordenadas y categoría, mientras que el resto de los metadatos puede mantenerse disponible sin contar necesariamente con un índice propio.

= Desarrollo y Metodología

== Datos y extracción

El conjunto utilizado para el análisis estuvo compuesto por archivos generados por el instrumento X-shooter y distribuidos en seis archivos ZIP correspondientes al período entre el 4 y el 9 de septiembre de 2026. Los archivos fueron procesados directamente desde estos ZIP mediante un programa desarrollado en Python, obteniéndose los encabezados de 1.861 archivos FITS válidos.

La extracción se realizó con la biblioteca Astropy @astropy, considerando el encabezado de la unidad principal de cada FITS, de acuerdo con el alcance utilizado como referencia en el enunciado del proyecto. Para cada archivo se recorrieron las palabras clave presentes en el encabezado y se almacenaron sus valores, además del ZIP de origen y el nombre del archivo, de manera que fuera posible mantener la relación entre los metadatos extraídos y el FITS original.

Durante este proceso se excluyeron las entradas sin nombre y los campos `COMMENT`, `HISTORY` y `CONTINUE`, ya que pueden aparecer varias veces y cumplen principalmente una función descriptiva. Asimismo, si una misma palabra clave aparecía repetida dentro de un encabezado, se conservó una sola ocurrencia para el análisis tabular.

A partir de esta extracción se generó `headers.csv`, donde cada fila representa un archivo FITS y cada columna corresponde a un campo encontrado en al menos uno de los encabezados. Además, se mantuvo un archivo de registro para documentar posibles errores durante la lectura.


== Preparación y análisis de los datos

Antes de calcular las estadísticas se distinguió entre un campo que no aparece en un encabezado y uno que sí aparece, pero no contiene información útil. Para este último caso se consideraron cadenas vacías y marcadores como `UNKNOWN`, `NOT SET`, `TEL NAME NOT SET`, `N/A`, `NONE`, `NULL` y `UNDEFINED`. El valor `NA` no se incluyó, ya que dependiendo del campo puede corresponder a un código válido.

De esta manera, para cada FITS se registró la cantidad de campos presentes, la cantidad de campos presentes sin información y, de forma adicional, la cantidad de atributos que no aparecen respecto de los 681 campos distintos encontrados en el conjunto completo. Este último valor se utilizó solamente para describir las diferencias entre encabezados y no para considerar la ausencia de un campo como un error.

Luego los atributos fueron separados en numéricos y no numéricos según el tipo de dato reconocido al leer el archivo consolidado. El campo `DATASUM` se trató de forma explícita como texto, ya que aunque sus valores están compuestos por dígitos, corresponde a información de verificación y no a una variable numérica sobre la cual tenga sentido calcular medidas estadísticas.

Para los campos numéricos se calcularon la cantidad de valores disponibles, valores ausentes, valores distintos y la varianza poblacional. Los datos ausentes fueron excluidos del cálculo y, aunque la varianza se obtuvo para todos los atributos reconocidos como numéricos, su interpretación se realizó considerando la función de cada campo, debido a que algunos números pueden corresponder a identificadores y no a mediciones.

En los campos no numéricos se calculó la cantidad de valores distintos y la frecuencia de cada uno. Se consideró de baja frecuencia un valor presente en menos del 1 % de los registros que contienen información para ese campo, utilizando este porcentaje como un criterio de análisis y no como una regla para eliminar registros. Además, se calculó la proporción entre valores distintos y valores disponibles, marcando como alta cardinalidad aquellos campos donde esta relación fue igual o superior al 80 %. Este segundo umbral se utilizó únicamente como apoyo para diferenciar identificadores o fechas de campos categóricos.

Como complemento, se aplicó el criterio IQR a `EXPTIME`, `NAXIS1` y `NAXIS2`, ya que corresponden a variables numéricas con una interpretación directa y contienen información en todos los archivos analizados. Los valores detectados como atípicos se mantuvieron sin modificaciones y, en el caso de `EXPTIME`, el cálculo también se realizó separando los registros por categoría de observación y brazo instrumental, con el fin de revisar si un valor extremo dentro de la muestra completa también presentaba el mismo comportamiento dentro de su propio grupo.

Asimismo, se buscaron valores numéricos como `-9999`, `-999`, `9999`, `99999` y `999999`, debido a que podrían corresponder a códigos especiales utilizados por algunos atributos. Estos valores solo fueron registrados para su posterior revisión y no se reemplazaron automáticamente, ya que su significado depende del campo donde aparecen.

Finalmente, se revisaron con mayor detalle RA, DEC, DATE-OBS y OBJECT, debido a que corresponden a los principales criterios de búsqueda definidos por el proyecto. También se analizaron ARCFILE, MJD-OBS, EXPTIME, INSTRUME, TELESCOP, ESO OBS PROG ID y los campos ESO DPR CATG, ESO DPR TYPE y ESO DPR TECH, considerando su disponibilidad, cantidad de valores distintos y distribución dentro de la muestra.


== Diseño de la propuesta

A partir de los resultados del análisis exploratorio se compararon distintas tecnologías de almacenamiento, considerando la variabilidad de los encabezados FITS y los criterios de búsqueda requeridos. Posteriormente, se diseñó una arquitectura para almacenar los metadatos y los archivos completos, junto con un modelo de datos que permite realizar consultas por los atributos principales. Finalmente, se definieron índices y reglas de negocio para determinar cómo se incorporarán las distintas categorías de archivos al sistema. Estas decisiones corresponden al diseño de esta primera entrega, ya que MongoDB y HDFS todavía no fueron implementados y, por lo tanto, no se realizaron pruebas de rendimiento, capacidad o tiempo de respuesta.

= Análisis y Resultados

== Resultados generales

El procesamiento permitió analizar correctamente 1.861 archivos FITS distribuidos en seis conjuntos correspondientes a distintos días de observación. A partir de sus encabezados se identificaron 681 campos FITS distintos, de los cuales 416 fueron reconocidos como numéricos y 265 como no numéricos. Asimismo, no se encontraron valores duplicados ni en el nombre de origen ni en ARCFILE, por lo que no se detectaron duplicados según estos identificadores dentro de la muestra.

Debido a la cantidad de atributos encontrados, los cálculos se realizaron sobre todos los campos correspondientes, mientras que las tablas siguientes presentan una selección de aquellos más relevantes para el análisis.

#figure(
  table(
    columns: (3fr, 1.2fr),
    align: (left, center),
    inset: 4.5pt,
    table.header(
      [Indicador],
      [Resultado],
    ),
    [Archivos FITS analizados], [1.861],
    [Conjuntos ZIP], [6],
    [Campos FITS distintos], [681],
    [Campos numéricos], [416],
    [Campos no numéricos], [265],
    [Promedio de campos por FITS], [385,34],
    [Mínimo de campos por FITS], [320],
    [Máximo de campos por FITS], [557],
    [Promedio de campos presentes sin información], [2,75],
    [Mínimo de campos presentes sin información], [1],
    [Máximo de campos presentes sin información], [7],
    [Duplicados por archivo de origen], [0],
    [Duplicados por ARCFILE], [0],
  ),
  caption: [Resumen general del conjunto de datos analizado.],
) <tab-resumen-general>

Los 681 campos corresponden a la unión de todas las palabras clave encontradas en los encabezados y no a la cantidad de atributos presentes en cada archivo. En promedio, un FITS contiene 385,34 campos y solamente 2,75 de ellos están presentes sin información útil, mientras que 295,66 campos de la estructura total no aparecen en un archivo promedio. Esta diferencia es importante, ya que un campo ausente no necesariamente representa información faltante, sino que puede tratarse de un atributo que no corresponde al tipo de observación realizada.

Por lo tanto, la diferencia entre los 320 campos del encabezado más pequeño y los 557 del más grande muestra que la estructura no es completamente uniforme. Esto también influye en la elección de la tecnología, debido a que una estructura que obligue a todos los registros a contener los mismos 681 atributos generaría una gran cantidad de campos que no serían aplicables en muchos archivos.

Para los 416 campos numéricos se calculó la varianza poblacional, obteniéndose 262 atributos con varianza mayor que cero, 153 con varianza igual a cero y uno donde no fue posible calcularla por falta de valores disponibles. Algunos resultados representativos se muestran en la siguiente tabla.

#figure(
  table(
    columns: (1.5fr, 1fr, 1fr, 1.4fr),
    align: (left, center, center, right),
    inset: 4.5pt,
    table.header(
      [Campo],
      [Presentes],
      [Valores distintos],
      [Varianza],
    ),
    [RA], [269], [33], [15.306,68],
    [DEC], [269], [33], [809,40],
    [EXPTIME], [1.861], [192], [209.093,22],
    [NAXIS1], [1.861], [7], [353.221,54],
    [NAXIS2], [1.861], [7], [1.185.125,34],
    [MJD-OBS], [1.861], [1.860], [2,86],
  ),
  caption: [Varianza poblacional de campos numéricos seleccionados.],
) <tab-varianza>

EXPTIME presenta 192 valores distintos y una variación considerable entre los archivos, mientras que NAXIS1 y NAXIS2 poseen solo siete valores diferentes, relacionados con distintas dimensiones de los productos generados. Por otro lado, EQUINOX mantiene un único valor en los 269 registros donde se encuentra disponible, por lo que su varianza es igual a cero. En consecuencia, una varianza baja o nula no implica que un campo sea innecesario, ya que algunos atributos constantes siguen siendo importantes para interpretar correctamente los datos.

En los 265 campos no numéricos se calculó la cantidad de valores distintos. ARCFILE, DATE-OBS, CHECKSUM y DATASUM poseen un valor diferente para cada uno de los 1.861 archivos, mientras que otros atributos presentan una cantidad mucho menor de categorías.

#figure(
  table(
    columns: (2.1fr, 1fr, 1fr),
    align: (left, center, center),
    inset: 4.5pt,
    table.header(
      [Campo],
      [Presentes],
      [Valores distintos],
    ),
    [ARCFILE], [1.861], [1.861],
    [DATE-OBS], [1.861], [1.861],
    [CHECKSUM], [1.861], [1.861],
    [DATASUM], [1.861], [1.861],
    [OBJECT], [1.861], [18],
    [ESO DPR CATG], [1.861], [3],
    [ESO DPR TYPE], [1.861], [17],
    [ESO DPR TECH], [1.861], [7],
    [ESO OBS PROG ID], [1.861], [15],
    [INSTRUME], [1.861], [1],
  ),
  caption: [Cantidad de valores distintos en campos no numéricos seleccionados.],
) <tab-cardinalidad>

OBJECT presenta 18 valores distintos, mientras que ESO DPR CATG posee tres, ESO DPR TYPE posee 17 y ESO DPR TECH siete, por lo que estos campos permiten agrupar los archivos según su función y tipo de observación. En cambio, INSTRUME posee un único valor, XSHOOTER, lo que permite conservar la procedencia del archivo, pero dentro de esta muestra no entrega información suficiente para justificar un índice independiente.


== Valores poco frecuentes y atípicos

En los campos no numéricos se consideró como poco frecuente un valor presente en menos del 1% de los registros que contienen información para ese atributo. Este resultado debe interpretarse según el significado del campo, ya que ARCFILE o DATE-OBS poseen 1.861 valores poco frecuentes simplemente porque cada archivo tiene un valor diferente, lo que corresponde a su funcionamiento normal.

En los campos categóricos, en cambio, este análisis permite reconocer valores menos representados dentro de la muestra.

#figure(
  table(
    columns: (2fr, 1.2fr, 1.2fr, 1.1fr),
    align: (left, center, center, center),
    inset: 4pt,
    table.header(
      [Campo],
      [Valores poco frecuentes],
      [Registros afectados],
      [Porcentaje],
    ),
    [OBJECT], [8], [70], [3,76 %],
    [ESO DPR CATG], [2], [20], [1,07 %],
    [ESO DPR TYPE], [6], [50], [2,69 %],
    [ESO DPR TECH], [1], [9], [0,48 %],
    [ESO OBS PROG ID], [9], [96], [5,16 %],
  ),
  caption: [Valores de baja frecuencia en campos categóricos seleccionados.],
) <tab-baja-frecuencia>

En ESO DPR CATG los dos valores de baja frecuencia corresponden a SCIENCE y ACQUISITION, con 18 y dos archivos respectivamente, mientras que CALIB concentra 1.841 registros. Esto significa que el 98,93 % de la muestra corresponde a calibraciones, el 0,97 % a archivos científicos y el 0,11 % a adquisición.

SCIENCE aparece entonces como una categoría poco frecuente desde un punto de vista estadístico, sin embargo, corresponde precisamente a uno de los tipos de archivo de mayor interés para las búsquedas científicas. Por lo tanto, la baja frecuencia no debe utilizarse como una regla automática para eliminar información.

El análisis de valores atípicos numéricos mediante IQR se aplicó a EXPTIME, NAXIS1 y NAXIS2. Para EXPTIME se obtuvo un primer cuartil de 0,58 segundos, una mediana de 2,70 segundos y un tercer cuartil de 12,48 segundos, dando como resultado un límite superior de 30,33 segundos.

#figure(
  table(
    columns: (1.2fr, 0.8fr, 0.9fr, 0.8fr, 0.9fr, 1fr, 1fr, 0.8fr),
    align: center,
    inset: 3.5pt,
    table.header(
      [Campo],
      [$Q_1$],
      [Mediana],
      [$Q_3$],
      [IQR],
      [Límite inferior],
      [Límite superior],
      [Atípicos],
    ),
    [EXPTIME], [0,58], [2,70], [12,48], [11,90], [-17,27], [30,33], [216],
    [NAXIS1], [1.053], [2.048], [2.106], [1.053], [-526,50], [3.685,50], [0],
    [NAXIS2], [1.100], [1.500], [3.000], [1.900], [-1.750], [5.850], [0],
  ),
  caption: [Detección de valores atípicos mediante IQR.],
) <tab-iqr>

#figure(
  image("EXPTIME_boxplot.png", width: 70%),
  caption: [Distribución global de EXPTIME.],
) <fig-exptime>

En total se identificaron 216 valores atípicos globales para EXPTIME, equivalentes al 11,61% de la muestra, de los cuales 198 corresponden a CALIB y 18 a SCIENCE. A primera vista esto podría indicar que los tiempos utilizados en los archivos científicos son poco habituales, no obstante, al analizarlos dentro de su propia categoría se observa un comportamiento completamente consistente.

Los seis archivos SCIENCE correspondientes al brazo UVB utilizan un EXPTIME de 450 segundos, mientras que los seis archivos VIS y los seis NIR utilizan 480 segundos, sin detectarse valores atípicos dentro de ninguno de los tres grupos. De esta manera, los 18 archivos científicos son extremos solamente cuando se comparan con una muestra dominada por calibraciones de menor duración, lo que muestra que un outlier estadístico no debe interpretarse automáticamente como un error.

NAXIS1 y NAXIS2 no presentaron valores fuera de sus límites intercuartílicos. Asimismo, durante el análisis se detectaron posibles valores especiales, entre ellos -9999 en doce campos relacionados con parámetros de refracción y -999 en ESO OBS CONTAINER ID y ESO OBS CONTAINER PARENT ID. Estos valores se conservaron sin modificaciones, ya que su comportamiento resulta llamativo, pero el análisis estadístico por sí solo no permite determinar su significado.


== Campos relevantes para el buscador

RA, DEC, DATE-OBS y OBJECT fueron revisados de manera específica debido a que corresponden a los criterios principales definidos para el buscador. DATE-OBS y OBJECT se encuentran disponibles en todos los archivos, mientras que RA y DEC aparecen conjuntamente en 269 registros, equivalentes al 14,45 % de la muestra.

#figure(
  table(
    columns: (1.5fr, 1fr, 1fr, 1.2fr, 1.1fr),
    align: center,
    inset: 4.5pt,
    table.header(
      [Campo],
      [Presentes],
      [Ausentes],
      [Cobertura],
      [Valores distintos],
    ),
    [RA], [269], [1.592], [14,45 %], [33],
    [DEC], [269], [1.592], [14,45 %], [33],
    [DATE-OBS], [1.861], [0], [100 %], [1.861],
    [OBJECT], [1.861], [0], [100 %], [18],
  ),
  caption: [Disponibilidad de los campos principales del buscador.],
) <tab-campos-principales>

Los 18 archivos SCIENCE y los dos ACQUISITION poseen RA y DEC, además, 249 archivos CALIB también contienen ambas coordenadas, mientras que los 1.592 archivos restantes sin ellas corresponden a calibraciones. La documentación de ESO indica que estos campos son obligatorios cuando son aplicables y menciona, por ejemplo, que no tienen que estar presentes en un archivo BIAS @dicd. Por lo tanto, la ausencia de coordenadas no puede utilizarse como criterio general para considerar un archivo incompleto o inválido.

OBJECT también requiere una interpretación según el tipo de archivo, ya que en una observación científica representa el objetivo, mientras que en otros productos puede describir el tipo de exposición @dicd. En consecuencia, este campo debe conservarse junto con la categoría del archivo y no analizarse de manera aislada.

A partir de estos resultados se seleccionaron los atributos que conviene mantener de forma directa dentro del modelo. Esto no significa eliminar los demás metadatos, sino identificar aquellos que tienen una utilidad más clara para las búsquedas, la clasificación o la identificación de los archivos.

#figure(
  table(
    columns: (1.8fr, 3.9fr),
    align: (left, left),
    inset: 4.5pt,
    table.header(
      [Campo],
      [Uso dentro del modelo],
    ),
    [RA y DEC],
    [Búsquedas por posición. Su ausencia debe interpretarse según el tipo de archivo.],

    [DATE-OBS y MJD-OBS],
    [Búsquedas y ordenamiento por fecha. DATE-OBS posee cobertura completa.],

    [OBJECT],
    [Búsqueda por objetivo o tipo de exposición, interpretado junto con la categoría.],

    [ARCFILE],
    [Identificación de cada archivo dentro del catálogo. No presenta duplicados en la muestra.],

    [ESO DPR CATG, TYPE y TECH],
    [Clasificación del propósito, tipo y técnica de la observación.],

    [ESO OBS PROG ID],
    [Agrupación de archivos pertenecientes a un mismo programa de observación.],

    [EXPTIME],
    [Información sobre el tiempo de exposición.],

    [INSTRUME y TELESCOP],
    [Identificación del instrumento y telescopio de origen.],

    [CHECKSUM y DATASUM],
    [Información utilizada para verificar la integridad del archivo.],
  ),
  caption: [Campos principales considerados para el modelo de datos.],
) <tab-campos-preservar>

En suma, no resulta conveniente seleccionar campos únicamente por su varianza, frecuencia o cantidad de valores distintos. Un campo constante puede seguir siendo necesario para interpretar una observación, mientras que otro con valores únicos puede cumplir una función de identificación, por lo tanto, la selección final considera tanto las estadísticas obtenidas como el significado de cada atributo.


== Tecnología y arquitectura

Los resultados muestran que los encabezados presentan una estructura variable, ya que se encontraron 681 campos diferentes, pero un FITS contiene en promedio alrededor de 385. Por esta razón, para los metadatos resulta conveniente utilizar una estructura donde los atributos que no son aplicables puedan omitirse, mientras que los archivos FITS completos pueden almacenarse de manera independiente.

Un modelo puramente relacional podría resolver el problema, sin embargo, una tabla con una columna por cada uno de los 681 campos produciría una gran cantidad de valores ausentes y cambios de estructura al incorporar nuevos atributos. Otra posibilidad sería separar los datos en varias tablas, aunque esto aumentaría la cantidad de relaciones necesarias para reconstruir un encabezado o combinar varios criterios de búsqueda. Por lo tanto, se selecciona una base documental como una alternativa más directa para la estructura observada, sin considerar que SQL sea técnicamente incapaz de resolver el problema.

Las tecnologías consideradas en la asignatura cumplen funciones diferentes y fueron comparadas de acuerdo con el tipo de información que deben manejar.

#figure(
  table(
    columns: (1.4fr, 1.3fr, 3.7fr, 1.5fr),
    align: (left, left, left, left),
    inset: 4pt,
    table.header(
      [Tipo],
      [Tecnología],
      [Evaluación],
      [Uso],
    ),

    [Documental],
    [MongoDB],
    [Permite documentos con campos opcionales e índices sobre los atributos utilizados para las búsquedas.],
    [Metadatos],

    [Distribuida orientada a disco],
    [Hadoop/HDFS],
    [Permite almacenar archivos en distintos nodos y utilizar replicación frente a fallas.],
    [Archivos FITS],

    [Distribuida orientada a memoria],
    [Spark],
    [Puede utilizarse posteriormente para procesar o analizar grandes cantidades de datos.],
    [Complementario],

    [Orientada a columnas],
    [Cassandra],
    [Permite alta distribución, aunque su modelo suele diseñarse según consultas conocidas previamente.],
    [No seleccionada],

    [Grafos],
    [Neo4j],
    [Está orientada a consultas donde las relaciones entre entidades son el elemento principal.],
    [No seleccionada],

    [Clave-valor],
    [Redis],
    [Es útil para accesos rápidos mediante una clave, aunque las búsquedas del proyecto requieren varios atributos.],
    [No seleccionada],
  ),
  caption: [Comparación de las tecnologías consideradas.],
) <tab-tecnologias>

MongoDB se selecciona para los metadatos debido a que permite representar cada archivo mediante un documento con campos opcionales, lo que se ajusta a las diferencias encontradas entre los encabezados. Además, permite crear índices únicamente sobre los atributos utilizados para las búsquedas, mientras que los demás valores pueden seguir disponibles sin contar con un índice propio @mongodb.

HDFS se propone para conservar los archivos FITS completos, ya que cumple un papel diferente al de MongoDB y permite distribuir los archivos entre distintos nodos @hdfs. De esta manera, MongoDB mantiene la información utilizada para localizar una observación y guarda la ruta del FITS correspondiente, mientras que HDFS conserva el archivo original.

La consulta funciona entonces utilizando primero los metadatos. El usuario entrega criterios como objeto, fecha o coordenadas, MongoDB identifica los documentos que cumplen estas condiciones y, si posteriormente se necesita el archivo completo, la ruta almacenada permite recuperarlo desde HDFS.

#v(0.2cm)
#figure(
  grid(
    columns: (2fr, auto, 1.5fr, auto, 1.5fr),
    column-gutter: 2pt,
    align: center + horizon,

    rect(inset: 7pt, stroke: 0.7pt)[
      Consulta \
      RA, DEC, fecha u objeto
    ],

    [#sym.arrow.r],

    rect(inset: 7pt, stroke: 0.7pt)[
      MongoDB \
      metadatos e índices
    ],

    [#sym.arrow.r],

    rect(inset: 7pt, stroke: 0.7pt)[
      HDFS \
      archivos FITS
    ],
  ),
  kind: image,
  supplement: [Figura],
  caption: [Funcionamiento general de la arquitectura propuesta.],
) <fig-arquitectura>
#v(0.5cm)

La propuesta todavía no fue implementada, por lo que no se presentan mediciones de tiempo de respuesta, capacidad o rendimiento. Asimismo, si en una implementación futura se manejara una cantidad muy elevada de archivos pequeños, sería necesario revisar si HDFS continúa siendo la alternativa más conveniente.


== Modelo de datos y reglas

Se propone representar cada archivo FITS mediante un documento independiente en MongoDB, separando la información utilizada por el buscador, los datos necesarios para localizar el archivo y los demás metadatos extraídos desde el encabezado. ARCFILE se utiliza como `_id`, ya que los 1.861 valores encontrados en la muestra son diferentes y MongoDB mantiene automáticamente un índice único sobre este atributo.

El siguiente ejemplo muestra la estructura propuesta. Los valores son ilustrativos y representan cómo podría almacenarse posteriormente uno de los archivos.

#figure(
```json
{
  "_id": "XSHOO.2026-09-06T08:04:59.035.fits",

  "search": {
    "object": "EUCLJ0353-4950",
    "ra": 58.474525,
    "dec": -49.847820,
    "date_obs": {
      "$date": "2026-09-06T08:04:59.035Z"
    },
    "mjd_obs": 61289.336794393,
    "exptime": 450.0,

    "dpr": {
      "catg": "SCIENCE",
      "type": "OBJECT",
      "tech": "ECHELLE,SLIT,NODDING"
    },

    "program_id": "117.2ADK.001",
    "instrument": "XSHOOTER",
    "telescope": "ESO-VLT-U3"
  },

  "storage": {
    "hdfs_path": "/eso/xshooter/2026/09/06/XSHOO.2026-09-06T08:04:59.035.fits",
    "checksum": "...",
    "datasum": "..."
  },

  "header": {
    "...": "otros metadatos extraídos"
  }
}
```,
  kind: image,
  supplement: [Figura],
  caption: [Ejemplo de la estructura propuesta para un archivo FITS.],
) <fig-documento-mongo>

La sección `search` contiene los atributos que se utilizan directamente para consultar o clasificar los archivos, mientras que `storage` mantiene la ruta del FITS original junto con CHECKSUM y DATASUM. Por otro lado, `header` conserva los demás metadatos extraídos que no forman parte del conjunto principal de búsqueda. El archivo FITS original permanece sin modificaciones en HDFS, por lo que sigue siendo la fuente completa de la información original.

DATE-OBS se almacena como fecha para facilitar búsquedas por intervalos, mientras que RA y DEC se mantienen como valores numéricos cuando están disponibles. Debido a que estas coordenadas no aparecen en todos los archivos, el modelo permite que sean opcionales y no considera su ausencia como un error por sí sola.

No se propone crear índices sobre los 681 campos, sino solamente sobre los atributos que tienen una utilidad directa para las consultas principales.

#figure(
  table(
    columns: (1.5fr, 2.2fr, 3.4fr),
    align: (left, left, left),
    inset: 4pt,
    table.header(
      [Índice],
      [Campo],
      [Uso],
    ),
    [Único],
    [`_id` mediante ARCFILE],
    [Identificación del archivo y control de duplicados.],

    [Simple],
    [`search.date_obs`],
    [Búsquedas y ordenamiento por fecha.],

    [Simple],
    [`search.object`],
    [Búsquedas por objetivo o tipo de exposición.],

    [Compuesto],
    [`search.ra` y `search.dec`],
    [Filtrado inicial mediante intervalos de coordenadas.],

    [Compuesto],
    [`search.dpr.catg` y `search.dpr.type`],
    [Clasificación de archivos por categoría y tipo.],

    [Opcional],
    [`search.program_id`],
    [Puede incorporarse si las consultas por programa son frecuentes.],
  ),
  caption: [Índices iniciales propuestos para MongoDB.],
) <tab-indices>

El índice compuesto de RA y DEC permite acotar consultas por intervalos, aunque una búsqueda basada en distancia angular exacta requeriría un método espacial más específico, lo que puede evaluarse en una etapa posterior. Asimismo, INSTRUME y TELESCOP se conservan, pero no se priorizan como índices debido a su baja variación dentro de esta muestra.

Las reglas de negocio se definieron a partir de la clasificación observada y de la documentación de ESO. La propuesta no elimina automáticamente archivos por ser poco frecuentes ni por carecer de coordenadas, sino que modifica la forma en que participan dentro del buscador.

#figure(
  table(
    columns: (1.5fr, 2fr, 4fr),
    align: (left, left, left),
    inset: 4pt,
    table.header(
      [Categoría],
      [Uso],
      [Tratamiento propuesto],
    ),

    [SCIENCE],
    [Búsqueda principal],
    [Se conserva el FITS y sus metadatos, además aparece por defecto en las búsquedas científicas.],

    [CALIB],
    [Consulta de calibraciones],
    [Se conserva el FITS y sus metadatos. La ausencia de RA o DEC no provoca su descarte.],

    [ACQUISITION],
    [Consulta auxiliar],
    [Se conserva, aunque no aparece por defecto cuando se solicitan solamente observaciones científicas.],

    [TECHNICAL],
    [Fuera de la búsqueda principal],
    [Si aparece en datos futuros, se conserva, puede mantenerse fuera de la búsqueda científica principal y, si se requiere, trasladarse a almacenamiento secundario.],

    [TEST],
    [Fuera de la búsqueda principal],
    [Se conserva para revisión, pero no aparece por defecto en las búsquedas científicas.],

    [OTHER],
    [Revisión],
    [Se conserva hasta determinar su función antes de decidir si participa en el buscador principal.],
  ),
  caption: [Tratamiento propuesto según la categoría del archivo.],
) <tab-reglas-categoria>

La categoría CALIB representa el 98,93% de la muestra, sin embargo, no se considera información prescindible, ya que estos archivos son necesarios para el procesamiento e interpretación de observaciones científicas. Asimismo, ESO distingue categorías como SCIENCE, CALIB, ACQUISITION, TECHNICAL, TEST y OTHER, por lo que la regla debe considerar el propósito de cada archivo y no solamente su frecuencia @dicd.

Además de la categoría se plantean algunas reglas generales para incorporar nuevos archivos al sistema.

#figure(
  table(
    columns: (0.8fr, 5.9fr),
    align: (center, left),
    inset: 4pt,
    table.header(
      [Regla],
      [Descripción],
    ),

    [R1],
    [ARCFILE debe estar disponible y no puede entrar en conflicto con otro archivo ya registrado con información diferente.],

    [R2],
    [DATE-OBS y OBJECT deben conservarse y validarse cuando estén disponibles.],

    [R3],
    [RA y DEC se revisan como un par cuando sean aplicables, pero su ausencia no invalida automáticamente un archivo.],

    [R4],
    [Los valores poco frecuentes y los outliers no se eliminan automáticamente, primero se interpretan según el tipo de observación.],

    [R5],
    [CHECKSUM, DATASUM y los posibles valores especiales se conservan sin modificar mientras no exista evidencia suficiente para tratarlos de otra forma.],

    [R6],
    [Los archivos que no puedan leerse correctamente o presenten conflictos de identificación se separan para revisión en lugar de eliminarse.],
  ),
  caption: [Reglas generales para la incorporación de archivos.],
) <tab-reglas-ingesta>

Estas reglas permiten distinguir entre almacenar un archivo, conservar sus metadatos y mostrarlo por defecto en una búsqueda. En esta primera propuesta se evita el descarte automático y se prioriza la conservación del FITS original, mientras que la visibilidad dentro del buscador depende de la categoría y del tipo de consulta.

Finalmente, el modelo corresponde a una propuesta inicial basada en seis días de archivos X-shooter, por lo que la incorporación de otros instrumentos o períodos puede generar nuevos campos y patrones de búsqueda. En consecuencia, los índices y reglas deberán revisarse cuando exista una implementación real y se disponga de información sobre las consultas y volúmenes utilizados.

= Conclusión

El análisis permitió caracterizar los metadatos de 1.861 archivos FITS generados por X-shooter y comprobar que sus encabezados no siguen una estructura completamente uniforme. En total se identificaron 681 campos distintos, de los cuales 416 fueron clasificados como numéricos y 265 como no numéricos, mientras que cada archivo contiene en promedio 385,34 campos y solo 2,75 campos presentes sin información útil. Además, DATE-OBS y OBJECT se encuentran disponibles en todos los registros, mientras que RA y DEC aparecen en 269 archivos, por lo que la ausencia de estos últimos debe interpretarse según el tipo de observación y no como un error general.

El análisis de frecuencia y de valores atípicos mostró también que un dato poco común no necesariamente corresponde a información incorrecta. SCIENCE representa menos del 1 % de la muestra y, aun así, corresponde a una de las categorías más importantes para el buscador. De manera similar, el criterio IQR identificó 216 valores atípicos globales en EXPTIME, incluidos los 18 archivos científicos, sin embargo, al compararlos dentro de su categoría y brazo instrumental ninguno presentó un comportamiento anormal. Por lo tanto, tanto los valores poco frecuentes como los outliers deben analizarse considerando el contexto antes de definir reglas de eliminación o modificación.

A partir de estos resultados se propone utilizar MongoDB para almacenar y consultar los metadatos, mientras que HDFS se utiliza para conservar los archivos FITS completos. Esta separación permite realizar búsquedas por fecha, objeto, coordenadas y clasificación sin tener que revisar directamente los archivos binarios en cada consulta. Asimismo, el modelo mantiene ARCFILE como identificador, conserva los campos principales de búsqueda y guarda los demás metadatos extraídos sin obligar a que todos los documentos tengan exactamente la misma estructura. Las reglas propuestas también diferencian entre conservar un archivo, mantener sus metadatos disponibles y mostrarlo por defecto en una búsqueda científica, evitando descartar información únicamente por su frecuencia o por la ausencia de determinados campos.

En suma, la propuesta cumple con el objetivo de definir una arquitectura inicial capaz de organizar los metadatos y facilitar la localización de los archivos FITS a partir de los criterios planteados en el proyecto. No obstante, el análisis se encuentra limitado a seis días de datos provenientes únicamente de X-shooter y la arquitectura todavía no fue implementada, por lo que no se dispone de mediciones reales de rendimiento o capacidad. Como trabajo posterior será necesario probar el modelo con otros instrumentos y períodos de observación, implementar MongoDB y HDFS y revisar los índices y reglas según las consultas que se utilicen en un entorno real.


#pagebreak()
= Bibliografía
#bibliography("referencias.bib", title: none, style: "apa")

#pagebreak()
= Anexos

== Anexo A: Boxplots adicionales

Los siguientes gráficos complementan el análisis de valores atípicos presentado anteriormente. Tanto NAXIS1 como NAXIS2 presentan distintas dimensiones dentro de la muestra, sin embargo, ninguno contiene valores fuera de los límites calculados mediante IQR.

#figure(
  image("NAXIS1_boxplot.png", width: 65%),
  caption: [Distribución de NAXIS1 mediante boxplot.],
)

#figure(
  image("NAXIS2_boxplot.png", width: 65%),
  caption: [Distribución de NAXIS2 mediante boxplot.],
)


== Anexo B: Posibles valores especiales

Durante el análisis se encontraron algunos valores numéricos que podrían corresponder a códigos especiales utilizados por determinados atributos. Debido a que su significado no puede determinarse únicamente mediante el análisis estadístico, estos valores se mantuvieron sin modificaciones y se registraron para su posterior revisión.

#figure(
  table(
    columns: (3fr, 1fr, 1.2fr),
    align: (left, center, center),
    inset: 4.5pt,
    table.header(
      [Campo],
      [Valor],
      [Apariciones],
    ),
    [12 campos asociados a ESO INS TILT1/TILT2/TILT3 REFRAC], [-9999], [1.477 por campo],
    [ESO OBS CONTAINER ID], [-999], [579],
    [ESO OBS CONTAINER PARENT ID], [-999], [656],
  ),
  caption: [Posibles valores especiales encontrados durante el análisis.],
)