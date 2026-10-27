using System;
using System.IO;
using System.Collections.Generic;
using UnityEngine;

namespace LiamFX
{
    public enum ScoringFeedbackType
    {
        Perfect,
        Super,
        Good,
        Ok,
        Miss,      // Bad / X
        Yeah,      // Gold Move
        GoldMiss   // Gold Miss
    }

    [Serializable]
    public class AttachmentDef
    {
        public int slot;
        public string name;
        public string region;
        public int page;
        public int nv;
        public Vector2[] uvs;
        public int[] tris;
    }

    [Serializable]
    public class SlotDef
    {
        public string name;
        public bool isAdditive;
        public string bone;
    }

    public class FrameData
    {
        public float time;
        public int attachmentIndex; // -1 if hidden
        public Color color;
        public Vector2[] vertices;  // in local units
    }

    public class TrackData
    {
        public int slot;
        public bool isAdditive;
        public List<FrameData> frames = new List<FrameData>();
    }

    public class AnimationData
    {
        public string name;
        public float duration;
        public List<TrackData> tracks = new List<TrackData>();
    }

    public class ScoringFXClip
    {
        public string name;
        public float fps = 60f;
        public List<string> pageFiles = new List<string>();
        public List<SlotDef> slots = new List<SlotDef>();
        public List<AttachmentDef> attachments = new List<AttachmentDef>();
        public Dictionary<string, AnimationData> animations = new Dictionary<string, AnimationData>(StringComparer.OrdinalIgnoreCase);

        public bool TryGetAnimation(string animName, out AnimationData anim)
        {
            return animations.TryGetValue(animName, out anim);
        }

        public string ResolveFeedbackName(ScoringFeedbackType type)
        {
            switch (type)
            {
                case ScoringFeedbackType.Perfect:
                    return animations.ContainsKey("Perfect") ? "Perfect" : "PERFECT";
                case ScoringFeedbackType.Super:
                    return animations.ContainsKey("Super") ? "Super" : "SUPER";
                case ScoringFeedbackType.Good:
                    return animations.ContainsKey("Good") ? "Good" : "GOOD";
                case ScoringFeedbackType.Ok:
                    return animations.ContainsKey("Ok") ? "Ok" : "OK";
                case ScoringFeedbackType.Miss:
                    if (animations.ContainsKey("Bad")) return "Bad";
                    if (animations.ContainsKey("Miss")) return "Miss";
                    return "MISS";
                case ScoringFeedbackType.Yeah:
                    if (animations.ContainsKey("Gold")) return "Gold";
                    if (animations.ContainsKey("Yeah")) return "Yeah";
                    return "YEAH";
                case ScoringFeedbackType.GoldMiss:
                    if (animations.ContainsKey("GoldMiss")) return "GoldMiss";
                    return "GOLDMISS";
                default:
                    return "Perfect";
            }
        }
    }

    /// <summary>
    /// Parser ligero y sin dependencias para archivos .lfx.json de LiamFX
    /// </summary>
    public static class LiamFXParser
    {
        public static ScoringFXClip Parse(string jsonText)
        {
            if (string.IsNullOrEmpty(jsonText)) return null;

            object parsed = MiniJson.Deserialize(jsonText);
            if (!(parsed is Dictionary<string, object> root)) return null;

            var clip = new ScoringFXClip();
            clip.name = root.ContainsKey("name") ? root["name"] as string : "ScoringFX";
            if (root.ContainsKey("fps")) clip.fps = Convert.ToSingle(root["fps"]);

            // 1. Pages
            if (root.ContainsKey("pages") && root["pages"] is List<object> pagesList)
            {
                foreach (var item in pagesList)
                {
                    if (item is Dictionary<string, object> pageDict && pageDict.ContainsKey("file"))
                    {
                        clip.pageFiles.Add(pageDict["file"] as string);
                    }
                }
            }

            // 2. Slots
            if (root.ContainsKey("slots") && root["slots"] is List<object> slotsList)
            {
                foreach (var item in slotsList)
                {
                    if (item is Dictionary<string, object> slotDict)
                    {
                        var s = new SlotDef();
                        s.name = slotDict.ContainsKey("name") ? slotDict["name"] as string : "";
                        s.bone = slotDict.ContainsKey("bone") ? slotDict["bone"] as string : "";
                        string blend = slotDict.ContainsKey("blend") ? slotDict["blend"] as string : "normal";
                        s.isAdditive = string.Equals(blend, "additive", StringComparison.OrdinalIgnoreCase);
                        clip.slots.Add(s);
                    }
                }
            }

            // 3. Attachments
            if (root.ContainsKey("attachments") && root["attachments"] is List<object> attsList)
            {
                foreach (var item in attsList)
                {
                    if (item is Dictionary<string, object> ad)
                    {
                        var att = new AttachmentDef();
                        att.slot = ad.ContainsKey("slot") ? Convert.ToInt32(ad["slot"]) : 0;
                        att.name = ad.ContainsKey("name") ? ad["name"] as string : "";
                        att.region = ad.ContainsKey("region") ? ad["region"] as string : "";
                        att.page = ad.ContainsKey("page") ? Convert.ToInt32(ad["page"]) : 0;
                        att.nv = ad.ContainsKey("nv") ? Convert.ToInt32(ad["nv"]) : 4;

                        if (ad.ContainsKey("uvs") && ad["uvs"] is List<object> uvsList)
                        {
                            int count = uvsList.Count / 2;
                            att.uvs = new Vector2[count];
                            for (int i = 0; i < count; i++)
                            {
                                float u = Convert.ToSingle(uvsList[i * 2]);
                                float v = 1.0f - Convert.ToSingle(uvsList[i * 2 + 1]); // Flip Y para coordenadas de textura en Unity
                                att.uvs[i] = new Vector2(u, v);
                            }
                        }

                        if (ad.ContainsKey("tris") && ad["tris"] is List<object> trisList)
                        {
                            att.tris = new int[trisList.Count];
                            for (int i = 0; i < trisList.Count; i++)
                            {
                                att.tris[i] = Convert.ToInt32(trisList[i]);
                            }
                        }

                        clip.attachments.Add(att);
                    }
                }
            }

            // 4. Animations
            if (root.ContainsKey("animations") && root["animations"] is Dictionary<string, object> animsDict)
            {
                foreach (var kvp in animsDict)
                {
                    string animName = kvp.Key;
                    if (!(kvp.Value is Dictionary<string, object> animDict)) continue;

                    var anim = new AnimationData();
                    anim.name = animName;
                    anim.duration = animDict.ContainsKey("duration") ? Convert.ToSingle(animDict["duration"]) : 0.5f;

                    if (animDict.ContainsKey("tracks") && animDict["tracks"] is List<object> tracksList)
                    {
                        foreach (var trackObj in tracksList)
                        {
                            if (!(trackObj is Dictionary<string, object> td)) continue;

                            var track = new TrackData();
                            track.slot = td.ContainsKey("slot") ? Convert.ToInt32(td["slot"]) : 0;
                            if (track.slot >= 0 && track.slot < clip.slots.Count)
                                track.isAdditive = clip.slots[track.slot].isAdditive;

                            if (td.ContainsKey("frames") && td["frames"] is List<object> framesList)
                            {
                                foreach (var frameObj in framesList)
                                {
                                    if (!(frameObj is List<object> fl) || fl.Count < 2) continue;

                                    var frame = new FrameData();
                                    frame.time = Convert.ToSingle(fl[0]);
                                    frame.attachmentIndex = Convert.ToInt32(fl[1]);

                                    if (frame.attachmentIndex >= 0 && fl.Count >= 6)
                                    {
                                        float r = Convert.ToSingle(fl[2]);
                                        float g = Convert.ToSingle(fl[3]);
                                        float b = Convert.ToSingle(fl[4]);
                                        float a = Convert.ToSingle(fl[5]);
                                        frame.color = new Color(r, g, b, a);

                                        int vertCoordCount = fl.Count - 6;
                                        int vertCount = vertCoordCount / 2;
                                        frame.vertices = new Vector2[vertCount];
                                        for (int vi = 0; vi < vertCount; vi++)
                                        {
                                            float vx = Convert.ToSingle(fl[6 + vi * 2]);
                                            float vy = Convert.ToSingle(fl[7 + vi * 2]);
                                            frame.vertices[vi] = new Vector2(vx, vy);
                                        }
                                    }

                                    track.frames.Add(frame);
                                }
                            }

                            anim.tracks.Add(track);
                        }
                    }

                    clip.animations[animName] = anim;
                }
            }

            return clip;
        }
    }

    /// <summary>
    /// MiniJSON embebido de alto rendimiento para Unity
    /// </summary>
    public static class MiniJson
    {
        public static object Deserialize(string json)
        {
            if (json == null) return null;
            return Parser.Parse(json);
        }

        sealed class Parser : IDisposable
        {
            const string WHITE_SPACE = " \t\n\r";
            const string WORD_BREAK = " \t\n\r{}[],:\"";

            StringReader json;

            Parser(string jsonString)
            {
                json = new StringReader(jsonString);
            }

            public static object Parse(string jsonString)
            {
                using (var instance = new Parser(jsonString))
                {
                    return instance.ParseValue();
                }
            }

            public void Dispose()
            {
                json.Dispose();
                json = null;
            }

            Dictionary<string, object> ParseObject()
            {
                var table = new Dictionary<string, object>();
                json.Read(); // descartar '{'

                while (true)
                {
                    switch (NextToken)
                    {
                        case TOKEN.NONE:
                            return null;
                        case TOKEN.COMMA:
                            continue;
                        case TOKEN.CURLY_CLOSE:
                            return table;
                        default:
                            string name = ParseString();
                            if (name == null) return null;
                            if (NextToken != TOKEN.COLON) return null;
                            json.Read(); // descartar ':'
                            table[name] = ParseValue();
                            break;
                    }
                }
            }

            List<object> ParseArray()
            {
                var array = new List<object>();
                json.Read(); // descartar '['

                var parsing = true;
                while (parsing)
                {
                    TOKEN nextToken = NextToken;
                    switch (nextToken)
                    {
                        case TOKEN.NONE:
                            return null;
                        case TOKEN.COMMA:
                            continue;
                        case TOKEN.SQUARED_CLOSE:
                            parsing = false;
                            break;
                        default:
                            object val = ParseByToken(nextToken);
                            array.Add(val);
                            break;
                    }
                }

                return array;
            }

            object ParseValue()
            {
                TOKEN nextToken = NextToken;
                return ParseByToken(nextToken);
            }

            object ParseByToken(TOKEN token)
            {
                switch (token)
                {
                    case TOKEN.STRING:
                        return ParseString();
                    case TOKEN.NUMBER:
                        return ParseNumber();
                    case TOKEN.CURLY_OPEN:
                        return ParseObject();
                    case TOKEN.SQUARED_OPEN:
                        return ParseArray();
                    case TOKEN.TRUE:
                        return true;
                    case TOKEN.FALSE:
                        return false;
                    case TOKEN.NULL:
                        return null;
                    default:
                        return null;
                }
            }

            string ParseString()
            {
                var s = new System.Text.StringBuilder();
                json.Read(); // descartar '"'

                bool parsing = true;
                while (parsing)
                {
                    if (json.Peek() == -1) break;

                    char c = NextChar;
                    switch (c)
                    {
                        case '"':
                            parsing = false;
                            break;
                        case '\\':
                            if (json.Peek() == -1) { parsing = false; break; }
                            c = NextChar;
                            switch (c)
                            {
                                case '"':
                                case '\\':
                                case '/':
                                    s.Append(c);
                                    break;
                                case 'b': s.Append('\b'); break;
                                case 'f': s.Append('\f'); break;
                                case 'n': s.Append('\n'); break;
                                case 'r': s.Append('\r'); break;
                                case 't': s.Append('\t'); break;
                                case 'u':
                                    var hex = new char[4];
                                    for (int i = 0; i < 4; i++) hex[i] = NextChar;
                                    s.Append((char)Convert.ToInt32(new string(hex), 16));
                                    break;
                            }
                            break;
                        default:
                            s.Append(c);
                            break;
                    }
                }

                return s.ToString();
            }

            object ParseNumber()
            {
                string number = NextWord;
                if (number.IndexOf('.') == -1)
                {
                    long parsedInt;
                    long.TryParse(number, System.Globalization.NumberStyles.Any, System.Globalization.CultureInfo.InvariantCulture, out parsedInt);
                    return parsedInt;
                }

                double parsedDouble;
                double.TryParse(number, System.Globalization.NumberStyles.Any, System.Globalization.CultureInfo.InvariantCulture, out parsedDouble);
                return parsedDouble;
            }

            void EatWhitespace()
            {
                while (WHITE_SPACE.IndexOf(PeekChar) != -1)
                {
                    json.Read();
                    if (json.Peek() == -1) break;
                }
            }

            char PeekChar => Convert.ToChar(json.Peek());
            char NextChar => Convert.ToChar(json.Read());

            string NextWord
            {
                get
                {
                    var word = new System.Text.StringBuilder();
                    while (WORD_BREAK.IndexOf(PeekChar) == -1)
                    {
                        word.Append(NextChar);
                        if (json.Peek() == -1) break;
                    }
                    return word.ToString();
                }
            }

            TOKEN NextToken
            {
                get
                {
                    EatWhitespace();
                    if (json.Peek() == -1) return TOKEN.NONE;

                    switch (PeekChar)
                    {
                        case '{': return TOKEN.CURLY_OPEN;
                        case '}': json.Read(); return TOKEN.CURLY_CLOSE;
                        case '[': return TOKEN.SQUARED_OPEN;
                        case ']': json.Read(); return TOKEN.SQUARED_CLOSE;
                        case ',': json.Read(); return TOKEN.COMMA;
                        case '"': return TOKEN.STRING;
                        case ':': return TOKEN.COLON;
                        case '0':
                        case '1':
                        case '2':
                        case '3':
                        case '4':
                        case '5':
                        case '6':
                        case '7':
                        case '8':
                        case '9':
                        case '-': return TOKEN.NUMBER;
                    }

                    switch (NextWord)
                    {
                        case "false": return TOKEN.FALSE;
                        case "true": return TOKEN.TRUE;
                        case "null": return TOKEN.NULL;
                    }

                    return TOKEN.NONE;
                }
            }

            enum TOKEN
            {
                NONE,
                CURLY_OPEN,
                CURLY_CLOSE,
                SQUARED_OPEN,
                SQUARED_CLOSE,
                COLON,
                COMMA,
                STRING,
                NUMBER,
                TRUE,
                FALSE,
                NULL
            }
        }
    }
}
