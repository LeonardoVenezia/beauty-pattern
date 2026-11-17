"""Textos por area (hogar, juguetes, prendas...), cada modulo con
`TEXTS: dict[idioma, dict[clave, texto]]`. Se suman a los catalogos al
importar engine.i18n; asi varias lineas de trabajo no editan el mismo archivo.
Las claves no pueden repetir una de los catalogos base (test)."""
