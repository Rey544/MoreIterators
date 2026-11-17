using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.Text;

internal static class Program
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);
    private static readonly Regex PlaceholderLine = new(@"(?m)^[ \t]*(__ENCOUNTER__)[ \t]*\r?$", RegexOptions.CultureInvariant);
    private const string Placeholder = "__ENCOUNTER__";
    private const string PlaceholderComment = "/*ENCOUNTER*/";
    private const int MaximumSymbols = 8;

    private sealed record Input(string Path, string Sha256, string Text, string ParsedText, int[] Placeholders);
    private sealed record Item(string Kind, string Text);
    private sealed record Comment(string Kind, string Text, int LeftToken, int RightToken, bool InlineAfterLeft);
    private sealed record Directive(int Kind, Item[] Tokens, Item[] Payload, int LeftToken, int RightToken);
    private sealed record Inactive(string Text, int AfterDirective);
    private sealed record Branch(string[] Symbols, Item[] Tokens, Comment[] Comments, Directive[] Directives);
    private sealed record FileSignature(string Path, string Sha256, string SignatureSha256, Branch[] Branches, Inactive[] NeverActive);
    private sealed record Analysis(string Root, string[] Symbols, FileSignature[] Files);

    private static int Main(string[] args)
    {
        try
        {
            if (args.Length == 1 && args[0] == "self-test")
            {
                return SelfTest();
            }
            if (args.Length == 1 && args[0] == "self-test-enum")
            {
                return SelfTestEnum();
            }
            if (args.Length == 4 && args[0] == "preserve-format")
            {
                string original = File.ReadAllText(args[1], StrictUtf8);
                string candidate = File.ReadAllText(args[2], StrictUtf8);
                string preserved = PreserveFormat(original, candidate, System.IO.Path.GetFileName(args[1]));
                string target = System.IO.Path.GetFullPath(args[3]);
                if (target.Equals(System.IO.Path.GetFullPath(args[1]), StringComparison.OrdinalIgnoreCase)
                    || target.Equals(System.IO.Path.GetFullPath(args[2]), StringComparison.OrdinalIgnoreCase)) throw new ArgumentException("Output must differ from both input files.");
                Directory.CreateDirectory(System.IO.Path.GetDirectoryName(target)!);
                File.WriteAllText(target, preserved, new UTF8Encoding(false));
                Console.WriteLine(JsonSerializer.Serialize(new { passed = true, operation = "preserve-format", output = target, sha256 = Hash(preserved) }, JsonOptions));
                return 0;
            }
            if (args.Length < 2 || (args[0] != "check" && args[0] != "inspect"))
            {
                throw new ArgumentException("Usage: format-guard check BEFORE AFTER [--files relative.cs ...] [--output report.json] | inspect ROOT [--files relative.cs ...] [--output report.json] | preserve-format BEFORE.cs FORMATTED.cs OUTPUT.cs | self-test");
            }
            bool compare = args[0] == "check";
            int required = compare ? 3 : 2;
            if (args.Length < required) throw new ArgumentException("Missing input path.");
            string[] selected = Array.Empty<string>();
            string? output = null;
            for (int i = required; i < args.Length; i++)
            {
                if (args[i] == "--output" && i + 1 < args.Length)
                {
                    output = args[++i];
                }
                else if (args[i] == "--files")
                {
                    List<string> files = new();
                    while (i + 1 < args.Length && !args[i + 1].StartsWith("--", StringComparison.Ordinal)) files.Add(args[++i]);
                    if (files.Count == 0 || selected.Length > 0) throw new ArgumentException("Supply --files once with at least one relative path.");
                    selected = files.ToArray();
                }
                else throw new ArgumentException("Unknown or incomplete option: " + args[i]);
            }
            Analysis before = Analyze(args[1], selected);
            Analysis? after = compare ? Analyze(args[2], selected) : null;
            if (after != null) AssertEquivalent(before, after);
            var report = new
            {
                passed = true,
                operation = args[0],
                checkedUtc = DateTimeOffset.UtcNow,
                languageVersion = "CSharp5",
                roslyn = typeof(CSharpSyntaxTree).Assembly.GetName().Version?.ToString(),
                before = Summary(before),
                after = after == null ? null : Summary(after),
                scope = "Syntax tokens, literal spelling, comments with token anchors, directives and every conditional-symbol combination. No semantic compilation or functional tests."
            };
            Emit(JsonSerializer.Serialize(report, JsonOptions), output);
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(JsonSerializer.Serialize(new { passed = false, error = error.Message }, JsonOptions));
            return 1;
        }
    }

    private static void Emit(string report, string? output)
    {
        if (output != null)
        {
            string absolute = System.IO.Path.GetFullPath(output);
            Directory.CreateDirectory(System.IO.Path.GetDirectoryName(absolute)!);
            File.WriteAllText(absolute, report + Environment.NewLine, new UTF8Encoding(false));
            Console.WriteLine(absolute);
        }
        else Console.WriteLine(report);
    }

    private static string Hash(string value) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();

    private static object Summary(Analysis analysis) => new
    {
        analysis.Root,
        analysis.Symbols,
        files = analysis.Files.Select(file => new
        {
            file.Path, file.Sha256, file.SignatureSha256,
            branches = file.Branches.Select(branch => new { branch.Symbols, tokens = branch.Tokens.Length, comments = branch.Comments.Length, directives = branch.Directives.Length }),
            neverActiveBlocks = file.NeverActive.Length
        })
    };

    private static Analysis Analyze(string path, string[] selected)
    {
        string full = System.IO.Path.GetFullPath(path);
        List<Input> inputs = new();
        if (File.Exists(full))
        {
            if (selected.Length > 0 || !full.EndsWith(".cs", StringComparison.OrdinalIgnoreCase)) throw new ArgumentException("Single-file input must be a C# file without --files.");
            inputs.Add(Read(full, "input.cs"));
        }
        else
        {
            if (!Directory.Exists(full)) throw new DirectoryNotFoundException(full);
            IEnumerable<string> paths;
            if (selected.Length > 0)
            {
                paths = selected.Select(relative => ResolveFile(full, relative));
            }
            else
            {
                string main = System.IO.Path.Combine(full, "src");
                string templates = System.IO.Path.Combine(full, "templates", "standalone");
                paths = Directory.Exists(main) || Directory.Exists(templates)
                    ? new[] { main, templates }.Where(Directory.Exists).SelectMany(directory => Directory.EnumerateFiles(directory, "*.cs", SearchOption.TopDirectoryOnly))
                    : Directory.EnumerateFiles(full, "*.cs", SearchOption.TopDirectoryOnly);
            }
            foreach (string file in paths.OrderBy(value => value, StringComparer.Ordinal))
            {
                inputs.Add(Read(file, System.IO.Path.GetRelativePath(full, file).Replace('\\', '/')));
            }
        }
        if (inputs.Count == 0) throw new InvalidOperationException("No C# input files found.");
        if (inputs.Select(input => input.Path).Distinct(StringComparer.Ordinal).Count() != inputs.Count) throw new InvalidOperationException("Duplicate input file.");
        SortedSet<string> symbols = new(StringComparer.Ordinal);
        foreach (Input input in inputs)
        {
            var root = Parse(input, Array.Empty<string>()).GetRoot();
            foreach (var directive in Directives(root))
            {
                ExpressionSyntax? condition = directive switch
                {
                    IfDirectiveTriviaSyntax start => start.Condition,
                    ElifDirectiveTriviaSyntax alternative => alternative.Condition,
                    _ => null
                };
                if (condition != null)
                {
                    foreach (var name in condition.DescendantNodesAndSelf().OfType<IdentifierNameSyntax>()) symbols.Add(name.Identifier.ValueText);
                }
            }
        }
        if (symbols.Count > MaximumSymbols) throw new InvalidOperationException("Conditional symbols exceed the guarded limit of " + MaximumSymbols + "; explicit review is required.");
        string[] allSymbols = symbols.ToArray();
        string[][] combinations = Enumerable.Range(0, 1 << allSymbols.Length)
            .Select(mask => allSymbols.Where((_, bit) => (mask & (1 << bit)) != 0).ToArray()).ToArray();
        return new Analysis(full, allSymbols, inputs.Select(input => AnalyzeFile(input, combinations)).ToArray());
    }

    private static string ResolveFile(string root, string relative)
    {
        if (System.IO.Path.IsPathRooted(relative)) throw new ArgumentException("--files paths must be relative.");
        string full = System.IO.Path.GetFullPath(System.IO.Path.Combine(root, relative));
        if (!full.StartsWith(root.TrimEnd(System.IO.Path.DirectorySeparatorChar) + System.IO.Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)
            || !full.EndsWith(".cs", StringComparison.OrdinalIgnoreCase) || !File.Exists(full)) throw new ArgumentException("Invalid or missing selected C# file: " + relative);
        return full;
    }

    private static Input Read(string file, string relative)
    {
        byte[] bytes = File.ReadAllBytes(file);
        int bom = bytes.Length >= 3 && bytes[0] == 239 && bytes[1] == 187 && bytes[2] == 191 ? 3 : 0;
        string text = StrictUtf8.GetString(bytes, bom, bytes.Length - bom);
        MatchCollection matches = PlaceholderLine.Matches(text);
        int[] positions = matches.Select(match => match.Groups[1].Index).ToArray();
        if (positions.Length > 0 && (!System.IO.Path.GetFileName(file).Equals("CreatorRuntime.cs", StringComparison.Ordinal) || positions.Length != 1))
        {
            throw new InvalidOperationException(relative + ": unsupported standalone encounter placeholder.");
        }
        string parsed = text;
        foreach (int position in positions.Reverse()) parsed = parsed.Remove(position, Placeholder.Length).Insert(position, PlaceholderComment);
        return new Input(relative, Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(), text, parsed, positions);
    }

    private static SyntaxTree Parse(Input input, string[] symbols) => CSharpSyntaxTree.ParseText(
        input.ParsedText,
        new CSharpParseOptions(LanguageVersion.CSharp5, DocumentationMode.Parse, SourceCodeKind.Regular, symbols),
        input.Path,
        Encoding.UTF8);

    private static IEnumerable<DirectiveTriviaSyntax> Directives(SyntaxNode root) => root.DescendantTrivia(descendIntoTrivia: true)
        .Where(trivia => trivia.HasStructure).Select(trivia => trivia.GetStructure()).OfType<DirectiveTriviaSyntax>();

    private static FileSignature AnalyzeFile(Input input, string[][] combinations)
    {
        List<Branch> branches = new();
        List<TextSpan> neverActive = new() { new TextSpan(0, input.Text.Length) };
        DirectiveTriviaSyntax[] firstDirectives = Array.Empty<DirectiveTriviaSyntax>();
        foreach (string[] symbols in combinations)
        {
            SyntaxTree tree = Parse(input, symbols);
            SyntaxNode root = tree.GetRoot();
            Diagnostic[] errors = tree.GetDiagnostics().Where(diagnostic => diagnostic.Severity == DiagnosticSeverity.Error).ToArray();
            if (errors.Length > 0) throw new InvalidOperationException(input.Path + " [" + string.Join(",", symbols) + "]: " + string.Join("; ", errors.Take(5).Select(error => error.ToString())));
            Diagnostic[] languageErrors = CSharpCompilation.Create("FormatGuardSyntax", new[] { tree }, options: new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary))
                .GetDiagnostics().Where(diagnostic => diagnostic.Severity == DiagnosticSeverity.Error && diagnostic.Id == "CS8026").ToArray();
            if (languageErrors.Length > 0) throw new InvalidOperationException(input.Path + ": " + string.Join("; ", languageErrors.Take(5).Select(error => error.ToString())));
            SyntaxTrivia[] trivia = root.DescendantTrivia(descendIntoTrivia: true).ToArray();
            if (trivia.Any(value => value.IsKind(SyntaxKind.SkippedTokensTrivia))) throw new InvalidOperationException(input.Path + ": skipped syntax tokens are not accepted.");
            DirectiveTriviaSyntax[] directives = Directives(root).OrderBy(directive => directive.SpanStart).ToArray();
            if (directives.Any(directive => directive.IsKind(SyntaxKind.NullableDirectiveTrivia))) throw new InvalidOperationException(input.Path + ": #nullable is not allowed in the C#5 product sources.");
            if (branches.Count == 0) firstDirectives = directives;
            SyntaxToken[] tokens = root.DescendantTokens(descendIntoTrivia: false).Where(token => !token.IsKind(SyntaxKind.EndOfFileToken)).ToArray();
            if (tokens.Any(token => token.IsMissing)) throw new InvalidOperationException(input.Path + ": missing syntax token.");
            Item[] tokenItems = tokens.Select(token => new Item(token.RawKind.ToString(), token.Text)).ToArray();
            List<Comment> comments = new();
            foreach (SyntaxTrivia value in root.DescendantTrivia(descendIntoTrivia: false))
            {
                if (!IsComment(value)) continue;
                (int left, int right) = Anchor(tokens, value.Span);
                bool placeholder = input.Placeholders.Contains(value.SpanStart) && value.ToFullString() == PlaceholderComment;
                comments.Add(new Comment(placeholder ? "EncounterPlaceholder" : value.RawKind.ToString(), placeholder ? Placeholder : value.ToFullString(), left, right,
                    left >= 0 && tree.GetLineSpan(tokens[left].Span).EndLinePosition.Line == tree.GetLineSpan(value.Span).StartLinePosition.Line));
            }
            Directive[] directiveItems = directives.Select(directive =>
            {
                (int left, int right) = Anchor(tokens, directive.Span);
                return new Directive(directive.RawKind,
                    directive.DescendantTokens(descendIntoTrivia: true).Select(token => new Item(token.RawKind.ToString(), token.Text)).ToArray(),
                    directive.DescendantTrivia(descendIntoTrivia: true).Where(value => !value.IsKind(SyntaxKind.WhitespaceTrivia) && !value.IsKind(SyntaxKind.EndOfLineTrivia))
                        .Select(value => new Item(value.RawKind.ToString(), value.ToFullString())).ToArray(), left, right);
            }).ToArray();
            branches.Add(new Branch(symbols, tokenItems, comments.ToArray(), directiveItems));
            TextSpan[] disabled = trivia.Where(value => value.IsKind(SyntaxKind.DisabledTextTrivia)).Select(value => value.Span).ToArray();
            neverActive = Intersect(neverActive, disabled);
        }
        Inactive[] inactive = neverActive.Select(span => new Inactive(input.Text.Substring(span.Start, span.Length), firstDirectives.Count(directive => directive.Span.End <= span.Start) - 1)).ToArray();
        string signature = JsonSerializer.Serialize(new { branches, inactive });
        return new FileSignature(input.Path, input.Sha256, Hash(signature), branches.ToArray(), inactive);
    }

    private static bool IsComment(SyntaxTrivia value) => value.IsKind(SyntaxKind.SingleLineCommentTrivia) || value.IsKind(SyntaxKind.MultiLineCommentTrivia)
        || value.IsKind(SyntaxKind.SingleLineDocumentationCommentTrivia) || value.IsKind(SyntaxKind.MultiLineDocumentationCommentTrivia);

    private static (int Left, int Right) Anchor(SyntaxToken[] tokens, TextSpan span)
    {
        int left = -1, right = tokens.Length;
        for (int index = 0; index < tokens.Length; index++)
        {
            if (tokens[index].Span.End <= span.Start) left = index;
            if (tokens[index].Span.Start >= span.End) { right = index; break; }
        }
        return (left, right);
    }

    private static List<TextSpan> Intersect(IEnumerable<TextSpan> left, IEnumerable<TextSpan> right)
    {
        List<TextSpan> result = new();
        foreach (TextSpan a in left)
        foreach (TextSpan b in right)
        {
            int start = Math.Max(a.Start, b.Start), end = Math.Min(a.End, b.End);
            if (end > start) result.Add(TextSpan.FromBounds(start, end));
        }
        return result;
    }

    private static void AssertEquivalent(Analysis before, Analysis after)
    {
        if (!before.Symbols.SequenceEqual(after.Symbols)) throw new InvalidOperationException("Conditional symbol set changed.");
        if (!before.Files.Select(file => file.Path).SequenceEqual(after.Files.Select(file => file.Path))) throw new InvalidOperationException("C# file set changed.");
        for (int index = 0; index < before.Files.Length; index++)
        {
            FileSignature a = before.Files[index], b = after.Files[index];
            if (a.SignatureSha256 != b.SignatureSha256)
            {
                for (int branch = 0; branch < a.Branches.Length; branch++)
                {
                    string mode = " [" + string.Join(",", a.Branches[branch].Symbols) + "]";
                    if (JsonSerializer.Serialize(a.Branches[branch].Tokens) != JsonSerializer.Serialize(b.Branches[branch].Tokens)) throw new InvalidOperationException(a.Path + mode + ": token kind/text/order changed.");
                    if (JsonSerializer.Serialize(a.Branches[branch].Comments) != JsonSerializer.Serialize(b.Branches[branch].Comments)) throw new InvalidOperationException(a.Path + mode + ": comment text, placeholder or token anchor changed.");
                    if (JsonSerializer.Serialize(a.Branches[branch].Directives) != JsonSerializer.Serialize(b.Branches[branch].Directives)) throw new InvalidOperationException(a.Path + mode + ": preprocessor directive or token anchor changed.");
                }
                throw new InvalidOperationException(a.Path + ": never-active conditional text changed.");
            }
        }
    }

    private static Input MemoryInput(string text, string name)
    {
        int[] positions = PlaceholderLine.Matches(text).Select(match => match.Groups[1].Index).ToArray();
        if (positions.Length > 0 && (name != "CreatorRuntime.cs" || positions.Length != 1)) throw new InvalidOperationException("Unsupported encounter placeholder.");
        string parsed = text;
        foreach (int position in positions.Reverse()) parsed = parsed.Remove(position, Placeholder.Length).Insert(position, PlaceholderComment);
        return new Input(name, Hash(text), text, parsed, positions);
    }

    private static string[][] SymbolCombinations(Input input)
    {
        SortedSet<string> names = new(StringComparer.Ordinal);
        foreach (var directive in Directives(Parse(input, Array.Empty<string>()).GetRoot()))
        {
            ExpressionSyntax? condition = directive switch { IfDirectiveTriviaSyntax start => start.Condition, ElifDirectiveTriviaSyntax next => next.Condition, _ => null };
            if (condition != null) foreach (var name in condition.DescendantNodesAndSelf().OfType<IdentifierNameSyntax>()) names.Add(name.Identifier.ValueText);
        }
        if (names.Count > MaximumSymbols) throw new InvalidOperationException("Too many conditional symbols.");
        string[] symbols = names.ToArray();
        return Enumerable.Range(0, 1 << symbols.Length).Select(mask => symbols.Where((_, index) => (mask & (1 << index)) != 0).ToArray()).ToArray();
    }

    private static string UsingKey(UsingDirectiveSyntax node) => JsonSerializer.Serialize(node.DescendantTokens().Select(token => new Item(token.RawKind.ToString(), token.Text)));

    private static List<SyntaxList<UsingDirectiveSyntax>> UsingLists(SyntaxNode root)
    {
        List<SyntaxList<UsingDirectiveSyntax>> lists = new() { ((CompilationUnitSyntax)root).Usings };
        lists.AddRange(root.DescendantNodes().OfType<NamespaceDeclarationSyntax>().Select(space => space.Usings));
        return lists;
    }

    private static string PreserveFormat(string original, string formatted, string name)
    {
        Input input = MemoryInput(original, name);
        string[][] combinations = SymbolCombinations(input);
        FileSignature expected = AnalyzeFile(input, combinations);
        string candidate = formatted;
        foreach (string[] symbols in combinations)
        {
            SyntaxNode beforeRoot = Parse(input, symbols).GetRoot();
            Input formattedInput = MemoryInput(candidate, name);
            SyntaxNode afterRoot = Parse(formattedInput, symbols).GetRoot();
            var beforeLists = UsingLists(beforeRoot);
            var afterLists = UsingLists(afterRoot);
            if (beforeLists.Count != afterLists.Count) throw new InvalidOperationException("Namespace structure changed.");
            List<(TextSpan Span, string Text)> edits = new();
            for (int index = 0; index < beforeLists.Count; index++)
            {
                var left = beforeLists[index];
                var right = afterLists[index];
                string[] order = left.Select(UsingKey).ToArray();
                if (order.SequenceEqual(right.Select(UsingKey))) continue;
                if (left.Count != right.Count || order.Distinct().Count() != order.Length || right.Select(UsingKey).Distinct().Count() != right.Count)
                    throw new InvalidOperationException("Changed or duplicate using declarations cannot be restored automatically.");
                var byKey = right.ToDictionary(UsingKey);
                if (!order.All(byKey.ContainsKey)) throw new InvalidOperationException("Using declaration content changed.");
                TextSpan span = TextSpan.FromBounds(right.First().FullSpan.Start, right.Last().FullSpan.End);
                if (right.Any(node => node.ContainsDirectives) || left.Any(node => node.ContainsDirectives)
                    || Directives(afterRoot).Any(directive => directive.FullSpan.IntersectsWith(span))) throw new InvalidOperationException("Using order across conditional directives requires manual whitespace-only formatting.");
                edits.Add((span, string.Concat(order.Select(key => byKey[key].ToFullString()))));
            }
            foreach (var edit in edits.OrderByDescending(edit => edit.Span.Start)) candidate = candidate.Remove(edit.Span.Start, edit.Span.Length).Insert(edit.Span.Start, edit.Text);
        }
        HashSet<int> remove = new();
        Input reordered = MemoryInput(candidate, name);
        foreach (string[] symbols in combinations)
        {
            SyntaxNode a = Parse(input, symbols).GetRoot();
            SyntaxNode b = Parse(reordered, symbols).GetRoot();
            var left = a.DescendantTokens().Where(token => !token.IsKind(SyntaxKind.EndOfFileToken)).ToArray();
            var right = b.DescendantTokens().Where(token => !token.IsKind(SyntaxKind.EndOfFileToken)).ToArray();
            HashSet<int> trailing = b.DescendantNodes().OfType<InitializerExpressionSyntax>()
                .Where(initializer => initializer.Expressions.Count > 0 && initializer.Expressions.SeparatorCount == initializer.Expressions.Count)
                .Select(initializer => initializer.Expressions.GetSeparators().Last().SpanStart).ToHashSet();
            trailing.UnionWith(b.DescendantNodes().OfType<EnumDeclarationSyntax>()
                .Where(declaration => declaration.Members.Count > 0 && declaration.Members.SeparatorCount == declaration.Members.Count)
                .Select(declaration => declaration.Members.GetSeparators().Last().SpanStart));
            int x = 0, y = 0;
            while (x < left.Length || y < right.Length)
            {
                if (x < left.Length && y < right.Length && left[x].RawKind == right[y].RawKind && left[x].Text == right[y].Text) { x++; y++; continue; }
                if (y < right.Length && right[y].IsKind(SyntaxKind.CommaToken) && trailing.Contains(right[y].SpanStart)) { remove.Add(right[y].SpanStart); y++; continue; }
                throw new InvalidOperationException("Formatter changed tokens beyond using order and new initializer or enum trailing commas.");
            }
        }
        foreach (int position in remove.OrderByDescending(value => value)) candidate = candidate.Remove(position, 1);
        FileSignature actual = AnalyzeFile(MemoryInput(candidate, name), combinations);
        AssertEquivalent(new Analysis("memory-before", Array.Empty<string>(), new[] { expected }), new Analysis("memory-after", Array.Empty<string>(), new[] { actual }));
        return candidate;
    }

    private static int SelfTestEnum()
    {
        const string original = "enum Problem{\n#if PLAYBACK\nNone, Missing=1 // keep\n#else\nNone, Missing=2 // keep\n#endif\n}\n";
        const string formatted = "enum Problem\n{\n#if PLAYBACK\n    None,\n    Missing = 1, // keep\n#else\n    None,\n    Missing = 2, // keep\n#endif\n}\n";
        string preserved = PreserveFormat(original, formatted, "Sample.cs");
        if (preserved != formatted.Replace("1, // keep", "1 // keep").Replace("2, // keep", "2 // keep"))
            throw new InvalidOperationException("Self-test failed: enum trailing comma restoration.");
        Console.WriteLine(JsonSerializer.Serialize(new { passed = true, checks = 1, cases = new[] { "New enum trailing commas removed in both PLAYBACK branches with comments and all tokens preserved" }, previousSelfTestsRepeated = false, productFilesTouched = false }, JsonOptions));
        return 0;
    }

    private static int SelfTest()
    {
        string root = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "mi-format-guard-" + Guid.NewGuid().ToString("N"));
        string before = System.IO.Path.Combine(root, "before"), after = System.IO.Path.Combine(root, "after");
        Directory.CreateDirectory(before);
        Directory.CreateDirectory(after);
        List<string> passed = new();
        void Case(string name, string left, string right, bool equivalent, string filename = "Sample.cs")
        {
            foreach (string existing in Directory.EnumerateFiles(before)) File.Delete(existing);
            foreach (string existing in Directory.EnumerateFiles(after)) File.Delete(existing);
            File.WriteAllText(System.IO.Path.Combine(before, filename), left);
            File.WriteAllText(System.IO.Path.Combine(after, filename), right);
            bool accepted;
            try { AssertEquivalent(Analyze(before, Array.Empty<string>()), Analyze(after, Array.Empty<string>())); accepted = true; }
            catch (InvalidOperationException) { accepted = false; }
            if (accepted != equivalent) throw new InvalidOperationException("Self-test failed: " + name);
            passed.Add(name);
        }
        try
        {
            Case("ordinary whitespace", "class C{int x=1;}\n", "class C\n{\n    int x = 1;\n}\n", true);
            Case("using order", "using System;using System.IO;class C{}", "using System.IO;using System;class C{}", false);
            Case("literal spelling", "class C{string s=\"a\";}", "class C{string s=\"\\u0061\";}", false);
            Case("comment text", "class C{int x; // first\n}", "class C{int x; // second\n}", false);
            Case("comment anchor", "class C{int x; // keep\nint y;}", "class C{int x; int y; // keep\n}", false);
            Case("comment indentation", "class C{\n// keep\nint x;}", "class C\n{\n    // keep\n    int x;\n}", true);
            Case("PLAYBACK changed branch", "class C{\n#if PLAYBACK\nint x=1;\n#else\nint x=2;\n#endif\n}", "class C{\n#if PLAYBACK\nint x=3;\n#else\nint x=2;\n#endif\n}", false);
            Case("PLAYBACK whitespace", "class C{\n#if PLAYBACK\nint x=1;\n#else\nint x=2;\n#endif\n}", "class C\n{\n#if PLAYBACK\n    int x = 1;\n#else\n    int x = 2;\n#endif\n}\n", true);
            Case("all symbols", "class C{\n#if A && B\nint x=1;\n#else\nint x=2;\n#endif\n}", "class C{\n#if A && B\nint x=3;\n#else\nint x=2;\n#endif\n}", false);
            Case("unreachable text", "class C{\n#if false\nunknown old code\n#endif\n}", "class C{\n#if false\nunknown new code\n#endif\n}", false);
            Case("directive payload", "#region first\nclass C{}\n#endregion", "#region second\nclass C{}\n#endregion", false);
            Case("nullable rejected", "#nullable enable\nclass C{}", "#nullable enable\nclass C{}", false);
            Case("new syntax rejected", "class C{int X => 1;}", "class C{int X => 1;}", false);
            Case("invalid syntax rejected", "class C{int x=;}", "class C{int x=;}", false);
            Case("encounter placeholder", "namespace N{class C{}\n__ENCOUNTER__\n}", "namespace N\n{\n    class C { }\n    __ENCOUNTER__\n}\n", true, "CreatorRuntime.cs");
            Case("placeholder cannot become comment", "namespace N{\n__ENCOUNTER__\n}", "namespace N{\n/*ENCOUNTER*/\n}", false, "CreatorRuntime.cs");
            File.WriteAllText(System.IO.Path.Combine(after, "Extra.cs"), "class Extra{}");
            bool fileSetRejected = false;
            try { AssertEquivalent(Analyze(before, Array.Empty<string>()), Analyze(after, Array.Empty<string>())); }
            catch (InvalidOperationException) { fileSetRejected = true; }
            if (!fileSetRejected) throw new InvalidOperationException("Self-test failed: file set changed");
            passed.Add("file set changed");
            void PreserveCase(string name, string left, string right, bool accepted)
            {
                bool success;
                try { PreserveFormat(left, right, "Sample.cs"); success = true; }
                catch (InvalidOperationException) { success = false; }
                if (success != accepted) throw new InvalidOperationException("Self-test failed: " + name);
                passed.Add(name);
            }
            PreserveCase("restore using and initializer comma", "using System.IO;using System;class C{int[] a=new int[]{1,2};}", "using System;\nusing System.IO;\nclass C\n{\n    int[] a = new int[] { 1, 2, };\n}\n", true);
            PreserveCase("preserve other token changes rejected", "class C{int x=1;}", "class C { int x = 2; }", false);
            PreserveCase("preserve changed comments rejected", "using System.IO; // original\nusing System; class C{}", "using System;\nusing System.IO; // changed\nclass C{}", false);
            PreserveCase("initializer comma in PLAYBACK branch", "class C{\n#if PLAYBACK\nint[] x=new int[]{1};\n#else\nint[] x=new int[]{2};\n#endif\n}", "class C\n{\n#if PLAYBACK\nint[] x = new int[] { 1, };\n#else\nint[] x = new int[] { 2, };\n#endif\n}", true);
            PreserveCase("non initializer comma rejected", "class C{void M(){F(1);}}", "class C{void M(){F(1,);}}", false);
            Console.WriteLine(JsonSerializer.Serialize(new { passed = true, checks = passed.Count, cases = passed, productFilesTouched = false }, JsonOptions));
            return 0;
        }
        finally { Directory.Delete(root, true); }
    }
}
