# M3TRIC Pages

Repositorio base para desplegar el sitio web comercial de **M3TRIC** en GitHub Pages.

El sitio está diseñado para que el contenido principal sea editable desde archivos Markdown en la carpeta `content/`, mientras que la presentación visual se controla desde `assets/css/styles.css` y la navegación desde `navigation.json`.

## Vista general

- Landing page comercial.
- Sección de ecosistema M3TRIC.
- Páginas de productos:
  - Sensórica multiescala.
  - Capacidades IoT.
  - Visualización y alertas.
  - Modelación geoespacial.
  - M3TRIC Decision System.
- Escalas de implementación:
  - M3 – Corredor.
  - M2 – Tramo.
  - M1 – Sitio.
- Casos de uso.
- Página de contacto.

## Estructura

```text
m3tric-pages/
├── assets/
│   ├── css/styles.css
│   ├── img/
│   └── js/main.js
├── content/
│   ├── index.md
│   ├── ecosistema.md
│   ├── productos/
│   ├── escalas/
│   ├── casos-uso/
│   └── contacto.md
├── scripts/
│   ├── build_site.py
│   └── check_site.py
├── templates/base.html
├── navigation.json
├── site.json
└── .github/workflows/deploy-pages.yml
```

## Editar contenido

La mayoría del sitio se modifica editando archivos `.md` dentro de `content/`.

Cada archivo puede tener un bloque inicial de metadatos:

```md
---
title: Título de la página
description: Descripción corta para SEO y metadatos.
wide: true
---
```

El campo `wide: true` hace que la página use un ancho amplio. Si se omite, la página usa un ancho más controlado para lectura.

## Construir localmente

No se requieren dependencias externas. Solo Python 3.11+.

```bash
python scripts/build_site.py
python scripts/check_site.py
```

Luego puedes abrir el sitio con:

```bash
python -m http.server 8000 --directory site
```

Y entrar a:

```text
http://localhost:8000
```

## Despliegue en GitHub Pages

El repositorio incluye el workflow `.github/workflows/deploy-pages.yml`.

Ese workflow se ejecuta automáticamente en cada `push` a la rama `main` y publica el contenido generado en `site/` usando GitHub Pages con GitHub Actions.

Pasos en GitHub:

1. Crear un repositorio, por ejemplo `m3tric-pages`.
2. Subir el contenido de este ZIP al repositorio.
3. Ir a `Settings → Pages`.
4. En `Build and deployment`, seleccionar `GitHub Actions`.
5. Hacer push a `main`.
6. Revisar la pestaña `Actions` para confirmar el despliegue.

La URL normalmente tendrá esta forma:

```text
https://TU-USUARIO.github.io/m3tric-pages/
```

## Personalización visual

La paleta M3TRIC está centralizada en variables CSS dentro de `assets/css/styles.css`:

```css
--m3tric-green-dark: #004124;
--m3tric-green-medium: #2C694F;
--m3tric-green-light: #74C69D;
--m3tric-green-pastel: #B7E3C7;
--m3tric-beige: #F6F2EA;
--m3tric-yellow: #FFD166;
--m3tric-orange: #F77F00;
--m3tric-red: #D62828;
```

## Agregar una nueva página

1. Crear un archivo `.md` dentro de `content/`.
2. Agregar la página en `navigation.json`.
3. Ejecutar:

```bash
python scripts/build_site.py
python scripts/check_site.py
```

4. Hacer commit y push a `main`.

## Nota sobre imágenes y fuentes

Las imágenes base están en `assets/img/`. La tipografía se define por CSS usando `DIN 2014 Rounded` si está disponible en el sistema del usuario, con fuentes de respaldo. No se incluyen archivos de fuente en el repositorio.
