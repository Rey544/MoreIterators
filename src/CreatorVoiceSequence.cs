namespace MoreIterators {
using System;
using System.Collections.Generic;
using System.Text;

internal sealed class CreatorVoiceNote {public int start,ticks,sample;public float pitch,offset;}
internal sealed class CreatorVoiceSequence {
 public readonly List<CreatorVoiceNote> notes=new List<CreatorVoiceNote>();public int ticks;
 sealed class Generator {uint state;public Generator(uint seed){state=seed==0?1:seed;}public int Next(int max){state^=state<<13;state^=state>>17;state^=state<<5;return (int)(state%(uint)max);}public bool Chance(double value){return Next(10000)<Math.Floor(value*10000+.5);}}
 static uint Hash(string text){uint n=2166136261;foreach(char c in text){n^=c;n=unchecked(n*16777619);}return n;}
 public static CreatorVoiceSequence Make(string text,CreatorVoiceDesign s){
  var result=new CreatorVoiceSequence();double speed=Math.Round(s.speed,5),basePitch=Math.Round(s.pitch,5),chaos=Math.Round(s.chaos,5);text=text??"";if(text.Length>600)text=text.Substring(0,600);
  var clean=new StringBuilder();foreach(char c in text)if(c>32)clean.Append(c);if(clean.Length==0)return result;
  var random=new Generator(Hash(text));var units=new List<string>();string body=clean.ToString();
  for(int i=0;i<body.Length;i+=3)units.Add(body.Substring(i,Math.Min(3,body.Length-i)));
  if(s.reverse&&chaos>0&&random.Chance(chaos))units.Reverse();
  var chunks=new List<string>();foreach(string unit in units){
   bool split=s.split&&chaos>0&&random.Chance(chaos*.65);
   for(int i=0;i<(split?unit.Length:1);i++){string part=split?unit.Substring(i,1):unit;chunks.Add(part);if(s.repeat&&chaos>0&&random.Chance(chaos*.45))chunks.Add(part);}
  }
  result.ticks=Math.Max(6,Math.Min(480,(int)Math.Ceiling(text.Length*2.8/speed)));int tick=0,index=0,previous=-1;string previousUnit=null;
  while(tick<result.ticks&&result.notes.Count<96){
   string unit=chunks[index++%chunks.Count];int sum=s.shortWeight+s.mediumWeight+s.longWeight,choice=sum>0?random.Next(sum):0;
   int low,range;if(sum==0||choice<s.shortWeight){low=5;range=5;}else if(choice<s.shortWeight+s.mediumWeight){low=11;range=10;}else{low=22;range=17;}
   int length=Math.Min(result.ticks-tick,Math.Max(3,(int)Math.Floor((low+random.Next(range))/speed+.5)));
   int sample=(int)(Hash(unit)%5);if(sample==previous&&unit!=previousUnit)sample=(sample+1+random.Next(4))%5;previous=sample;previousUnit=unit;
   float pitch=(float)Math.Max(.2,Math.Min(3,basePitch*(1+(chaos>0?(random.Next(2001)-1000)/1000.0*.18*chaos:0))));
   float offset=.3f+((Hash(unit)>>8)%600)/1000f;
   result.notes.Add(new CreatorVoiceNote{start=tick,ticks=length,sample=sample,pitch=pitch,offset=offset});tick+=length+Math.Max(1,(int)Math.Floor((3+random.Next(6))/speed+.5));
  }
  return result;
 }
}
}
