using System;
using System.Collections.Generic;

public static class MediaBackgroundInstallCheck
{
    static int checks;
    static void Check(bool value,string reason){checks++;if(!value)throw new Exception(reason);}
    static int Hooks(){var value=(Delegate)typeof(On.BackgroundScene).GetField("RoomToWorldPos",System.Reflection.BindingFlags.Static|System.Reflection.BindingFlags.NonPublic).GetValue(null);return value==null?0:value.GetInvocationList().Length;}
    public static int Main(string[] args)
    {
        try
        {
            AssetManager.root=args[0];var first=new List<Action>();var second=new List<Action>();
            MoreIterators.CreatorBackgroundCoordinates.Install(first);MoreIterators.CreatorBackgroundCoordinates.Install(first);MoreIterators.CreatorBackgroundCoordinates.Install(second);
            Check(Hooks()==1,"duplicate installs attach one hook");Check(first.Count==1&&second.Count==0,"duplicate install adds no mismatched cleanup owner");
            first[0]();Check(Hooks()==0,"owned cleanup removes hook");
            MoreIterators.CreatorBackgroundCoordinates.Install(second);Check(Hooks()==1,"reinstall after cleanup succeeds");first[0]();Check(Hooks()==1,"old cleanup callback cannot remove new subscription");
            second[0]();second[0]();Check(Hooks()==0,"repeat current cleanup is harmless");
            bool rejected=false;try{MoreIterators.CreatorBackgroundCoordinates.Install(null);}catch(ArgumentNullException){rejected=true;}
            Check(rejected&&Hooks()==0,"invalid cleanup owner never leaves an untracked hook");
            Console.WriteLine("media background checks passed: "+checks);return 0;
        }
        catch(Exception error){Console.Error.WriteLine(error);return 1;}
    }
}
