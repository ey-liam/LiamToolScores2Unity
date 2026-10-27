# LiamToolScores2Unity V3.0

Herramienta web profesional para crear, personalizar, previsualizar y exportar efectos de puntuación (**ScoringFX**) de Just Dance directamente a Unity y al juego.

- **GitHub Pages**: https://ey-liam.github.io/LiamToolScores2Unity/
- **Repositorio**: https://github.com/ey-liam/LiamToolScores2Unity

---

## Novedades en V3.0

- **Malla y deformación 60 FPS auténtica de Spine**: Motor de renderizado WebGL que reproduce con precisión las mallas deformadas, transformaciones de huesos y blend modes (Normal y Aditivo) originales de Spine 4.0.
- **21 Plantillas Originales de Just Dance Next**: Biblioteca pre-horneada que incluye packs icónicos como `Basic`, `Neon`, `Aqua`, `Candy`, `Celebration`, `Christmas`, `Confetti`, `Flamepassion`, `Flower`, `Glitter`, `Halloween`, `Heartlove`, `Megastar`, `Memphis`, `Olympus`, `RoadTrip`, `Rosemolding`, `SparkleFirework`, `TropicalPlants`, `Unicorn` y `Y2K`.
- **Editor de Tipografía y Estilo Vectorial**:
  - Doble contorno (*stroke*) con colores y grosores independientes.
  - Gradientes verticales de color primario y secundario.
  - Resplandor exterior (*glow*) difuminado y extrusión 3D simulada.
  - Fuentes tipográficas personalizadas con la fuente oficial `JustDanceBold.ttf` pre-cargada.
- **Importador de Texturas y Partículas Dinámicas**:
  - Soporte de arrastrar y soltar (Drag & Drop) para imágenes PNG, JPG y WebP.
  - Generador de formas procedurales integrado (Estrella, Rombo, Rayo, Glow, Chispa, Anillo, Nota Musical, Corazón).
  - Emisor de partículas por feedback: control en tiempo real de velocidad, gravedad, dispersión, vida, color inicial y final, y blend aditivo.
  - Capas de fondo y rayos radiales giratorios con curvas elásticas (*outBack*, *outElastic*, *outBounce*).
- **Simulador de Ritmo en Vivo (Stream Test)**:
  - Prueba de secuencias con contador de combo dinámico y sintetizador Web Audio API integrado para retroalimentación sonora inmediata.
- **Centro de Multi-Exportación**:
  - **Unity Bundle (.zip)**: Archivo `.lfx.json`, texturas de atlas optimizadas, shaders multi-pipeline y runtime en C#.
  - **Spine / JD Next (.zip)**: Archivo `.skel` binario de Spine 4.0 y `.atlas` repintado para inyección directa en `StreamingAssets/DancerCardCatalog/Assets/Data/Spine/ScoringFXs`.
  - **Definición de Catálogo**: Snippet JSON listo para `scoring_fx_definitions.json`.

---

## Elementos de Puntuación Incluidos

Cada ScoringFX cuenta con los 6 elementos de juicio oficiales más las variantes especiales:

| Elemento | Animación Original | Descripción Visual |
| :--- | :--- | :--- |
| ⭐ **PERFECT** | `Perfect` | Tipografía cian/oro con rayos aditivos giratorios, partículas estelares y destellos. |
| 💚 **SUPER** | `Super` | Estilo esmeralda con estrellas orbitantes y animación elástica de entrada. |
| 💙 **GOOD** | `Good` | Tonos cian y azul profundo con ondas de choque expansivas. |
| 💛 **OK** | `Ok` | Diseño cálido en amarillo y naranja con destellos circulares. |
| ❌ **MISS (X)** | `Bad` / `Miss` | Animación de fallo con impacto, vibración e inclinación. |
| 🏆 **YEAH!** | `Gold` | Juicio para Gold Moves con rayos dorados de blend aditivo intenso. |
| ⚠ **GOLD MISS** | `GoldMiss` | Variación de fallo para movimientos dorados. |

---

## Estructura de Archivos Exportados

Al exportar un proyecto desde la herramienta web se generan los siguientes archivos:

```text
ScoringFX_<Nombre>/
├── ScoringFX_<Nombre>.lfx.json      # Definición de mallas, UVs y animación a 60 FPS
├── ScoringFX_<Nombre>.png           # Textura atlas de alta resolución
├── ScoringFX_<Nombre>.skel          # Archivo binario Spine 4.0 (para el juego)
├── ScoringFX_<Nombre>.atlas         # Descriptor de atlas Spine
├── ScoringFX_Thumbnail_<Nombre>.png # Miniatura para el catálogo del juego
└── scoring_fx_definitions.json      # Entrada para el catálogo de StreamingAssets
```

---

## Paquete de Integración para Unity

La carpeta `Unity/` incluye el runtime completo libre de basura de memoria (GC Free) y compatible tanto con objetos 3D como con UI Canvas (uGUI):

### Scripts Incluidos:
- **`LiamFXPlayer.cs`**: MonoBehaviour que reproduce el clip a 60 FPS mediante `MeshRenderer` con submallas separadas para Normal y Additive, soporte de audio SFX y modo ejecución en edición (`[ExecuteAlways]`).
- **`LiamFXCanvasGraphic.cs`**: Componente `MaskableGraphic` para anclar los scores directamente dentro de un `Canvas` (sobre la Dancer Card del jugador o HUD).
- **`LiamFXData.cs`**: Estructuras de datos, parser ultrarrápido y deserializador `MiniJson` sin dependencias externas.
- **`Editor/LiamFXPlayerEditor.cs`**: Inspector interactivo con botones de prueba rápida para los 6 feedbacks y barra de tiempo (timeline scrubber).
- **`Editor/LiamFXReviewWindow.cs`**: Ventana de trabajo accesible en `Window > Liam > Scoring FX Studio Review` con generador de instancias a un clic y simulador de combo por BPM.
- **`Shaders/LiamFXNormal.shader`**: Shader unlit transparente con mezcla alfa compatible con Built-in RP y URP.
- **`Shaders/LiamFXAdditive.shader`**: Shader unlit aditivo (`Blend One One`) con atenuación por color de vértice.

### Ejemplo de Uso en Código C#:

```csharp
using UnityEngine;
using LiamFX;

public class GameplayScoringBridge : MonoBehaviour
{
    [SerializeField] private LiamFXPlayer scoringPlayer;

    public void OnJudgmentReceived(ScoringFeedbackType judgment)
    {
        scoringPlayer.Play(judgment);
    }
}
```

O directamente en el Canvas:
```csharp
using UnityEngine;
using LiamFX;

public class UIScoreCard : MonoBehaviour
{
    [SerializeField] private LiamFXCanvasGraphic uiGraphic;

    public void TriggerSuper()
    {
        uiGraphic.Play(ScoringFeedbackType.Super);
    }
}
```

---

## Requisitos y Compatibilidad

- **Navegadores Soportados**: Google Chrome, Microsoft Edge, Mozilla Firefox, Brave, Opera (requiere soporte de WebGL 1.0/2.0).
- **Versiones de Unity**: Unity 2019.4 LTS o superior (incluyendo Unity 2020, 2021, 2022 y Unity 6).
- **Render Pipelines en Unity**: Built-in Render Pipeline, Universal Render Pipeline (URP).
- **Versión de Spine**: Spine 4.0.64 (formato de Just Dance Next).

---

## Licencia y Créditos

- Dar los créditos correspondientes al autor (**Liam**) en los proyectos donde se utilice la herramienta.
- Queda prohibida la copia o redistribución no autorizada del código fuente.
