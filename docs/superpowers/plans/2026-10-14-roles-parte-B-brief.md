# Roles, parte B: los grupos Jefe/Vendedora se derivan de la membresia (un solo lugar los sincroniza)

Proyecto Django (backend/), español. NO uses terminal: solo leer/buscar/editar/crear archivos.

## Contexto
Parte A (ya hecha): el rol de negocio se decide por `MembresiaEmpresa.rol` via `apps/tenancy/scope.py` (`rol_en`, `es_jefe`, `es_jefe_actual`, `tiene_rol_actual`, `es_vendedora_actual`). Ya nadie decide reglas por el grupo. Los grupos Django `Jefe` y `Vendedora` quedan SOLO como paquetes de permisos de modelo (los define `apps/bookings/management/commands/setup_roles.py`). El grupo `OperadorPlataforma` NO se toca nunca (no tiene membresia).
Parte B: que esos dos grupos se mantengan SOLOS a partir de las membresias, en un unico lugar, para que no se puedan desincronizar.

## 1. Modulo `apps/tenancy/roles.py`
- `GRUPO_POR_ROL = {MembresiaEmpresa.Rol.JEFE: 'Jefe', MembresiaEmpresa.Rol.VENDEDORA: 'Vendedora'}` (import perezoso o al nivel de modulo segun evite ciclos).
- `asegurar_grupo(nombre)`: devuelve el `Group`; si no existe corre `call_command('setup_roles')` (esto sustituye al `call_command('setup_roles')` que hoy hay dentro de `crear_usuario_con_rol` en `apps/tenancy/usuarios.py` ~linea 85; quitalo de ahi) y lo devuelve.
- `sincronizar_grupos_de_usuario(user)`: calcula el conjunto de roles que el usuario tiene en TODAS sus membresias; para cada rol presente asegura que esta en su grupo; para cada rol ausente lo saca de su grupo (solo `Jefe` y `Vendedora`; jamas toca `OperadorPlataforma` ni otros grupos). Idempotente. Si el usuario no tiene `pk` o ya no existe, no hace nada.
- `sincronizar_todos()`: recorre los usuarios con al menos una membresia y llama a lo anterior; devuelve cuantos. (Tambien debe sacar de Jefe/Vendedora a usuarios SIN ninguna membresia que esten en esos grupos? NO: no lo hagas; solo usuarios con membresias, para no quitar permisos por accidente a operadores o cuentas especiales.)

## 2. Señales
En `apps/tenancy/signals.py` (crealo si no existe; conectalo en `apps/tenancy/apps.py::ready`): `post_save` y `post_delete` de `MembresiaEmpresa` llaman a `sincronizar_grupos_de_usuario(instance.user)`. En `post_delete` el usuario puede haberse borrado ya (cascada): atrapa `User.DoesNotExist`/usuario sin pk y sigue sin error.

## 3. Quitar la asignacion manual de grupos (ahora redundante)
Quita los `groups.add(...)`/`groups.set(...)` de Jefe/Vendedora en: `apps/tenancy/usuarios.py` (~106), `apps/tenancy/management/commands/migrar_la_paz_a_empresa.py` (jefe/vendedora; el del operador `grupo_operador` SE QUEDA), `apps/bookings/management/commands/seed_perfiles_demo.py` (~55), `apps/testing.py` (~67 y ~83: los helpers que arman jefe/vendedora ya crean la membresia; verifica que la creen ANTES de que alguien llame a una regla). Las variables/imports que queden sin uso se limpian solo si son tuyas; reporta lo que borres. Ojo: `crear_usuario_con_rol` crea usuario + membresia + perfil `Vendedora` en una transaccion; la señal sincroniza al crear la membresia, asi que el usuario sale con su grupo.

## 4. `setup_roles`
Al final de `apps/bookings/management/commands/setup_roles.py`, despues de crear/actualizar los grupos y sus permisos, llama a `sincronizar_todos()` e imprime cuantos usuarios se sincronizaron (asi, correr `setup_roles` tras cada deploy tambien arregla cuentas viejas). Cuidado con ciclos de import y con que `setup_roles` lo llama `asegurar_grupo` (no entrar en recursion: `asegurar_grupo` solo lo corre si falta el grupo; `setup_roles` no debe llamar a `asegurar_grupo`).

## 5. El grupo deja de ser editable a mano en el admin de usuarios
En `UserAdmin` (`apps/bookings/admin.py`, clase `UserAdmin`) y/o `EmpresaScopedUserAdminMixin` (`apps/tenancy/admin_mixins.py`): el campo `groups` debe ser de SOLO LECTURA para todos (operador incluido), de modo que guardar el usuario no reemplace los grupos que la señal puso. CUIDADO: una vez, marcar `password` como readonly rompio el formulario de Unfold (KeyError 'password' en `UserChangeForm`); si tocas `get_readonly_fields`/`get_fieldsets`, lee como esta resuelto hoy en esas clases y comprueba con una prueba que GET y POST de `/admin/auth/user/<id>/change/` siguen dando 200/302 para operador, jefe y vendedora, y que un POST no cambia los grupos. El unico lugar para cambiar un rol es `MembresiaEmpresaAdmin` (operador) o el formulario "Alta de usuario"; no cambies esas pantallas.

## 6. Pruebas (crear `backend/apps/tenancy/tests_sincronizacion_grupos.py`; corrige las existentes que se rompan)
- Crear membresia JEFE => el usuario queda en grupo Jefe y NO en Vendedora; cambiar `rol` a VENDEDORA (save) => pasa a Vendedora y sale de Jefe; borrar la membresia => sale del grupo; usuario con dos membresias (JEFE en A, VENDEDORA en B) => en ambos grupos; borrar solo la de JEFE => queda solo en Vendedora; borrar el usuario no lanza error.
- Un usuario en el grupo `OperadorPlataforma` con una membresia: tras sincronizar sigue en `OperadorPlataforma`.
- `sincronizar_todos` arregla un usuario con membresia JEFE al que se le quito el grupo a mano; `setup_roles` lo corre (verifica con `call_command('setup_roles')`).
- UserAdmin: `groups` de solo lectura (operador y jefe): GET 200, POST no cambia grupos.
- `crear_usuario_con_rol` deja el grupo correcto sin que el servicio lo asigne a mano.
Busca y corrige pruebas existentes que hagan `groups.add(Group.objects.get(name='Jefe'|'Vendedora'))` creyendo que eso da el rol: ya no lo da; deben crear la membresia (la señal pone el grupo). Los helpers de `apps/testing.py` ya lo hacen despues de tu cambio.

## 7. Documentacion
En `backend/CLAUDE.md`, seccion "Roles: Jefes vs Vendedora": cambia el texto para decir que el rol vive en `MembresiaEmpresa.rol`, que los grupos Jefe/Vendedora se derivan solos (señal en `apps/tenancy/roles.py`/`signals.py`) y son solo paquetes de permisos de modelo, que el unico helper de lectura es `scope.es_jefe(...)` y similares, y la limitacion conocida: una cuenta con roles distintos en dos empresas recibe la union de permisos de modelo porque los grupos no pueden limitarse por empresa. En `docs/deploy/QA.md`, en "Después de cada deploy", añade que `setup_roles` tambien sincroniza los grupos con las membresias.

## Restricciones
- No toques RLS, modelos ni migraciones. No borres funciones: si algo queda sin uso, dilo en el resumen.
- NO ejecutes pruebas (sin terminal). Yo reporto fallos.
Al final entrega resumen: archivos creados/tocados, que quitaste, y cualquier lugar donde todavia se asigne un grupo Jefe/Vendedora a mano (no deberia haber ninguno fuera de `roles.py`).
