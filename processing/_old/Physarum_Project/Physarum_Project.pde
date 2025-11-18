 //<>// //<>// //<>//
PrintWriter outputFile,outputFileData;
BufferedReader inputFileData;
import processing.serial.*;
import controlP5.*;
ControlP5 cp5;
PImage saveButton,recordButton,okButton,allOkButton,voltsButton,startButton,snapshotButton,exitButton;
 
//final ThirdApplet  ta = new ThirdApplet();

int N=1024;  //PREDEFINED VALUE// Sample count need to be multiple of 2. (2,4,8,16,32,64,128,256,512,1024,2048,4096,8192...)
int ND2 = N/2; // Sample count half
int viewHertzSize=1024;
BenFFT CurveA = new BenFFT(N);  //Create FFT object with N samples

float f,oneSample,temp,twoSample,sliderValue,newVal,startTime,elapsed,elapsedTime,fs,twoSampleView,orderOfMagnitude,initialHertz,prevY, percentageTime,percentageWindow;
float hertz,prevHertz;
color c=color(255,0,0);
int PeriodeTime = 1000;
int Signal = 1,counterSamples;
int secBegin,secEnd,minBegin,minEnd,secDifference,minDifference,duration,sampleRate,kappa=0,sliderRange=3000,iteration=0,hertzCounter=0;
int sizePresentationArray=1024,counterLines=0,twoSampleCounter=0,timeHertz=1000,timeHertzNext;

boolean begin=false,beginTime=false,toggleValue,toggleValueRecorded,flagRemoveSave=false,flagRecord=false, flagSecondOrder=false, flagFirstOrder=true,flagSaveVolts=false,flagThirdOrder=false,flagHertz=false;
String finalPath,finalPathVoltage,finalPathInputVoltage,samples,durationVal,captureImgName,stringHour,stringMin,stringSec,stringDay,stringMonth,stringYear,finalFileName,samplesPerSecond;
String [] captureImgPath;
String [] folderNameTemp;
String [] folderName;
String [] lines;
  float [] hertzArray =new float[viewHertzSize];
float [] hertzTimeArray;

 
Serial myPort;
String val=" ";
String preVal=" ";
String[] temporal;



//void settings(){
//  size(400,250);
//  frame.setLocation(2200,200);
//}

void setup() {
  size(400, 250);
  frame.setLocation(2200,200);
   surface.setResizable(true);
 
  textSize(13);
  hertzTimeArray=new float [500];
  
  saveButton=loadImage("save.png");
  recordButton=loadImage("record.png");
  okButton=loadImage("ok.jpg");
  // final String[] switches = { "--sketch-path=" + sketchPath(), "" };
  // runSketch(switches, ta);
  voltsButton=loadImage("volts.png");
  startButton=loadImage("start.png");
  snapshotButton=loadImage("snapshot.png");
  exitButton=loadImage("exit.png");
  /* CREATE THE TEXTBOX */
  cp5=new ControlP5(this);
 
  
 // cp5.addTextfield("Give the filename").setPosition(20,100).setSize(200,40).setAutoClear(false);
 
 
  cp5.addToggle("toggleValueRecorded").setPosition(20,60).setSize(80,20).setCaptionLabel("Read Recorded \n Measurements from \n saved file or\n shared database").setColorBackground(color(255,30,0)).setColorActive(color(0,180,0))
   .setColorForeground(color(255,255,0)) .setMode(ControlP5.DEFAULT);
   
  cp5.addToggle("toggleValue").setPosition(150,60).setSize(80,20).setCaptionLabel("Record New \n Measurement Data").setColorBackground(color(255,30,0)).setColorActive(color(0,180,0)).setColorForeground(color(255,255,0))
  .setMode(ControlP5.DEFAULT);
  
  cp5.addToggle("toggleValueNoUse").setPosition(280,60).setSize(80,20).setCaptionLabel("Just produce the FFT").setColorBackground(color(255,30,0)).setColorActive(color(0,180,0)).setColorForeground(color(255,255,0))
  .setMode(ControlP5.DEFAULT);
  cp5.addSlider("slider").setPosition(150,140).setSize(100,20).setMin(10).setMax(1000).setDefaultValue(500).setNumberOfTickMarks(3)
      .setSliderMode(Slider.FLEXIBLE).setCaptionLabel("Select the voltage's order of magnitude");
  cp5.getController("slider").getCaptionLabel().align(ControlP5.CENTER, ControlP5.TOP_OUTSIDE).setPaddingX(0);
  cp5.addBang("OK").setPosition(170,190).setSize(50,50).setImage(okButton);

  /* CREATE THE SLIDER */
 // cp5.addSlider("Time of experiment").setPosition(20,150).setSize(800,20).setRange(0,sliderRange).setValue(10.0);

}

void draw() {
  

  if(begin==false)
  {
    initialPresentation();
    startTime=millis();
   
  //  println(startTime);
  }
  
  if(begin==true)
  {
    elapsedTime=millis()-startTime;
   
    smooth();
    noFill();
    // Make some live data 
    if(toggleValueRecorded==false)
    {
    if(myPort.available()>0)
    {
      val=myPort.readStringUntil('\n');
    }
   // println(val);
   if(val!=null)
   {
     if(!val.equals(preVal))
     {
       if(orderOfMagnitude==10.0)
       {
         preVal=val;
         newVal=float(val);
         twoSampleView=newVal;
         newVal=(newVal/10)/4-1;
       }
       else if(orderOfMagnitude==505.0)
       {
         preVal=val;
         newVal=float(val);
         twoSampleView=newVal;
         newVal=(newVal/100)/2-1;
       }
       else
       {
         preVal=val;
         newVal=float(val);
         twoSampleView=newVal;
         newVal=(newVal/1000)-1;
       }
     }
     counterSamples++;
      twoSample=newVal;
   }
    }
    else
    {
      if(counterLines<lines.length)
      {
        if(orderOfMagnitude==10.0)
       {
         twoSample=float(lines[counterLines]);
         twoSampleView=(twoSample*10)*4+40;
         counterLines++;
       }
       else if(orderOfMagnitude==505.0)
       {
         twoSample=float(lines[counterLines]);
         twoSampleView=(twoSample*100)*2+200;
         counterLines++;
       }
       else
       {
         twoSample=float(lines[counterLines]);
         twoSampleView=(twoSample*1000)+1000;
         counterLines++;
       }
      /*  twoSample=float(lines[counterLines]);
        newVal=twoSample;
        counterLines++;*/
        counterSamples++;
      }
      else
      {
        //outputFile.close();
        exit();
      }
    }
   
    //take the Sample
    CurveA.oneSample(twoSample);
   
   //println(counterSamples);
    // The CurveA.XOut is an array with N/2 point
    if(counterSamples>=N)
    {
    CurveA.fft();
    hertz=CurveA.ToppF()*fs/N;
    if(frameCount %100==0)
    {
      CurveA.sendHertz(hertz);
    }
    }
    //Frequency_of_Peak = Data_Sample_Rate * Bin_number_of_Peak / Length_of_FFT ;
    //println(CurveA.ToppF()*64.0/N+" Hz");
    
    // draw CurveA.XR - the innput data array and CurveA.XOut - the output data array
    drawPresentation(CurveA.XR,CurveA.XOut);

    //Send FFT data to database
   createDatabase(CurveA.XOut,twoSample);
    secEnd=second();
    minEnd=minute();
    secDifference=secEnd-secBegin;
    minDifference=minEnd-minBegin;
    duration=minDifference*60+secDifference;
    if(duration>=sliderValue*60)
    {
      noLoop();
      exit();
      outputFile.close();
      outputFileData.close();
      
    }
    twoSampleCounter++;

  }
   //delay(20);
}
 
 
 void fileSelected(File selection) {
  if (selection == null) {
    println("Window was closed or the user hit cancel.");
  } else {
    println("User selected " + selection.getAbsolutePath());
    finalPath=selection.getAbsolutePath();
    outputFile=createWriter(finalPath);
    cp5.remove("Save_Database_FFT");
    flagRemoveSave=false;
    
    if(toggleValue==true && toggleValueRecorded==false)
   {
     cp5.addBang("Save_Database_Voltage").setPosition(160,50).setSize(60,60).setCaptionLabel("Now select the path to save the voltage values").setImage(voltsButton);
    
     flagSaveVolts=true;
    // println("serial list:"+ Serial.list()[1]);
     temporal=new String[10];
     temporal=Serial.list();
     int portCount=temporal.length;
     String portName=Serial.list()[portCount-1];     
    // println("portName:"+ portName);
    if(orderOfMagnitude==10.0)
    {
      myPort=new Serial(this,portName,1100); 
    }
    else if(orderOfMagnitude==1000.0)
    {
      myPort=new Serial(this,portName,5300); 
    }
    else if(orderOfMagnitude == 505.0)
    {
      myPort=new Serial(this,portName,5000); 
    }
     
   }
   else if((toggleValue==true || toggleValue==false) && toggleValueRecorded==true)
   {
      cp5.addBang("Read_From_Database").setPosition(160,50).setSize(60,60).setCaptionLabel("Select the path where your database exists").setImage(recordButton);
      flagRecord=true;
   }
   else
   {
     
     temporal=new String[10];
     temporal=Serial.list();
     int portCount=temporal.length;
     String portName=Serial.list()[portCount-1];
    if(orderOfMagnitude==10.0)
    {
       myPort=new Serial(this,portName,1100);
    }
    else if(orderOfMagnitude==1000.0)
    {
      myPort=new Serial(this,portName,5300); 
    }
    else if(orderOfMagnitude==505.0)
    {
      myPort=new Serial(this,portName,5000); 
    }
    
     
     flagSecondOrder=false;
     flagFirstOrder=false;
     flagThirdOrder=true;

     cp5.addTextfield("Samples. (Must be multiple of 2. (...128,256,512,1024...)").setPosition(40,50).setSize(60,40).setAutoClear(false).setColorBackground(color(0,0,0)).setColorActive(color(0,0,0)).setColorForeground(color(0,0,0))
     .setCaptionLabel("Enter number of bins. \n Must be multiple of 2. \n Usuaslly 256,512,1024.");
     cp5.addTextfield("SamplingRate").setPosition(290,50).setSize(60,40).setAutoClear(false).setColorBackground(color(0,0,0)).setColorActive(color(0,0,0)).setColorForeground(color(0,0,0)).setCaptionLabel("Samples Per Second (SPS) \n Default value:128");
     cp5.addTextfield("Duration of Experimens (Mins)").setPosition(170,50).setSize(60,40).setAutoClear(false).setColorBackground(color(0,0,0)).setColorActive(color(0,0,0)).setColorForeground(color(0,0,0))
      .setCaptionLabel("Duration of Experimens \n (Mins)");
     
     cp5.addBang("Begin").setPosition(130,180).setSize(156,50).setImage(startButton);
     
   }
  // createOutput(path);
 // println(finalPath);
  }
}


 void fileSelectedVoltage(File selectionVoltage) {
  if (selectionVoltage == null) {
    println("Window was closed or the user hit cancel.");
  } else {
    println("User selected " + selectionVoltage.getAbsolutePath());
    finalPathVoltage=selectionVoltage.getAbsolutePath();
    outputFileData=createWriter(finalPathVoltage);
    cp5.remove("Save_Database_Voltage");
      
    flagSaveVolts=false;
    flagSecondOrder=false;
    flagThirdOrder=true;
    cp5.addTextfield("Samples. (Must be multiple of 2. (...128,256,512,1024...)").setPosition(40,50).setSize(60,40).setAutoClear(false).setColorBackground(color(0,0,0)).setColorActive(color(0,0,0)).setColorForeground(color(0,0,0))
     .setCaptionLabel("Enter number of bins. \n Must be multiple of 2. \n Usuaslly 256,512,1024.");
     cp5.addTextfield("SamplingRate").setPosition(290,50).setSize(60,40).setAutoClear(false).setColorBackground(color(0,0,0)).setColorActive(color(0,0,0)).setColorForeground(color(0,0,0)).setCaptionLabel("Samples Per Second (SPS) \n Default value:128");
     cp5.addTextfield("Duration of Experimens (Mins)").setPosition(170,50).setSize(60,40).setAutoClear(false).setColorBackground(color(0,0,0)).setColorActive(color(0,0,0)).setColorForeground(color(0,0,0))
     .setCaptionLabel("Duration of Experimens \n (Mins)");;
     cp5.addBang("Begin").setPosition(130,180).setSize(156,50).setImage(startButton);
  // createOutput(path);
 // println(finalPath);
  }
}



 void fileInputVoltage(File selectionInputVoltage) {
  if (selectionInputVoltage == null) {
    println("Window was closed or the user hit cancel.");
  } else {
    println("User selected " + selectionInputVoltage.getAbsolutePath());
    finalPathInputVoltage=selectionInputVoltage.getAbsolutePath();
  inputFileData=createReader(finalPathInputVoltage);
  lines=loadStrings(finalPathInputVoltage);
  println(lines.length);
    cp5.remove("Read_From_Database");
    flagRecord=false;
    flagSecondOrder=false;
    flagThirdOrder=true;
    cp5.addTextfield("Samples. (Must be multiple of 2. (...128,256,512,1024...)").setPosition(40,50).setSize(60,40).setAutoClear(false).setColorBackground(color(0,0,0)).setColorActive(color(0,0,0)).setColorForeground(color(0,0,0))
     .setCaptionLabel("Enter number of bins. \n Must be multiple of 2. \n Usuaslly 256,512,1024.");
     cp5.addTextfield("SamplingRate").setPosition(290,50).setSize(60,40).setAutoClear(false).setColorBackground(color(0,0,0)).setColorActive(color(0,0,0)).setColorForeground(color(0,0,0)).setCaptionLabel("Samples Per Second (SPS) \n Default value:128");
     cp5.addTextfield("Duration of Experimens (Mins)").setPosition(170,50).setSize(60,40).setAutoClear(false).setColorBackground(color(0,0,0)).setColorActive(color(0,0,0)).setColorForeground(color(0,0,0))
     .setCaptionLabel("Duration of Experimens \n (Mins)");
     cp5.addBang("Begin").setPosition(130,180).setSize(156,50).setImage(startButton);
    
   // cp5.remove("toggleValue");
  //  cp5.remove("toggleValueRecorded");
  // createOutput(path);
 // println(finalPath);
  }
}
 
 
 void OK(){
    orderOfMagnitude=cp5.getValue("slider");
    cp5.remove("toggleValue");
    cp5.remove("toggleValueRecorded");
    cp5.remove("toggleValueNoUse");
    cp5.remove("slider");
    flagFirstOrder=false;
    flagSecondOrder=true;
    flagRemoveSave=true;
    
    cp5.addBang("Save_Database_FFT").setPosition(160,50).setSize(60,60).setImage(saveButton) ;
    cp5.remove("OK");
 }
 
 
 void Save_Database_FFT(){
   selectOutput("Select a file to write to:", "fileSelected");
 
 }
 
  void Save_Database_Voltage(){
   selectOutput("Select a file to write to:", "fileSelectedVoltage");
 }
 
   void Read_From_Database(){
   selectOutput("Select a file to write to:", "fileInputVoltage");
 }
 
 
 
 void capt(){
   stringHour=str(hour());
   stringMin=str(minute());
   stringSec=str(second());
   stringDay=str(day());
   stringMonth=str(month());
   stringYear=str(year());
   captureImgName=captureImgPath[0]+"\\"+stringDay+"-"+stringMonth+"-"+stringYear+" "+stringHour+"h"+stringMin+"m"+stringSec+"sec.tif";
   
 //println(captureImgName);
  saveFrame(captureImgName);
 }


 
 void Begin(){
   samples=cp5.get(Textfield.class,"Samples. (Must be multiple of 2. (...128,256,512,1024...)").getText();
   N=Integer.parseInt(samples);
   ND2=N/2;
   CurveA = new BenFFT(N);
  
   println("Order: "+orderOfMagnitude);
 //  println(sampleRate);
 //  sliderValue=cp5.get(Slider.class,"Time of experiment").getValue();
  durationVal=cp5.get(Textfield.class,"Duration of Experimens (Mins)").getText();
  samplesPerSecond=cp5.get(Textfield.class,"SamplingRate").getText();
  fs=(float(Integer.parseInt(samplesPerSecond)));
  println("FS: "+fs);
  sliderValue=float(durationVal);
  println(sliderValue);
  secBegin=second();
  minBegin=minute();
  
  begin=true; //<>//
  captureImgPath=split(finalPath,".");
  folderName=split(captureImgPath[0],"\\");
  //println(folderName[2]);
  cp5.remove("Begin");
  cp5.remove("Duration of Experimens (Mins)");
  cp5.remove("Samples. (Must be multiple of 2. (...128,256,512,1024...)");
  cp5.remove("toggleValue");
  cp5.remove("toggleValueRecorded");
  cp5.remove("toggleValueNoUse");
  cp5.remove("SamplingRate");
  cp5.remove("slider");
   cp5.addBang("capt").setPosition(200,70).setSize(60,60).setImage(snapshotButton);
   

  flagThirdOrder=false;
  if(N<=256)
  {
    surface.setSize(650, 810);
  }
  else if(N>256 && N<1024)
  {
    surface.setSize(700, 810);
  }
  else if(N>=1024)
  {
    surface.setSize(N+200,810);
  }
 
 }
 
 
 
 //class ThirdApplet extends PApplet {
 //  float prevY;
 // void settings() {
 //   size(600, 200);
 //   smooth(3);
 ////   noLoop();

 //   println(sketchPath());
 // }
 
//  void draw() {
  //  background(180);
 //  line(frameCount-1,prevHertz+60,frameCount,hertz+60);
 //  prevHertz=hertz;
  //println(timeHertz);
  // if(int(elapsedTime/100) %2==0)
  //{
  //   //println("Hello");
  //  flagHertz=true;
  //  hertzCounter=hertzCounter+1;
  //}
  //else
  //{
  //  flagHertz=false;
  //  hertzCounter=0;
  //}
  
  //if(flagHertz==true && hertzCounter==1 && timeHertz<=600)
  //{
  //   stroke(0, 0, 0); //<>//
  //  line(timeHertz,prevHertz+60,timeHertz+1,hertz+60);
  //  prevHertz=hertz;
  //  timeHertz=timeHertz+1;
  //  println(timeHertz);
  //}
  //else if(flagHertz==true && hertzCounter==1 && timeHertz>600)
  //{
  //  timeHertz=0;
  //  background(180);
  //}
   
   
//  }
//}
