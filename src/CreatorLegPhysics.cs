namespace MoreIterators {
using UnityEngine;

// A supported upper leg and a freely hanging lower leg, joined at the knee.
public sealed class CreatorLegPhysics {
 public Vector2 knee,ankle,lastKnee,lastAnkle;
 Vector2 oldHip,oldHipVelocity,oldKneeVelocity;
 float thighAngle,shinAngle,lastThighAngle,lastShinAngle,shinVelocity,fallSide=1;
 bool ready;
 static float Angle(Vector2 direction){return Mathf.Atan2(direction.x,-direction.y)*Mathf.Rad2Deg;}
 static Vector2 Direction(float angle){float a=angle*Mathf.Deg2Rad;return new Vector2(Mathf.Sin(a),-Mathf.Cos(a));}
 public Vector2 ThighDirection(float time){return Direction(Mathf.LerpAngle(lastThighAngle,thighAngle,time));}
 public Vector2 ShinDirection(float time){return Direction(Mathf.LerpAngle(lastShinAngle,shinAngle,time));}
 public void FollowParallel(CreatorLegPhysics source,Vector2 sourceHip,Vector2 hip){
  Vector2 nextKnee=hip+source.knee-sourceHip,nextAnkle=hip+source.ankle-sourceHip;
  lastKnee=ready?knee:nextKnee;lastAnkle=ready?ankle:nextAnkle;
  lastThighAngle=source.lastThighAngle;lastShinAngle=source.lastShinAngle;
  oldHipVelocity=ready?hip-oldHip:Vector2.zero;oldKneeVelocity=ready?nextKnee-knee:Vector2.zero;
  knee=nextKnee;ankle=nextAnkle;thighAngle=source.thighAngle;shinAngle=source.shinAngle;
  shinVelocity=source.shinVelocity;fallSide=source.fallSide;oldHip=hip;ready=true;
 }
 public void Step(Vector2 hip,Vector2 down,Vector2 nativeFoot,float thigh,float shin,float elasticity,float gravity){
  thigh=Mathf.Max(1,thigh);shin=Mathf.Max(1,shin);elasticity=Mathf.Clamp01(elasticity);gravity=Mathf.Max(0,gravity);
  if(down.sqrMagnitude<.001f)down=Vector2.down;else down.Normalize();
  float bodyAngle=Angle(down),sine=Mathf.Sin(bodyAngle*Mathf.Deg2Rad);
  // Keep the same falling side through upside-down. Symmetry shares directions.
  if(Mathf.Abs(sine)>.35f)fallSide=-Mathf.Sign(sine);
  if(!ready||Vector2.Distance(hip,oldHip)>100){
   thighAngle=lastThighAngle=bodyAngle;shinAngle=lastShinAngle=gravity>.001f?0:bodyAngle;
   knee=lastKnee=hip+down*thigh;ankle=lastAnkle=knee+Direction(shinAngle)*shin;
   oldHip=hip;oldHipVelocity=oldKneeVelocity=Vector2.zero;shinVelocity=0;ready=true;
  }
  lastKnee=knee;lastAnkle=ankle;lastThighAngle=thighAngle;lastShinAngle=shinAngle;
  Vector2 velocity=hip-oldHip,acceleration=Vector2.ClampMagnitude(velocity-oldHipVelocity,5);
  oldHip=hip;oldHipVelocity=velocity;
  Vector2 tangent=new Vector2(-down.y,down.x);
  float weight=1-Mathf.Exp(-gravity*8),inversion=(1-Vector2.Dot(down,Vector2.down))*.5f;
  float cone=Mathf.Lerp(12,24,elasticity);
  float gravityLean=fallSide*cone*inversion*weight;
  float inertia=Mathf.Clamp(-Vector2.Dot(acceleration,tangent)*1.4f,-6,6);
  thighAngle=Mathf.LerpAngle(thighAngle,bodyAngle+gravityLean+inertia,Mathf.Lerp(.4f,.25f,elasticity));
  knee=hip+Direction(thighAngle)*thigh;
  Vector2 kneeVelocity=knee-lastKnee,kneeAcceleration=Vector2.ClampMagnitude(kneeVelocity-oldKneeVelocity,6);oldKneeVelocity=kneeVelocity;
  float angle=shinAngle*Mathf.Deg2Rad;
  Vector2 shinTangent=new Vector2(Mathf.Cos(angle),Mathf.Sin(angle));
  float torque=(-Mathf.Sin(angle)*gravity*1.15f-Vector2.Dot(kneeAcceleration,shinTangent)*.35f)/shin*Mathf.Rad2Deg;
  // No body-facing spring or angular stop in gravity: the shin can hang towards
  // the floor even when the thigh is upside down. Zero gravity retains inertia.
  if(gravity<.001f)torque+=Mathf.DeltaAngle(shinAngle,thighAngle)*Mathf.Lerp(.025f,.006f,elasticity);
  shinVelocity=shinVelocity*Mathf.Lerp(.87f,.972f,elasticity)+torque;
  shinAngle=Mathf.DeltaAngle(0,shinAngle+shinVelocity);
  ankle=knee+Direction(shinAngle)*shin;
 }
}
}

