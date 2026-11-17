# Investigación: estrategia de IA y catálogo de opciones (2026-11-17)

Tres investigaciones en paralelo con búsqueda web. Las cifras marcadas "(sin verificar)" no tienen fuente sólida; Ravelry y DROPS no permiten búsqueda automática, así que los conteos de Ravelry son de un relevamiento de 2015 (sirven por proporción, no por valor absoluto).

## 1. ¿Estamos usando la estrategia correcta?

### Qué existe

- **Nadie publicó un sistema que vaya de foto a patrón completo con precisión medida.** Lo más cercano:
  - Neural Inverse Knitting (MIT, 2019) y Sheng et al. (2025) solo reconocen la *textura* de una muestra, para máquina de tejer.
  - AutoKnit (CMU, 2018) y AmiGo (2022) convierten un modelo 3D en puntos con fórmulas, sin IA. Demuestran que el paso forma → puntos es un problema de cálculo resuelto.
- **CrochetBench (Notre Dame, ACL 2026)** es la evidencia más fuerte: 6085 patrones y 9 modelos de visión (GPT-4o, Claude Sonnet 4, Gemini, Qwen).
  - Cuando el modelo escribe el patrón completo, **solo el 5–8 % se puede tejer** en los mejores casos; en la mayoría, menos del 3 %.
  - Reconocer puntos en una foto: como mucho 61 % de acierto.
  - Los modelos más grandes inventaban puntos inexistentes *más* seguido.
  - Entrenarlos específicamente mejoró el formato, no los conteos.
- **Prueba de abcrafty (octubre 2026):** de 4 patrones de ChatGPT y Gemini, funcionó 1. La pelota de ChatGPT tenía los totales de cada vuelta bien y aun así salía plana.
- Hay apps que prometen "foto a patrón" (Knittable.ai, StitchMind, Loopify…). Ninguna publica su precisión.

### Qué dice la evidencia general sobre "más responsabilidad a la IA y verificar después"

- **La IA no se corrige sola.** Pedirle que revise su propio trabajo no mejora o empeora (Huang et al., ICLR 2024). Sí funciona cuando un verificador externo y confiable le devuelve los errores (LLM-Modulo, 2024).
- **El verificador solo garantiza lo que mide.** Nuestro simulador verifica que las cuentas cierren, no que la forma se parezca a la foto: es el caso de la pelota plana. Además, los modelos fuertes aprenden a "pasar el examen" (ImpossibleBench, 2025). Con un ciclo de reparación, un patrón escrito vuelta por vuelta converge a lo que el simulador acepta, no a la forma correcta.
- **Lo que mejor funciona en problemas parecidos** (diseño CAD a partir de imágenes: CAD-Recode, ICCV 2025): la IA describe el objeto con parámetros de alto nivel y un programa lo convierte en geometría. Eso dio unas 10 veces menos error que generar la geometría directamente.

### Conclusión

Nuestra arquitectura ("la IA interpreta, el código calcula, el simulador verifica") coincide con la evidencia. La intuición de darle más responsabilidad a la IA es correcta para **interpretar el diseño**, e incorrecta para **escribir las instrucciones con números**.

Camino recomendado para los casos fuera de catálogo, cuando los encaremos:
- la IA (un modelo más fuerte, en una sola llamada) describe el objeto como **piezas combinables**: esfera, tubo, cono, disco, con tamaños relativos y dónde se cosen, sin números de puntos;
- el código valida esa descripción, le devuelve los errores a la IA (como mucho 2 reparaciones), la convierte en vueltas y el simulador la verifica;
- se vota la estructura entre 3 muestras, igual que hoy votamos los campos;
- opcional: dibujar la silueta y preguntarle a un modelo barato si se parece a la foto, solo para avisar o repetir, nunca para calcular.

Costo estimado: 3 a 5 llamadas por patrón.

**Medición propuesta:** un set de 150–300 fotos etiquetadas, en 4 grupos (prendas del catálogo, juguetes del catálogo, formas fuera de catálogo y fotos difíciles). Se mide:
- acierto por campo;
- acierto de la estructura;
- tasa de "entregado o rechazado con honestidad";
- costo y tiempo.

Además, tejer de verdad 10–20 patrones por versión: es la única prueba de punta a punta.

## 2. Catálogo de opciones (para cubrir el 95 %)

### Categorías que faltan (prendas y accesorios)

| Opción | Frecuencia | Evidencia | Nombres |
|---|---|---|---|
| Top (musculosa, remera, crop, halter) | muy común | Ravelry: 7200 sin mangas + 3600 remeras; tendencia crochet 2024–26 | top, musculosa / débardeur / Top / canotta |
| Saco, tapado, campera | común | Ravelry: 10 700 | saco, tapado / veste, manteau / Jacke / giacca |
| Vestido, túnica | común | Ravelry: 5200 | vestido / robe / Kleid / abito |
| Poncho, ruana, capa | común; muy común en Argentina y los Andes | Ravelry: 2600 + 1600; DROPS: 266 | poncho, ruana / poncho, cape / Poncho / mantella |
| Bolero, torera | común | Ravelry: 3900 | bolero |
| Mitones sin dedos | muy común | parte grande de "manos" en Ravelry (23 700) | mitones / mitaines / Pulswärmer |
| Escarpines (bebé) | común | Ravelry: 3500 | escarpines / patucos / chaussons |
| Pantuflas | común | Ravelry: 2200 | pantuflas / chaussons / Hausschuhe |
| Polainas | común | Ravelry: 1800 | polainas / jambières / Stulpen |
| Pasamontañas, balaclava | común (tendencia 2022–25) | subcategoría propia en DROPS | pasamontañas / cagoule / Sturmhaube |
| Vincha, cubreorejas | común | — | vincha / bandeau / Stirnband |
| Pollera | nicho, en alza en crochet | Ravelry: 1700 | pollera / jupe / Rock |

**Tipos de gorro** (el gorro es la categoría más grande de Ravelry):
- beanie: muy común;
- piluso (bucket): muy común en crochet;
- boina: común;
- chullo con orejeras: común, y muy común en los Andes;
- capelina o gorro de verano, incluido el casquete de red: tendencia 2025–26 en Argentina y Chile;
- slouchy: común;
- capota: nicho.

### Construcción: hoy mezcla tres cosas distintas

Conviene separarla en:
- **hombro:** raglán, canesú, manga montada, hombro caído, *hombro caído modificado*, *hombro sillín (saddle)*, *manga murciélago (dolman)* y *en T o rectángulos* (muy común en crochet de principiantes);
- **dirección:** de arriba hacia abajo, de abajo hacia arriba, de costado o desde el centro;
- **armado:** en redondo sin costuras, en piezas cosidas, por módulos o de una pieza.

**Medias:** puño hacia abajo o punta hacia arriba; talón con solapa, con vueltas cortas o "afterthought"; punta en cuña o en estrella.

### Escotes, mangas y calce

- **Escotes:** agregar cuello alto corto (mock neck, muy común), medio cierre o henley, polo, cuello chal y escote redondo profundo. Unir "funnel" con cuello alto, porque en una foto no se distinguen.
- **Estilo de manga:** recta, globo u obispo (muy común entre 2020 y 2025), campana y casquillo.
- **Largos:** agregar manga al codo y largo a la cintura.
- **Calce:** agregar "oversized", que es como la gente lo llama.
- **Silueta:** "curved" no se entiende; reemplazarla por "evasé o peplum".

### Terminaciones

Agregar pompón (muy común en gorros), cierre, cuello, lazos o cordón, orejeras, borde decorativo (picot, abanico, punto cangrejo, i-cord) y volado. Unir flecos y borlas en una sola opción.

### Puntos

- **Corrección importante, seed vs. moss:**
  - "seed" en EE. UU. es "moss" en el Reino Unido: el punto arroz.
  - "moss" en EE. UU. es el punto arroz doble.
  - Hoy, una persona de EE. UU. y una del Reino Unido entenderían cosas distintas. Hay que renombrarlos **punto arroz** y **punto arroz doble**.
- **Elástico:** una sola opción con medidas (1×1, 2×2, 3×1…), más el elástico retorcido.
- **Agujas, faltan:** jersey revés, elástico inglés (se parece al brioche), canasta, waffle, elástico quebrado y puntos deslizados (punto lino).
- **Crochet, faltan:**
  - **muy comunes:** elástico de crochet (por la hebra de atrás), punto granny, punto lino o musgo de crochet, punto V y abanico;
  - **comunes:** punto alto doble, puff, red o filet, crochet tunecino y C2C.
- **Nombres por país** (para no confundir): el punto bajo de EE. UU. es el "medio punto" en Argentina, y el punto alto de EE. UU. es la "vareta" en Argentina. Internamente guardamos el nombre de EE. UU. y mostramos el de cada país.

### Colores

- **Jacquard o tejido con dos hebras**, con estilos:
  - Fair Isle;
  - nórdico, Selbu o lopapeysa;
  - andino;
  - Bohus (nicho).
- **Faltan:**
  - **bloques de color:** muy común y distinto del intarsia;
  - **tapestry crochet:** común;
  - **mosaico de crochet:** común;
  - **C2C o pixel:** común.
- **Rayas helicoidales:** unirlas con las rayas comunes.

### Aspecto del hilo

- Reemplazar "mohair" por **"esponjoso o halo"**, que incluye mohair, alpaca cepillada y suri.
- **Faltan:**
  - **muy comunes:** jaspeado o teñido a mano, y algodón o lino mate;
  - **comunes:** tweed, autorayado o degradé, hilo grueso tipo XXL, rafia o papel, y trapillo o cinta.

### Juguetes (amigurumi)

**Formas de cuerpo**, de 2 a unas 6:
- en piezas, sentado;
- de una pieza sin costuras: muy común y creciendo;
- bolita: ya existe;
- de pie, o muñeca;
- alargado: serpiente, salchicha, dragón;
- radial con patas colgando: pulpo, medusa.

Además, "chunky" (hilo chenille, sin costuras) como opción de hilo, no de forma.

**Figuras:** unas 20 más un genérico.
- **Muy comunes:** oso, conejo, gato, perro, pulpo, elefante.
- **Comunes:** unicornio, dinosaurio o dragón, ballena, tortuga, medusa, pato o pollito, rana, abeja, vaca, oveja, ratón, zorro, búho, pingüino, chancho, koala, león, mono, jirafa y muñecas.
- **Tendencia:** ajolote, hongo, fantasma.
- Los personajes con licencia (Pokémon, Disney) quedan como genérico más colores.

**Partes con variantes**, para que el genérico también quede bien:
- orejas: redondas, en punta, largas, caídas, grandes;
- hocico: ninguno, ovalado, de chancho, trompa, pico;
- cola: pompón, larga, enrulada, de pez;
- alas, cuernos, antenas y pelo o melena.

Con unas 6 formas, unas 20 figuras y partes combinables se cubriría aproximadamente el 75–85 % de los amigurumi de animales (estimación).

**Comida, plantas en maceta y figuras de fiesta** (calabaza, fantasma, gnomo, Papá Noel): son comunes y necesitan plantillas propias, chicas.

### Hogar y objetos chicos

Casi todo se reduce a **tres geometrías**:

- **Disco o cuadrado plano:**
  - posavasos: muy común;
  - individuales y carpetitas: comunes, y muy comunes en Argentina, España e Italia;
  - agarraderas: comunes, y muy comunes en Alemania;
  - paños de cocina: muy comunes en EE. UU. y el Reino Unido.
- **Cilindro o funda:**
  - **funda de mate y de termo: muy común en Argentina y Uruguay** (hay un catálogo oficial de Mendoza lleno de ejemplos);
  - fundas de taza, botella, celular y anteojos;
  - cartucheras.
- **Canasto, que es una base más paredes:** canastos (muy comunes, también de trapillo), alfombras, almohadones y macetas colgantes.

Otros:
- **Muy comunes:** carteras y bolsos (tote, red de mercado, bandolera, bucket), llaveros, colitas para el pelo y flores (ramos).
- **Comunes:** señaladores, adornos navideños, objetos de bebé (sonajero, mantita con cabeza de muñeco).

### Mantas

- **Construcciones:**
  - **muy comunes:** granny unidos (incluida la unión mientras se teje), un solo granny gigante, rayas de un punto, mantas de bebé y C2C;
  - **comunes:** ondas o chevron, mosaico, manta de temperaturas, tapestry, hexágonos o flor africana, y chunky tejida con las manos.
- **Motivos:** agregar el **hexágono** y las variantes del granny (clásico, macizo y con flor al centro). Con eso se pasaría de cubrir alrededor del 60–70 % de los motivos a alrededor del 90 %.

### Regionales

- **Río de la Plata:** funda de mate y termo, bolso matero, yerbero y azucarero, carpetitas, poncho y ruana.
- **Andes:** chullo, chuspa (bolsita), llamas.
- **España:** trapillo, patucos, toquilla.
- **Nórdicos:** bolas de Navidad tejidas, nisse o tomte, cojines Selbu.
- **Alemania:** Topflappen (agarraderas).
- **Francia:** doudou (mantita con cabeza de muñeco).
- **Italia:** centrini (carpetitas).
- **Japón:** origen del amigurumi; sus patrones usan diagramas de símbolos.

## Fuentes principales

- CrochetBench: https://arxiv.org/html/2511.09483v2
- Neural Inverse Knitting: https://deepknitting.csail.mit.edu
- AmiGo: https://ar5iv.labs.arxiv.org/html/2211.01178
- AutoKnit: https://textiles-lab.github.io/publications/2018-autoknit
- Smeyers (Leiden, 2025): https://theses.liacs.nl/pdf/2024-2025-SmeyersCCatherine.pdf
- Prueba de abcrafty: https://abcrafty.com/ai-crochet-patterns/
- Huang et al. (autocorrección): https://arxiv.org/abs/2310.01798
- LLM-Modulo: https://arxiv.org/abs/2402.01817
- ImpossibleBench: https://arxiv.org/pdf/2510.20270
- CAD-Recode: https://arxiv.org/abs/2412.14042
- CADCodeVerify: https://arxiv.org/abs/2410.05340
- Formatos estrictos y razonamiento: https://arxiv.org/abs/2408.02442
- Conteos de Ravelry (2015): https://www.r-bloggers.com/2015/08/knitting-patterns-categories/
- Catálogos DROPS: https://www.garnstudio.com/catalogues.php?lang=en
- Tendencias 2025–26:
  - https://www.lanternmoon.com/blogs/blog-post/crochet-trends-2026-fashion-guide
  - https://www.cadena3.com/noticia/espectaculos/el-mesh-hat-el-gorro-de-crochet-liviano-que-arrasa-en-el-verano-2026_484491
- Construcciones de hombro: https://bendigowoollenmills.com.au/blogs/news/understanding-the-five-common-shoulder-constructions-in-our-knitting-patterns
- Talones y puntas de medias: https://sweetgeorgiayarns.com/choosing-the-best-heel-and-toe-constructions-for-your-socks/
- Estilos de jacquard: https://kelbournewoolens.com/blogs/blog/stranded-colorwork-vs-fair-isle-knitting
- Tejido andino: https://pieceworkmagazine.com/andean-knitting
- Amigurumi:
  - https://lovecrafts.com/en-us/c/article/top-free-amigurumi-crochet-patterns
  - https://www.gathered.how/knitting-and-crochet/crochet/best-crochet-animals
- Fundas de mate (catálogo de Mendoza): https://www.mendoza.gov.ar/catalogoeconomiasocial/producto/fundas-tejidas-para-el-mate/
