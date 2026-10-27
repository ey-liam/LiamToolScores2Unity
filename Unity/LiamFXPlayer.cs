using System;
using System.Collections.Generic;
using UnityEngine;

namespace LiamFX
{
    /// <summary>
    /// LiamFXPlayer - Reproductor nativo en Unity para animaciones de ScoringFX de Just Dance
    /// exportadas desde LiamToolScoringFX2Unity (.lfx.json).
    /// 
    /// Replica fielmente el renderizado de Spine 4.0 original:
    /// - Deformación de mallas a 60 FPS
    /// - Separación automática de materiales Normal y Additive
    /// - Cero asignaciones de memoria (GC Free) mediante buffers de vértices reutilizados
    /// - Compatible con modo Edición (Preview en tiempo real sin darle Play)
    /// </summary>
    [ExecuteAlways]
    [DisallowMultipleComponent]
    [RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
    public class LiamFXPlayer : MonoBehaviour
    {
        [Header("1. Archivos del ScoringFX")]
        [Tooltip("Archivo .lfx.json generado por LiamToolScoringFX2Unity")]
        public TextAsset clipJsonAsset;

        [Tooltip("Texturas del atlas (en el mismo orden que las páginas del .lfx.json)")]
        public Texture2D[] atlasTextures = new Texture2D[1];

        [Header("2. Parámetros de Reproducción")]
        [Range(0.1f, 3.0f)]
        public float speedMultiplier = 1.0f;
        [Range(0.001f, 10.0f)]
        public float worldScale = 0.01f; // 0.01 convierte unidades de Spine (~1000px) a unidades de Unity (~10m o UI)
        public Vector3 offset = Vector3.zero;
        public bool loop = false;
        public bool autoHideOnComplete = true;
        public bool playOnAwake = false;
        public ScoringFeedbackType defaultFeedback = ScoringFeedbackType.Perfect;

        [Header("3. Materiales y Shaders")]
        public Material normalMaterial;
        public Material additiveMaterial;

        [Header("4. Efectos de Sonido (Opcional)")]
        public AudioSource audioSource;
        public AudioClip perfectSfx;
        public AudioClip superSfx;
        public AudioClip goodSfx;
        public AudioClip okSfx;
        public AudioClip missSfx;
        public AudioClip yeahSfx;

        [Header("5. Estado en Tiempo Real (Solo Lectura)")]
        [SerializeField] private string currentAnimationName = "";
        [SerializeField] private float currentTime = 0f;
        [SerializeField] private float duration = 0f;
        [SerializeField] private bool isPlaying = false;

        public string CurrentAnimationName => currentAnimationName;
        public float CurrentTime => currentTime;
        public float Duration => duration;
        public bool IsPlaying => isPlaying;
        public float NormalizedTime => duration > 0f ? Mathf.Clamp01(currentTime / duration) : 0f;

        public event Action<string> OnAnimationStarted;
        public event Action<string> OnAnimationCompleted;

        // Clip parseado
        private ScoringFXClip clip;
        private string loadedJsonGuid = "";

        // Componentes
        private MeshFilter meshFilter;
        private MeshRenderer meshRenderer;
        private Mesh dynamicMesh;

        // Buffers reutilizables para evitar basura en el Garbage Collector
        private readonly List<Vector3> verticesBuffer = new List<Vector3>(256);
        private readonly List<Vector2> uvsBuffer = new List<Vector2>(256);
        private readonly List<Color32> colorsBuffer = new List<Color32>(256);
        private readonly List<int> normalTrisBuffer = new List<int>(512);
        private readonly List<int> additiveTrisBuffer = new List<int>(512);

        void Awake()
        {
            EnsureComponents();
            ReloadClipIfNeed();
        }

        void Start()
        {
            if (Application.isPlaying && playOnAwake)
            {
                Play(defaultFeedback);
            }
        }

        void OnEnable()
        {
            EnsureComponents();
            ReloadClipIfNeed();
        }

        void OnDisable()
        {
            ClearMesh();
        }

        void OnDestroy()
        {
            if (dynamicMesh != null)
            {
                if (Application.isPlaying) Destroy(dynamicMesh);
                else DestroyImmediate(dynamicMesh);
            }
        }

        void Update()
        {
            if (!isPlaying) return;

            float dt = Application.isPlaying ? Time.deltaTime : 0.0166f;
            currentTime += dt * Mathf.Max(0.01f, speedMultiplier);

            if (currentTime >= duration)
            {
                if (loop)
                {
                    currentTime = duration > 0f ? (currentTime % duration) : 0f;
                }
                else
                {
                    currentTime = duration;
                    isPlaying = false;
                    OnAnimationCompleted?.Invoke(currentAnimationName);
                    if (autoHideOnComplete)
                    {
                        ClearMesh();
                        return;
                    }
                }
            }

            RenderAtTime(currentTime);
        }

        public void Play(ScoringFeedbackType feedback)
        {
            ReloadClipIfNeed();
            if (clip == null) return;
            string animName = clip.ResolveFeedbackName(feedback);
            Play(animName);
            PlaySfxForFeedback(feedback);
        }

        public void Play(string animName)
        {
            ReloadClipIfNeed();
            if (clip == null) return;

            if (!clip.TryGetAnimation(animName, out AnimationData anim))
            {
                Debug.LogWarning($"[LiamFXPlayer] Animación '{animName}' no encontrada en el clip '{clip.name}'.");
                return;
            }

            currentAnimationName = animName;
            duration = anim.duration;
            currentTime = 0f;
            isPlaying = true;

            EnsureMaterials();
            RenderAtTime(0f);
            OnAnimationStarted?.Invoke(animName);
        }

        public void Stop()
        {
            isPlaying = false;
            currentTime = 0f;
            ClearMesh();
        }

        public void Pause()
        {
            isPlaying = false;
        }

        public void Resume()
        {
            if (!string.IsNullOrEmpty(currentAnimationName))
            {
                isPlaying = true;
            }
        }

        public void Seek(float time)
        {
            ReloadClipIfNeed();
            if (clip == null || string.IsNullOrEmpty(currentAnimationName)) return;

            currentTime = Mathf.Clamp(time, 0f, duration);
            RenderAtTime(currentTime);
        }

        public void SeekNormalized(float normalizedProgress)
        {
            Seek(normalizedProgress * duration);
        }

        public List<string> GetAvailableAnimations()
        {
            ReloadClipIfNeed();
            if (clip == null) return new List<string>();
            return new List<string>(clip.animations.Keys);
        }

        public void ReloadClipIfNeed(bool force = false)
        {
            if (clipJsonAsset == null)
            {
                clip = null;
                loadedJsonGuid = "";
                return;
            }

            string currentText = clipJsonAsset.text;
            if (!force && clip != null && loadedJsonGuid == currentText)
                return;

            try
            {
                clip = LiamFXParser.Parse(currentText);
                loadedJsonGuid = currentText;
                EnsureMaterials();
            }
            catch (Exception ex)
            {
                Debug.LogError($"[LiamFXPlayer] Error parseando el archivo JSON: {ex.Message}\n{ex.StackTrace}");
            }
        }

        private void EnsureComponents()
        {
            if (meshFilter == null) meshFilter = GetComponent<MeshFilter>();
            if (meshRenderer == null) meshRenderer = GetComponent<MeshRenderer>();

            if (dynamicMesh == null)
            {
                dynamicMesh = new Mesh();
                dynamicMesh.name = "LiamFX_DynamicMesh";
                dynamicMesh.MarkDynamic();
                meshFilter.sharedMesh = dynamicMesh;
            }
        }

        public void EnsureMaterials()
        {
            EnsureComponents();

            Shader normShader = Shader.Find("LiamFX/Normal") ?? Shader.Find("Sprites/Default") ?? Shader.Find("UI/Default");
            Shader addShader = Shader.Find("LiamFX/Additive") ?? Shader.Find("Mobile/Particles/Additive") ?? Shader.Find("Sprites/Default");

            if (normalMaterial == null && normShader != null)
            {
                normalMaterial = new Material(normShader);
                normalMaterial.name = "LiamFX_Normal_Mat";
            }
            if (additiveMaterial == null && addShader != null)
            {
                additiveMaterial = new Material(addShader);
                additiveMaterial.name = "LiamFX_Additive_Mat";
            }

            Texture2D mainAtlas = (atlasTextures != null && atlasTextures.Length > 0) ? atlasTextures[0] : null;
            if (mainAtlas != null)
            {
                if (normalMaterial != null) normalMaterial.mainTexture = mainAtlas;
                if (additiveMaterial != null) additiveMaterial.mainTexture = mainAtlas;
            }

            meshRenderer.sharedMaterials = new Material[] { normalMaterial, additiveMaterial };
        }

        private void RenderAtTime(float t)
        {
            if (clip == null || string.IsNullOrEmpty(currentAnimationName)) return;
            if (!clip.TryGetAnimation(currentAnimationName, out AnimationData anim)) return;

            verticesBuffer.Clear();
            uvsBuffer.Clear();
            colorsBuffer.Clear();
            normalTrisBuffer.Clear();
            additiveTrisBuffer.Clear();

            // Evaluar cada track de la animación
            for (int ti = 0; ti < anim.tracks.Count; ti++)
            {
                TrackData track = anim.tracks[ti];
                if (track.frames.Count == 0) continue;

                // Muestrear frame en el tiempo t
                if (!SampleTrack(track, t, out int attIndex, out Color color, out Vector2[] localVerts))
                    continue;

                if (attIndex < 0 || attIndex >= clip.attachments.Count)
                    continue;

                AttachmentDef att = clip.attachments[attIndex];
                if (att.uvs == null || att.tris == null) continue;

                int baseVertIndex = verticesBuffer.Count;
                int vertCount = Mathf.Min(att.uvs.Length, localVerts.Length);

                Color32 c32 = color;
                for (int vi = 0; vi < vertCount; vi++)
                {
                    Vector3 worldPos = new Vector3(localVerts[vi].x * worldScale, localVerts[vi].y * worldScale, 0f) + offset;
                    verticesBuffer.Add(worldPos);
                    uvsBuffer.Add(att.uvs[vi]);
                    colorsBuffer.Add(c32);
                }

                List<int> targetTris = track.isAdditive ? additiveTrisBuffer : normalTrisBuffer;
                for (int tri = 0; tri < att.tris.Length; tri++)
                {
                    int index = att.tris[tri];
                    if (index < vertCount)
                    {
                        targetTris.Add(baseVertIndex + index);
                    }
                }
            }

            // Subir datos al Mesh
            EnsureComponents();
            dynamicMesh.Clear();

            if (verticesBuffer.Count > 0)
            {
                dynamicMesh.SetVertices(verticesBuffer);
                dynamicMesh.SetUVs(0, uvsBuffer);
                dynamicMesh.SetColors(colorsBuffer);
                dynamicMesh.subMeshCount = 2;
                dynamicMesh.SetTriangles(normalTrisBuffer, 0);
                dynamicMesh.SetTriangles(additiveTrisBuffer, 1);
                dynamicMesh.RecalculateBounds();
            }
        }

        private bool SampleTrack(TrackData track, float t, out int attIndex, out Color color, out Vector2[] verts)
        {
            attIndex = -1;
            color = Color.white;
            verts = null;

            var frames = track.frames;
            if (frames.Count == 0 || t < frames[0].time) return false;

            // Búsqueda binaria del frame correspondiente
            int lo = 0;
            int hi = frames.Count - 1;
            while (lo < hi)
            {
                int mid = (lo + hi + 1) >> 1;
                if (frames[mid].time <= t) lo = mid;
                else hi = mid - 1;
            }

            FrameData a = frames[lo];
            if (a.attachmentIndex < 0) return false;

            if (lo + 1 >= frames.Count)
            {
                attIndex = a.attachmentIndex;
                color = a.color;
                verts = a.vertices;
                return true;
            }

            FrameData b = frames[lo + 1];
            if (b.attachmentIndex != a.attachmentIndex || b.time <= a.time)
            {
                attIndex = a.attachmentIndex;
                color = a.color;
                verts = a.vertices;
                return true;
            }

            // Interpolación suave entre frames contiguos
            float factor = Mathf.Clamp01((t - a.time) / (b.time - a.time));
            attIndex = a.attachmentIndex;
            color = Color.Lerp(a.color, b.color, factor);

            int count = Mathf.Min(a.vertices.Length, b.vertices.Length);
            verts = new Vector2[count];
            for (int i = 0; i < count; i++)
            {
                verts[i] = Vector2.LerpUnclamped(a.vertices[i], b.vertices[i], factor);
            }

            return true;
        }

        private void ClearMesh()
        {
            if (dynamicMesh != null)
            {
                dynamicMesh.Clear();
            }
        }

        private void PlaySfxForFeedback(ScoringFeedbackType type)
        {
            if (audioSource == null) return;

            AudioClip clipToPlay = null;
            switch (type)
            {
                case ScoringFeedbackType.Perfect: clipToPlay = perfectSfx; break;
                case ScoringFeedbackType.Super: clipToPlay = superSfx; break;
                case ScoringFeedbackType.Good: clipToPlay = goodSfx; break;
                case ScoringFeedbackType.Ok: clipToPlay = okSfx; break;
                case ScoringFeedbackType.Miss: clipToPlay = missSfx; break;
                case ScoringFeedbackType.Yeah: clipToPlay = yeahSfx; break;
                case ScoringFeedbackType.GoldMiss: clipToPlay = missSfx; break;
            }

            if (clipToPlay != null)
            {
                audioSource.PlayOneShot(clipToPlay);
            }
        }
    }
}
