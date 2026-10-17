# Archivos privados de la carga inicial

`private/importacion_negocio/originales/`: los tres adjuntos sin cambios.
`private/importacion_negocio/normalizados/`: copias preparadas para importar.
`private/importacion_negocio/preparacion.json`: hashes y conciliación de preparación.

`private/` está excluido de Git y del contexto Docker. Las copias locales no se
recuperan con git clone/pull; transferirlas por separado a la Raspberry. Nunca
incorporar datos del negocio como fixtures de pruebas ni publicarlos en GitHub.

Comandos y mapeo: [docs/IMPORTACION_JSON.md](../docs/IMPORTACION_JSON.md).
