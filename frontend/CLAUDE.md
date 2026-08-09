@AGENTS.md

# CLAUDE.md — frontend/

Notas especificas de este modulo. Contexto de negocio completo: ../docs/contexto-negocio.md.

## Next.js 16 — cuidado con supuestos de entrenamiento

Este proyecto usa Next.js 16.3.0 (Turbopack). Antes de asumir una API de versiones anteriores,
revisa `node_modules/next/dist/docs/` (AGENTS.md de este repo ya lo indica). Cambio clave ya
aplicado aqui: `middleware.ts` fue renombrado a `proxy.ts` (exporta `proxy`, no `middleware`).

## Enrutamiento es/en

- Todo vive bajo `src/app/[lang]/` (layout, page, dictionaries). No hay `layout.tsx`/`page.tsx`
  sueltos en `src/app/` — el root layout es el de `[lang]`.
- `src/proxy.ts` redirige segun `Accept-Language`; locale por defecto `es`.
- Diccionarios: `src/app/[lang]/dictionaries.ts` + `dictionaries/{es,en}.json`. Patron:
  agregar clave nueva a ambos JSON, usar `getDictionary(lang)` en Server Components.
- `params` es async (`Promise`) en pages/layouts — usar `await params`, tipos `PageProps<'/[lang]'>`
  / `LayoutProps<'/[lang]'>`.

## Estado

Solo scaffold — `[lang]/page.tsx` es un placeholder. Sin pantallas reales todavia.
