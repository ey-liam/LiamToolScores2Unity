using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEditor;

namespace LiamFX
{
    /// <summary>
    /// LiamFXReviewWindow - Ventana de inspección y prueba interactiva en Unity Editor para ScoringFX.
    /// Permite probar clips .lfx.json, simular secuencias rítmicas de juego, inspeccionar capas
    /// y crear prefabs/instancias listas para usar en Scene o UI Canvas con un solo clic.
    /// </summary>
    public class LiamFXReviewWindow : EditorWindow
    {
        [MenuItem("Window/Liam/Scoring FX Studio Review", false, 100)]
        public static void OpenWindow()
        {
            var win = GetWindow<LiamFXReviewWindow>("Scoring FX Review");
            win.minSize = new Vector2(420, 520);
            win.Show();
        }

        private TextAsset selectedClipJson;
        private Texture2D selectedAtlasTexture;
        private LiamFXPlayer activePlayerInScene;

        // Simulación de Combo
        private bool isSimulatingCombo = false;
        private double lastSimTime = 0;
        private int comboIndex = 0;
        private readonly ScoringFeedbackType[] comboPattern = new ScoringFeedbackType[]
        {
            ScoringFeedbackType.Perfect,
            ScoringFeedbackType.Perfect,
            ScoringFeedbackType.Super,
            ScoringFeedbackType.Perfect,
            ScoringFeedbackType.Good,
            ScoringFeedbackType.Perfect,
            ScoringFeedbackType.Yeah,
            ScoringFeedbackType.Perfect
        };

        private Vector2 scrollPos;

        void OnEnable()
        {
            EditorApplication.update += OnEditorUpdate;
        }

        void OnDisable()
        {
            EditorApplication.update -= OnEditorUpdate;
        }

        void OnEditorUpdate()
        {
            if (isSimulatingCombo)
            {
                double now = EditorApplication.timeSinceStartup;
                if (now - lastSimTime >= 0.75) // Un beat a ~80-120 BPM
                {
                    lastSimTime = now;
                    TriggerComboStep();
                }
                Repaint();
            }
        }

        void OnGUI()
        {
            scrollPos = EditorGUILayout.BeginScrollView(scrollPos);

            // Encabezado
            EditorGUILayout.Space(8);
            GUIStyle headerStyle = new GUIStyle(EditorStyles.boldLabel) { fontSize = 14 };
            EditorGUILayout.LabelField("🎵 LiamTool ScoringFX - Editor Workbench", headerStyle);
            EditorGUILayout.LabelField("Herramienta de revisión de Scores para Just Dance en Unity", EditorStyles.miniLabel);
            EditorGUILayout.Space(4);

            EditorGUILayout.HelpBox(
                "Selecciona un archivo .lfx.json generado por la Web Tool y su textura atlas para probar los feedbacks o instanciarlo directamente.",
                MessageType.Info
            );

            EditorGUILayout.Space(6);
            selectedClipJson = (TextAsset)EditorGUILayout.ObjectField("Archivo Clip (.lfx.json)", selectedClipJson, typeof(TextAsset), false);
            selectedAtlasTexture = (Texture2D)EditorGUILayout.ObjectField("Textura del Atlas", selectedAtlasTexture, typeof(Texture2D), false);

            EditorGUILayout.Space(10);
            EditorGUILayout.LabelField("1. Vincular a Player en Escena", EditorStyles.boldLabel);
            activePlayerInScene = (LiamFXPlayer)EditorGUILayout.ObjectField("Player en Escena", activePlayerInScene, typeof(LiamFXPlayer), true);

            if (activePlayerInScene == null)
            {
                activePlayerInScene = FindObjectOfType<LiamFXPlayer>();
            }

            if (GUILayout.Button("✨ Crear nuevo ScoringFX Player en Escena (3D)", GUILayout.Height(28)))
            {
                CreateNewPlayerInScene(false);
            }

            if (GUILayout.Button("🖥 Crear ScoringFX UI en Canvas (2D Graphic)", GUILayout.Height(28)))
            {
                CreateNewPlayerInScene(true);
            }

            EditorGUILayout.Space(14);
            EditorGUILayout.LabelField("2. Pruebas de Feedback Directas", EditorStyles.boldLabel);

            if (activePlayerInScene == null)
            {
                EditorGUILayout.HelpBox("Asigna o crea un Player en la Escena para enviar los feedbacks en tiempo real.", MessageType.Warning);
            }
            else
            {
                DrawFeedbackButtons();

                EditorGUILayout.Space(10);
                EditorGUILayout.LabelField("3. Simulador de Combo de Baile (Stream Test)", EditorStyles.boldLabel);
                EditorGUILayout.BeginHorizontal();
                if (!isSimulatingCombo)
                {
                    GUI.backgroundColor = new Color(0.2f, 1f, 0.4f);
                    if (GUILayout.Button("▶ Iniciar Secuencia Rítmica (BPM Test)", GUILayout.Height(30)))
                    {
                        isSimulatingCombo = true;
                        comboIndex = 0;
                        lastSimTime = EditorApplication.timeSinceStartup;
                    }
                }
                else
                {
                    GUI.backgroundColor = new Color(1f, 0.4f, 0.3f);
                    if (GUILayout.Button("⏹ Detener Secuencia", GUILayout.Height(30)))
                    {
                        isSimulatingCombo = false;
                    }
                }
                GUI.backgroundColor = Color.white;
                EditorGUILayout.EndHorizontal();

                if (isSimulatingCombo)
                {
                    EditorGUILayout.LabelField($"Feedback actual: {comboPattern[comboIndex]} (Paso {comboIndex + 1}/{comboPattern.Length})");
                }
            }

            EditorGUILayout.EndScrollView();
        }

        private void DrawFeedbackButtons()
        {
            EditorGUILayout.BeginHorizontal();
            GUI.backgroundColor = new Color(0.2f, 0.8f, 1f);
            if (GUILayout.Button("PERFECT", GUILayout.Height(32)))
            {
                SyncAndPlay(ScoringFeedbackType.Perfect);
            }

            GUI.backgroundColor = new Color(0.2f, 1f, 0.4f);
            if (GUILayout.Button("SUPER", GUILayout.Height(32)))
            {
                SyncAndPlay(ScoringFeedbackType.Super);
            }
            EditorGUILayout.EndHorizontal();

            EditorGUILayout.BeginHorizontal();
            GUI.backgroundColor = new Color(0.3f, 0.6f, 1f);
            if (GUILayout.Button("GOOD", GUILayout.Height(26)))
            {
                SyncAndPlay(ScoringFeedbackType.Good);
            }

            GUI.backgroundColor = new Color(1f, 0.85f, 0.2f);
            if (GUILayout.Button("OK", GUILayout.Height(26)))
            {
                SyncAndPlay(ScoringFeedbackType.Ok);
            }

            GUI.backgroundColor = new Color(1f, 0.3f, 0.3f);
            if (GUILayout.Button("MISS (X)", GUILayout.Height(26)))
            {
                SyncAndPlay(ScoringFeedbackType.Miss);
            }
            EditorGUILayout.EndHorizontal();

            EditorGUILayout.BeginHorizontal();
            GUI.backgroundColor = new Color(1f, 0.8f, 0f);
            if (GUILayout.Button("🏆 YEAH! (Gold Move)", GUILayout.Height(28)))
            {
                SyncAndPlay(ScoringFeedbackType.Yeah);
            }

            GUI.backgroundColor = new Color(0.8f, 0.5f, 0.2f);
            if (GUILayout.Button("⚠ GOLD MISS", GUILayout.Height(28)))
            {
                SyncAndPlay(ScoringFeedbackType.GoldMiss);
            }
            EditorGUILayout.EndHorizontal();

            GUI.backgroundColor = Color.white;
        }

        private void SyncAndPlay(ScoringFeedbackType type)
        {
            if (activePlayerInScene == null) return;

            if (selectedClipJson != null && activePlayerInScene.clipJsonAsset != selectedClipJson)
            {
                activePlayerInScene.clipJsonAsset = selectedClipJson;
            }
            if (selectedAtlasTexture != null && (activePlayerInScene.atlasTextures == null || activePlayerInScene.atlasTextures.Length == 0 || activePlayerInScene.atlasTextures[0] != selectedAtlasTexture))
            {
                activePlayerInScene.atlasTextures = new Texture2D[] { selectedAtlasTexture };
            }

            activePlayerInScene.Play(type);
            EditorUtility.SetDirty(activePlayerInScene);
        }

        private void TriggerComboStep()
        {
            if (activePlayerInScene == null) return;
            var feedback = comboPattern[comboIndex];
            SyncAndPlay(feedback);
            comboIndex = (comboIndex + 1) % comboPattern.Length;
        }

        private void CreateNewPlayerInScene(bool isUI)
        {
            string baseName = selectedClipJson != null ? selectedClipJson.name : "ScoringFX_Player";

            if (isUI)
            {
                // Buscar Canvas en escena o crear uno
                Canvas canvas = FindObjectOfType<Canvas>();
                if (canvas == null)
                {
                    GameObject cGo = new GameObject("ScoringFX_Canvas", typeof(Canvas), typeof(UnityEngine.UI.CanvasScaler), typeof(UnityEngine.UI.GraphicRaycaster));
                    canvas = cGo.GetComponent<Canvas>();
                    canvas.renderMode = RenderMode.ScreenSpaceOverlay;
                }

                GameObject go = new GameObject(baseName + "_UI", typeof(RectTransform), typeof(LiamFXCanvasGraphic));
                go.transform.SetParent(canvas.transform, false);

                var graphic = go.GetComponent<LiamFXCanvasGraphic>();
                graphic.clipJsonAsset = selectedClipJson;
                graphic.atlasTexture = selectedAtlasTexture;
                graphic.canvasScale = 1.0f;

                Selection.activeGameObject = go;
                Undo.RegisterCreatedObjectUndo(go, "Create ScoringFX UI");
            }
            else
            {
                GameObject go = new GameObject(baseName, typeof(MeshFilter), typeof(MeshRenderer), typeof(LiamFXPlayer));
                var player = go.GetComponent<LiamFXPlayer>();
                player.clipJsonAsset = selectedClipJson;
                if (selectedAtlasTexture != null)
                {
                    player.atlasTextures = new Texture2D[] { selectedAtlasTexture };
                }
                player.EnsureMaterials();

                activePlayerInScene = player;
                Selection.activeGameObject = go;
                Undo.RegisterCreatedObjectUndo(go, "Create ScoringFX Player");
            }
        }
    }
}
