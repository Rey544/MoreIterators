
import re

def with_dialogue_line(root,fixture):
    source=(root/'src/CreatorDialogue.cs').read_text('utf-8-sig')
    begin=source.index('[Serializable] public sealed class CreatorDialogueLine {')
    end=source.index('\npublic sealed class CreatorDialogueProfile',begin)
    production=source[begin:end]
    result,count=re.subn(r'public (?:sealed )?class CreatorDialogueLine\s*\{\s*public string text;\s*\}',lambda _:production,fixture)
    if count!=1:raise AssertionError('Expected exactly one dialogue-line host stub')
    return result
