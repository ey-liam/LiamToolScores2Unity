using UnityEngine;
using UnityEditor;

namespace LiamFX
{
    [CustomEditor(typeof(LiamFXPlayer))]
    [CanEditMultipleObjects]
    public class LiamFXPlayerEditor : Editor
    {
        private LiamFXPlayer player;

        void OnEnable()
        {
            player = (LiamFXPlayer)target;
        }

        public override void OnInspectorGUI()
        {
            DrawDefaultInspector();

            EditorGUILayout.Space(10);
            EditorGUILayout.LabelField("🎮 Pruebas de Feedback en Vivo", EditorStyles.boldLabel);

            EditorGUILayout.BeginHorizontal();
            GUI.backgroundColor = new Color(0.2f, 0.8f, 1f);
            if (GUILayout.Button("⭐ PERFECT", GUILayout.Height(30)))
            {
                player.Play(ScoringFeedbackType.Perfect);
                EditorUtility.SetDirty(player);
            }

            GUI.backgroundColor = new Color(0.2f, 1f, 0.4f);
            if (GUILayout.Button("💚 SUPER", GUILayout.Height(30)))
            {
                player.Play(ScoringFeedbackType.Super);
                EditorUtility.SetDirty(player);
            }
            EditorGUILayout.EndHorizontal();

            EditorGUILayout.BeginHorizontal();
            GUI.backgroundColor = new Color(0.3f, 0.6f, 1f);
            if (GUILayout.Button("💙 GOOD", GUILayout.Height(26)))
            {
                player.Play(ScoringFeedbackType.Good);
                EditorUtility.SetDirty(player);
            }

            GUI.backgroundColor = new Color(1f, 0.85f, 0.2f);
            if (GUILayout.Button("💛 OK", GUILayout.Height(26)))
            {
                player.Play(ScoringFeedbackType.Ok);
                EditorUtility.SetDirty(player);
            }

            GUI.backgroundColor = new Color(1f, 0.3f, 0.3f);
            if (GUILayout.Button("❌ MISS (X)", GUILayout.Height(26)))
            {
                player.Play(ScoringFeedbackType.Miss);
                EditorUtility.SetDirty(player);
            }
            EditorGUILayout.EndHorizontal();

            EditorGUILayout.BeginHorizontal();
            GUI.backgroundColor = new Color(1f, 0.8f, 0f);
            if (GUILayout.Button("🏆 YEAH! (Gold Move)", GUILayout.Height(28)))
            {
                player.Play(ScoringFeedbackType.Yeah);
                EditorUtility.SetDirty(player);
            }

            GUI.backgroundColor = new Color(0.8f, 0.5f, 0.2f);
            if (GUILayout.Button("⚠ GOLD MISS", GUILayout.Height(28)))
            {
                player.Play(ScoringFeedbackType.GoldMiss);
                EditorUtility.SetDirty(player);
            }
            EditorGUILayout.EndHorizontal();

            GUI.backgroundColor = Color.white;
            EditorGUILayout.Space(8);

            // Timeline Scrubber
            if (player.Duration > 0f)
            {
                EditorGUILayout.LabelField($"Timeline: {player.CurrentTime:F2}s / {player.Duration:F2}s ({player.CurrentAnimationName})");
                EditorGUI.BeginChangeCheck();
                float newT = EditorGUILayout.Slider(player.CurrentTime, 0f, player.Duration);
                if (EditorGUI.EndChangeCheck())
                {
                    player.Pause();
                    player.Seek(newT);
                    EditorUtility.SetDirty(player);
                }
            }

            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button("⏹ Stop"))
            {
                player.Stop();
                EditorUtility.SetDirty(player);
            }
            if (GUILayout.Button("🔄 Recargar Clip"))
            {
                player.ReloadClipIfNeed(true);
                EditorUtility.SetDirty(player);
            }
            EditorGUILayout.EndHorizontal();
        }
    }
}
