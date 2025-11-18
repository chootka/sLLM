
int createDatabase(float[] XOut, float twoSample, int N, boolean toggleValue, PrintWriter outputFile, PrintWriter outputFileData, int iteration) {

  for(int i=0;i<N/2;i++)
   {
     outputFile.println(XOut[i]);
    
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

   
   return iteration+1;
}
