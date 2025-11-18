void initialPresentation(boolean flagFirstOrder, boolean flagSecondOrder, boolean flagRemoveSave, boolean flagRecord, boolean flagSaveVolts, boolean flagThirdOrder){
  // loadFont() is deprecated but still works with .vlw files
  // For Processing 4.0+, consider using createFont() with system fonts instead
  // loadFont("Rockwell-Bold-48.vlw");
  
   if(flagFirstOrder==true)
   {
      background(180);
      
     textSize(19);
    text("1) Select one of the three choices:",30,30);
   // text("-------------------------------------------------",5,140);
   }
  
  if(flagSecondOrder==true)
  {
     background(180);
    textSize(19);
    text("2) Select the Paths:",100,30);
    //text("-------------------------------------------------",5,140);
  }
  
  if(flagRemoveSave==true)
  {
     background(180);
  textSize(12);
  text("Path and File Name",140,130);
  text(" to save FFT values",140,145);
 }
 if(flagRecord==true)
 {
    background(180);
   delay(100);
  textSize(12);
  text("Select the path and file ",130,130);
  text(" where your database exists",110,145);
 }
 
 
 if(flagSaveVolts==true)
 {
    background(180);
   textSize(12);
  text("Select the path and file ",130,130);
  text(" to save voltage measurements",110,145);
 }
 
  if(flagThirdOrder==true)
 {
    background(180);
   delay(100);
   textSize(19);
   text("3) Fill the parameters and start",60,30);
 
 }
 
}
