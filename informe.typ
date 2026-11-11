// =====================================================================
// Proyecto Semestral - Gestión de Datos Astronómicos
// Big Data - Sección 2 - Segundo Semestre 2026
// Universidad Diego Portales
// =====================================================================
// COMPLETAR antes de entregar: nombres y correos de los integrantes
// (buscar el marcador "INTEGRANTE" más abajo).
// =====================================================================

#set document(
  title: "Gestión de Datos Astronómicos: Diseño de un Motor de Búsqueda para Metadatos de Observaciones ESO",
  author: ("Integrante 1", "Integrante 2"),
)

#set text(font: "New Computer Modern", lang: "es", size: 11pt)
#set par(justify: true, leading: 0.65em, first-line-indent: 0pt)
#set heading(numbering: "1.1")
#set table(stroke: 0.5pt + rgb("#999999"))

// ---------------------------------------------------------------------
// Encabezado institucional (aparece en cada página)
// ---------------------------------------------------------------------
#let udp_header = grid(
  columns: (auto, 1fr),
  align: (left + horizon, right + horizon),
  column-gutter: 1fr,
  image("assets/udp_logo.png", width: 4.2cm),
  text(size: 8.5pt, style: "italic")[
    Universidad Diego Portales \
    Facultad de Ingeniería y Ciencias \
    Ingeniería Civil en Informática y Telecomunicaciones \
    Big Data - Sección 2 \
    Segundo Semestre 2026
  ],
)

#set page(
  paper: "a4",
  margin: (top: 3.4cm, bottom: 2.6cm, x: 2.4cm),
  numbering: "1",
  header: [
    #udp_header
    #v(-0.3em)
    #line(length: 100%, stroke: 0.6pt + rgb("#c0392b"))
  ],
)

// ---------------------------------------------------------------------
// Estilo de encabezados de sección
// ---------------------------------------------------------------------
#show heading.where(level: 1): it => [
  #v(0.6em)
  #set text(size: 14pt, weight: "bold", fill: rgb("#c0392b"))
  #block(it)
  #v(0.2em)
]
#show heading.where(level: 2): it => [
  #v(0.4em)
  #set text(size: 12pt, weight: "bold")
  #block(it)
]

#show link: it => text(fill: rgb("#1a5276"), it)

// =====================================================================
// PORTADA / TÍTULO
// =====================================================================
#align(center)[
  #v(1.5cm)
  #image("assets/udp_logo.png", width: 6.5cm)
  #v(1.2cm)
  #text(size: 11pt)[Facultad de Ingeniería y Ciencias \
  Ingeniería Civil en Informática y Telecomunicaciones \
  Big Data - Sección 2 — Segundo Semestre 2026]

  #v(2.2cm)
  #text(size: 20pt, weight: "bold")[
    Gestión de Datos Astronómicos: \
    Diseño de un Motor de Búsqueda para \
    Metadatos de Observaciones del Very Large Telescope (ESO)
  ]

  #v(0.5cm)
  #text(size: 13pt, style: "italic")[Primera Entrega — Proyecto Semestral]

  #v(2cm)
  #text(size: 12pt)[
    *Integrantes:* \
    ⟨Nombre Apellido 1⟩ — ⟨correo1⟩\@mail.udp.cl \
    ⟨Nombre Apellido 2⟩ — ⟨correo2⟩\@mail.udp.cl
  ]

  #v(1cm)
  #text(size: 12pt)[
    *Profesor:* Sebastián I. Alvarado Aceituno \
    sebastian.alvarado2\@mail.udp.cl
  ]

  #v(1.5cm)
  #text(size: 11pt)[Santiago, Chile — Septiembre de 2026]
]

#pagebreak()

// =====================================================================
// RESUMEN
// =====================================================================
= Resumen

El Observatorio Europeo Austral (ESO) opera instrumentos como el espectrógrafo
X-shooter, instalado en el Very Large Telescope (VLT) en Cerro Paranal, los
cuales generan diariamente un enorme volumen de archivos en formato FITS,
cada uno acompañado de un encabezado (_header_) con centenares de metadatos
técnicos y científicos. Este informe corresponde a la primera entrega de un
proyecto semestral cuyo objetivo final es diseñar la arquitectura de
almacenamiento y un motor de búsqueda que permita a investigadores de todo
el mundo encontrar rápidamente observaciones a partir de sus coordenadas
espaciales, fecha de observación u objeto astronómico.

En esta etapa se realizó un análisis exploratorio de datos (EDA) sobre una
muestra real de *1.861 archivos* y *682 campos* de encabezado provenientes
del instrumento X-shooter, calculando la cantidad de campos presentes y
vacíos por archivo, la varianza de los campos numéricos, la cardinalidad de
los campos no numéricos y la frecuencia de sus valores atípicos. Los
resultados muestran una fuerte heterogeneidad estructural: el número de
campos poblados por archivo varía entre 319 y 556 (promedio 385,8; 56,6 %
de los 682 posibles), y campos obligatorios como *RA* y *DEC* solo están
presentes en el 14,5 % de los registros, concentrados casi exclusivamente en
observaciones científicas y en un subconjunto específico de calibraciones.

A partir de estos hallazgos se justifica que un modelo puramente relacional
no es adecuado para este volumen y variabilidad de datos, y se propone una
arquitectura políglota compuesta por una *base de datos documental
(MongoDB)* para los metadatos indexables y un *almacenamiento de objetos*
para los archivos binarios FITS. Finalmente, se define un modelo de datos
orientado a documentos con índices geoespaciales y temporales, junto con
reglas de negocio —derivadas directamente del EDA— para distinguir los
archivos que deben indexarse en el buscador principal de aquellos que deben
moverse a almacenamiento secundario.

= Introducción

El Observatorio Europeo Austral (ESO) opera algunos de los telescopios más
avanzados del mundo @eso_archive, entre ellos el Very Large Telescope (VLT)
ubicado en Cerro Paranal, Región de Antofagasta, Chile. Instrumentos como el
espectrógrafo de eco X-shooter @eso_xshooter generan, para un solo evento de
observación, decenas de archivos agrupados: la observación científica
principal (_Science Frame_) y múltiples archivos de calibración (_Bias_,
_Flats_, _Arcs_, _Darks_, entre otros). Cada archivo se almacena en formato
binario estándar FITS, compuesto por un encabezado extenso de metadatos y el
cuerpo de la imagen.

Nuestro equipo fue contratado como el equipo de Ingeniería de Datos
responsable de diseñar la nueva arquitectura de almacenamiento y búsqueda
para estos datos, de modo que investigadores de todo el mundo puedan
consultar y encontrar rápidamente la ruta de almacenamiento de las imágenes
científicas a partir de sus coordenadas espaciales (_Right Ascension_ y
_Declination_), su fecha de observación, el nombre de su objetivo, o
cualquier otro atributo relevante.

Para esta primera entrega, el trabajo se organizó en tres etapas
consecutivas, que se corresponden con las secciones de este informe:

1. *Análisis exploratorio* (@marco-teorico y @desarrollo): caracterización
  estadística de los 682 campos que componen el encabezado de los archivos
  FITS disponibles, con el fin de identificar cuáles son relevantes de
  preservar en el modelo de datos.
2. *Definición de tecnología* (@resultados-tecnologia): selección justificada
  del tipo de base de datos a utilizar para los metadatos indexables y para
  los archivos binarios pesados, argumentando por qué un modelo puramente
  relacional no es el más adecuado.
3. *Definición del modelo de datos* (@resultados-modelo): diseño del esquema
  que soportará el motor de búsqueda, junto con las reglas de negocio que
  distinguen los archivos indexables de aquellos que deben moverse a
  almacenamiento secundario.

El documento se estructura de la siguiente forma: la @marco-teorico
presenta los conceptos técnicos utilizados (formato FITS, Big Data, bases de
datos NoSQL); la @desarrollo detalla la metodología seguida para extraer y
analizar los datos; la @resultados presenta los resultados del EDA, la
tecnología escogida y el modelo de datos propuesto; y finalmente la
@conclusion resume lo realizado y verifica el cumplimiento de los objetivos
de esta primera entrega.

= Marco Teórico <marco-teorico>

== Big Data y sus dimensiones

Se entiende por Big Data a conjuntos de datos cuyo volumen, velocidad de
generación y variedad estructural superan la capacidad de las herramientas
de gestión de datos tradicionales. En el caso del archivo científico de
ESO, las tres dimensiones se manifiestan claramente: *volumen*, porque un
solo instrumento como X-shooter genera miles de archivos por semana y el
observatorio en su conjunto produce terabytes de información diaria;
*variedad*, porque cada encabezado FITS puede contener cientos de campos de
tipos heterogéneos (booleanos, enteros, flotantes, cadenas de texto) cuya
presencia depende del instrumento, el brazo óptico y la plantilla de
observación utilizada; y *velocidad*, porque las exposiciones se registran
de forma continua durante toda la noche de observación, con tiempos de
integración que van desde fracciones de segundo hasta una hora.

== El formato FITS y sus encabezados

FITS (_Flexible Image Transport System_) es el estándar binario utilizado
por la comunidad astronómica para el intercambio de imágenes y datos
tabulares @fits_standard. Cada archivo FITS contiene una Unidad de Datos
Primaria compuesta por un encabezado (_header_) de metadatos en pares
clave-valor y un cuerpo con la imagen o el espectro. ESO extiende el
estándar FITS con un conjunto propio de palabras clave jerárquicas
identificadas con el prefijo `HIERARCH ESO`, organizadas en categorías como
`DET` (detector), `INS` (instrumento), `TEL` (telescopio), `OBS`
(observación), `DPR` (producto de datos) y `TPL` (plantilla de
observación) @eso_icd. Esta nomenclatura jerárquica (por ejemplo,
`ESO TEL AMBI TEMP` o `ESO DET WIN1 NX`) es clave para el diseño del
modelo de datos propuesto en la @resultados-modelo, ya que se traduce de
forma natural en sub-documentos anidados.

El documento _Data Interface Control Document_ de ESO @eso_icd —el
"diccionario" de datos oficial— define además las palabras clave `DPR.CATG`,
`DPR.TYPE` y `DPR.TECH`, que en conjunto describen de forma única el
propósito y la técnica de cada observación. En particular, `DPR.CATG` debe
tomar uno de seis valores posibles (`SCIENCE`, `CALIB`, `ACQUISITION`,
`TECHNICAL`, `TEST`, `OTHER`), y es determinante para saber si un archivo
corresponde a una observación científica o a una calibración instrumental
@eso_icd. Como se muestra en la @resultados, esta clasificación resultó
ser la variable más relevante para definir las reglas de negocio del
proyecto.

== Análisis exploratorio de datos (EDA)

El análisis exploratorio de datos es un proceso para analizar e investigar
conjuntos de datos y resumir sus características principales, a menudo
empleando métodos de visualización de datos @ibm_eda. En este proyecto el
EDA cumple un rol instrumental: permite decidir, de manera informada y no
arbitraria, qué campos de un encabezado con cientos de atributos deben
preservarse en el modelo de datos definitivo y cuáles pueden descartarse
por no aportar poder de discriminación (varianza nula, cardinalidad 1) o
por no estar disponibles de forma consistente.

== Modelo relacional versus modelo NoSQL

El modelo relacional exige que todas las filas de una tabla compartan un
esquema fijo de columnas, definido _a priori_. Cuando los datos son
dispersos (muchos valores nulos) y su esquema cambia según el origen —como
ocurre con los encabezados FITS de distintos instrumentos y plantillas de
observación—, este modelo produce tablas extremadamente anchas y
mayoritariamente vacías, o bien obliga a normalizar en un esquema
entidad-atributo-valor (EAV) que degrada el rendimiento de las consultas.
Las bases de datos NoSQL —y en particular las bases de datos documentales
como MongoDB— surgen como respuesta a estos escenarios de alta variedad y
volumen, permitiendo que cada documento tenga su propio conjunto de campos
y que el esquema evolucione sin necesidad de migraciones costosas
@sadalage_fowler. Los documentos, habitualmente en formato JSON/BSON, se
adaptan además de forma natural a estructuras jerárquicas como las
categorías `DET`/`INS`/`TEL` de los encabezados ESO, y soportan índices
compuestos, geoespaciales y de texto sobre cualquier campo, sin necesidad
de reunir información mediante `JOIN`s @mongodb_docs.

== Herramientas utilizadas

Para el análisis exploratorio se utilizó Python con las bibliotecas
`pandas` (cómputo estadístico y tabular) y `astropy.io.fits`
@astropy, esta última mencionada en el material del curso como la
herramienta estándar para leer encabezados FITS. El dataset de muestra fue
provisto en dos formatos: un archivo `headers_consolidado.csv` con los 682
campos de encabezado de 1.861 archivos, y una hoja de cálculo
`eda_resultados.xlsx` con las estadísticas descriptivas ya tabuladas.

= Desarrollo / Metodología <desarrollo>

Esta sección describe lo realizado durante la primera entrega, sin emitir
juicios sobre los resultados (los cuales se analizan en la @resultados).

== Descripción del dataset de trabajo

Se recibieron dos artefactos de datos:

- `headers_consolidado.csv`: una tabla de *1.861 filas* (una por archivo
  FITS) y *684 columnas*, de las cuales 682 corresponden a palabras clave
  reales de encabezado FITS y 2 son columnas técnicas agregadas por el
  proceso de extracción (`_source_zip`, `_source_file`) que identifican el
  archivo comprimido y el nombre de archivo de origen.
- `eda_resultados.xlsx`: hoja de cálculo con cuatro pestañas, una por cada
  grupo de estadísticas solicitadas (campos por archivo; varianza de
  numéricos; cardinalidad de no numéricos; valores de baja frecuencia).

Adicionalmente se consultó el _Data Interface Control Document_ de ESO
(ESO-044156, versión 8) @eso_icd para interpretar correctamente el
significado de las palabras clave `HIERARCH ESO ...` y las reglas de
nomenclatura de los archivos (`ORIGFILE`, `ARCFILE`) durante el análisis.

== Extracción y carga de datos

Los datos fueron cargados con `pandas.read_csv`, inspeccionando primero una
muestra de filas para verificar tipos de datos antes de cargar la tabla
completa, dado el tamaño del archivo (~6,7 MB, con celdas que contienen
saltos de línea internos en campos de texto largos). Se verificó que el
número de filas cargadas (1.861) coincidiera exactamente con el número de
filas de la pestaña `1-2_por_archivo` de `eda_resultados.xlsx`, confirmando
la consistencia entre ambos artefactos entregados.

== Cálculo de las estadísticas del EDA

Para cada uno de los 682 campos de encabezado se calcularon las cinco
estadísticas solicitadas en el enunciado del proyecto:

+ *Cantidad de campos por archivo*: para cada una de las 1.861 filas, se
  contó el número de columnas con valor no nulo (`DataFrame.notna().sum(axis=1)`).
+ *Cantidad de campos sin información por archivo*: análogamente, se contó
  el número de columnas con valor nulo (`DataFrame.isna().sum(axis=1)`) por
  fila.
+ *Varianza de los campos numéricos*: se filtraron las columnas de tipo
  numérico (`int`/`float`) y se calculó `Series.var()` para cada una,
  ordenando el resultado de mayor a menor varianza.
+ *Cantidad de elementos distintos por campo no numérico*: para cada
  columna de tipo texto/categórico se calculó `Series.nunique()`.
+ *Cantidad de elementos de baja frecuencia (outliers) por campo no
  numérico*: para cada campo no numérico se calculó la tabla de frecuencias
  de sus valores (`value_counts()`) y se registraron los pares
  (campo, valor, frecuencia); en la práctica, todo valor que ocurre una
  única vez en el conjunto de datos corresponde a un elemento de baja
  frecuencia.

Estas estadísticas se cruzaron además con la variable `ESO DPR CATG`
(categoría de producto de datos: científico o de calibración) para
entender si la disponibilidad de los campos obligatorios (`RA`, `DEC`,
`DATE-OBS`, `OBJECT`) dependía del tipo de archivo, dado que el enunciado
señala que estos cuatro campos deben considerarse sí o sí.

== Selección de la tecnología y diseño del modelo

A partir de los resultados del EDA (detallados en la @resultados) se
evaluaron las seis familias de bases de datos vistas en clases (orientadas
a disco, orientadas a memoria, documentales, de grafos, de columnas y de
clave-valor) frente a las tres dimensiones de Big Data identificadas en el
@marco-teorico (volumen, variedad, velocidad), seleccionando la tecnología
que mejor sostiene el motor de búsqueda requerido. Con la tecnología
definida, se diseñó un esquema de documento que preserva los campos
identificados como relevantes, se definieron los índices necesarios para
las búsquedas por coordenadas, fecha y nombre de objetivo, y se derivaron
reglas de negocio —directamente desde los hallazgos del EDA— para separar
los archivos que deben indexarse en el buscador principal de aquellos que
deben moverse a almacenamiento secundario.

= Análisis y Resultados <resultados>

== Resultados del análisis exploratorio

=== Cantidad de campos presentes y vacíos por archivo

Sobre los 682 campos de encabezado analizables, cada archivo presenta en
promedio *385,8 campos con información* (56,6 %) y *296,2 campos vacíos*
(43,4 %), con una desviación estándar de 60,1 en ambos casos. El rango es
amplio: el archivo más "pobre" en metadatos tiene 319 campos poblados,
mientras que el más "rico" alcanza 556.

#figure(
  table(
    columns: 5,
    align: (left, right, right, right, right),
    table.header[Estadística][Media][Desv. estándar][Mínimo][Máximo],
    [Campos presentes], [385,8], [60,1], [319], [556],
    [Campos vacíos], [296,2], [60,1], [126], [363],
  ),
  caption: [Estadísticas de campos presentes/vacíos por archivo (n = 1.861 archivos, 682 campos posibles).],
) <tab-campos-archivo>

La @fig-dist-campos muestra que esta variabilidad no es aleatoria: los
archivos se agrupan en solo *28 "firmas" distintas* de cantidad de campos
poblados, lo que sugiere que la dispersión de metadatos está determinada
por un número limitado de combinaciones de instrumento, brazo óptico
(UVB/VIS/NIR/AGC) y plantilla de observación, y no por errores o
inconsistencias aleatorias de registro. Esta es una observación central
para el diseño del modelo de datos: la dispersión (_sparsity_) es
estructural, y una base de datos documental puede modelarla de forma
natural sin desperdiciar espacio en columnas mayoritariamente nulas.

#figure(
  image("assets/fig_dist_campos.png", width: 92%),
  caption: [Distribución del número de campos presentes por archivo. Los valores se agrupan en 28 combinaciones discretas, evidenciando dispersión estructural y no aleatoria.],
) <fig-dist-campos>

=== Varianza de los campos numéricos

Se analizaron *417 campos numéricos*. La tabla de varianzas está dominada
por campos identificadores y de integridad (`DATASUM`, `ESO OBS ID`,
`ESO OBS CONTAINER ID`), cuya alta varianza no refleja información
científica sino que es un artefacto de tratarse de números grandes y
arbitrarios (checksums, IDs correlativos). Los campos con verdadero
significado astronómico ocupan posiciones intermedias en el ranking:

#figure(
  table(
    columns: 4,
    align: (left, right, right, left),
    table.header[Campo][Varianza][Posición (de 417)][Interpretación],
    [`NAXIS2`], [1.185.762,5], [42], [Alto: tamaño de imagen variable según brazo/binning],
    [`NAXIS1`], [353.411,4], [46], [Alto: idem],
    [`EXPTIME`], [209.205,6], [51], [Alto: tiempos de exposición de 0 a 3.600 s],
    [`RA`], [15.363,8], [60], [Relevante: dispersión real de apuntado],
    [`DEC`], [812,4], [77], [Relevante: dispersión real de apuntado],
    [`ESO TEL AMBI TEMP`], [3,47], [115], [Bajo: temperatura ambiente estable],
    [`MJD-OBS`], [2,86], [117], [Bajo: observaciones concentradas en pocos días],
    [`ESO TEL AIRM START`], [0,06], [170], [Muy bajo: masa de aire similar entre exposiciones],
  ),
  caption: [Varianza de campos numéricos seleccionados, con su posición en el ranking completo de 417 campos.],
) <tab-varianza>

En el extremo opuesto, *9 campos numéricos tienen varianza exactamente 0*
(por ejemplo, varias tensiones de referencia del detector
`ESO DET VOLT1 DC*`, o el propio `NAXIS`, que siempre vale 2): son
constantes en toda la muestra y, por lo tanto, no aportan poder de
discriminación para un motor de búsqueda, aunque pueden ser relevantes
para trazabilidad técnica del instrumento.

=== Cantidad de valores distintos por campo no numérico

Se analizaron *265 campos no numéricos*. Como es esperable, los
identificadores únicos de archivo encabezan el ranking con 1.861 valores
distintos (cardinalidad 100 %):

#figure(
  table(
    columns: 3,
    align: (left, right, left),
    table.header[Campo][N° de valores distintos][Naturaleza],
    [`ARCFILE`], [1.861], [Identificador único de archivo en el archivo científico],
    [`CHECKSUM`], [1.861], [Suma de verificación de integridad (única por archivo)],
    [`DATE`], [1.861], [Timestamp de creación del archivo],
    [`DATE-OBS`], [1.861], [Timestamp de inicio de observación],
    [`ORIGFILE`], [1.771], [Nombre de archivo original en la estación del instrumento],
    [`ESO DET EXP UTC`], [407], [Hora UTC de la exposición],
    [`ESO DET FRAM UTC`], [407], [Hora UTC del frame],
    [`ESO DET EXP NAME`], [377], [Nombre interno de la exposición],
    [`ESO TPL START`], [225], [Inicio de la plantilla de observación],
    [`ESO OBS START`], [50], [Inicio del bloque de observación],
  ),
  caption: [Diez campos no numéricos de mayor cardinalidad, de un total de 265 analizados.],
) <tab-distintos>

En el extremo opuesto, un número importante de campos —como `RADECSYS`,
`OBSERVER` o `ESO OCS ARM`— tiene un único valor distinto en toda la
muestra: son constantes categóricas (propias de que la muestra proviene de
un solo instrumento en un período acotado) y, al igual que los campos
numéricos de varianza 0, no aportan valor discriminante para búsquedas,
aunque sí para la descripción técnica completa del archivo.

=== Elementos de baja frecuencia (outliers) por campo no numérico

Se identificaron *10.787 combinaciones (campo, valor)* de baja frecuencia,
concentradas en *35 campos de alta cardinalidad*. La distribución es muy
sesgada: el *95,5 % de estas combinaciones ocurre exactamente una vez*
(mediana = 1, máximo = 18 apariciones). La mayor parte de estos "outliers"
corresponde en realidad a identificadores inherentemente únicos por
exposición (`ARCFILE`, `CHECKSUM`, `DATE-OBS`, horas UTC), por lo que no
constituyen anomalías de calidad de datos sino el comportamiento esperado
de un identificador. Los casos con mayor valor analítico —outliers en el
sentido estricto de valores raros dentro de un campo mayormente repetido—
se encuentran en campos como `ESO OBS NAME` (24 valores distintos, algunos
con solo 6 apariciones), `ESO TPL ID` (13 valores distintos) y
`ESO OBS PROG ID` (9 valores distintos), útiles para detectar programas de
observación o plantillas poco frecuentes dentro de la muestra.

== Cobertura de los campos clave (RA, DEC, DATE-OBS, OBJECT)

El enunciado del proyecto exige preservar sí o sí los campos `RA`, `DEC`,
`DATE-OBS` y `OBJECT`, por ser los más usados para búsqueda. El EDA revela
un hallazgo crítico para el diseño del motor de búsqueda: *`DATE-OBS` y
`OBJECT` están presentes en el 100 % de los archivos (1.861/1.861)*, pero
*`RA` y `DEC` solo están presentes en 269 archivos (14,5 %)*.

#figure(
  image("assets/fig_ra_por_catg.png", width: 80%),
  caption: [Disponibilidad de RA/DEC según la categoría `ESO DPR CATG` del archivo.],
) <fig-ra-catg>

Cruzando esta disponibilidad con `ESO DPR CATG` (@fig-ra-catg) se observa
que:

- El *100 % de los archivos científicos* (`SCIENCE`, 18/18) y de
  verificación de apuntado (`ACQUISITION`, 2/2) tienen `RA`/`DEC` válidos.
- Solo *249 de 1.841 archivos de calibración* (13,5 %) tienen `RA`/`DEC`,
  correspondientes específicamente a los tipos `LAMP,AFC` (231 casos,
  compensación activa de flexión, que sí requiere apuntar el telescopio) y
  `STD,FLUX` (18 casos, estrellas estándar de calibración de flujo, que
  también requieren apuntado real).
- El *86,5 % restante de las calibraciones* (`BIAS`, `DARK`, la mayoría de
  los `FLAT` y `LAMP,WAVE`, entre otros) se obtiene con la cúpula cerrada o
  con lámparas internas, por lo que el telescopio no apunta a coordenadas
  celestes reales y ESO simplemente no registra `RA`/`DEC` en esos
  encabezados.

Además, se detectó que el campo `OBJECT` tiene un significado distinto
según la categoría del archivo: en los 18 archivos `SCIENCE` de la muestra,
`OBJECT` contiene el nombre real del objetivo astronómico observado
(`EUCLJ0353-4950`, el único blanco científico presente en esta muestra); en
los archivos `CALIB`, en cambio, `OBJECT` se rellena con una etiqueta
genérica que replica el valor de `ESO DPR TYPE` (por ejemplo, `"BIAS"` o
`"LAMP,FLAT"`), es decir, *no representa un objeto astronómico real*. Esta
distinción es fundamental: usar `OBJECT` como filtro de búsqueda por
nombre de objetivo solo tiene sentido para archivos `SCIENCE` (y, con
matices, `STD,FLUX`).

#figure(
  image("assets/fig_dprcatg.png", width: 68%),
  caption: [Distribución de archivos según `ESO DPR CATG` en la muestra analizada.],
) <fig-dprcatg>

Como se observa en la @fig-dprcatg, la muestra está fuertemente
desbalanceada hacia archivos de calibración (1.841 de 1.861, 99 %), lo cual
es consistente con el contexto del proyecto: un evento de observación
científica requiere una cantidad mucho mayor de archivos de calibración
asociados (_bias_, _flats_, _arcs_) que de archivos científicos
propiamente tales.

== Campos relevantes a preservar en el modelo de datos <campos-relevantes>

En base a las estadísticas anteriores, además de los cuatro campos
obligatorios del enunciado, se recomienda preservar como atributos
indexables de primer nivel los siguientes campos, junto con su
justificación:

#figure(
  table(
    columns: 2,
    align: (left, left),
    table.header[Campo][Justificación],
    [`RA`, `DEC`], [Obligatorios; permiten búsqueda espacial. Varianza no trivial (15.363,8 y 812,4) confirma dispersión real de apuntado, no un valor constante.],
    [`DATE-OBS`, `MJD-OBS`], [Obligatorio y complemento numérico; 100 % de cobertura; base para búsquedas y filtros por rango de fecha.],
    [`OBJECT`], [Obligatorio; único campo de texto libre con el nombre del objetivo científico (en archivos `SCIENCE`).],
    [`ESO DPR CATG` / `TYPE` / `TECH`], [100 % de cobertura; máxima relevancia semántica: definen si un archivo es científico o de calibración y de qué tipo — clave para las reglas de negocio (@reglas-negocio).],
    [`INSTRUME`, `ESO SEQ ARM`], [100 % de cobertura; identifican el instrumento y brazo óptico (UVB/VIS/NIR) usado, necesarios para interpretar el resto de los campos técnicos.],
    [`EXPTIME`], [Alta varianza (209.205,6); permite filtrar por tiempo de exposición.],
    [`NAXIS1`, `NAXIS2`], [Alta varianza; describen la geometría de la imagen almacenada.],
    [`ARCFILE`, `ORIGFILE`], [Cardinalidad máxima (1.861 y 1.771 respectivamente); identificadores naturales para clave primaria y trazabilidad al archivo original.],
    [`ESO OBS PROG ID`, `ESO OBS TARG NAME`, `ESO TPL ID`], [Cardinalidad baja-media (9, 21 y 13 valores); permiten agrupar archivos por programa de observación o plantilla, útil para vincular calibraciones con su ciencia asociada.],
    [`CHECKSUM`, `DATASUM`], [Cardinalidad máxima pero sin valor de búsqueda; se preservan solo para verificación de integridad del archivo binario, no como filtro.],
  ),
  caption: [Campos recomendados para el modelo de datos indexable, derivados del EDA.],
) <tab-campos-relevantes>

Por el contrario, se recomienda *no* promover a atributos indexados de
primer nivel a los campos con varianza 0 o cardinalidad 1 (por ejemplo,
`RADECSYS`, `OBSERVER`, la familia `ESO DET VOLT1 *`), dado que no aportan
poder de discriminación en la muestra analizada; estos campos se conservan
únicamente dentro del encabezado completo embebido en cada documento, para
no perder trazabilidad ni información potencialmente relevante en el
futuro (por ejemplo, si se incorporan otros instrumentos donde esos campos
sí varíen).

== Definición de tecnología <resultados-tecnologia>

=== Por qué un modelo relacional no es adecuado

Los resultados del EDA permiten argumentar, con evidencia concreta y no
solo de forma teórica, que un modelo puramente relacional (SQL) no es
adecuado para este problema:

- *Esquema disperso y variable (variedad).* El número de campos poblados
  por archivo varía entre 319 y 556 de un total de 682 posibles
  (@tab-campos-archivo), agrupados en 28 combinaciones distintas
  (@fig-dist-campos). Modelar esto en una única tabla relacional exigiría
  una tabla con más de 680 columnas, de las cuales en promedio un 43,4 %
  estaría vacía en cada fila —un antipatrón de tabla dispersa que
  desperdicia espacio de almacenamiento y degrada el rendimiento de
  lectura—. La alternativa relacional "correcta" (normalizar en un esquema
  entidad-atributo-valor con una tabla de metadatos por cada categoría
  `DET`/`INS`/`TEL`/`OBS`) obligaría a construir consultas con decenas de
  `JOIN`s para reconstruir un único encabezado, penalizando exactamente el
  tipo de búsqueda multi-atributo (coordenadas + fecha + objeto) que el
  motor de búsqueda debe resolver de forma rápida.
- *Evolución del esquema.* El campo `ESO DPR CATG` (@fig-dprcatg) y el
  conjunto de campos disponibles dependen del instrumento y la plantilla de
  observación. ESO opera múltiples instrumentos y está construyendo el
  Extremely Large Telescope @eso_archive, por lo que nuevos instrumentos
  introducirán nuevas palabras clave con el tiempo. En un modelo relacional
  esto implica sentencias `ALTER TABLE` sobre tablas de gran tamaño,
  operación costosa y bloqueante a escala de producción; en un modelo de
  documentos, cada documento admite campos adicionales sin necesidad de
  migración alguna @sadalage_fowler.
- *Semántica condicional de los campos.* Se demostró que `RA`/`DEC` solo
  son significativos para el 14,5 % de los archivos y que `OBJECT`
  significa cosas distintas según `ESO DPR CATG` (@fig-ra-catg). Estas
  relaciones condicionales son naturales de expresar en documentos JSON con
  sub-estructuras opcionales, pero forzarían columnas nulas o tablas
  adicionales en un esquema relacional rígido.
- *Volumen y velocidad.* Esta muestra corresponde a solo *un instrumento*
  durante *aproximadamente una semana* de operación (`DATE-OBS` entre el
  4 y el 9 de septiembre de 2026). El contexto del proyecto señala que el
  observatorio genera terabytes de datos diariamente entre todos sus
  instrumentos; a esa escala, la capacidad de escalar horizontalmente
  (_sharding_) sin coordinar transacciones ACID globales —propia de las
  bases NoSQL— es preferible a la escala vertical típica de los motores
  relacionales tradicionales.

=== Tecnología seleccionada

Se propone una arquitectura *políglota* de dos componentes, correspondiente
a la naturaleza dual de los datos descrita en el enunciado (metadatos
livianos e indexables vs. archivos binarios pesados):

#figure(
  table(
    columns: 3,
    align: (left, left, left),
    table.header[Componente][Tecnología][Rol],
    [Metadatos indexables], [Base de datos *documental* (ej. MongoDB)], [Motor de búsqueda: almacena un documento JSON por archivo FITS, con los campos de la @tab-campos-relevantes promovidos a nivel superior e índices compuestos, geoespaciales y de texto.],
    [Archivos binarios (imágenes FITS)], [Almacenamiento de objetos / _data lake_ (ej. compatible S3, o HDFS)], [Guarda el contenido pesado de la imagen; el documento de metadatos solo referencia su ruta (`bucket` + `path`).],
  ),
  caption: [Arquitectura políglota propuesta para el proyecto.],
) <tab-tecnologia>

Se descartaron las demás alternativas vistas en clases por los siguientes
motivos: las bases orientadas a *grafos* (ej. Neo4j) no aportan ventaja
aquí, ya que las relaciones relevantes (ciencia–calibración, archivo–programa
de observación) son pocas y poco profundas, no un problema de recorrido de
redes complejas; las bases de *columnas* (ej. Cassandra) están optimizadas
para escrituras masivas de series de tiempo con un patrón de consulta fijo,
mientras que este proyecto requiere flexibilidad de consulta por múltiples
combinaciones de atributos; las bases de *clave-valor* (ej. Redis) carecen
de capacidad de consulta por rango/geoespacial nativa, que es un requisito
central del motor de búsqueda; y los motores *distribuidos orientados a
memoria o a disco* (Spark, Hadoop) son complementarios y muy útiles para
el procesamiento por lotes de la ingesta (por ejemplo, para recalcular este
mismo EDA a escala completa), pero no reemplazan la necesidad de una base
de datos operacional que sirva consultas de búsqueda de baja latencia al
usuario final.

La elección de una base documental se apoya además en un argumento
práctico observado directamente en el material del curso: el código de
ejemplo entregado por el profesor (`fits.open(...).header`) ya produce un
diccionario Python, es decir, una estructura de pares clave-valor
equivalente a un documento JSON. Persistir ese diccionario casi
directamente —agregando los campos derivados descritos en la
@resultados-modelo— minimiza la complejidad del proceso de ingesta (ETL)
en comparación con transformarlo en múltiples filas relacionales.

== Definición del modelo de datos <resultados-modelo>

=== Esquema de documento

Se propone un documento por archivo FITS, identificado por `ARCFILE` (el
identificador de mayor cardinalidad de la muestra, 100 % único), con los
campos relevantes de la @tab-campos-relevantes promovidos a nivel superior
o agrupados en sub-documentos temáticos que reflejan la jerarquía
`HIERARCH ESO ...` original, y el encabezado completo conservado como
respaldo para trazabilidad:

```json
{
  "_id": "XSHOO.2026-09-04T01:43:37.983.fits",
  "origfile": "XSHOOT.2026-09-04T01:43:37.983.fits",
  "instrumento": "XSHOOTER",
  "brazo": "UVB",
  "fecha_obs": {"date_obs": "2026-09-04T01:43:37.983Z", "mjd_obs": 61200.071},
  "exptime": 2.7,
  "naxis": [2106, 3000],
  "objeto": {
    "nombre": "BIAS",
    "es_objetivo_real": false
  },
  "coordenadas": {
    "disponibles": false,
    "ra_deg": null,
    "dec_deg": null,
    "geo": null
  },
  "clasificacion": {"dpr_catg": "CALIB", "dpr_type": "BIAS", "dpr_tech": "IMAGE"},
  "programa": {"prog_id": "060.A-9800(P)", "obs_name": "...", "tpl_id": "..."},
  "condiciones": {"airmass": null, "seeing": null, "temp_ambiente": null},
  "integridad": {"checksum": "...", "datasum": "..."},
  "almacenamiento": {
    "bucket": "eso-xshooter-raw",
    "path": "xshooter/2026/09/04/XSHOO.2026-09-04T01_43_37.983.fits",
    "tamano_bytes": 8388608
  },
  "encabezado_completo": { "...": "los 682 campos originales, sin normalizar" },
  "buscador": {"indexado": false, "nivel": "frio"}
}
```

Para un archivo `SCIENCE` o `STD,FLUX` con coordenadas válidas, el
sub-documento `coordenadas` se completa así:

```json
"coordenadas": {
  "disponibles": true,
  "ra_deg": 53.4,
  "dec_deg": -49.9,
  "geo": {"type": "Point", "coordinates": [-126.6, -49.9]}
}
```

donde `geo` traduce `RA` (0°–360°) al rango `[-180°, 180°]` requerido por
el formato GeoJSON, para poder construir un índice geoespacial nativo.

=== Índices propuestos

#figure(
  table(
    columns: 3,
    align: (left, left, left),
    table.header[Índice][Campo(s)][Propósito],
    [Único], [`_id` (`ARCFILE`)], [Identificación inequívoca de cada archivo.],
    [Geoespacial (`2dsphere`)], [`coordenadas.geo`], [Búsqueda por proximidad/región del cielo (RA/DEC), solo sobre documentos con `coordenadas.disponibles = true`.],
    [Rango], [`fecha_obs.date_obs`], [Búsqueda y ordenamiento por fecha de observación (100 % de cobertura).],
    [Texto], [`objeto.nombre`], [Búsqueda libre por nombre de objetivo científico.],
    [Compuesto], [`clasificacion.dpr_catg`, `instrumento`, `fecha_obs.date_obs`], [Consultas típicas de operación: "todas las calibraciones de este instrumento en este rango de fechas".],
    [Compuesto], [`programa.prog_id`, `programa.tpl_id`], [Vincular archivos científicos con sus calibraciones asociadas dentro del mismo programa/plantilla.],
  ),
  caption: [Índices propuestos sobre la colección de metadatos.],
) <tab-indices>

=== Reglas de negocio para indexación vs. almacenamiento secundario <reglas-negocio>

Las siguientes reglas surgen directamente de los hallazgos del EDA
(@resultados) y determinan el valor del campo `buscador.indexado`:

+ *Archivos `ESO DPR CATG = SCIENCE`*: siempre se indexan en el buscador
  principal ("caliente"). Son el 100 % de los casos con `RA`/`DEC`
  válidos y `OBJECT` con un nombre de objetivo real; son el objetivo
  primario de búsqueda de los investigadores.
+ *Archivos `CALIB` con `RA`/`DEC` presentes* (tipos `LAMP,AFC` y
  `STD,FLUX`, 249 archivos de la muestra): se indexan también en el
  buscador principal, ya que su información de apuntado real permite
  encontrarlos por cercanía espacial a una observación científica —por
  ejemplo, para asociar la estrella de calibración de flujo más cercana a
  un objetivo dado.
+ *Archivos `CALIB` sin `RA`/`DEC`* (`BIAS`, `DARK`, la mayoría de los
  `FLAT`, `LAMP,WAVE`, etc.; 1.592 archivos, 86,5 % de las calibraciones en
  la muestra): *no* se indexan por coordenadas (no aplica), pero se
  conservan indexados por atributos técnicos (`instrumento`,
  `clasificacion.dpr_type`, `fecha_obs.date_obs`, `programa.prog_id`) para
  poder asociarlos administrativamente a su grupo de calibración. Se
  recomienda moverlos a almacenamiento secundario ("frío") transcurrido un
  período de retención corto, dado su bajo valor de búsqueda individual y
  su volumen dominante (99 % de los archivos de la muestra).
+ *Archivos `ACQUISITION`*: se excluyen del buscador científico (su
  propósito es solo verificar el apuntado del telescopio, no son datos
  científicos ni de calibración reutilizables) y se mueven directamente a
  almacenamiento secundario, conservando únicamente metadatos mínimos de
  trazabilidad.
+ *Campos de varianza 0 o cardinalidad 1* (ver @campos-relevantes): no se
  promueven a atributos indexados de primer nivel; permanecen únicamente
  dentro de `encabezado_completo`, evitando inflar innecesariamente el
  tamaño de los índices sin ganar capacidad de búsqueda.
+ *Integridad de archivo* (`CHECKSUM`, `DATASUM`): se preservan siempre,
  independiente de la regla de indexación, ya que son necesarios para
  verificar la integridad del binario asociado al momento de recuperarlo
  desde el almacenamiento de objetos.

Estas reglas permiten estimar, a partir de la muestra analizada, que solo
alrededor de un *15 %* de los archivos de calibración (más el 100 % de los
científicos) requeriría permanecer en el nivel "caliente" del buscador,
mientras que el resto puede migrarse a almacenamiento secundario de menor
costo sin perder la posibilidad de recuperarlo administrativamente por
instrumento, tipo y fecha.

= Conclusión <conclusion>

En esta primera entrega se cumplieron los tres objetivos definidos por el
enunciado del proyecto. Primero, se realizó un análisis exploratorio
completo sobre una muestra real de 1.861 archivos y 682 campos de
encabezado FITS del instrumento X-shooter, calculando las cinco
estadísticas solicitadas y, a partir de ellas, identificando qué campos son
relevantes de preservar en el modelo de datos. El hallazgo más relevante
fue que los campos obligatorios `RA` y `DEC` solo están disponibles en el
14,5 % de los archivos, y que esa disponibilidad está determinada por la
categoría `ESO DPR CATG` del archivo (ciencia versus calibración), lo cual
terminó siendo la base de las reglas de negocio propuestas.

Segundo, se justificó —con evidencia cuantitativa del propio EDA y no solo
con argumentos teóricos— que un modelo relacional no es adecuado para este
problema, debido a la alta dispersión y variabilidad estructural de los
encabezados (entre 319 y 556 campos poblados de 682 posibles, agrupados en
28 combinaciones distintas), y se propuso en su lugar una arquitectura
políglota compuesta por una base de datos documental para los metadatos
indexables y un almacenamiento de objetos para los archivos FITS binarios.

Tercero, se diseñó un modelo de datos orientado a documentos, con un
esquema que agrupa los campos del encabezado en sub-documentos temáticos,
índices geoespaciales, temporales, de texto y compuestos que soportan las
búsquedas por coordenadas, fecha y objeto exigidas por el enunciado, y un
conjunto de reglas de negocio —derivadas directamente de los resultados del
EDA— que permiten distinguir de forma automática qué archivos deben
mantenerse indexados en el buscador principal y cuáles pueden moverse a
almacenamiento secundario.

Como trabajo futuro, quedan pendientes para las siguientes entregas del
proyecto: la implementación efectiva del modelo propuesto sobre una
instancia real de la tecnología seleccionada, la construcción del proceso
de ingesta (ETL) a partir de `astroquery.eso`, la validación del modelo con
una muestra que incluya más de un instrumento (para confirmar si la
variabilidad estructural observada se mantiene o se amplía), y el
desarrollo de la interfaz del motor de búsqueda propiamente tal.

#pagebreak()
= Bibliografía
#bibliography("references.bib", title: none, style: "apa")

#pagebreak()
= Anexos

== Anexo A: Top 15 campos numéricos por varianza (completo)

#{
  let data = csv("assets/top15_varianza.csv")
  table(
    columns: 2,
    align: (left, right),
    table.header[Campo][Varianza],
    ..data.slice(1).map(row => (row.at(0), row.at(1))).flatten()
  )
}

== Anexo B: Top 15 campos no numéricos por cardinalidad (completo)

#{
  let data = csv("assets/top15_distintos.csv")
  table(
    columns: 2,
    align: (left, right),
    table.header[Campo][N° de valores distintos],
    ..data.slice(1).map(row => (row.at(0), row.at(1))).flatten()
  )
}

== Anexo C: Campos de baja frecuencia agregados por campo (35 campos)

Cantidad de combinaciones (campo, valor) de baja frecuencia por cada uno de
los 35 campos no numéricos donde se detectaron, con el rango de frecuencia
observado.

#{
  let data = csv("assets/agg5_baja_frecuencia.csv")
  table(
    columns: 4,
    align: (left, right, right, right),
    table.header[Campo][N° valores baja frec.][Frec. mínima][Frec. máxima],
    ..data.slice(1).map(row => (row.at(0), row.at(1), row.at(2), row.at(3))).flatten()
  )
}

== Anexo D: Completitud de los campos clave exigidos por el enunciado

#{
  let data = csv("assets/completitud_campos_clave.csv")
  table(
    columns: 4,
    align: (left, right, right, right),
    table.header[Campo][No nulos][Nulos][% completo],
    ..data.slice(1).map(row => (row.at(0), row.at(1), row.at(2), row.at(3))).flatten()
  )
}

== Anexo E: Extracto del código de análisis (Python)

```python
import pandas as pd

df = pd.read_csv("headers_consolidado.csv", low_memory=False)
campos = [c for c in df.columns if c not in ("_source_zip", "_source_file")]
df = df[campos]

# 1-2. Campos presentes / vacíos por archivo
presentes = df.notna().sum(axis=1)
vacios = df.isna().sum(axis=1)

# 3. Varianza de campos numéricos
numericos = df.select_dtypes(include="number")
varianza = numericos.var().sort_values(ascending=False)

# 4. Cardinalidad de campos no numéricos
no_numericos = df.select_dtypes(exclude="number")
distintos = no_numericos.nunique().sort_values(ascending=False)

# 5. Elementos de baja frecuencia por campo no numérico
filas = []
for col in no_numericos.columns:
    vc = no_numericos[col].value_counts()
    bajos = vc[vc <= 1]  # umbral de "baja frecuencia": una sola aparición
    for valor, n in bajos.items():
        filas.append({"campo": col, "valor": valor, "n_apariciones": n})
baja_frecuencia = pd.DataFrame(filas)

# Cruce clave: disponibilidad de RA/DEC según categoría del archivo
cruce = pd.crosstab(df["ESO DPR CATG"], df["RA"].notna())
```
