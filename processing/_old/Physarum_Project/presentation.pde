void drawPresentation(float[] SamplingData, float[] XOut) {
  int TimeScalar = 2;  // Scale data to screen
 
  background(180);
 //textSize(13);
  stroke(0,0,0);
  strokeWeight(2);
  //line(0, height/3+124, N+20, height/3+124);
  //line(N-12+20,height/3+119,N+20,height/3+124);
  //line(N-12+20,height/3+129,N+20,height/3+124);
  //line(N+25,height/3-76,N+25,height/3+124);
  //line(N+20,height/3-66,N+25,height/3-76);
  //line(N+25,height/3-76,N+30,height/3-66);
  //text("Time (sec)",N-50,height/3+154);
  //text("Amplitude (mV)",N+40,height/3-46);
  
  line(0, height/3+24, 1024+20, height/3+24);
  line(1024-12+20,height/3+19,1024+20,height/3+24);
  line(1024-12+20,height/3+29,1024+20,height/3+24);
  line(1024+25,height/3-76,1024+25,height/3+24);
  line(1024+20,height/3-66,1024+25,height/3-76);
  line(1024+25,height/3-76,1024+30,height/3-66);
  text("Time (ms)",1024-50,height/3+54);
  text("Amplitude (mV)",1024+40,height/3-46);
  
  text("Instant Amplitude",20,20);
  text("(mV) :",180,20);
  text(twoSampleView,300,20);
  
  text("Instant Time",20,40);
  text("(sec) :",180,40);
  text(elapsedTime/1000,300,40);
  
  text("Bins:", 500, 20);
  text(samples, 550,20);
  
  text("Experiment's Duration (mins) :", 500,60);
  text(durationVal,725,60);
  
  
  text("SPS:", 500,40);
  text(samplesPerSecond, 550,40);
  
  text("Time percentage:", 800, 20);
  text(100-((sliderValue*60)-(elapsedTime/1000))/(sliderValue*60)*100,950, 20);
  text("%", 1010,20);
  
  text("Time until FFT window:", 800, 40);
  if((100-((float(samples)-counterSamples)/float(samples)))<100)
  {
    text(100-((float(samples)-counterSamples)/float(samples))*100,970,40);
  }
  else
  {
    text("100.0",970,40);
  }
  text("%",1030,40);
  
  //line(0, height/3+474, N+20, height/3+474);
  //line(N-12+20,height/3+469,N+20,height/3+474);
  //line(N-12+20,height/3+479,N+20,height/3+474);
  //line(N+25,height/3+194,N+25,height/3+474);
  //line(N+20,height/3+204,N+25,height/3+194);
  //line(N+25,height/3+194,N+30,height/3+204);  
  //text("Frequency (Hz)",N-50,height/3+504);
  //text("Magnitude",N+40,height/3+234);
  line(0, height/3+274, 1024+20, height/3+274);
  line(1024-12+20,height/3+269,1024+20,height/3+274);
  line(1024-12+20,height/3+279,1024+20,height/3+274);
  line(1024+25,height/3+194,1024+25,height/3+274);
  line(1024+20,height/3+204,1024+25,height/3+194);
  line(1024+25,height/3+194,1024+30,height/3+204);  
  text("Bins ",1024-50,height/3+304);
  text("Magnitude",1024+40,height/3+234);
  
  text("Calculated Frequency",20,60);
  text("(Hz) :",180,60);
  text(hertz,300,60);
  
  
  
  finalFileName=folderName[2]+".txt";
  text("Database Name :",20,80);
  text(finalFileName,300,80);
  
  text("Final Figure at :",20,100);
  if(captureImgName==null)
  {
    text("No figure yet.",300,100);
  }
  else
  {
    text(captureImgName,300,100);
  }
  
  textSize(15);
  text("Measured Signal",20,height/3-106);
  stroke(255,255,255);
  line(18, height/3-101, 140, height/3-101);
  
  text("Signal Analysis via Fast Fourier Transform (FFT)",20,height/3+129);
  stroke(255,255,255);
  line(18, height/3+134, 365, height/3+134);
  
  stroke(0,0,255);
  beginShape();
  if(N>=1024)
  {
  //for(int i = 0; i<N/2; i++) {
    for(int i = N-1024; i<N; i++) {
    curveVertex(i-(N-1024), (height/3-20*SamplingData[i])); // is also the last control point //50
    
    
  }
  }
  else
  {
    for(int i = 0; i<N; i++) {
    curveVertex(i, (height/3-20*SamplingData[i])); // is also the last control point //50
    
    
  }
  }
  endShape();
  
  
  stroke(0,0,255);
  strokeWeight(2);
  beginShape();
 // for(int i = 0; i<XOut.length/2; i = i + TimeScalar) {
   for(int i = 0; i<512; i = i + TimeScalar) {
    if(N<=1024)
    {
      curveVertex(i*TimeScalar, ((height/3+150)-XOut[i]/2 )+90); // is also the last control point //358
    }
    else if(N>1024 && N< 2500)
    {
      curveVertex(i*TimeScalar, ((height/3+150)-XOut[i]/3 )+90); // is also the last control point //358
    }
    else if (N>=2500 && N<4500)
    {
      curveVertex(i*TimeScalar, ((height/3+150)-XOut[i]/5 )+90); // is also the last control point //358
    }
    else if(N>=4500 && N< 8500)
    {
      curveVertex(i*TimeScalar, ((height/3+150)-XOut[i]/10 )+90); // is also the last control point //358
    }
    else if(N>=8500 && N< 17000)
    {
      curveVertex(i*TimeScalar, ((height/3+150)-XOut[i]/9 )+17); // is also the last control point //358
    }
    else if(N>=17000 && N< 35000)
    {
      curveVertex(i*TimeScalar, ((height/3+150)-XOut[i]/9 )+33); // is also the last control point //358
    }
    else if(N>=35000 && N< 70000)
    {
      curveVertex(i*TimeScalar, ((height/3+150)-XOut[i]/66 )+33); // is also the last control point //358
    }
    else
    {
      curveVertex(i*TimeScalar, ((height/3+150)-XOut[i]/130 )+90); // is also the last control point
    }
   
  }
  endShape();  //<>//
  
  //SHAPE OF FREQUENCY OVER TIME GRAPH
  

  stroke(0,0,255);
  strokeWeight(2);
  beginShape();
    if(orderOfMagnitude==10.0)
    {
      for(int i = 0; i<viewHertzSize; i++) 
      {
        curveVertex(i, (height/3-1000*hertzArray[i])+480); // is also the last control point
      }
    }
    else if(orderOfMagnitude==1000.0 || orderOfMagnitude==505.0)
    {
      for(int i = 0; i<viewHertzSize; i++) 
      {
        curveVertex(i, (height/3-20*hertzArray[i])+480); // is also the last control point
      }
    }
  endShape();
  
   stroke(0,0,0);
  line(0, height/3+500, 1024+20, height/3+500);
  line(1024-12+20,height/3+495,1024+20,height/3+500);
  line(1024-12+20,height/3+505,1024+20,height/3+500);
  line(1024+25,height/3+380,1024+25,height/3+500);
  line(1024+20,height/3+390,1024+25,height/3+380);
  line(1024+25,height/3+380,1024+30,height/3+390);  
  text("Time (ms)",1024-50,height/3+530);
  text("Frequency (Hz)",1024+40,height/3+460);
  
  text("Frequency over time",20,height/3+320);
  stroke(255,255,255);
  line(18, height/3+325, 170, height/3+325);
  
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
  
  //if(flagHertz==true && hertzCounter==1 && timeHertz<=1500)
  //{
  //   stroke(0, 0, 0);
  //  line(timeHertz,prevHertz+60,timeHertz+1,hertz+60);
  //  prevHertz=hertz;
  //  timeHertz=timeHertz+1;
  //  println(timeHertz);
  //}
  //else if(flagHertz==true && hertzCounter==1 && timeHertz>1500)
  //{
  //  timeHertz=0;
  //  background(180);
  //}


  //line(frameCount-1,initialHertz+60,frameCount,hertz+60);
  //if(int(elapsedTime/100) %2==0)
  //{
  //  flagHertz=true;
  //  hertzCounter=hertzCounter+1;
  //}
  //else
  //{
  //  flagHertz=false;
  //  hertzCounter=0;
  //}
  
  //if(flagHertz==true && hertzCounter==1 && timeHertz<=1500)
  //{
  //   stroke(0, 0, 0);
  // // line(timeHertz,prevHertz+60,timeHertz+1,hertz+60);
  //  prevHertz=hertz;
  //  timeHertz=timeHertz+1;
  //  println(timeHertz);
  //}
  //else if(flagHertz==true && hertzCounter==1 && timeHertz>1500)
  //{
  //  timeHertz=1000;
  //}

}
