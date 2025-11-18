
void createDatabase(float[] XOut, float twoSample) {

  for(int i=0;i<N/2;i++)
   {
     outputFile.println(CurveA.XOut[i]);
    
   }
   
   if(toggleValue==true)
   {
     outputFileData.println(twoSample);
     outputFileData.flush();
   }
   outputFile.println("-------------------"+"Iteration: "+iteration+"-------------------------------------");
   outputFile.println("-------------------"+"Time: "+hour()+":"+minute()+":"+second()+"-------------------------------------");
   outputFile.flush();

   //outputFileData.println("-------------------"+"Iteration: "+iteration+"-------------------------------------");
  // outputFileData.println("-------------------"+"Time: "+hour()+":"+minute()+":"+second()+"-------------------------------------");

   
   iteration=iteration+1;
}
