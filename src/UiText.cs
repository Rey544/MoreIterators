using System;

namespace MoreIterators
{
    // UI and built-in fallbacks only. Authored names and dialogue stay literal.
    public static class UiText
    {
        static RainWorld current;

        public static void Use(RainWorld game)
        {
            if (game != null) current = game;
        }

        public static string LanguageKey
        {
            get
            {
                RainWorld game = current != null ? current : RWCustom.Custom.rainWorld;
                return game != null && game.inGameTranslator != null
                    ? game.inGameTranslator.currentLanguage.ToString() : "English";
            }
        }

        public static string Get(string original)
        {
            if (String.IsNullOrEmpty(original)) return original ?? "";
            try
            {
                RainWorld game = current != null ? current : RWCustom.Custom.rainWorld;
                if (game != null && game.inGameTranslator != null)
                {
                    string translated = game.inGameTranslator.Translate(original);
                    if (!String.IsNullOrEmpty(translated) && translated != "!NO TRANSLATION!")
                        return Display(translated);
                }
            }
            catch (Exception error) { MiDiagnostics.Report("MI-I18N-003", "UiText.Get", error, "original=" + original); }
            return Display(original);
        }

        static string Display(string value)
        {
            return value.Replace("<LINE>", "\n").Replace("<WWLINE>", "");
        }

        public static string Format(string original, params object[] values)
        {
            try { return String.Format(System.Globalization.CultureInfo.CurrentCulture, Get(original), values); }
            catch (FormatException error)
            {
                MiDiagnostics.Report("MI-I18N-004", "UiText.Format", error, "original=" + original);
                return String.Format(System.Globalization.CultureInfo.CurrentCulture, Display(original), values);
            }
        }
    }
}
