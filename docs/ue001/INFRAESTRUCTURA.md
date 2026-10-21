# UE-001: auditoría de infraestructura

21 de octubre de 2026, America/Mexico_City. Inventario realizado antes de modificar
el proyecto; [datos medidos](infrastructure.json) y [referencias oficiales](official-references.json).

| Recurso | Disponible realmente |
| --- | --- |
| Sistema | Debian 13.6 x86_64, glibc 2.41, kernel 6.18.55 |
| CPU | Xeon Platinum 8573C, 5 CPU visibles; cuota efectiva de 4 vCPU |
| RAM | Límite cgroup 32 GiB; sin swap |
| Disco | ~27,9 GiB libres en workspace en el momento del inventario |
| GPU | Ningún dispositivo /dev/dri/renderD* o /dev/nvidia* expuesto; sin herramientas Vulkan/NVIDIA |
| Escritorio | Sin DISPLAY ni WAYLAND_DISPLAY |
| Compiladores | g++ disponible; sin clang, .NET, MSVC ni Windows SDK detectables |
| Unreal | Ningún editor en PATH, variables o raíces conocidas; búsqueda adicional sin coincidencias |
| Docker | Cliente/daemon 28.4.0 funcional, sin imágenes; no proporciona UE/GPU por sí solo |
| GitHub | Git y API del proyecto funcionan; inventario de self-hosted runners rechazado con 403 |

No se lanzó Unreal. No hay compilación C++, UHT, importación, mapa binario,
colisión cocinada, captura UE ni ejecutable verificables en este entorno.

## Requisitos contrastados

Epic recomienda para UE5.6 CPU de cuatro núcleos a 2,5 GHz, 32 GB RAM y 8 GB VRAM;
Windows 10/11 compatible con DX11/12. Lumen/Nanite tienen condiciones adicionales.
En Linux recomienda Ubuntu 22.04, GPU dedicada con 8 GB y Vulkan; la toolchain es
clang 18.1.0 del SDK de Epic. Debian 13 no figura como plataforma recomendada.
Windows C++ requiere VS2022 (17.8 mínimo, 17.14 recomendado), MSVC 14.38.33130 y
Windows SDK (10.0.19041.0 mínimo, 10.0.22621.0 o posterior recomendado).

El login de Epic es necesario para descargar el Installed Build Linux; para el
código de GitHub se necesitan cuentas Epic/GitHub asociadas y aceptación aplicable
de licencia. La integración actual recibe 404 en EpicGames/UnrealEngine: no tiene
acceso comprobable; esto no demuestra si la cuenta personal del titular está vinculada.
Los dos portales unrealengine.com consultados devolvieron CONNECT 403 del proxy;
las páginas dev.epicgames.com sí permitieron revisar requisitos y procedimiento.

## Opciones reales

1. **Este cloud:** pruebas Python, auditoría numérica, estructura Unreal y preparación
   de fuentes. Instalar UE no está autorizado. Tampoco se dispone de GPU, SDK ni
   espacio cómodo para motor, toolchain, shaders, DDC y cooking. No se descarga UE.
2. **Runner Windows con UE ya licenciado:** compilar editor/juego, importar GEO-003,
   convertir a World Partition, abrir el mapa en proceso de juego con RHI real,
   probar desplazamiento/cámara/suelo, capturar PNG, cocinar y lanzar el ejecutable.
   Es la ruta recomendada para la plataforma comercial.
3. **Runner Linux con UE instalado:** la misma herramienta admite build/importación
   y paquete Linux nativos. No equivale a generar ni validar un ejecutable Windows.
   No se presenta la toolchain Linux como cross-compilador Windows disponible.
4. **GitHub hosted Windows:** permite las pruebas externas; no se ha demostrado una
   instalación licenciada de UE ni GPU apta. No se intenta descargar el motor allí.
   El workflow UE usa dispatch explícito y self-hosted; no ejecuta PR públicos.

## Requisito concreto para continuar con motor

Propuesta de capacidad del proyecto (no mínimos oficiales): un runner Windows
10/11, 8 vCPU o más, 64 GB RAM, GPU DX12 con al menos 8 GB VRAM y SSD con 200 GB
libres. Debe tener **UE5.6.1 instalado legalmente**, VS2022 y SDK anteriores,
Python 3.12 y UE_ROOT apuntando al motor. La etapa visual necesita una sesión/RHI
que renderice; NullRHI no aprueba exploración ni capturas. Puede ser una máquina
existente o infraestructura nueva cuya provisión/coste debe autorizar el titular.

No se necesita compartir contraseñas ni tokens en el chat. Para descubrir runners
existentes mediante esta integración haría falta permiso de lectura de administración
del repositorio; actualmente el endpoint está denegado. También es posible adjuntar
un entorno Windows accesible al agente sin usar ese endpoint. Registrar/provisionar
un runner y la instalación considerable del motor se dejan pendientes de autorización.
