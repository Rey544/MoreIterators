using System;
using System.Collections.Generic;
using System.IO;

 
 
public sealed class InGameTranslator
{
    public enum LanguageID { English, Chinese, TraditionalChinese, French }
    readonly RainWorld game;
    readonly Dictionary<string, Dictionary<string, string>> tables = new Dictionary<string, Dictionary<string, string>>();
    public InGameTranslator(RainWorld game) { this.game = game; }
    public LanguageID currentLanguage { get { return game.options.language; } }

    Dictionary<string, string> Load(string language)
    {
        Dictionary<string, string> table;
        if (tables.TryGetValue(language, out table)) return table;
        table = new Dictionary<string, string>();
        string root = Environment.GetEnvironmentVariable("MI_TEST_NATIVE_TEXT_ROOT");
        string path = Path.Combine(root, "text_" + language, "strings.txt");
        if (File.Exists(path))
        {
            foreach (string line in File.ReadAllLines(path))
            {
                int split = line.IndexOf('|');
                if (split > 0) table[line.Substring(0, split)] = line.Substring(split + 1);
            }
        }
        tables[language] = table;
        return table;
    }

    public string Translate(string key)
    {
        var language = game.options.language;
        string name = language == LanguageID.Chinese ? "chi" : language == LanguageID.TraditionalChinese ? "tra" : language == LanguageID.French ? "fre" : "eng";
        string value;
        if (Load(name).TryGetValue(key, out value)) return value;
        return Load("eng").TryGetValue(key, out value) ? value : key;
    }
}
