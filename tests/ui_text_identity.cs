namespace MoreIterators {
 public static class UiText {
  public static string LanguageKey{get{return "English";}}
  public static string Get(string original){return original;}
  public static string Format(string original,params object[] values){return System.String.Format(original,values);}
 }
}
