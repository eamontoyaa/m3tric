# Pruebas locales realizadas

Fecha de generación: automática en el entorno de trabajo de ChatGPT.

Comandos ejecutados:

```bash
python -m py_compile scripts/build_site.py scripts/check_site.py
python scripts/build_site.py
python scripts/check_site.py
```

Resultado:

```text
Built 15 pages into site/
Site check passed: 15 HTML files verified.
```

Qué se verificó:

- Los scripts Python compilan correctamente.
- El sitio estático se genera sin dependencias externas.
- Se generan 15 páginas HTML.
- Existe `site/index.html`.
- Existe `site/.nojekyll`, necesario para evitar procesamiento con Jekyll.
- Existen los assets principales de CSS, JS e imágenes.
- Los enlaces y fuentes internas generados no están rotos.
- No se usan rutas absolutas tipo `/assets/...`, para que funcione en GitHub Pages de proyecto, por ejemplo `https://usuario.github.io/repositorio/`.

Nota:

El workflow de GitHub Actions no puede ejecutarse desde este entorno porque requiere un repositorio real en GitHub con Pages habilitado. No obstante, el repositorio incluye `.github/workflows/deploy-pages.yml`, que construye, valida y despliega el sitio automáticamente en cada `push` a `main`.
