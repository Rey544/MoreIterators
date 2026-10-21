using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;

namespace MoreIterators
{
    // UI resources only. Author dialogue, names and machine identifiers are never translated here.
    public static class UiText
    {
        static readonly Dictionary<string, Dictionary<string, object>> resources = new Dictionary<string, Dictionary<string, object>>();
        static string locale = "zh-CN";

        public static void Use(RainWorld game)
        {
            if (game == null || game.options == null) return;
            var language = game.options.language;
            locale = language == InGameTranslator.LanguageID.Chinese || language == InGameTranslator.LanguageID.TraditionalChinese ? "zh-CN" : "en";
        }

        static Dictionary<string, object> Load(string name)
        {
            Dictionary<string, object> table;
            if (resources.TryGetValue(name, out table)) return table;
            table = new Dictionary<string, object>();
            try
            {
                using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("mi.ui." + name + ".json"))
                {
                    if (stream == null) throw new FileNotFoundException("Missing embedded UI language resource: " + name);
                    using (var reader = new StreamReader(stream))
                        table = Json.Deserialize(reader.ReadToEnd()) as Dictionary<string, object> ?? table;
                }
            }
            catch (Exception error) { MiDiagnostics.Report("MI-I18N-001", "UiText.Load", error, "locale=" + name); }
            resources[name] = table;
            return table;
        }

        public static string Get(string key)
        {
            object value;
            if (Load(locale).TryGetValue(key, out value) && value is string) return (string)value;
            // English is safe in both game font sets; a missing resource stays conspicuous.
            if (Load("en").TryGetValue(key, out value) && value is string) return (string)value;
            MiDiagnostics.Warn("MI-I18N-002", "UiText.Get", "Undefined UI key", key);
            return "[" + key + "]";
        }

        public static string Format(string key, params object[] values)
        {
            return String.Format(System.Globalization.CultureInfo.CurrentCulture, Get(key), values);
        }
    }
}
