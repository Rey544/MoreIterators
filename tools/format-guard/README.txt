This tool checks C# formatting changes. It never edits its inputs.

Build with the fixed .NET 8 SDK. Restore once to generate packages.lock.json;
subsequent restores must use --locked-mode. Roslyn is fixed to 4.11.0.
The tool itself uses .NET 8; product files are parsed as C# 5.

FormatGuard check BEFORE AFTER --output comparison.json
FormatGuard inspect ROOT --output signatures.json
FormatGuard check BEFORE AFTER --files src/CreatorAffinity.cs
FormatGuard check before.cs after.cs
FormatGuard preserve-format before.cs standard-formatter.cs output.cs
FormatGuard self-test
FormatGuard self-test-enum

Directory input selects src/*.cs and templates/standalone/*.cs when those
directories exist, otherwise top-level *.cs (for generated standalone code).
--files accepts explicit relative C# file paths. File sets must match.

The check compares token kind, exact spelling and order for every combination
of conditional symbols, up to eight symbols. This preserves strings, character
literals and using order. Comments retain their exact text, adjacent token
anchors and inline attachment. Directives retain their tokens and non-whitespace
payload. Text inactive in every combination is frozen exactly, including spaces.
Invalid syntax, #nullable and skipped/missing tokens are rejected.

The bare __ENCOUNTER__ line in CreatorRuntime.cs is temporarily parsed as the
same-length /*ENCOUNTER*/ comment. Its original identity and token anchors are
checked separately. The source file is never rewritten by this mapping.

This proves syntax-level equivalence within the selected files, not semantic
compilation or game behavior. It does not run existing functional tests.

preserve-format accepts a standard formatter's result. It only restores using
order within the same scope (conditional using groups are rejected) and removes
new trailing commas from initializers or enum declarations. The complete equivalence check must then
pass before a separate output file is written. Other changes are rejected.
Use --output for compact signature reports without dumping source text.

The tool rejects compiler language-version diagnostics as well as parse errors;
ParseText(LanguageVersion.CSharp5) alone does not reject every newer feature.
