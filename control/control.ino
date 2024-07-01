#define REV 800
int PLS[2]={8,9},DIR[2]={10,11},ENA[2]={12,13};

void setup() {
  // put your setup code here, to run once:
  pinMode(PLS[0], OUTPUT);
  pinMode(PLS[1], OUTPUT);
  pinMode(DIR[0], OUTPUT);
  pinMode(DIR[1], OUTPUT);
  pinMode(ENA[0], OUTPUT);
  pinMode(ENA[1], OUTPUT);
  Serial.begin(9600);
  digitalWrite(ENA[0],HIGH);
  digitalWrite(ENA[1],HIGH);
  digitalWrite(DIR[0],LOW);
  digitalWrite(DIR[1],LOW);
}
uint8_t t;
int m,a;
void loop() {
  // put your main code here, to run repeatedly:
  while(Serial.available()>0){t=Serial.read();}
  if (t!=0){
//    Serial.println(t);
    a=int(t);
    m=a/60;
    a=a%60;
    a=a*REV;
    if (m==2){
      digitalWrite(ENA[0],LOW);
      digitalWrite(ENA[1],LOW);
      digitalWrite(DIR[0],HIGH);
      digitalWrite(DIR[1],HIGH);
      for (int j=0;j<50;++j){
      for (int i=0;i<REV;++i){
        digitalWrite(PLS[0],HIGH);
        digitalWrite(PLS[1],HIGH);
        delay(1);
        digitalWrite(PLS[0],LOW);
        digitalWrite(PLS[1],LOW);
        delay(1);
      }}
      digitalWrite(DIR[0],LOW);
      digitalWrite(DIR[1],LOW);
      digitalWrite(ENA[0],HIGH);
      digitalWrite(ENA[1],HIGH);
    }else{
      digitalWrite(ENA[m],LOW);
      for (int i=0;i<a;++i){
        digitalWrite(PLS[m],HIGH);
        delay(1);
        digitalWrite(PLS[m],LOW);
        delay(1);
      }
      digitalWrite(DIR[m],HIGH);
      for(int i=0;i<REV*2;++i){
        digitalWrite(PLS[m],HIGH);
        delay(1);
        digitalWrite(PLS[m],LOW);
        delay(1);
      }
      digitalWrite(DIR[m],LOW);
      digitalWrite(ENA[m],HIGH);
    }
    t=0;
    Serial.println("f");
  }
}
