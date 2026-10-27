using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace LiamFX
{
    /// <summary>
    /// LiamFXCanvasGraphic - Componente de UI para reproducir ScoringFX directamente en Canvas (uGUI).
    /// Permite anclar los Scores de Just Dance a cualquier Dancer Card, HUD o posición de pantalla
    /// con escalado automático por CanvasScaler.
    /// </summary>
    [ExecuteAlways]
    [RequireComponent(typeof(CanvasRenderer))]
    public class LiamFXCanvasGraphic : MaskableGraphic
    {
        [Header("1. Datos del ScoringFX")]
        [Tooltip("Archivo .lfx.json")]
        public TextAsset clipJsonAsset;
        [Tooltip("Textura del Atlas")]
        public Texture2D atlasTexture;

        [Header("2. Parámetros de Animación")]
        [Range(0.1f, 3.0f)] public float speedMultiplier = 1.0f;
        [Range(0.1f, 5.0f)] public float canvasScale = 1.0f;
        public bool loop = false;
        public bool autoHideOnComplete = true;

        [Header("3. Estado en Vivo")]
        [SerializeField] private string currentAnim = "";
        [SerializeField] private float currentTime = 0f;
        [SerializeField] private float duration = 0f;
        [SerializeField] private bool isPlaying = false;

        public override Texture mainTexture => atlasTexture != null ? atlasTexture : base.mainTexture;

        private ScoringFXClip clip;
        private string loadedJsonGuid = "";

        public event Action<string> OnAnimationStarted;
        public event Action<string> OnAnimationCompleted;

        protected override void Awake()
        {
            base.Awake();
            ReloadClipIfNeed();
        }

        protected override void OnEnable()
        {
            base.OnEnable();
            ReloadClipIfNeed();
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
                    OnAnimationCompleted?.Invoke(currentAnim);
                    if (autoHideOnComplete)
                    {
                        SetVerticesDirty();
                        return;
                    }
                }
            }

            SetVerticesDirty();
        }

        public void Play(ScoringFeedbackType type)
        {
            ReloadClipIfNeed();
            if (clip == null) return;
            Play(clip.ResolveFeedbackName(type));
        }

        public void Play(string animName)
        {
            ReloadClipIfNeed();
            if (clip == null) return;

            if (!clip.TryGetAnimation(animName, out AnimationData anim))
            {
                Debug.LogWarning($"[LiamFXCanvasGraphic] Animación '{animName}' no encontrada.");
                return;
            }

            currentAnim = animName;
            duration = anim.duration;
            currentTime = 0f;
            isPlaying = true;
            SetVerticesDirty();
            OnAnimationStarted?.Invoke(animName);
        }

        public void Stop()
        {
            isPlaying = false;
            currentTime = 0f;
            SetVerticesDirty();
        }

        public void Seek(float time)
        {
            currentTime = Mathf.Clamp(time, 0f, duration);
            SetVerticesDirty();
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
            }
            catch (Exception ex)
            {
                Debug.LogError($"[LiamFXCanvasGraphic] Error parseando JSON: {ex.Message}");
            }
        }

        protected override void OnPopulateMesh(VertexHelper vh)
        {
            vh.Clear();
            if (clip == null || string.IsNullOrEmpty(currentAnim) || (!isPlaying && autoHideOnComplete && currentTime >= duration))
                return;

            if (!clip.TryGetAnimation(currentAnim, out AnimationData anim))
                return;

            // Recorrer tracks
            for (int ti = 0; ti < anim.tracks.Count; ti++)
            {
                TrackData track = anim.tracks[ti];
                if (track.frames.Count == 0) continue;

                if (!SampleTrack(track, currentTime, out int attIndex, out Color trackColor, out Vector2[] localVerts))
                    continue;

                if (attIndex < 0 || attIndex >= clip.attachments.Count)
                    continue;

                AttachmentDef att = clip.attachments[attIndex];
                if (att.uvs == null || att.tris == null) continue;

                int baseVert = vh.currentVertCount;
                int vertCount = Mathf.Min(att.uvs.Length, localVerts.Length);

                Color finalColor = trackColor * this.color;
                for (int vi = 0; vi < vertCount; vi++)
                {
                    Vector3 pos = new Vector3(localVerts[vi].x * canvasScale, localVerts[vi].y * canvasScale, 0f);
                    vh.AddVert(pos, finalColor, att.uvs[vi]);
                }

                for (int tri = 0; tri < att.tris.Length; tri += 3)
                {
                    int i0 = att.tris[tri];
                    int i1 = att.tris[tri + 1];
                    int i2 = att.tris[tri + 2];
                    if (i0 < vertCount && i1 < vertCount && i2 < vertCount)
                    {
                        vh.AddTriangle(baseVert + i0, baseVert + i1, baseVert + i2);
                    }
                }
            }
        }

        private bool SampleTrack(TrackData track, float t, out int attIndex, out Color color, out Vector2[] verts)
        {
            attIndex = -1;
            color = Color.white;
            verts = null;

            var frames = track.frames;
            if (frames.Count == 0 || t < frames[0].time) return false;

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
    }
}
